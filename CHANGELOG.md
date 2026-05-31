# Changelog

All notable changes to Trucking Pay Wizard are documented here.
Entries are written for staff using the app — not for developers.

---

## [1.0.2] — 2026-05-31

### Fixed
- Fixed highlight placement on rotated, landscape document pages (such as the wide earnings and deduction tables on ArcBest settlement statements). The highlights now sit correctly across the values instead of being drawn sideways.

### Changed
- Settlement statements that only show open or outstanding items — where nothing was actually paid out that period (for example, a statement noting "No items were closed this period") — now have their amounts flagged for manual review instead of being marked as confirmed, so staff can verify them.

---

## [1.0.1] — 2026-05-31

### Fixed
- Fixed an issue where payment dates written with a leading day of the week or an abbreviated month with a period (for example, "Sunday, Feb. 16, 2025") were left blank in the spreadsheet instead of being recognized as a date.

---

## [1.0.0] — 2026-05-31

### Added
- The tool now decides whether each document is actually proof of a payment to the carrier. Documents that clearly are not (such as an insurance certificate, a bill of lading, or a file uploaded to the wrong place by mistake) are flagged. When the tool is unsure, it keeps the document in to be safe.
- Documents the tool could not confirm as payment proof are now listed in the spreadsheet, grayed out, with a note explaining they were left out of the combined PDF because they did not contain payment information.

### Changed
- The combined PDF now contains only payment documents. Documents identified as non-payment, and exact duplicate files, are no longer added to the PDF.
- The spreadsheet now lists every document. Payment documents come first (in date order), followed by payment documents with no readable date, then the excluded documents (non-payment and duplicates), with the TOTALS row at the very bottom. Excluded rows leave the date and pay columns blank so the totals stay correct.
- When a document is a payment document but the tool could not pull out any amount or date, the spreadsheet now shows a single row highlighted in red, marked for review, with the document's page range in the combined PDF (for example, "33 - 38").
- Duplicate files now appear as their own grayed-out rows that name the original file they duplicate, instead of being noted on the original document's row.

---

## [0.6.0] — 2026-05-31

### Added
- Added support for multi-page settlement remittance statements that begin with a summary page (such as the "Settlement at a glance" page on ArcBest/Panther statements). The tool now reads the net period pay-out and the period date from the summary page and ignores the detailed per-trip earning and deduction tables, so these documents report a single correct payment instead of being split into many line items.

---

## [0.5.0] — 2026-05-31

### Changed
- The combined PDF now includes only the pages up to the last highlighted value for documents where all fields were extracted with high confidence. Documents where extraction was uncertain or incomplete still include all pages, so staff can find and verify the relevant information manually.

---

## [0.4.0] — 2026-05-25

### Added
- The tool now detects when the same document has been submitted more than once (identical file contents under different filenames). Only one copy is processed; the duplicates are skipped. The spreadsheet notes which filenames were excluded in the Notes column of the corresponding row.

---

## [0.3.0] — 2026-05-25

### Added
- Added support for remittance advice / advice-of-deposit documents (such as those issued by Weyerhaeuser) — the tool now correctly extracts the total payment amount and the processing date from these documents.

### Fixed
- Fixed an issue where documents listing multiple invoice line items could cause the tool to report an individual line-item amount instead of the overall total.
- Fixed an issue where documents with no pickup date (such as remittance advices) caused the date field to be left blank — the tool now falls back to the earliest date visible in the document.

---

## [0.2.0] — 2026-05-25

### Changed
- Improved accuracy when identifying the correct carrier payment on documents that also show shipper prices, broker fees, COD amounts, or deposits — the tool now correctly targets the amount labeled as carrier payment.
- Fixed cases where a document with a revision history (e.g. an older $0.00 entry) could cause the wrong pay amount to be extracted — the tool now picks the current/final amount.
- Improved date extraction to prefer "Pickup Date" or "Pickup Exactly" fields and avoid picking up settlement-level dates (invoice date, statement date) as the load pickup date.
- Extraction results are now fully deterministic — repeated runs on the same document will always produce the same result.

---

## [0.1.4] — 2026-05-08

### Changed
- Test release to verify auto-update functionality.

---

## [0.1.3] — 2026-05-08

### Fixed
- Fixed initialization-order bug that prevented auto-update checks from running on app startup.

- Changed auto-update checks to re-run after an hour.

---

## [0.1.2] — 2026-05-08

---

## [0.1.1] — 2026-05-08

### Fixed
- Credential verification now correctly connects to Azure Document Intelligence.

---

## [0.1.0] — 2026-05-08

Initial release.

### Added
- Process a folder of trucking income documents in one click.
- Automatic text recognition (OCR) on PDFs and images.
- Extraction of gross pay, net pay, and payment dates from settlement statements and dispatch sheets.
- Combined PDF report and Excel spreadsheet exported to the working folder.
- Setup code flow — staff enter a single code on first launch instead of managing API keys directly.
- Caching of processed documents so unchanged files are not re-processed on subsequent runs.
- In-app update notifications when a new version is available.
