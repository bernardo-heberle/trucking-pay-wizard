# DTC Income Extraction

Desktop application for extracting trucking income information from documents submitted during downtime insurance claims.

Staff work with folder-based sessions — drop documents into a working folder, run the tool, and receive a combined PDF of the payment documents and a cross-referenced Excel spreadsheet listing every document. The tool also classifies whether each document is actually proof of a payment; non-payment documents and exact duplicates are left out of the PDF and grayed out in the spreadsheet. Adding more documents and re-running processes only the new files and regenerates the full output.

---

# Problem

Truck drivers submitting downtime claims must upload documents showing their income.

These documents are often:

- settlement statements
- pay summaries
- exported PDFs from carrier portals
- screenshots or photos of documents

Currently, staff manually inspect each document and record financial information needed for claim calculations.

This process is time consuming and difficult to scale.

---

# Solution

A standalone desktop application that:

1. Manages folder-based processing sessions (one folder per claim or batch)
2. Accepts documents via drag-and-drop into the working folder
3. Converts documents into machine-readable text using OCR
4. Extracts and validates financial fields via schema-driven LLM extraction
5. Classifies whether each document is proof of a payment, erring toward inclusion when unsure
6. Generates a combined PDF of the payment documents (in date order) with extracted values highlighted
7. Generates an Excel spreadsheet listing every document, cross-referenced to PDF page numbers, with non-payment documents and duplicates grayed out at the bottom
8. Caches per-document results so re-runs only process new files

The tool is distributed as a self-contained executable. No server infrastructure or installation process required.

---

# Delivery Model

The application is a standalone desktop tool built for direct use by DTC staff.

---

# Project Documentation

- Vision: `project/vision.md`
- Architecture: `project/architecture.md`
- Setup Instructions: `project/setup.md`
- Developer Guidelines: `project/developer_guidelines.md`

---

# Current Status

Active development.

Current focus areas:

- folder-based batch processing workflow
- desktop GUI for folder management, document input, and result review
- OCR integration
- financial field extraction and validation (schema-driven LLM extraction via Anthropic API)
- document classification (payment vs. non-payment) to keep irrelevant uploads out of the report
- report assembly (combined PDF + Excel generation)
- packaging as a distributable executable
- evaluation with DTC staff for feedback

---

# Configuration

The tool reads settings from a `.env` file in the project root (see `.env.example`).

| Variable | Required | Description |
|---|---|---|
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Always | Azure OCR endpoint |
| `AZURE_DOCUMENT_INTELLIGENCE_KEY` | Always | Azure OCR API key |
| `ANTHROPIC_API_KEY` | Always | Anthropic API key for Claude |
| `LLM_MODEL` | No | Claude model for extraction. Default: `claude-sonnet-4-5` (recommended). Use `claude-haiku-4-5` for ~3.5x lower cost at the expense of higher date-omission rates on dense documents. |

---

# Security

Documents may contain sensitive financial and personal data.

Guidelines:

- Do not commit documents to the repository
- Store credentials in `.env`
- Restrict access to API keys
- The executable should not persist sensitive data beyond the active session

## Privacy and LLM Extraction

When LLM extraction is active, OCR text is sent to the Anthropic API (Claude) for field extraction. Two independent safeguards protect sensitive data:

1. **PII sanitization** — before any text leaves the machine, a regex-based sanitizer scrubs Social Security numbers, EINs, and other sensitive identifiers. Redaction counts are logged; actual values are never logged or transmitted.
2. **Anthropic data policy** — API inputs are not used for model training under Anthropic's standard terms.

The LLM never sees the raw document file (PDF, image). It receives only PII-sanitized plain text extracted by the OCR stage.

---

# Testing

## Test levels

| Level | Directory | Runs by default | What it covers |
|---|---|---|---|
| Unit | `tests/unit/` | Yes | Extraction, validation, caching, report formatting — all mocked |
| Integration | `tests/integration/` | Yes | Stage boundaries with a real `LlmExtractor` and mocked API client |
| Live API | `tests/live/` | **No** | Real Azure OCR and/or real Anthropic calls against known documents |

## Running the test suite

```powershell
# All unit + integration tests with branch coverage (threshold: 85%)
.venv\Scripts\pytest

# Fast run — no coverage (useful during development)
.venv\Scripts\pytest --no-cov

# Run with randomised test order to surface order-dependent failures
.venv\Scripts\pytest -p randomly --no-cov
```

## Live API tests

Live tests make real network calls and are **not** included in the default run. They require API credentials in `.env` and auto-skip any test whose credentials are missing.

```powershell
# All live tests (Azure + Anthropic)
.venv\Scripts\pytest tests/live/ --no-cov -v

# Extraction only (Anthropic) — faster, cheaper
.venv\Scripts\pytest tests/live/test_extraction_live.py --no-cov -v

# OCR only (Azure)
.venv\Scripts\pytest tests/live/test_ocr_live.py --no-cov -v

# Full end-to-end pipeline (both APIs)
.venv\Scripts\pytest tests/live/test_pipeline_live.py --no-cov -v
```

`--no-cov` is recommended because the 85% coverage threshold is calibrated for the unit/integration suite.

**When to run live tests:** after changing prompts, extraction schemas, OCR integration, or before a release. They pin expected values (e.g. `pay == "750.00"`) against known fixture text, so a prompt regression will fail the test.

## Coverage

Coverage is measured with branch coverage enabled (`--cov-branch`). The suite must pass `--cov-fail-under=85` to pass CI. GUI code (`src/gui/`) is excluded — it is exercised via manual smoke testing.

To view a line-by-line coverage report:

```powershell
.venv\Scripts\pytest --cov-report=html
# Opens htmlcov/index.html in a browser
```

---

# License

Private internal project.
