# DTC Income Extraction

Automated document processing pipeline for extracting trucking income information from documents submitted during downtime insurance claims.

The system processes uploaded PDFs and images and converts them into structured financial records used to estimate lost income.

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

This project builds an automated pipeline that:

1. Processes uploaded documents
2. Converts documents into machine-readable text using OCR
3. Identifies documents containing income information
4. Extracts financial fields
5. Validates extracted data
6. Produces structured output for review

---


# Project Documentation

- Vision: `project/vision.md`
- Architecture: `project/architecture.md`
- Setup Instructions: `project/setup.md`
- Developer Guidelines: `project/developer_guidelines.md`

---

# Current Status

Prototype development.

Current focus areas:

- OCR integration
- financial field extraction
- validation rules
- prototype evaluation with sample documents

---

# Security

Documents may contain sensitive financial and personal data.

Guidelines:

- Do not commit documents to the repository
- Store credentials in `.env`
- Restrict access to API keys

---

# License

Private internal project.