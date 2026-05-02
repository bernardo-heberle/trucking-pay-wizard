# System Architecture

The system processes documents through a structured pipeline where each stage performs a specific transformation. A desktop GUI provides the interface for staff to manage working folders and review results.

---

# Deployment Model

The tool is delivered as a standalone desktop application (executable) targeting **Windows**. All end users (downtime claims staff) are on Windows. Staff select or create a working folder, drop documents into it, run the pipeline, and review the generated output artifacts.

This standalone model is the primary delivery path. Integration with IT-LAW remains a possibility depending on long-term need and feasibility, but the architecture does not assume it.

```
Standalone Desktop App  ←  current path
        or
IT-LAW Integration      ←  possible future path
```

To keep both options open, the processing pipeline is independent of the GUI. The GUI calls into the pipeline; the pipeline knows nothing about the GUI.

The entire dependency stack (Python, PySide6, PyMuPDF, OpenCV, Azure SDK, Anthropic SDK) is cross-platform. All file and directory operations use `pathlib.Path` to avoid OS-specific path separators. The Windows `.exe` is produced by running PyInstaller on Windows.

---

# Session Model

The tool operates against a **working folder** on disk. Each folder represents a processing session — typically one claim or one batch of related documents.

```
working-folder/
  ├── <source documents>         # dropped in by staff
  ├── .cache/                    # per-document processing results
  ├── combined_report.pdf        # generated output
  └── extracted_data.csv         # generated output
```

Staff place documents into the folder, run the tool, and output artifacts are written to the same folder. To add more documents later, staff drop new files into the folder and re-run — only new or unprocessed documents go through the pipeline, and the output artifacts are regenerated from the full set.

This folder-based model keeps things simple: no database, no server, no session management. The folder *is* the session.

---

# Processing Pipeline

## Beta Pipeline

For the beta, staff will only input real income documents. Document classification is not needed yet — every document is assumed to be a valid income document. The pipeline for beta:

```
  Working Folder (source documents)
                 ↓
       ┌─────────────────────────────────┐
       │   Per-Document (cacheable)       │
       │                                  │
       │   Ingestion → OCR → Extract →   │
       │                      Validate    │
       └─────────────┬───────────────────┘
                     ↓
         Cache results in folder
                     ↓
       ┌─────────────────────────────────┐
       │   Report Assembly                │
       │                                  │
       │   Combined PDF (with index)      │
       │   CSV/Excel (with page refs)     │
       └─────────────────────────────────┘
```

Only new or unprocessed documents run through the per-document stages. Report assembly always rebuilds from the full set of cached results.

## Future Pipeline

Classification can be inserted between OCR and Extraction without disrupting the rest of the pipeline:

```
  Working Folder (source documents)
                 ↓
       ┌─────────────────────────────────────────────┐
       │   Per-Document (cacheable)                    │
       │                                               │
       │   Ingestion → OCR → Classification → Extract →│
       │                                      Validate │
       └──────────────────┬────────────────────────────┘
                          ↓
              Cache results in folder
                          ↓
                   Report Assembly
```

This allows the tool to reject irrelevant documents automatically once classification is ready.

---

# Components

## Desktop GUI

Provides the user-facing interface:

- folder selection or creation for a processing session
- drag-and-drop document input into the working folder
- batch processing trigger with progress indication
- display of extracted results for review
- access to output artifacts (combined PDF + CSV/Excel)

The GUI is a thin layer over the processing pipeline. It handles presentation and user interaction only.

---

## Document Ingestion

Responsible for:

- loading files
- converting PDFs to images
- normalizing file formats
- splitting multi-page documents

---

## OCR Layer

Converts images and PDFs into machine readable text.

The selected provider is **Azure Document Intelligence**. The adapter pattern keeps the provider swappable if that changes.

OCR returns:

- text
- line structure
- bounding boxes
- table structure

---

## Document Classification (future)

Determines whether a document contains income information. Not active in the beta — all documents are assumed to be valid income documents. The pipeline is structured so classification can be inserted between OCR and Extraction later.

Examples of future classifications:

- settlement statement
- pay summary
- irrelevant document

---

## Field Extraction

Extracts financial values from the OCR text produced by the previous stage. Both strategies receive an `OcrResult` and return a `DocumentExtractionResult` — the rest of the pipeline is unaware of which strategy ran.

Fields include:

- gross pay
- net pay
- payment dates

### Extraction Strategies

The extraction stage uses a **strategy pattern** controlled by the `EXTRACTION_MODE` config flag:

- **Rules** (`EXTRACTION_MODE=rules`) — regex patterns tried in priority order; first match wins. Deterministic and fast. This is the default.
- **LLM** (`EXTRACTION_MODE=llm`) — schema-driven structured extraction via the Anthropic API (Claude Haiku). OCR text is PII-sanitized before it leaves the machine, then sent with a tool-use schema that forces structured JSON output. Each field includes a confidence score.

Both strategies produce the same `DocumentExtractionResult` with provenance metadata, so caching, validation, and report assembly work identically regardless of which strategy ran.

### LLM Failure Handling

The LLM extractor retries up to three times with exponential backoff before giving up on a document. The Anthropic Python SDK also retries transient errors twice per attempt internally, so the total number of HTTP attempts before the application gives up can be as high as nine.

**Retryable failures** (retried with backoff):
- Rate limit (429) and server overload (529)
- Network / connection errors
- Server-side errors (5xx)
- Response missing the expected `tool_use` block

**Non-retryable failures** (surface immediately as a pipeline error):
- Authentication failure (401) — API key is wrong
- Permission denied (403) — API key lacks access
- Bad request (400) — a code defect; retrying the same request will not help

When all retries are exhausted, the extractor returns a `DocumentExtractionResult` with an empty `fields` list and `extraction_error` set to a description of the failure. The pipeline worker recognises this flag and skips caching so the document is retried on the next run. The document still appears in both output artifacts — in the PDF index with a "review manually" notice, and in the CSV/Excel with a red-filled Notes column — so staff can identify and manually process any document that could not be extracted automatically.

### PII Sanitization (LLM path only)

Before OCR text is sent to the Anthropic API, a regex-based sanitizer scrubs sensitive identifiers (SSNs, EINs). The sanitizer is extensible — new patterns are added as simple regex entries. Redaction counts are logged; actual values are never logged.

### Extraction Schemas

The LLM extractor is schema-driven. Each schema defines the fields to extract, the prompt context, and the tool-use JSON definition. New document types are supported by adding a schema — the extractor itself does not change.

---

## Validation

Validation ensures extracted values are reasonable.

Examples:

- valid currency formats
- valid dates
- numeric consistency checks

---

## Report Assembly

Report assembly consumes all cached per-document results and produces two cross-referenced output artifacts:

**Combined PDF** contains:

- A generated summary/index page listing each source document, its starting page in the combined PDF, and a summary of extracted values
- All original documents concatenated in order (images converted to PDF pages)

**CSV/Excel** contains:

- One row per extracted record
- All extracted fields (gross pay, net pay, dates, etc.)
- A page number column referencing the corresponding page in the combined PDF

The two artifacts form a cross-referenced pair: staff review the spreadsheet and flip to the exact page in the PDF to verify any value. Report assembly always regenerates from the full set of cached results, so adding new documents and re-running produces an updated, complete report.

In a future integration scenario, report assembly output could also feed directly into external systems.

---

# Design Goals

The architecture prioritizes:

- **modularity** — pipeline and GUI are independent layers; extraction strategies are swappable via config
- **traceability** — extracted values link back to source documents regardless of extraction strategy
- **reliability** — deterministic rules provide the baseline; LLM extraction adds coverage with confidence scoring and human review as safety nets
- **privacy** — PII sanitization scrubs sensitive identifiers before any text reaches external APIs
- **provider independence** — the OCR layer wraps Azure Document Intelligence through an adapter; extraction wraps both rules and LLM behind a common protocol; either provider can be swapped without touching the rest of the pipeline
- **deliverability** — the tool ships as a self-contained executable
