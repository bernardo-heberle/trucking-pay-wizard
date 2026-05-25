# Changelog

All notable changes to Trucking Pay Wizard are documented here.
Entries are written for staff using the app — not for developers.

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
