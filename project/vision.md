# Project Vision

## Objective

Automate extraction of income data from trucking payment documents submitted during downtime claims.

The system reduces the manual effort required by legal staff while improving accuracy and traceability. It is delivered as a standalone desktop application that staff use directly.

---

## Delivery Path

The immediate goal is a standalone desktop tool distributed as an executable. Staff work with **folder-based sessions** — each folder holds source documents for a claim or batch. Staff drop documents into a folder, run the tool, and receive two cross-referenced output artifacts:

- **Combined PDF** — the payment documents concatenated in date order with extracted values highlighted, so reviewers can jump to any referenced page. Documents that are not proof of payment, and exact duplicates, are left out.
- **Excel** — one entry per document with a page reference into the combined PDF. Payment documents come first; documents the tool flagged as non-payment or duplicate are grayed out at the bottom so staff can see exactly what was filtered out and why.

To process additional documents, staff add them to the folder and re-run. Only new documents are processed; the output artifacts are regenerated from the full set.

The standalone desktop application is the product. Staff use it directly — no server infrastructure, no installation complexity, no dependency on external systems.

---

## Long-Term Goals

The system should:

1. Automate the majority of document processing tasks
2. Provide reliable structured financial data
3. Flag uncertain results for human review
4. Maintain full traceability from extracted values to original documents
5. Improve over time as more documents are processed
6. Be simple enough for non-technical staff to operate

---

## Design Philosophy

### Verifiable

Every extracted value carries a confidence score. Values below the review threshold are flagged for human review. Provenance metadata traces each extracted value back to its source location in the document.

### Human-in-the-loop

Automation assists human reviewers rather than replacing them entirely. The GUI surfaces results for review; staff make the final call.

### Traceability

Every extracted value must be traceable to a document location.

### Incremental Development

The system improves gradually as additional documents are labeled and evaluated. Staff feedback drives this loop.

### Deliverability

The tool must be easy to distribute and run. No server infrastructure, no browser dependency, no installation complexity. A single **Windows executable** that runs on staff machines without installation.

---

## Potential Future Extensions

Future improvements may include:

- confidence review UI — surface low-confidence LLM extractions for staff approval
- comparison mode — run both extractors on the same documents to evaluate accuracy
- schema registry — load extraction schemas from config files for non-developer customisation
- document template detection
- improved review interface based on staff feedback
- local model option for zero-data-egress environments
