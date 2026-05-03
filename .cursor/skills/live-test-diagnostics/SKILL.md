---
name: live-test-diagnostics
description: Run the live API tests for the Trucking Pay Wizard and read the diagnostic output to investigate extraction failures, prompt regressions, or pay-verification issues. Use when the user asks to run live tests, investigate why live tests are failing, iterate on prompts, or understand what the LLM returned for a given fixture.
---

# Live Test Diagnostics

## Running the live tests

```powershell
pytest tests/live/ --no-cov -v -p randomly
```

Requirements: `ANTHROPIC_API_KEY` and `AZURE_DOCUMENT_INTELLIGENCE_*` in `.env`. Tests auto-skip when credentials are missing.

After each run, a timestamped directory is created under `tests/live/_diagnostics/`:

```
tests/live/_diagnostics/
  20260503T224715Z/
    summary.md                          ← start here
    TestSettlementExtraction-test_pay_value.json
    TestV2DispatchPipeline-test_extracts_pay.json
    ... one JSON per test ...
```

## Reading the summary

Open `tests/live/_diagnostics/<latest>/summary.md`. It shows:

- **Pass/fail counts** and model used
- **Failure breakdown by category** (`PAY_VALUE_MISMATCH`, `CERTAINTY_DOWNGRADE`, `SCHEMA_PARSE_ERROR`, `LOAD_COUNT_MISMATCH`, `DATE_VALUE_MISMATCH`, `SOURCE_LOCATION_MISS`, `OTHER`)
- **Non-prompt suspects** — signals that point to issues outside the prompt:
  - Pay verifier HIGH→REVIEW downgrades (pay value not found in OCR text)
  - Source-location resolver misses (LLM value not matched back to OCR verbatim)
  - PII sanitizer redactions (verify no overlap with expected pay/date strings)
  - Token cap warnings (output > 85% of max_tokens=1024)
  - Schema fallback paths hit (`flat_format_wrapped`, `plain_string_field:pay/date`)

## Reading a per-test JSON

Each JSON contains the full diagnostic record for that one test call. Key fields:

| Field | What it tells you |
|---|---|
| `raw_tool_input` | **Verbatim** structured JSON the LLM returned — compare against `user_message` to see what the model decided |
| `user_message` | Full sanitized OCR text sent to the LLM |
| `system_prompt` | System prompt that was active |
| `tool_definition` | Tool schema that was active |
| `input_tokens` / `output_tokens` | Token usage for this call |
| `schema_fallbacks_used` | List of fallback paths triggered (empty = clean response) |
| `source_records[].pay_found_in_ocr` | Whether the LLM's raw pay string was found verbatim in OCR |
| `source_records[].pay_n_matches` | How many times the pay string appears in OCR (>1 = ambiguous) |
| `verification_records[].verification_matched` | Whether pay verification passed (`true`) or downgraded HIGH→REVIEW (`false`) |
| `verification_records[].normalized_pay_value` | Normalized form of the pay value that was checked against OCR |
| `final_loads_summary` | What each load looks like after all stages |

## Prompt-iteration workflow

1. Run tests, open `summary.md`
2. Identify failing tests and their categories
3. Open the corresponding `.json` files
4. Compare `raw_tool_input` against `user_message` to understand what the model saw and decided
5. Edit the system prompt or tool schema in `src/extract/llm/schemas/income.py`
6. Re-run — diff `summary.md` between runs to confirm the change moved the needle

## How pay assertions work

`pay.value` stores the **raw LLM string** as it appeared in the document (e.g. `"$1,850.00"`, `"$820"`). All pay assertions in the live tests normalise it:

```python
from src.extract.llm.schemas.income import _normalize_pay_value

assert _normalize_pay_value(pay.value) == "1850.00"  # canonical string stays pinned
```

`_normalize_pay_value` strips `$`, `,`, spaces and pads to two decimal places — the same function the pay verifier and Excel exporter use. The canonical expected string (right-hand side) never changes; the wrapper accepts any legal raw format the prompt might produce.

## Architecture of the diagnostic system

Three test-only files (no production-code changes):

- `tests/live/_diagnostic_recorder.py` — `RecordingLlmExtractor` subclass that overrides `_call_llm`, `_resolve_source_locations`, and `_verify_pay_fields`; every override calls `super()` and only adds capture. A `_CapturingClient` wrapper intercepts `anthropic.Anthropic.messages.create` to record token usage and the raw tool response.
- `tests/live/_diagnostic_plugin.py` — three pytest hooks: `pytest_sessionstart` (creates run dir), `pytest_runtest_logreport` (writes per-test JSON after each test call), `pytest_sessionfinish` (writes `summary.md`). Wrapped in `try/except` so it can never affect the test exit code.
- `tests/live/conftest.py` — registers the plugin via `pytest_plugins`, replaces the `anthropic_extractor` fixture with `RecordingLlmExtractor`. The extractor instance is exposed as `_diagnostic_recorder._active_extractor` so the plugin can find it.

`tests/live/_diagnostics/` is gitignored — artifacts never land in version control.

## Anti-gaming rules (always enforce)

- Canonical expected values in assertions never change (`"750.00"`, `"1850.00"`, etc.)
- No `xfail`, `skip`, or retry loops added based on results
- `RecordingLlmExtractor` is observe-only — every override returns `super()`'s value unchanged
- Fixture JSON files are never edited to make a test pass
- Production code in `src/` is never changed to improve diagnostic coverage
