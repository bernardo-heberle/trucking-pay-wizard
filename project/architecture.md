# System Architecture

The system processes documents through a structured pipeline where each stage performs a specific transformation. A desktop GUI provides the interface for staff to manage working folders and review results.

---

# Deployment Model

The tool is delivered as a standalone desktop application (executable). Staff select or create a working folder, drop documents into it, run the pipeline, and review the generated output artifacts.

This standalone model is the primary delivery path. Integration with IT-LAW remains a possibility depending on long-term need and feasibility, but the architecture does not assume it.

```
Standalone Desktop App  ←  current path
        or
IT-LAW Integration      ←  possible future path
```

To keep both options open, the processing pipeline is independent of the GUI. The GUI calls into the pipeline; the pipeline knows nothing about the GUI.

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

Possible providers include:

- Azure Document Intelligence
- AWS Textract
- Google Document AI

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

Extracts financial values from the document text.

Fields include:

- gross pay
- net pay
- payment dates

Extraction is primarily rule-based.

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

- **modularity** — pipeline and GUI are independent layers
- **traceability** — extracted values link back to source documents
- **reliability** — deterministic rules over opaque models
- **provider independence** — OCR providers are swappable
- **deliverability** — the tool ships as a self-contained executable
