"""Pytest plugin that writes per-test diagnostic JSON files and a session-end
summary for the live API test tier.

Registered via ``pytest_plugins`` in ``tests/live/conftest.py``.  Hooks:

  - ``pytest_sessionstart`` — creates ``tests/live/_diagnostics/<timestamp>/``
  - ``pytest_runtest_logreport`` — after each test call, writes ``<Class>-<test>.json``
  - ``pytest_sessionfinish`` — writes ``summary.md``

Failure categorisation is heuristic (based on assertion message + recorded
data) and never mutates the test result — the assertion outcome is always
the source of truth.
"""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# Path to the live test directory — diagnostics land beside it.
_LIVE_DIR = Path(__file__).parent
_DIAGNOSTICS_ROOT = _LIVE_DIR / "_diagnostics"


# ---------------------------------------------------------------------------
# Session-level state
# ---------------------------------------------------------------------------

class _DiagnosticSession:
    """Holds per-session state shared across hooks."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.records: list[dict[str, Any]] = []  # one entry per test call

    def record_path(self, class_name: str, test_name: str) -> Path:
        safe = re.sub(r"[^\w\-]", "_", f"{class_name}-{test_name}")
        return self.run_dir / f"{safe}.json"


_session: _DiagnosticSession | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _categorise_failure(
    outcome: str,
    longrepr: str,
    record: dict[str, Any],
) -> str:
    """Derive a failure category from the assertion message + recorded data."""
    if outcome == "passed":
        return "PASSED"

    extraction_error = record.get("extraction_error")
    if extraction_error:
        return "EXTRACTION_ERROR"

    fallbacks = record.get("schema_fallbacks_used", [])
    if any("flat_format" in f or "plain_string" in f for f in fallbacks):
        return "SCHEMA_PARSE_ERROR"

    msg = longrepr or ""

    if "load" in msg.lower() and ("count" in msg.lower() or "len" in msg.lower()):
        return "LOAD_COUNT_MISMATCH"

    if "pay" in msg.lower() and "certainty" in msg.lower():
        return "CERTAINTY_DOWNGRADE"
    if "certainty" in msg.lower() and "HIGH" in msg:
        return "CERTAINTY_DOWNGRADE"

    # Check verification records for a downgrade that produced the failure.
    ver_records = record.get("verification_records", [])
    for vr in ver_records:
        if vr.get("verification_matched") is False:
            if "certainty" in msg.lower() or "high" in msg.lower():
                return "CERTAINTY_DOWNGRADE"

    if "pay" in msg.lower() and (
        "value" in msg.lower() or "normalize" in msg.lower() or "=="  in msg
    ):
        return "PAY_VALUE_MISMATCH"

    if "date" in msg.lower() and "value" in msg.lower():
        return "DATE_VALUE_MISMATCH"

    # Check source records for missing spans on asserted fields.
    src_records = record.get("source_records", [])
    for sr in src_records:
        if sr.get("pay_found_in_ocr") is False or sr.get("date_found_in_ocr") is False:
            return "SOURCE_LOCATION_MISS"

    return "OTHER"


def _record_to_dict(record: Any) -> dict[str, Any]:
    """Convert an ``ExtractionRecord`` (dataclass) to a plain dict for JSON."""
    try:
        return dataclasses.asdict(record)
    except Exception:
        return {"error": "Could not serialise record", "repr": repr(record)}


def _build_ocr_snippet(sanitized_text: str, window: int = 60) -> str:
    """Return the first *window* lines of sanitized OCR text as a string."""
    lines = sanitized_text.splitlines()
    return "\n".join(lines[:window])


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

def pytest_sessionstart(session: pytest.Session) -> None:
    global _session
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = _DIAGNOSTICS_ROOT / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    _session = _DiagnosticSession(run_dir)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if _session is None:
        return
    if report.when != "call":
        return

    # Retrieve the extractor from the test's fixture values (if available).
    record_dict: dict[str, Any] = {}
    try:
        # The fixture is session-scoped; access via the test item's session.
        extractor = report._item.session._store.get(  # type: ignore[attr-defined]
            pytest.StashKey(), None
        )
    except Exception:
        extractor = None

    # Try to get the extractor from the session fixture cache instead.
    if extractor is None:
        try:
            fm = report._item.session._fixturemanager  # type: ignore[attr-defined]
            cache = fm._arg2fixturedefs
            if "anthropic_extractor" in cache:
                # The live session should have stored last_record on the fixture value.
                pass
        except Exception:
            pass

    # Best-effort: look for the extractor on a module-level stash.
    import tests.live._diagnostic_recorder as _rec_mod
    extractor = getattr(_rec_mod, "_active_extractor", None)

    if extractor is not None:
        raw_record = getattr(extractor, "last_record", None)
        if raw_record is not None:
            record_dict = _record_to_dict(raw_record)

    outcome = report.outcome  # "passed", "failed", "error"
    longrepr = str(report.longrepr) if report.longrepr else ""
    category = _categorise_failure(outcome, longrepr, record_dict)

    # Derive class and test name from nodeid  (e.g. "tests/live/test_X.py::Class::test_y")
    nodeid = report.nodeid
    parts = nodeid.split("::")
    class_name = parts[-2] if len(parts) >= 3 else "NoClass"
    test_name = parts[-1] if parts else "unknown"

    entry: dict[str, Any] = {
        "nodeid": nodeid,
        "class": class_name,
        "test": test_name,
        "outcome": outcome,
        "category": category,
        "failure_message": longrepr[:4000] if longrepr else None,
        "record": record_dict,
    }

    # Write per-test JSON.
    json_path = _session.record_path(class_name, test_name)
    try:
        json_path.write_text(
            json.dumps(entry, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        # Never let diagnostic writing break the test session.
        print(f"\n[diagnostic] WARNING: could not write {json_path}: {exc}")

    _session.records.append(entry)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _session is None or not _session.records:
        return

    try:
        _write_summary(_session)
    except Exception as exc:
        # Diagnostic writing must never affect the test exit code.
        print(f"\n[diagnostic] WARNING: summary writer failed: {exc}")


# ---------------------------------------------------------------------------
# Summary writer
# ---------------------------------------------------------------------------

def _write_summary(ds: _DiagnosticSession) -> None:
    records = ds.records
    total = len(records)
    passed = sum(1 for r in records if r["outcome"] == "passed")
    failed = total - passed

    # Collect model name from any record that has it.
    model = next(
        (r["record"].get("model", "") for r in records if r["record"].get("model")),
        "unknown",
    )

    # Failure breakdown.
    from collections import Counter
    category_counts: Counter[str] = Counter(
        r["category"] for r in records if r["outcome"] != "passed"
    )

    # Non-prompt suspects — aggregate signals.
    verif_downgrades: list[dict[str, Any]] = []
    source_misses: list[dict[str, Any]] = []
    near_cap_tests: list[str] = []
    fallback_uses: list[str] = []
    sanitizer_hits: list[dict[str, Any]] = []

    for r in records:
        rec = r["record"]
        test_id = r["nodeid"]

        # Verification downgrades
        for vr in rec.get("verification_records", []):
            if vr.get("verification_matched") is False:
                verif_downgrades.append({
                    "test": test_id,
                    "load_index": vr.get("load_index"),
                    "raw_pay": vr.get("raw_pay_value"),
                    "normalized": vr.get("normalized_pay_value"),
                    "reason": vr.get("verification_reason"),
                })

        # Source location misses
        for sr in rec.get("source_records", []):
            for fname in ("pay", "date"):
                found_key = f"{fname}_found_in_ocr"
                if sr.get(found_key) is False:
                    source_misses.append({
                        "test": test_id,
                        "field": fname,
                        "value": sr.get(f"{fname}_value"),
                        "n_matches_in_ocr": sr.get(f"{fname}_n_matches"),
                    })

        # Near token cap
        if rec.get("near_token_cap"):
            near_cap_tests.append(
                f"{test_id} — in={rec.get('input_tokens')} out={rec.get('output_tokens')} "
                f"max={rec.get('max_tokens')}"
            )

        # Schema fallbacks
        for fb in rec.get("schema_fallbacks_used", []):
            fallback_uses.append(f"{test_id}: {fb}")

        # Sanitizer
        if rec.get("sanitizer_total_redactions", 0) > 0:
            sanitizer_hits.append({
                "test": test_id,
                "total": rec["sanitizer_total_redactions"],
                "by_pattern": rec.get("sanitizer_redaction_counts", {}),
            })

    lines: list[str] = [
        f"# Live Test Diagnostic Report — {datetime.now(timezone.utc).isoformat()}",
        f"",
        f"Model: `{model}`  |  Total: {total}  |  Pass: {passed}  |  Fail: {failed}",
        f"",
    ]

    # --- Failure breakdown ---
    if category_counts:
        lines += ["## Failure breakdown by category", ""]
        for cat, count in category_counts.most_common():
            lines.append(f"- **{cat}** × {count}")
        lines.append("")
    else:
        lines += ["## All tests passed", ""]

    # --- Non-prompt suspects ---
    lines += ["## Non-prompt suspects (signals to investigate)", ""]

    if verif_downgrades:
        lines.append(
            f"### Pay verifier downgraded HIGH→REVIEW on {len(verif_downgrades)} load(s)"
        )
        lines.append("")
        lines.append(
            "_A downgrade means the normalised pay value was not found in the OCR text._"
            "  _Possible causes: sanitizer mangled the number, OCR formatting differs from_"
            "  __normalize_pay_value assumptions, or the LLM returned the wrong field._"
        )
        lines.append("")
        for vd in verif_downgrades:
            lines.append(
                f"- `{vd['test']}` load {vd['load_index']}: "
                f"raw=`{vd['raw_pay']}` normalised=`{vd['normalized']}` — {vd['reason']}"
            )
        lines.append("")
    else:
        lines += ["### Pay verifier: no HIGH→REVIEW downgrades detected", ""]

    if source_misses:
        lines.append(
            f"### Source-location resolver missed {len(source_misses)} field(s)"
        )
        lines.append("")
        lines.append(
            "_A miss means the LLM-returned value string was not found verbatim in the_"
            "  _OCR text. The LLM may have reformatted the value, or the sanitizer removed_"
            "  _characters that appear in the field value._"
        )
        lines.append("")
        for sm in source_misses:
            lines.append(
                f"- `{sm['test']}` field=`{sm['field']}` "
                f"value=`{sm['value']}` ocr_matches={sm['n_matches_in_ocr']}"
            )
        lines.append("")
    else:
        lines += ["### Source-location resolver: all fields located in OCR text", ""]

    if sanitizer_hits:
        lines.append(
            f"### PII sanitizer redacted content in {len(sanitizer_hits)} test(s)"
        )
        lines.append("")
        lines.append(
            "_Verify that no redaction placeholder overlaps with the expected pay or date string._"
        )
        lines.append("")
        for sh in sanitizer_hits:
            lines.append(
                f"- `{sh['test']}`: {sh['total']} redaction(s) — {sh['by_pattern']}"
            )
        lines.append("")
    else:
        lines += ["### PII sanitizer: no redactions in any live fixture", ""]

    if near_cap_tests:
        lines.append(
            f"### Token usage near cap (>85% of max_tokens) on {len(near_cap_tests)} test(s)"
        )
        lines.append("")
        lines.append(
            "_Consider increasing max_tokens (currently 1024) for multi-load fixtures._"
        )
        lines.append("")
        for nc in near_cap_tests:
            lines.append(f"- {nc}")
        lines.append("")
    else:
        lines += ["### Token usage: no tests near cap", ""]

    if fallback_uses:
        lines.append(
            f"### Schema fallback paths triggered on {len(fallback_uses)} occurrence(s)"
        )
        lines.append("")
        lines.append(
            "_`flat_format_wrapped`: model returned old `{{pay, date}}` shape instead of_"
            "  _`{{loads: [...]}}`. Reinforce the loads-array requirement in the system prompt._"
        )
        lines.append("")
        lines.append(
            "_`plain_string_field:pay/date`: model collapsed a field to a bare string._"
            "  _Reinforce the `{{value, confidence}}` object schema._"
        )
        lines.append("")
        for fb in fallback_uses:
            lines.append(f"- {fb}")
        lines.append("")
    else:
        lines += ["### Schema fallbacks: none triggered", ""]

    # --- Failed test details ---
    failed_records = [r for r in records if r["outcome"] != "passed"]
    if failed_records:
        lines += ["---", "", "## Failed tests (details)", ""]
        for r in failed_records:
            rec = r["record"]
            lines += [
                f"### `{r['nodeid']}`",
                f"",
                f"- **Category**: {r['category']}",
                f"- **Failure message** (truncated):",
                f"",
                f"  ```",
            ]
            msg = (r.get("failure_message") or "")[:2000]
            for mline in msg.splitlines()[:30]:
                lines.append(f"  {mline}")
            lines += [
                f"  ```",
                f"",
            ]
            # Per-load snapshot
            for load_sum in rec.get("final_loads_summary", []):
                pay = load_sum.get("pay") or {}
                date = load_sum.get("date") or {}
                lines.append(
                    f"- **load {load_sum.get('index')}**: "
                    f"pay raw=`{pay.get('value')}` "
                    f"normalised=`{pay.get('normalized')}` "
                    f"certainty={pay.get('certainty')}  |  "
                    f"date=`{date.get('value')}` certainty={date.get('certainty')}"
                )
            lines.append("")

            # OCR snippet for prompt-iteration context
            sanitized = rec.get("sanitized_text", "")
            if sanitized:
                lines += [
                    "**OCR snippet (first 40 lines of sanitized text sent to LLM):**",
                    "",
                    "```",
                ]
                snippet_lines = sanitized.splitlines()[:40]
                lines.extend(snippet_lines)
                lines += ["```", ""]

            lines += [
                f"**Diagnostic file**: `{ds.run_dir.name}/{r['nodeid'].split('::')[-2]}"
                f"-{r['nodeid'].split('::')[-1]}.json`",
                "",
            ]

    summary_path = ds.run_dir / "summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[diagnostic] Report written -> {summary_path}")
