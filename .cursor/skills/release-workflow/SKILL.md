---
name: release-workflow
description: >-
  Build and release the Trucking Pay Wizard installer. Use when the user
  asks to release, ship, build the installer, push an update, bump the
  version, publish a new version, or update the mirror repo. Also use
  when the user asks how to release or what the release steps are.
---

# Release Workflow

## Overview

The app ships as a Windows installer built by PyInstaller + Inno Setup.
Releases are published to a **public mirror repo** so the in-app auto-updater
can poll anonymously. The source repo stays private.

| Component | Value |
|-----------|-------|
| Source repo (private) | `bernardo-heberle/trucking-pay-wizard` |
| Mirror repo (public) | `bernardo-heberle/trucking-pay-wizard-releases` |
| Version source of truth | `src/__version__.py` |
| Inno Setup AppId (never change) | `{0467D9FD-C633-4F29-B7AB-E101FAE85B83}` |
| Support email | `bernardo.aguzzoli@gmail.com` |

## What the agent can automate

1. Bump the version in `src/__version__.py`.
2. Run the test suite to verify nothing is broken.
3. Produce a step-by-step release guide tailored to the current version.

## What requires manual action

1. Running `.\packaging\build.ps1` (needs the local `.venv`, PyInstaller, and
   Inno Setup installed — cannot run in a sandboxed agent).
2. Creating the GitHub Release on the mirror repo and uploading the installer
   `.exe` as an asset.
3. Generating/distributing staff setup codes.

## Release procedure

When the user asks to release a new version, follow these steps:

### Step 1 — Bump version and update changelog (agent does this)

Edit `src/__version__.py` and change `__version__` to the new version.
Use semantic versioning: `MAJOR.MINOR.PATCH`.

- Patch: bug fixes, minor improvements.
- Minor: new features, UX changes.
- Major: breaking changes (unlikely during beta).

Then update `CHANGELOG.md` at the project root. Add a new section at the top:

```markdown
## [VERSION] — YYYY-MM-DD

### Added / Fixed / Changed
- Plain-English entries for anything staff would notice.
```

See `.cursor/rules/versioning.mdc` for what belongs in the changelog and how to phrase entries. Changelog content and version bump go in the **same commit**.

### Step 2 — Run tests (agent does this)

Run **both** the standard suite (unit + integration) and the live API tests.
A release must not ship if either fails.

```powershell
# Standard suite — must pass with >=85% coverage
.venv\Scripts\python.exe -m pytest tests/unit/ tests/integration/ -q --tb=short

# Live API tests — real Anthropic + Azure calls against known fixtures
.venv\Scripts\python.exe -m pytest tests/live/ --no-cov -v
```

Live tests auto-skip when credentials are missing from `.env`. If they skip,
**warn the user** that live tests were not exercised and the release is not
fully validated. Both suites must pass (not just skip) before proceeding.

If live tests fail, stop the release and investigate. Common causes:
- API key expired or rotated — update `.env`.
- Prompt or schema change broke expected extraction values — update pinned
  expected values in `tests/live/` after verifying the new output is correct.
- Azure endpoint changed — update `.env`.

### Step 3 — Produce the release guide (agent does this)

Print the following checklist with the **actual new version** substituted in.
The user follows it manually.

---

**Copy-paste release checklist for the user:**

```
RELEASE CHECKLIST — v{VERSION}
==============================

Prerequisites:
  [ ] Inno Setup 6 + ISPP installed (https://jrsoftware.org/isdl.php)
  [ ] .venv activated with all requirements installed
  [ ] GitHub CLI installed and authenticated (https://cli.github.com — run gh auth login once)

1. Build the installer:
     .\packaging\build.ps1
   Output: dist\TruckingPayWizardSetup.exe

2. Smoke-test locally:
   - Double-click dist\TruckingPayWizardSetup.exe
   - Verify the welcome page shows "v{VERSION}" in the footer
   - If first run: paste a setup code, verify keys save
   - Run a small document folder end-to-end

3. Publish the GitHub Release (open a fresh PowerShell terminal).
   The agent must produce the full ready-to-run command with the actual version
   and the full CHANGELOG.md entry for that version embedded in --notes.
   Example of what the agent should output (with real content substituted):

     gh release create v{VERSION} "dist\TruckingPayWizardSetup.exe" `
       --repo bernardo-heberle/trucking-pay-wizard-releases `
       --title "v{VERSION}" `
       --notes "### Added
     - ...
     ### Fixed
     - ..."

   The user pastes and runs this command as-is — no manual editing required.
   Verify at: https://github.com/bernardo-heberle/trucking-pay-wizard-releases/releases

4. Verify auto-update (for non-first releases):
   - Open an older installed version of the app
   - Confirm the update dialog appears
   - Click "Install now" and verify it upgrades cleanly

5. Notify staff (first release or significant changes):
   - Email with the setup code (if new users)
   - Point to: docs/USER_INSTALL.md
```

---

### Step 4 — Commit (agent does this, if asked)

Commit the version bump with message:

```
Bump version to {VERSION}
```

## Generating a staff setup code

When the user asks to generate a setup code, tell them to run:

```powershell
python scripts\gen_setup_code.py
```

This prompts for the three API keys (masked input) and prints a single
base64 string. Staff paste it into the app on first launch.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| PyInstaller missing modules at runtime | Add to `hiddenimports` in `packaging/TruckingPayWizard.spec` |
| Logo missing after install | Check `datas` entry in the spec points to `src/gui/assets` |
| SmartScreen blocks installer | Expected without code signing. Staff click More info → Run anyway |
| Inno Setup not found during build | Install from jrsoftware.org or set `$env:ISCC_PATH` |
| Auto-update not triggering | Check `_MIRROR_OWNER` and `_MIRROR_REPO` in `src/updater.py` match the mirror repo |
| Old version still running after update | Inno Setup `CloseApplications=yes` should handle this; check the app isn't pinned by antivirus |

## Key files

| File | Purpose |
|------|---------|
| `src/__version__.py` | Version string — single source of truth |
| `src/updater.py` | Auto-update logic (polls mirror repo) |
| `packaging/TruckingPayWizard.spec` | PyInstaller config |
| `packaging/installer.iss` | Inno Setup config (AppId, shortcuts, silent-update flags) |
| `packaging/build.ps1` | One-command build script |
| `scripts/gen_setup_code.py` | Staff setup-code generator |
| `packaging/README.md` | Developer build guide (detailed) |
| `docs/USER_INSTALL.md` | Staff-facing install instructions |
