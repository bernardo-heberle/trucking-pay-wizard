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

---

## Python Practices

### Project Structure

```
src/
  ingestion/       # Document loading, format conversion
  ocr/             # OCR provider adapters
  classification/  # Document type detection
  extraction/      # Field extraction logic
  validation/      # Value and consistency checks
  output/          # CSV/Excel export
tests/
  unit/
  integration/
```

Each package maps to a pipeline stage. New pipeline stages get new packages.

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

Use `.env` files for secrets (API keys, credentials) and YAML/TOML for application settings (OCR provider selection, output format preferences). Never hard-code configuration that might change between environments.

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
