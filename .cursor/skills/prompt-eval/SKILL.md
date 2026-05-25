---
name: prompt-eval
description: Evaluate extraction accuracy against ground-truth documents and iterate on the LLM prompt. Use when real-world documents produce wrong pay amounts or dates, when adding support for a new document type, or when you want to measure prompt changes before running the full live test suite.
---

# Prompt Evaluation Workflow

Use this skill whenever staff report that the tool extracted wrong values from real documents, or when you want to test a new document type before releasing.

## Step 1 — Prepare test data

You need two things in the same folder:

**A. Pre-OCR'd text files** — one `.txt` per document, produced by `ocr_dump.py`:

```powershell
.venv\Scripts\python.exe prototyping/ocr_dump.py "C:\path\to\pdfs"
```

Each `.txt` will have this structure (one section per page):
```
--- Page 1 ---
line1
line2
...
```

**B. `correct_answers.csv`** — hand-verified expected values:

```csv
Document,Date,Pay
REMITTANCE ADVICE.txt,03/04/2026,"$3,274.69"
REMITTANCE ADVICE 2.txt,02/25/2026,"$5,343.67"
TOTALS,,...   ← optional totals row, skipped automatically
```

- `Document` — exact filename of the `.txt` file
- `Date` — expected date in `MM/DD/YYYY` format
- `Pay` — expected pay amount (dollar sign and commas are fine)

## Step 2 — Run the baseline eval

```powershell
.venv\Scripts\python.exe prototyping/prompt_eval.py "C:\path\to\folder"
```

Output is printed to the terminal and saved to `<folder>/eval_results.txt`:

```
Document                  Expected Pay  Got Pay    Pay OK  Expected Date  Got Date    Date OK
---------------------------------------------------------------------------------------------
REMITTANCE ADVICE.txt     $3,274.69     3,274.69   Y       03/04/2026     03/04/2026  Y
REMITTANCE ADVICE 2.txt   $5,343.67     4,163.97   N       02/25/2026     (none)      N
...
Pay:   8/11 correct
Date:  1/11 correct
Both:  1/11 fully correct
```

Save or screenshot the baseline table — you will compare it against the next run after your prompt change.

## Step 3 — Diagnose failures

**Pay failures** — `Got Pay` is wrong or `(none)`:
- Wrong amount: the LLM picked a different dollar figure (line item vs. TOTAL, shipper price vs. carrier pay, line item 1 vs. a later one).
- `(none)`: the LLM returned `null` for pay — the document structure may be unfamiliar.

**Date failures** — `Got Date` is wrong or `(none)`:
- `(none)`: the LLM returned `null` — check if the prompt's date rules are too restrictive for this document type.
- Wrong date: the LLM picked the wrong date label (e.g. "available on" vs. "processed on").

Look at the raw `.txt` files side by side with the failures to understand what the LLM is seeing.

## Step 4 — Edit the prompt

Open [`src/extract/llm/schemas/income.py`](src/extract/llm/schemas/income.py). The two places to edit:

**`_SYSTEM_PROMPT`** (the big multi-line string around line 98) — controls what the LLM is instructed to do. This is the main prompt you iterate on.

**`_TOOL_SCHEMA`** (the JSON schema dict, lines 14-96) — controls the field descriptions the LLM sees in the tool definition. Keep descriptions consistent with the system prompt; e.g. if you relax date extraction, update the `date` field description too.

Common prompt fixes:
| Failure type | Fix |
|---|---|
| LLM splits line items into separate loads | Strengthen the TOTAL-row rule: "return exactly ONE load using the TOTAL amount" |
| LLM returns null for date | Add a fallback: "if no pickup date, use the earliest date visible in the document" |
| LLM picks shipper price instead of carrier pay | Add more label examples to the disambiguation section |
| New document type not recognised | Add it to the "Common formats include" list at the top |

**Important:** changing the system prompt or tool schema automatically invalidates the extraction cache (the `fingerprint()` method hashes both), so previously cached results for documents in the working folder will be re-extracted on the next pipeline run.

## Step 5 — Re-run and compare

```powershell
.venv\Scripts\python.exe prototyping/prompt_eval.py "C:\path\to\folder"
```

Compare `Both: X/11` between runs. Repeat Steps 3-5 until all documents pass or you reach diminishing returns.

## Step 6 — Regression check

Once the eval passes, confirm no existing document types broke:

```powershell
.venv\Scripts\python.exe -m pytest tests/live/ --no-cov -v
```

All 50 tests should pass. The live test suite covers: CentralDispatch, V2 Dispatch, Super Dispatch / BacklotCars, COD settlement, multi-vehicle, multi-load, revision history, duplicate pay, and duplicate date fixtures.

If a previously passing test now fails, your prompt change caused a regression — roll back or refine the wording so it is specific enough not to affect the existing cases.

## Step 7 — Commit and release

When both the eval and the regression suite pass:

1. Bump the version in `src/__version__.py` (MINOR for new document type support, PATCH for a targeted fix).
2. Add a changelog entry in `CHANGELOG.md` describing what changed in plain English for staff.
3. Commit both files alongside `src/extract/llm/schemas/income.py`.
4. Follow the release workflow skill to build and publish the installer.

## Quick reference

| Task | Command |
|---|---|
| OCR a folder of PDFs to .txt | `.venv\Scripts\python.exe prototyping/ocr_dump.py <folder>` |
| Run extraction eval | `.venv\Scripts\python.exe prototyping/prompt_eval.py <folder>` |
| Run live regression suite | `.venv\Scripts\python.exe -m pytest tests/live/ --no-cov -v` |
| Edit prompt | `src/extract/llm/schemas/income.py` → `_SYSTEM_PROMPT` and `_TOOL_SCHEMA` |

## Anti-overfitting rules

- Write prompt rules that describe the *document structure* (e.g. "when a TOTAL row is present"), not specific shipper names or exact label strings.
- After each change, confirm the regression suite still passes — this is the guard against overfitting to the new documents at the expense of old ones.
- If a rule only helps the new documents and hurts the old ones, find a more general phrasing or split the rule into conditions.
