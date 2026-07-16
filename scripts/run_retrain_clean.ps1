# run_retrain_clean.ps1 — Train lai CA 4 MODEL tren nhan da lam sach (split_clean_*)
# Chay tren host co GPU (RTX 4060). Moi model ~15-40 phut -> tong ~1.5-2 gio.
#
#   cd D:\DATN
#   .\datn-env\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"   # kiem tra GPU
#   powershell -ExecutionPolicy Bypass -File scripts\run_retrain_clean.ps1

$ErrorActionPreference = "Stop"
$py = ".\datn-env\Scripts\python.exe"
$configs = @(
    "configs\detect_densenet121_224_clean.yaml",   # nhe nhat -> chay truoc de kiem tra pipeline
    "configs\detect_resnet50_224_clean.yaml",
    "configs\detect_convnext_tiny_224_clean.yaml",
    "configs\detect_vgg16_224_clean.yaml"          # nang nhat -> chay cuoi
)

$t0 = Get-Date
foreach ($cfg in $configs) {
    Write-Host "`n========================================================" -ForegroundColor Cyan
    Write-Host "TRAIN: $cfg" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Cyan
    & $py scripts\train.py --config $cfg
    if ($LASTEXITCODE -ne 0) {
        Write-Host "LOI o $cfg (exit $LASTEXITCODE). Dung lai." -ForegroundColor Red
        exit 1
    }
}
$dt = (Get-Date) - $t0
Write-Host "`nXONG 4 model trong $([math]::Round($dt.TotalMinutes,1)) phut." -ForegroundColor Green
Write-Host "Buoc tiep: so sanh truoc/sau bang scripts\aggregate_results.py --filter detect_" -ForegroundColor Yellow
