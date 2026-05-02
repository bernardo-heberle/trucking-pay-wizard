"""Quick validation that char_start/char_end offsets are correct in all JSON fixtures."""
import json
from pathlib import Path

_FIXTURES_DIR = Path(__file__).parent
_ALL = [p for p in _FIXTURES_DIR.glob("*.json") if p.name not in ("settlement_ocr.json", "pay_summary_ocr.json")]

ok = True
for fpath in sorted(_ALL):
    raw = json.loads(fpath.read_text(encoding="utf-8"))
    lines = raw["lines"]

    pages_grouped: dict = {}
    for ln in lines:
        pages_grouped.setdefault(ln["page_number"], []).append(ln)

    full_text = "\n\n".join(
        "\n".join(ln["text"] for ln in pages_grouped[pn])
        for pn in sorted(pages_grouped)
    )

    errors = []
    for ln in lines:
        sliced = full_text[ln["char_start"]:ln["char_end"]]
        if sliced != ln["text"]:
            errors.append(f"  GOT {sliced!r}, WANT {ln['text']!r}")

    status = "OK" if not errors else f"FAIL ({len(errors)} errors)"
    print(f"{fpath.name}: {status}")
    for e in errors[:3]:
        print(e)
    if errors:
        ok = False

raise SystemExit(0 if ok else 1)
