# literature-structured-notes

A Skill + companion scripts that turn one research paper into an
evidence-anchored, structured literature note (文献总结与结构化笔记).

## What it does

1. Deterministically parses the PDF into page/bbox/section/table/figure/formula
   provenance (`parse_pdf.py`).
2. Guides the agent to build a paper structure map, a uniform paper card,
   chapter-aligned summaries, and searchable knowledge points.
3. Verifies the note mechanically (`verify_notes.py`) against the parsed evidence
   layer: required fields present, chapter summaries 1:1 with sections, every
   claim anchored, and every anchor pointing to a real page/section/figure/table.

The note is structured around four gates:

- **对得上** — the note skeleton follows the paper's own chapter and argument order.
- **留得住** — research question, data, methods, conditions/premises, findings and
  limitations are all recorded.
- **找得回** — every claim carries an anchor back to page/section/figure/table.
- **用得上** — fixed JSON schema, normalised terminology, searchable/reusable.

## Files

| Path | Purpose |
|---|---|
| `SKILL.md` | Skill definition (name/description frontmatter + workflow + schema + gates) |
| `resources/FIELD_DICTIONARY.md` | Field dictionary and anchor format |
| `src/parse_pdf.py` | Layout-aware PDF parser (PyMuPDF) |
| `src/verify_notes.py` | Note verifier (fields, alignment, anchors) |
| `src/requirements.txt` | Runtime dependency (PyMuPDF) |
| `README.md` | This document |

## Install and run

```bash
pip install -r src/requirements.txt

# 1) deterministic evidence layer
python3 src/parse_pdf.py /input/paper.pdf /app/work/parsed

# 2) build note.json following SKILL.md Steps 2–6 (this is the agent's job)

# 3) verify anchors and fields
python3 src/verify_notes.py /app/work/note.json /app/work/parsed/parsed.json /app/work/verify
```

If PyMuPDF is not available, `parse_pdf.py` falls back to a pure-text extraction
that still keeps page provenance but has coarser layout information;
`verify_notes.py` runs its structure and field checks independently of the
parser.

## Inputs and outputs

Input: `/input/case.json` (case_id + output_contract + paper path) and
`/input/task.md`, plus the actual paper PDF.

Outputs (final, under `/app/output`):

- `result.json` — output_contract fields + case_id + `reading_result` +
  `evidence_boundary` + `status` + `change_records`.
- `note.md` — human-readable rendering of `reading_result` with `[pN]`/`[sN]` markers.
- `parsed.json` / `parsed.md` — evidence layer copied from the parser.

Intermediate artifacts live under `/app/work` (`parsed/`, `note.json`, `verify/`).

## Anchor format

`p{page}` · `s{n}` · `fig{page}_{i}` · `t{page}_{i}` · `eq{page}_{i}` ·
optional `para{n}`, comma/space separated. Full definitions in
`resources/FIELD_DICTIONARY.md`.

## Example

```bash
python3 src/parse_pdf.py paper.pdf out
# … produce note.json …
python3 src/verify_notes.py note.json out/parsed.json verify
cat verify/verification.md
```

See `SKILL.md` → "Minimal invocation example" for a full illustrative input/output.

## Limitations

- Column detection targets the common one/two-column layout; exotic layouts may
  need manual review.
- Table extraction depends on ruled lines or PyMuPDF's detector; borderless
  tables are best-effort.
- Formula handling preserves the text layer and flags math-looking spans; it does
  not reconstruct LaTeX from images.
- Scanned PDFs (no text layer) are flagged for OCR, which the caller supplies via
  the environment's OCR tool.
- The note itself (paper card, chapter summaries, knowledge points) is produced
  by the agent following `SKILL.md`, then checked by `verify_notes.py`; the
  verifier catches structural and anchor errors, not semantic accuracy, so the
  agent must still read the actual paper.

## Self-check

After a run, confirm: `section_map` matches the paper's headings 1:1;
`chapter_summaries` covers every section; every claim has an anchor that resolves;
numbers/units are verbatim; confidence is marked per claim; `result.json`
contains every `output_contract` key and `case_id`; and `note.md` mirrors the JSON.
