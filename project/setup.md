# Setup

## Prerequisites

- Python 3.11+
- Git
- Azure Document Intelligence resource (endpoint + API key)

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

Copy `.env.example` to `.env` and fill in your Azure credentials:

```
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://...
AZURE_DOCUMENT_INTELLIGENCE_KEY=...
```

The application reads these values at startup. Never commit `.env` to version control.

---

## Running in Development

```bash
python -m src.gui
```

Pipeline stages can also be exercised directly without the GUI, which is useful for development and debugging individual stages.

---

## Testing

```bash
pytest
pytest tests/unit/
pytest tests/integration/
```

`tests/fixtures/` contains sanitized sample OCR outputs. Tests for extraction and validation logic should use these realistic inputs rather than toy strings.

---

## Packaging (Building the Executable)

```bash
pyinstaller --onefile --windowed src/gui/__main__.py
```

- Output lands in `dist/`
- Test the executable on a clean machine before distributing
- API key must be provided at runtime — do not bake it into the build
