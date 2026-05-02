# Developer Guidelines

These guidelines keep the codebase healthy as it grows. They favor pragmatism over ceremony — do what works, revisit when it doesn't.

---

## Core Principles

### Don't Repeat Yourself (DRY) — but don't over-abstract

Duplication of *knowledge* is the real enemy, not duplication of code. Two functions that happen to look similar today but serve different concerns can diverge freely. Extract shared logic only when the duplication represents the same business rule.

### Orthogonality

Changes to OCR processing should not ripple into validation. Changes to output format should not touch extraction. Keep components independent so they can be developed, tested, and replaced in isolation.

### Tracer Bullets

When building a new capability, wire together a thin end-to-end path first — document in, structured data out — even if each stage is minimal. This proves the integration works before you invest in depth.

### Good Enough Software

Ship working increments. A rule-based extractor that handles 80% of documents today is more valuable than a perfect one that ships next quarter. Flag what you can't handle and let human review cover the gap.

### Reversibility

Avoid decisions that are hard to undo. Use interfaces and configuration to keep OCR providers, output formats, and extraction strategies swappable. Lean on dependency injection and configuration files, not hard-coded choices.

The delivery model itself is a reversibility question — the standalone desktop app may remain the final product or the pipeline may integrate into IT-LAW. Keeping the GUI as a thin layer over the pipeline ensures either path stays open.

### Open/Closed

Pipeline stages should be extendable without editing existing ones. The classification placeholder is a concrete example — when classification is ready, it slots between OCR and Extraction; neither of those stages changes. Write stages that consume a well-defined input and produce a well-defined output so new stages can be added around them.

---

## Python Practices

### Project Structure

```
src/
  gui/             # Desktop GUI (presentation only)
  ingestion/       # Document loading, format conversion
  ocr/             # Azure Document Intelligence adapter
  classification/  # Document type detection (placeholder — not active in beta)
  extraction/      # Field extraction logic
    llm/           # Schema-driven LLM extraction (Anthropic API)
      schemas/     # Pluggable extraction schemas (one per document type)
  validation/      # Value and consistency checks
  report/          # Report assembly: PDF stitching, index generation, CSV export
  config.py        # Application settings loaded from .env
tests/
  unit/
  integration/
```

Each package maps to a pipeline stage or application layer. The `gui` package depends on the pipeline; the pipeline never imports from `gui`.

`src/classification/` exists as a structural placeholder. The beta pipeline skips classification entirely — all documents are assumed to be valid income documents. The package is present so the pipeline can be extended with a classification stage later without reorganizing the project. Do not add classification logic until it is explicitly needed.

`src/report/` is responsible for consuming cached per-document extraction results and producing the two output artifacts (combined PDF and CSV/Excel). Extraction produces data; report assembly consumes it. These concerns must stay separate.

### Naming

Use clear, intention-revealing names. Prefer `extract_gross_pay()` over `process()`. Prefer `settlement_text` over `data`. If a name needs a comment to explain it, choose a better name.

### Functions

Keep functions focused. A function should do one thing well, but "one thing" is defined at the right level of abstraction — `process_document()` orchestrating five steps is fine. Avoid rigid line-count rules; let readability guide length.

### Type Hints

Use type hints on all public function signatures. They serve as lightweight documentation and catch bugs early. Internal helper functions can be more relaxed.

```python
def extract_payment_date(text: str) -> date | None:
    ...
```

### Error Handling

Fail fast and fail loud. Raise specific exceptions rather than returning `None` for unexpected failures. Reserve `None` returns for genuinely optional results (e.g., a field that may not exist in a document).

```python
class ExtractionError(Exception):
    """Raised when extraction fails in an unexpected way."""

class FieldNotFound(Exception):
    """Raised when an expected field is missing from the document."""
```

### Logging over Printing

Use `logging` everywhere. Every pipeline stage should log enough to reconstruct what happened to a document without re-running the pipeline. This directly supports the project's traceability goal.

### Dependencies

Pin versions in `requirements.txt`. Add new dependencies deliberately — every dependency is code you didn't write and can't fully control.

---

## Design by Contract

Each pipeline stage has a clear contract:

- **Preconditions** — what the stage expects (e.g., OCR layer expects an image or PDF path)
- **Postconditions** — what the stage guarantees (e.g., extraction returns a typed dataclass or raises)
- **Invariants** — what always holds (e.g., every extracted value carries a source reference)

Keep stage contracts narrow. A caller that only needs extracted text should not depend on a type that also carries bounding boxes and confidence scores. Split contracts when consumers only need a subset — this keeps stages independently testable and prevents unintended coupling.

Use `assert` in development to verify contracts. Use validation logic in production.

---

## Testing

### Write tests that matter

Prioritize tests for extraction rules and validation logic — these are where bugs cause real damage. Don't chase coverage metrics for the sake of it.

### Test at the right level

- **Unit tests** for extraction functions, validators, and formatting logic.
- **Integration tests** for pipeline stage boundaries (OCR output → extraction input).
- **Sample document tests** for end-to-end verification with known documents.

### Use real-ish data

Keep a `tests/fixtures/` directory with sanitized sample OCR outputs. Test against realistic text, not toy strings.

---

## Traceability

This is a project-level requirement, not a nice-to-have.

- Every extracted value must reference the source document and location.
- Use dataclasses or models that carry provenance metadata alongside values.
- Log the full processing path for each document.

```python
@dataclass
class ExtractedField:
    name: str
    value: str
    source_document: str
    source_location: str | None = None
    confidence: float | None = None
```

---

## Configuration

Use `.env` files for secrets (API keys, credentials) and YAML/TOML for application settings (Azure endpoint, model selection, output format preferences). Never hard-code configuration that might change between environments.

Key configuration variables:

- `ANTHROPIC_API_KEY` — required
- `LLM_MODEL` — which Claude model to use (defaults to `claude-haiku-4-5`)

---

## Extraction

The `LlmExtractor` receives an `OcrResult` and returns a `DocumentExtractionResult`. It sends PII-sanitized OCR text to Claude via tool_use and returns structured fields with confidence scores.

### Extraction Schemas

Each LLM schema subclasses `ExtractionSchema` and defines what fields to extract, the tool_use JSON definition, and a parser for the LLM response. To support a new document type, add a new schema in `src/extract/llm/schemas/` — the `LlmExtractor` does not change.

---

## PII Sanitization

**Never send unsanitized document text to an external API.**

The PII sanitizer (`src/extract/llm/sanitizer.py`) scrubs sensitive identifiers from OCR text before it reaches the Anthropic API. Patterns include SSNs and EINs. The sanitizer is extensible — add new `RedactionPattern` entries for additional PII types.

Redaction counts are logged; actual matched values are never logged or stored.

---

## Folder-Based Session Layout

The tool operates on working folders. Code that reads or writes session data must follow this layout:

```
working-folder/
  ├── <source documents>         # staff-provided files (PDFs, images)
  ├── .cache/                    # per-document processing results (JSON)
  │     ├── doc1_hash.json
  │     └── doc2_hash.json
  ├── combined_report.pdf        # generated output artifact
  └── extracted_data.csv         # generated output artifact
```

Conventions:

- Cache files are named `<hash>_llm[_<version>].json`, keyed by content hash and an optional version fingerprint. Changing the sanitizer patterns or extraction schema automatically invalidates stale entries.
- Output artifacts are always regenerated from the full set of cached results, never incrementally patched.
- The `.cache/` directory is an implementation detail — users should not need to interact with it.
- Source documents are never modified or moved by the tool.

---

## GUI Layer

The GUI is a presentation layer. It should:

- Call into the pipeline, never contain business logic itself.
- Remain replaceable — if the pipeline integrates into IT-LAW, the GUI is discarded, not refactored.
- Handle all user interaction: drag-and-drop, progress display, result review, export triggers.
- Never be imported by pipeline code. The dependency arrow points one way: `gui → pipeline`.

Keep GUI code in `src/gui/`. If you find yourself writing extraction logic or validation rules in a GUI module, move it to the appropriate pipeline package.

---

## Platform-Neutral Code

The tool deploys as a **Windows executable**, but code must be written in a platform-neutral way. This keeps the codebase clean and avoids OS-specific assumptions that are fragile even within Windows.

### File Paths

Always use `pathlib.Path` for file and directory operations. Never build paths with string concatenation or hardcoded separators (`\` or `/`).

```python
# ✅ GOOD
from pathlib import Path
cache_dir = working_folder / ".cache"
output_pdf = working_folder / "combined_report.pdf"

# ❌ BAD
cache_dir = working_folder + "\\.cache"
output_pdf = os.path.join(working_folder, "combined_report.pdf")
```

### No OS-Specific Assumptions

- Do not use `os.system()` or shell commands that differ between platforms.
- Do not assume file name case-sensitivity (macOS filesystems are case-insensitive by default; Windows always is; Linux is not).
- Do not rely on platform-specific temp directories — use `pathlib.Path` and `tempfile` from the standard library.

### `.cache/` Visibility

On Windows, files and folders starting with `.` are not hidden by the OS. This is cosmetically different from macOS but does not affect functionality. Do not add platform-specific code to hide the `.cache/` directory.

---

## Packaging and Distribution

The application ships as a standalone executable. Keep packaging concerns in mind:

- Minimize dependencies that complicate bundling.
- Test the packaged executable, not just the development environment.
- Avoid hard-coded paths — use relative paths or user-configurable locations.
- Secrets (API keys) should be configurable at runtime, not baked into the build.
- **PyInstaller** — run on Windows to produce the `.exe`. Test on a clean Windows machine before distributing.

---

## Version Control

- Write commit messages that explain *why*, not just *what*.
- Keep commits focused — one logical change per commit.
- Do not commit documents, data files, or credentials.

---

## When in Doubt

1. Make it work.
2. Make it clear.
3. Make it fast — only if profiling says you need to.

Optimize for readability and maintainability. Clever code is a liability when someone else (or future you) needs to debug it at midnight.
