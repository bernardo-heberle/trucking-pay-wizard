# DTC Income Extraction

Desktop application for extracting trucking income information from documents submitted during downtime insurance claims.

Staff work with folder-based sessions — drop documents into a working folder, run the tool, and receive a combined PDF with an index page and a cross-referenced CSV/Excel spreadsheet. Adding more documents and re-running processes only the new files and regenerates the full output.

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
4. Extracts and validates financial fields (via rule-based patterns or schema-driven LLM extraction)
5. Generates a combined PDF with a summary index page and all source documents
6. Generates a CSV/Excel spreadsheet cross-referenced to PDF page numbers
7. Caches per-document results so re-runs only process new files

The beta operates on income documents only — document classification is a future addition. The tool is distributed as a self-contained executable. No server infrastructure or installation process required.

---

# Delivery Model

The application is currently a standalone desktop tool built for direct use by DTC staff. Integration with IT-LAW is a future possibility but not assumed. See `project/vision.md` for details on both paths.

---

# Project Documentation

- Vision: `project/vision.md`
- Architecture: `project/architecture.md`
- Beta Plan: `project/beta_plan.md`
- Setup Instructions: `project/setup.md`
- Developer Guidelines: `project/developer_guidelines.md`

---

# Current Status

Beta prototype development.

Current focus areas:

- folder-based batch processing workflow
- desktop GUI for folder management, document input, and result review
- OCR integration
- financial field extraction and validation (schema-driven LLM extraction via Anthropic API)
- report assembly (combined PDF + CSV/Excel generation)
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
| `LLM_MODEL` | No | Override the default Claude model (`claude-haiku-4-5`) |

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

## Mutation testing

Mutation testing is configured in `pyproject.toml` and targets `src/extract/`, `src/cache/`, and `src/report/excel_exporter.py` — the financial-critical paths where a surviving mutant is a real defect risk.

**Note:** `mutmut` requires WSL on Windows (native Windows support is not available in mutmut 3.x; tracked in [mutmut#397](https://github.com/boxed/mutmut/issues/397)). Run mutation tests from WSL or a Linux CI environment:

```bash
# WSL / Linux — initial run (slow: every mutant runs the full suite)
mutmut run

# Inspect results
mutmut results

# Inspect a specific surviving mutant
mutmut show <id>
```

**Target scores:** ≥ 90% on `src/extract/**` and `src/cache/**`; ≥ 80% on all other targeted paths.

When a mutant survives: read what changed, then write the test that would have caught it. Do not silence the operator. If a surviving mutant is genuinely equivalent (e.g. a change to a log-string only), mark the source line with `# pragma: no mutate` and add a comment explaining why.

Mutation testing is **not** a pre-commit gate — it is too slow for that. Run it on a schedule or before merging to a protected branch.

---

# License

Private internal project.
