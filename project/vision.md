# Project Vision

## Objective

Automate extraction of income data from trucking payment documents submitted during downtime claims.

The system reduces the manual effort required by legal staff while improving accuracy and traceability. It is delivered as a standalone desktop application that staff use directly.

---

## Delivery Path

The immediate goal is a standalone desktop tool distributed as an executable. Staff work with **folder-based sessions** — each folder holds source documents for a claim or batch. Staff drop documents into a folder, run the tool, and receive two cross-referenced output artifacts:

- **Combined PDF** — an index page followed by all source documents, so reviewers can jump to any referenced page
- **CSV/Excel** — one row per extracted record with a page-number column pointing into the combined PDF

To process additional documents, staff add them to the folder and re-run. Only new documents are processed; the output artifacts are regenerated from the full set.

Whether this standalone tool becomes the long-term solution or eventually integrates into IT-LAW depends on organizational need and feasibility. The system is designed so either path remains viable.

```
Now:     Standalone desktop app → folder-based batch processing → staff beta testing
Later:   Standalone app remains the product
           or
         Pipeline integrates into IT-LAW
```

The architecture keeps these options open by separating the processing pipeline from the interface layer.

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

### Deterministic First

Extraction should prioritize deterministic logic and validation rather than opaque machine learning models.

### Human-in-the-loop

Automation assists human reviewers rather than replacing them entirely. The GUI surfaces results for review; staff make the final call.

### Traceability

Every extracted value must be traceable to a document location.

### Incremental Development

The system improves gradually as additional documents are labeled and evaluated. Beta testing with staff drives this feedback loop.

### Deliverability

The tool must be easy to distribute and run. No server infrastructure, no browser dependency, no installation complexity. A single executable that works on staff machines.

---

## Potential Future Extensions

Future improvements may include:

- document classification to automatically reject irrelevant documents
- document template detection
- integration with IT-LAW or case management systems
- automatic document processing on upload (if integrated)
- improved review interface based on beta feedback
