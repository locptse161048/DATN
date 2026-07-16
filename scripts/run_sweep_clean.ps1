# run_sweep_clean.ps1 — Train lai CA 54 RUN cua luoi 5x3 tren nhan da lam sach (sweep_clean_*)
# Chay tren host co GPU (RTX 4060). Uoc tinh ~13 gio -> nen chay qua dem.
#
#   cd D:\DATN
#   powershell -ExecutionPolicy Bypass -File scripts\run_sweep_clean.ps1
#
# CHAY TIEP neu bi ngat: script TU BO QUA run da xong (co thu muc experiments\<run>_* + best.pt).

$ErrorActionPreference = "Stop"
$py = ".\datn-env\Scripts\python.exe"

# Thu tu: 224 (re) -> 336 -> 448 (nang). De phat hien loi som & xong phan re truoc.
$order = @("224", "336", "448")
$configs = @()
foreach ($sz in $order) {
    $configs += Get-ChildItem "configs\sweep_*_${sz}_*_clean.yaml" | Sort-Object Name | ForEach-Object { $_.FullName }
}
Write-Host "Tong config _clean: $($configs.Count)" -ForegroundColor Cyan

$t0 = Get-Date
$done = 0; $skip = 0
foreach ($cfg in $configs) {
    $run = (Select-String -Path $cfg -Pattern "^run_name:\s*(\S+)").Matches.Groups[1].Value
    # da co run xong chua? (thu muc experiments\<run>_<timestamp>\best.pt)
    $exists = Get-ChildItem "experiments\${run}_*" -Directory -ErrorAction SilentlyContinue |
              Where-Object { Test-Path (Join-Path $_.FullName "best.pt") }
    if ($exists) {
        Write-Host "[SKIP] $run (da xong)" -ForegroundColor DarkGray
        $skip++; continue
    }
    Write-Host "`n===== TRAIN: $run =====" -ForegroundColor Cyan
    & $py scripts\train.py --config $cfg
    if ($LASTEXITCODE -ne 0) {
        Write-Host "LOI o $run (exit $LASTEXITCODE). Dung. Chay lai lenh nay de tiep tuc." -ForegroundColor Red
        exit 1
    }
    $done++
}
$dt = (Get-Date) - $t0
Write-Host "`nXONG. Train moi: $done | Bo qua (da co): $skip | Tong thoi gian: $([math]::Round($dt.TotalHours,1)) gio." -ForegroundColor Green
Write-Host "Buoc tiep: python scripts\analyze_grid.py (dung sweep_clean) de dung lai bang luoi 5x3." -ForegroundColor Yellow
