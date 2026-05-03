# Packaging — Developer Guide

This folder contains everything needed to turn the Python source into a
distributable Windows installer.

## Prerequisites

Install these once on your development machine:

| Tool | Install | Notes |
|------|---------|-------|
| Python 3.12 | Already installed | Used to run PyInstaller |
| PyInstaller | `pip install pyinstaller>=6.5` (already in `requirements.txt`) | Bundles the app |
| Inno Setup 6 + ISPP | [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php) | Wraps the bundle into an installer; **must include the ISPP option** |

> Inno Setup free, single installer download. During setup, tick
> **Install Inno Setup Preprocessor (ISPP)** — the spec uses `#define` macros.

## Building the installer

From the **project root**, in PowerShell:

```powershell
.\packaging\build.ps1
```

This runs two steps:

1. **PyInstaller** reads `packaging/TruckingPayWizard.spec` and produces
   `dist/TruckingPayWizard/` (a folder with the `.exe` and all DLLs).
2. **Inno Setup** reads `packaging/installer.iss` and wraps that folder into
   a single `dist/TruckingPayWizardSetup.exe`.

Upload `dist/TruckingPayWizardSetup.exe` to a GitHub Release on the
**mirror repo** (`trucking-pay-wizard-releases`).

## Releasing a new version

1. Bump `__version__` in `src/__version__.py`.
2. Run `.\packaging\build.ps1`.
3. On GitHub, draft a new release on the **mirror repo** with tag `vX.Y.Z`.
4. Attach `dist/TruckingPayWizardSetup.exe` as the release asset.
5. Paste the changelog as the release body (users see it in the update dialog).

## Generating a staff setup code

Staff don't create their own API keys — you provision them centrally and
share a single-string *setup code* per deployment:

```powershell
python scripts\gen_setup_code.py
```

Follow the prompts (key fields are masked). Copy the printed code and paste
it into your onboarding email.  Staff paste it into the **"Have a setup
code?"** field on first launch.

## Inno Setup AppId

The `AppId` GUID in `installer.iss` is:

```
{0467D9FD-C633-4F29-B7AB-E101FAE85B83}
```

**Never change this GUID.** Inno Setup uses it to identify upgrades.
If it changes, the installer creates a side-by-side installation instead of
upgrading, and the old version stays on the machine.

## Update mirror repo

The app polls:

```
https://api.github.com/repos/bernardo-heberle/trucking-pay-wizard-releases/releases/latest
```

The mirror repo needs:
- To be **public** (so the app can poll anonymously).
- Each release tagged `vX.Y.Z` with `TruckingPayWizardSetup.exe` attached
  as an asset.
- Release notes written for a non-technical audience (staff see them in the
  update dialog).

## Icon

`packaging/icon.ico` is the application icon (16×16 through 256×256 sizes).
To regenerate from `src/gui/assets/logo.png`:

```powershell
# Requires ImageMagick (choco install imagemagick)
magick convert src\gui\assets\logo.png -define icon:auto-resize=256,128,64,48,32,16 packaging\icon.ico
```

Or use any image editor that exports `.ico` with multiple sizes.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Module not found: fitz` at runtime | Add `"fitz"` to `hiddenimports` in the spec |
| `keyring` backend error on target machine | Ensure `keyring.backends.Windows` is in `hiddenimports` |
| Logo missing after install | Check `datas` entry in the spec points to `src/gui/assets` |
| SmartScreen blocks the installer | Expected without a code-signing cert. Staff click **More info → Run anyway**. See `docs/USER_INSTALL.md`. |
| Inno Setup not found | Install from jrsoftware.org or set `$env:ISCC_PATH` to the full path of `ISCC.exe` |
