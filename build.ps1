[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = if (Test-Path ".venv\Scripts\python.exe") {
    ".venv\Scripts\python.exe"
} else {
    "python"
}

Write-Host "Using Python: $Python"
& $Python -c "import PyInstaller; print('PyInstaller', PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed. Run: $Python -m pip install -r requirements-dev.txt"
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --noupx `
    --name ScheduleReminder `
    --icon assets/icon.ico `
    --add-data "assets/icon.ico;assets" `
    --version-file version_info.txt `
    --workpath build `
    --distpath dist `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$exe = Join-Path $Root "dist\ScheduleReminder.exe"
if (-not (Test-Path $exe)) {
    throw "Expected executable was not produced: $exe"
}
Write-Host ""
Write-Host "Built: $exe"
