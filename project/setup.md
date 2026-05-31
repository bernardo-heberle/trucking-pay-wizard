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

Get your key from https://console.anthropic.com/. The default model is `claude-sonnet-4-5` (recommended for accuracy); override with `LLM_MODEL` if needed — for example, `claude-haiku-4-5` is ~3.5x cheaper but omits dates more often on dense documents.

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

## Packaging (Building the Executable)

The tool deploys as a Windows `.exe`. Build from Windows using PowerShell:

```powershell
pyinstaller --onefile --windowed src/gui/__main__.py
```

- Output lands in `dist/`
- Test the executable on a clean Windows machine before distributing
- API key must be provided at runtime — do not bake it into the build
- Use `pathlib.Path` throughout the codebase; never hardcode path separators
