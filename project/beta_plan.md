# Beta Plan

This document captures what the beta delivers, what it defers, and how we'll know it works. It is the "what are we building right now" reference — see `vision.md` and `architecture.md` for the longer-lived design context.

---

## Goal

Get the tool into staff hands for real-world feedback. The beta should be functional enough that staff can use it on actual claims and tell us what works, what doesn't, and what's missing.

---

## In Scope

- **Folder-based batch processing** — each working folder is a session; staff drop documents in and run the tool
- **OCR** — convert source documents (PDFs, images) into machine-readable text
- **Field extraction** — extract gross pay, net pay, payment dates, and other financial fields using rule-based logic
- **Validation** — verify extracted values are reasonable (currency formats, date formats, numeric consistency)
- **Report assembly** — produce a combined PDF with a summary index page and a cross-referenced CSV/Excel spreadsheet
- **Per-document caching** — re-runs only process new or unprocessed documents; output artifacts regenerate from the full set
- **Desktop GUI** — folder selection, drag-and-drop document input, batch processing trigger, result review, access to output artifacts
- **Packaging** — distributed as a standalone executable that runs on staff machines without installation

---

## Intentionally Deferred

These are known future needs that are explicitly out of scope for the beta:

- **Document classification** — the beta assumes all input documents are valid income documents; classification will be added later to automatically reject irrelevant files
- **IT-LAW integration** — the beta is a standalone tool; integration with case management systems is a future path
- **Template detection** — recognizing specific carrier formats to improve extraction accuracy
- **Automatic upload processing** — server-side processing triggered by document uploads (relevant only if integrated)

---

## Workflow

What staff will do, step by step:

1. **Create or select a working folder** for a claim or batch of documents
2. **Drop source documents** into the folder (PDFs, images, screenshots)
3. **Run the tool** — the GUI points at the folder and triggers processing
4. **Review output** — open the combined PDF to verify the index and source pages; open the CSV/Excel to review extracted data
5. **Add more documents** if needed — drop them into the same folder
6. **Re-run** — only the new documents are processed; both output artifacts are regenerated from the complete set

---

## Output Spec

### Combined PDF

- Starts with a generated summary/index page listing each source document, its starting page in the combined PDF, and a summary of extracted values
- Followed by all source documents concatenated in order (images converted to PDF pages)

### CSV/Excel

- One row per extracted record
- Columns for all extracted fields (gross pay, net pay, dates, etc.)
- A page number column referencing the corresponding page in the combined PDF

The two artifacts are a cross-referenced pair: staff review the spreadsheet and flip to the exact page in the PDF to verify any value.

---

## Success Criteria

The beta works when:

- Staff can run the tool on their machines without developer assistance
- The tool processes a folder of real income documents without crashing
- The combined PDF is coherent — index page is accurate, page numbers match, source documents are legible
- The CSV/Excel contains reasonable extracted values that staff can verify against the PDF
- Staff can add documents to an existing folder and re-run without reprocessing everything
- Staff provide actionable feedback on accuracy, usability, and missing features

---

## Known Constraints

- **Income documents only** — the beta has no classification safety net; irrelevant documents will be processed and may produce garbage output
- **Azure Document Intelligence** — selected OCR provider; API key must be configured at runtime via `.env`
- **Extraction coverage** — rule-based extraction will not handle all document formats; staff feedback will identify gaps
- **No automated testing with real documents** — beta validation depends on staff review, not automated accuracy benchmarks