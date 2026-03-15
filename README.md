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
4. Extracts and validates financial fields
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
- financial field extraction and validation
- report assembly (combined PDF + CSV/Excel generation)
- packaging as a distributable executable
- evaluation with DTC staff for feedback

---

# Security

Documents may contain sensitive financial and personal data.

Guidelines:

- Do not commit documents to the repository
- Store credentials in `.env`
- Restrict access to API keys
- The executable should not persist sensitive data beyond the active session

---

# License

Private internal project.
