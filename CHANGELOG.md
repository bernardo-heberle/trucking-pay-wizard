# Changelog

All notable changes to Trucking Pay Wizard are documented here.
Entries are written for staff using the app — not for developers.

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
