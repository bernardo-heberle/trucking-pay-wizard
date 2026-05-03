# build.ps1 — Build the Trucking Pay Wizard installer in one step.
#
# Prerequisites (must be on PATH or installed):
#   - Python virtual environment at .venv\ with all requirements installed
#   - Inno Setup 6 with ISPP: https://jrsoftware.org/isdl.php
#     After install, iscc.exe is typically at:
#       C:\Program Files (x86)\Inno Setup 6\ISCC.exe
#
# Usage (from the project root):
#   .\packaging\build.ps1
#
# Output:
#   dist\TruckingPayWizard\        — PyInstaller one-folder bundle
#   dist\TruckingPayWizardSetup.exe — Inno Setup installer (ship this)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

# ---------------------------------------------------------------------------
# 1. Activate the virtual environment
# ---------------------------------------------------------------------------
$Activate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $Activate)) {
    Write-Error "Virtual environment not found at .venv\. Run: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
}
. $Activate

# ---------------------------------------------------------------------------
# 2. PyInstaller — produce the one-folder bundle
# ---------------------------------------------------------------------------
Write-Host "`n[1/2] Running PyInstaller..." -ForegroundColor Cyan
$SpecFile = Join-Path $ProjectRoot "packaging\TruckingPayWizard.spec"
pyinstaller $SpecFile --clean --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
}

# ---------------------------------------------------------------------------
# 3. Inno Setup — wrap the bundle into a single installer .exe
# ---------------------------------------------------------------------------
Write-Host "`n[2/2] Running Inno Setup..." -ForegroundColor Cyan

# Try common install locations; allow override via $env:ISCC_PATH
$IsccCandidates = @(
    $env:ISCC_PATH,
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "iscc.exe"   # if on PATH
)

$Iscc = $IsccCandidates | Where-Object { $_ -and (Get-Command $_ -ErrorAction SilentlyContinue) } | Select-Object -First 1
if (-not $Iscc) {
    Write-Error "Inno Setup (ISCC.exe) not found. Install it from https://jrsoftware.org/isdl.php or set `$env:ISCC_PATH."
}

$IssFile = Join-Path $ProjectRoot "packaging\installer.iss"
& $Iscc $IssFile

if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup failed with exit code $LASTEXITCODE"
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
$InstallerPath = Join-Path $ProjectRoot "dist\TruckingPayWizardSetup.exe"
if (Test-Path $InstallerPath) {
    $SizeMB = [math]::Round((Get-Item $InstallerPath).Length / 1MB, 1)
    Write-Host "`nBuild complete!" -ForegroundColor Green
    Write-Host "  Installer : $InstallerPath ($SizeMB MB)" -ForegroundColor Green
} else {
    Write-Error "Installer was not produced at expected path: $InstallerPath"
}
