<#
vm_verify_files.ps1  —  Kiểm chứng NHÃN bằng cách phân tích FILE THẬT, TRONG VM
================================================================================
Mục đích (S6.3): với các mẫu model bỏ sót (ta gán 'malware' nhưng model nói
'sạch'), kiểm tra file GỐC để biết nhãn có sai không — mà KHÔNG upload, KHÔNG
chạy file. Bổ sung cho tra-VirusTotal-bằng-hash (đặc biệt cứu 2 mẫu 'không có
trên VT').

AN TOÀN — script này CHỈ:
  * ĐỌC byte tĩnh của file (kiểm tra header, .NET, chữ ký số)
  * Quét bằng Windows Defender CỤC BỘ (offline, không gửi file ra mạng)
Script này KHÔNG:
  * KHÔNG thực thi file  *  KHÔNG upload đi đâu  *  KHÔNG sửa/di chuyển file
=> Chạy TRONG VM cô lập. Đầu ra là 1 file CSV metadata (an toàn mang ra host).

Ba tín hiệu độc lập để phán định nhãn:
  1. Chữ ký số hợp lệ bởi nhà phát hành thật  -> gần như chắc chắn SẠCH (nhãn sai)
  2. Windows Defender phát hiện                -> xác nhận ĐỘC HẠI (nhãn đúng)
  3. Là .NET + GUI subsystem                   -> nhiều khả năng là BUILDER, không phải payload

CÁCH DÙNG (trong PowerShell của VM Windows, quyền Administrator để quét Defender):
    powershell -ExecutionPolicy Bypass -File vm_verify_files.ps1 `
        -HashList rat_all_hashes.txt `
        -LabelsCsv labels.csv `
        -OutCsv vm_verify_rat.csv

Nếu labels.csv cột 'path' là đường dẫn lúc thu thập và file đã đổi chỗ, dùng
-SearchRoot để tìm lại theo tên/ă hash trong một thư mục gốc.
#>

param(
    [Parameter(Mandatory = $true)][string]$HashList,     # file .txt: 1 sha256/dòng
    [Parameter(Mandatory = $true)][string]$LabelsCsv,    # labels.csv (có cột path, sha256, family, source)
    [string]$OutCsv = "vm_verify_files.csv",
    [string]$SearchRoot = "",                            # (tùy chọn) thư mục để tìm lại file nếu path gốc sai
    [switch]$SkipDefender                                # bỏ qua bước quét Defender (nhanh hơn, chỉ lấy chữ ký + PE)
)

$ErrorActionPreference = "Stop"

# --- Nạp danh sách hash cần kiểm ---
$wanted = Get-Content -LiteralPath $HashList | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ }
$wantedSet = [System.Collections.Generic.HashSet[string]]::new()
$wanted | ForEach-Object { [void]$wantedSet.Add($_) }
Write-Host "Cần kiểm: $($wantedSet.Count) hash"

# --- Map sha256 -> {path, family, source} từ labels.csv ---
$meta = @{}
Import-Csv -LiteralPath $LabelsCsv | ForEach-Object {
    $h = $_.sha256.ToLower()
    if ($wantedSet.Contains($h)) {
        $meta[$h] = [pscustomobject]@{ path = $_.path; family = $_.family; source = $_.source }
    }
}
Write-Host "Khớp metadata trong labels.csv: $($meta.Count)/$($wantedSet.Count)"

# --- Định vị Defender ---
$mpCmd = Join-Path $env:ProgramFiles "Windows Defender\MpCmdRun.exe"
$haveDefender = (-not $SkipDefender) -and (Test-Path $mpCmd)
if (-not $SkipDefender -and -not $haveDefender) {
    Write-Warning "Không thấy MpCmdRun.exe -> bỏ qua quét Defender (chỉ lấy chữ ký + PE)."
}

# --- Đọc vài byte đầu để nhận diện PE / .NET (KHÔNG chạy file) ---
function Get-PeInfo([string]$Path) {
    $info = [ordered]@{ is_pe = $false; is_dotnet = $false; subsystem = ""; machine = "" }
    try {
        $fs = [System.IO.File]::OpenRead($Path)
        try {
            $br = New-Object System.IO.BinaryReader($fs)
            if ($fs.Length -lt 64) { return $info }
            if ($br.ReadUInt16() -ne 0x5A4D) { return $info }   # 'MZ'
            $fs.Position = 0x3C
            $peOff = $br.ReadUInt32()
            if ($peOff + 24 -ge $fs.Length) { return $info }
            $fs.Position = $peOff
            if ($br.ReadUInt32() -ne 0x00004550) { return $info } # 'PE\0\0'
            $info.is_pe = $true
            $machine = $br.ReadUInt16()
            $info.machine = "0x{0:X4}" -f $machine
            $fs.Position = $peOff + 6
            $numSec = $br.ReadUInt16()
            $fs.Position = $peOff + 20
            $optSize = $br.ReadUInt16()
            $fs.Position = $peOff + 24
            $magic = $br.ReadUInt16()          # 0x10B=PE32, 0x20B=PE32+
            # Subsystem nằm ở offset khác nhau tùy PE32/PE32+
            $subOff = if ($magic -eq 0x20B) { $peOff + 24 + 68 } else { $peOff + 24 + 68 }
            $fs.Position = $subOff
            $sub = $br.ReadUInt16()
            $info.subsystem = switch ($sub) { 2 { "GUI" } 3 { "Console" } default { "other($sub)" } }
            # Data directory 14 = COM descriptor (.NET). Vị trí: sau optional header phần cố định.
            $ddOff = if ($magic -eq 0x20B) { $peOff + 24 + 112 } else { $peOff + 24 + 96 }
            $fs.Position = $ddOff + 14 * 8
            $comRva = $br.ReadUInt32()
            $info.is_dotnet = ($comRva -ne 0)
        } finally { $fs.Close() }
    } catch { }
    return $info
}

$results = @()
$i = 0
foreach ($h in $wantedSet) {
    $i++
    $m = $meta[$h]
    $path = if ($m) { $m.path } else { "" }

    # Tìm lại file nếu path gốc không còn
    if ($path -and -not (Test-Path -LiteralPath $path) -and $SearchRoot) {
        $cand = Get-ChildItem -LiteralPath $SearchRoot -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like "*$($h.Substring(0,12))*" } | Select-Object -First 1
        if ($cand) { $path = $cand.FullName }
    }

    $row = [ordered]@{
        sha256 = $h; family = if ($m) { $m.family } else { "" }
        source = if ($m) { $m.source } else { "" }
        file_found = $false; is_pe = $false; is_dotnet = $false; subsystem = ""
        sig_status = ""; sig_signer = ""
        defender_threat = ""; verdict = ""
    }

    if (-not $path -or -not (Test-Path -LiteralPath $path)) {
        $row.verdict = "FILE_KHONG_TIM_THAY"
        $results += [pscustomobject]$row
        Write-Host ("[{0}/{1}] {2}  -> KHONG TIM THAY FILE" -f $i, $wantedSet.Count, $h.Substring(0,12))
        continue
    }
    $row.file_found = $true

    # 1) PE / .NET / subsystem
    $pe = Get-PeInfo $path
    $row.is_pe = $pe.is_pe; $row.is_dotnet = $pe.is_dotnet; $row.subsystem = $pe.subsystem

    # 2) Chữ ký số
    try {
        $sig = Get-AuthenticodeSignature -LiteralPath $path
        $row.sig_status = $sig.Status.ToString()
        if ($sig.SignerCertificate) { $row.sig_signer = $sig.SignerCertificate.Subject }
    } catch { $row.sig_status = "error" }

    # 3) Windows Defender (offline, cục bộ)
    if ($haveDefender) {
        try {
            $out = & $mpCmd -Scan -ScanType 3 -File $path 2>&1
            $rc = $LASTEXITCODE
            $threat = ($out | Select-String -Pattern "Threat" | Select-Object -First 1)
            if ($rc -eq 2 -or $threat) {
                $row.defender_threat = if ($threat) { ($threat.ToString().Trim()) } else { "detected(rc=2)" }
            } else {
                $row.defender_threat = "clean"
            }
        } catch { $row.defender_threat = "scan_error" }
    }

    # --- Phán định tổng hợp ---
    $signedClean = ($row.sig_status -eq "Valid")
    $defDetected = ($row.defender_threat -and $row.defender_threat -ne "clean" -and $row.defender_threat -ne "scan_error")
    $row.verdict =
        if ($defDetected)      { "NHAN_DUNG (Defender phat hien)" }
        elseif ($signedClean)  { "NHAN_SAI (ky so hop le -> sach)" }
        elseif ($row.is_dotnet -and $pe.subsystem -eq "GUI") { "NGHI BUILDER (.NET GUI, chua co bang chung doc)" }
        else                   { "CHUA_KET_LUAN" }

    $results += [pscustomobject]$row
    Write-Host ("[{0}/{1}] {2}  {3}  sig={4}  def={5}" -f `
        $i, $wantedSet.Count, $h.Substring(0,12), $row.verdict, $row.sig_status, $row.defender_threat)
}

# --- Xuất CSV (an toàn mang ra host: chỉ metadata, không có nội dung file) ---
$results | Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8
Write-Host ""
Write-Host "Da luu: $OutCsv ($($results.Count) dong)"

# --- Tom tat ---
$byVerdict = $results | Group-Object verdict | Sort-Object Count -Descending
Write-Host "`n=== TOM TAT PHAN DINH ==="
foreach ($g in $byVerdict) { "{0,-40} {1}" -f $g.Name, $g.Count | Write-Host }
$nSai = ($results | Where-Object { $_.verdict -like "NHAN_SAI*" }).Count
$nDung = ($results | Where-Object { $_.verdict -like "NHAN_DUNG*" }).Count
$tot = $results.Count
Write-Host "`nNHAN SAI (ky so hop le): $nSai/$tot"
Write-Host "NHAN DUNG (Defender bat): $nDung/$tot"
Write-Host "`nLuu y: chi 'NHAN_SAI' (ky so) va 'NHAN_DUNG' (Defender) la KET LUAN CHAC."
Write-Host "'NGHI BUILDER' / 'CHUA_KET_LUAN' can doi chieu them voi ket qua VirusTotal theo hash."
