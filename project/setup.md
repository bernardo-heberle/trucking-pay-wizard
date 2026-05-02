# Setup

## Prerequisites

- Python 3.11+
- Git
- Azure Document Intelligence resource (endpoint + API key)
- Anthropic API key

Use a virtual environment (`venv`) rather than installing into your system Python. This keeps dependencies isolated and avoids version conflicts across projects.

---

## Environment Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` in the project root and fill in your Azure credentials:

```powershell
Copy-Item .env.example .env
```

Then open `.env` and paste your endpoint and key from the Azure Portal (Keys and Endpoint page of your Document Intelligence resource):

```
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=<your-key>
```

### Anthropic API key

Set your Anthropic API key in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get your key from https://console.anthropic.com/. The default model is `claude-haiku-4-5`; override with `LLM_MODEL` if needed.

### Notes

The application reads these values at startup. `.env` is gitignored — never commit it. `.env.example` (the blank template) is committed and safe to share.

---

## Running in Development

```bash
python -m src.gui
```

Pipeline stages can also be exercised directly without the GUI, which is useful for development and debugging individual stages.

---

## Testing

```powershell
# Unit + integration tests with branch coverage (default)
.venv\Scripts\pytest

# Fast run — no coverage
.venv\Scripts\pytest --no-cov

# Live API tests (real Azure OCR + Anthropic calls — opt-in, auto-skip if credentials missing)
.venv\Scripts\pytest tests/live/ --no-cov -v
```

The default run covers `tests/unit/` and `tests/integration/`. Live tests in `tests/live/` are excluded by default and require both API credentials to be set in `.env`.

`tests/fixtures/` contains sanitized sample OCR outputs. Tests for extraction and validation logic use these realistic inputs rather than toy strings.

---

## WSL Setup (for mutation testing)

`mutmut` does not run on native Windows. Mutation tests must be run from WSL2 (Ubuntu). This is a one-time setup.

### 1. Install WSL2

Open PowerShell **as Administrator**:

```powershell
wsl --install -d Ubuntu
```

Reboot when prompted. After reboot, Ubuntu launches and asks you to set a Linux username and password.

### 2. Clone the repo inside WSL and run the bootstrap script

From the Ubuntu terminal (WSL):

```bash
cd ~
git clone <your-repo-url> trucking-pay-wizard
cd trucking-pay-wizard
chmod +x scripts/wsl-setup.sh
./scripts/wsl-setup.sh
```

The script:
- Verifies Python 3.11+ is available (installs it via `apt` if not)
- Creates `.venv` and installs `requirements-wsl.txt` (identical to `requirements.txt` minus `PySide6`, which requires a display server)
- Copies `.env.example` to `.env` if it does not exist
- Runs `pytest --no-cov -q` as a smoke test
- Prints the commands to start mutation testing

**Important:** clone into the Linux home directory (`~/`), not `/mnt/c/...`. The Windows-to-Linux filesystem bridge adds significant I/O overhead — mutmut spawns hundreds of subprocesses and this matters.

### 3. Connect Cursor to WSL (optional, for IDE-integrated runs)

1. Install the **WSL** extension in Cursor.
2. `Ctrl+Shift+P` → "WSL: Connect to WSL" → Ubuntu.
3. **File → Open Folder** → navigate to `~/trucking-pay-wizard`.
4. The integrated terminal is now bash inside WSL.

### 4. Run mutation tests

```bash
source .venv/bin/activate
mutmut run

mutmut results          # inspect results after the run
mutmut show <id>        # inspect a specific surviving mutant
```

### Keeping the two clones in sync

- **Windows clone** (`c:\Users\...\trucking-pay-wizard`) — primary development copy (PowerShell, GUI, packaging).
- **WSL clone** (`~/trucking-pay-wizard`) — mutation testing only.

Run `git pull` in the WSL clone before each mutmut run to pick up latest changes.

---

## Packaging (Building the Executable)

The tool deploys as a Windows `.exe`. Build from Windows using PowerShell:

```powershell
pyinstaller --onefile --windowed src/gui/__main__.py
```

- Output lands in `dist/`
- Test the executable on a clean Windows machine before distributing
- API key must be provided at runtime — do not bake it into the build
- Use `pathlib.Path` throughout the codebase; never hardcode path separators
