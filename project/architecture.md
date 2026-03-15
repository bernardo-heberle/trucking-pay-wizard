# System Architecture

The system processes documents through a structured pipeline where each stage performs a specific transformation.

---

# Processing Pipeline

Documents pass through the following stages:











---

# Components

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

## Document Classification

Determines whether the document contains income information.

Examples:

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

## Output

Results are exported to structured formats such as:

- CSV
- Excel

These outputs support further claims processing workflows.

---

# Design Goals

The architecture prioritizes:

- modularity
- traceability
- reliability
- provider independence for OCR