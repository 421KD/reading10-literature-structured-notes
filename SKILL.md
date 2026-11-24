---
name: literature-structured-notes
description: >-
  Read a research paper and produce an evidence-anchored, structured literature
  note: a uniform paper card, chapter-aligned summaries, and searchable knowledge
  points, with every claim traced to its page/section/figure/table and explicit
  unreported / uncertain / conflicting items. Use when the task asks to summarise,
  structurally note, extract, or answer questions about a research paper with
  source evidence.
---

# Literature Structured Notes（文献总结与结构化笔记）

Turn one real paper into a reusable, verifiable note — **not** a compressed
abstract. The deliverable is a machine-readable structure whose every claim can
be traced back to a specific page, section, paragraph, figure, table or formula
of the original file.

## When to use

Use this Skill when the input is a scientific paper (PDF) and the task asks for
any of: structured summary, chapter summary, paper card, knowledge-point
extraction, question answering with source citations, or "read this paper and
produce a note". Do **not** use it to paraphrase the abstract, to write a
literature review from memory, or to invent content that is not in the paper.

## Input contract

At execution time the original material is under `/input` (typically
`case.json`, `task.md`, and the actual paper PDF). Read these files first:

1. Find the PDF path, the `case_id`, and the `output_contract` (the keys the
   final `result.json` must contain) in `/input/case.json`.
2. Read `/input/task.md` to learn exactly what to return (language, scope, any
   field overrides).
3. **Never** assume the paper's content from its filename or topic labels. Read
   the actual PDF; the PDF parsing step receives the real file with no
   pre-extracted answer layer.

Work under `/app/work`; write final results and editable artifacts under
`/app/output`. Every run must end with `/app/output/result.json`.

## Four principles（对得上 · 留得住 · 找得回 · 用得上）

These four gates are the definition of "done". A note that fails any of them is
a compressed abstract, not a structured note.

1. **对得上 (alignment)** — the note's skeleton must follow the paper's own
   chapter and argument order. Build the section map from the paper's real
   headings; do not impose a generic "Background → Method → Result" template
   onto a paper whose actual order is different.
2. **留得住 (retention)** — record the research question, data, methods, method
   conditions/premises, main findings and limitations. Especially keep the
   **premises that make a conclusion valid** (sample, settings, assumptions,
   metrics, ranges). A conclusion without its condition is misleading.
3. **找得回 (traceability)** — every key note carries an anchor to a real
   location (page / section / paragraph / figure / table / formula). Anchors must
   point to locations that actually exist in the parsed PDF.
4. **用得上 (usability)** — the note is machine-readable, searchable, comparable
   across papers, and reusable for the next reading/writing task. Use a fixed
   field schema and consistent terminology (one term = one definition; handle
   abbreviations and synonyms).

## Workflow

### Step 0 — Inventory
List `/input`; read `case.json` and `task.md`. Record `case_id` and every
`output_contract` key. Locate the PDF. If no PDF path is given, search `/input`
for `*.pdf`.

### Step 1 — Deterministic layout parse
Run the bundled layout parser to get page/bbox/section/table/figure provenance:

```bash
python3 src/parse_pdf.py /input/<paper>.pdf /app/work/parsed
```

This writes `/app/work/parsed/parsed.json` (blocks, sections, tables, figures,
formulas, reading order, uncertainties) and `parsed.md` (readable Markdown with
`[pN]` page markers). Keep these as the evidence layer. If the parser flags pages
with no text layer, run OCR (environment `ocr-tool`, rasterise with
`pdf-render-tool` first) and merge the recognised text back, preserving page
provenance.

### Step 2 — Build the section map（对得上）
From `parsed.json` → `sections` (or the headings visible in `parsed.md`), produce
a `section_map` that reproduces the paper's own hierarchy **in order**. For each
section record: `section_id`, `level`, `title`, `page_start`, `page_end`. This map
is the skeleton of the note; the chapter summaries in Step 4 must be indexed 1:1
against it. Do not rename, merge, or reorder the paper's sections.

### Step 3 — Extract the paper card（留得住）
Fill the uniform paper card. For every field, state the claim **and** its anchor
and confidence (`reported` / `inferred` / `unreported` / `conflict`):

- `research_question` — the problem the paper solves.
- `objectives` — what the paper set out to show.
- `data` — dataset, sample, sources, size, domain.
- `methods` — the approach and key procedures.
- `conditions` — premises/assumptions/settings/metrics/ranges under which the
  conclusions hold (the most often dropped field).
- `main_findings` — results with their numbers and units verbatim.
- `limitations` — stated limits, scope bounds, and caveats.

Rule: a numeric result without its unit or its condition is a transcription
error. Copy numbers and units **verbatim** from the source; never round,
convert, or "correct" them silently.

### Step 4 — Write chapter-aligned summaries（对得上 + 留得住）
For each entry in `section_map`, write a summary with four fields where they
exist in that section — `purpose`, `method`, `results`, `conclusion` — each with
its own anchor. Add `links_to` (section_ids) to record how the argument flows
between sections. Leave a field absent (not empty) when the section does not
contain it; do not invent it. Preserve cross-section causal/concessive relations
("because A, B") and section ordering.

### Step 5 — Extract knowledge points（用得上）
Decompose important concepts, variables, methods, formulas and conclusions into
searchable entries: `{id, type, term, definition, anchor}`. Normalise
terminology: give each concept **one** canonical term and list its abbreviations
and synonyms, so entries do not duplicate or contradict each other. Do not emit
the same fact twice under two names.

### Step 6 — Anchor and verify（找得回）
Every claim-like object must carry a non-empty `anchor`. Use the anchor format in
`resources/FIELD_DICTIONARY.md` (`p{page}`, `s{n}`, `fig{page}_{i}`,
`t{page}_{i}`, `eq{page}_{i}`, optionally `para{n}`). Then run the verifier:

```bash
python3 src/verify_notes.py /app/work/note.json /app/work/parsed/parsed.json /app/work/verify
```

Fix every flagged issue before Step 7: dangling anchors, anchors pointing past
the last page, missing paper-card fields, `section_map` sections with no chapter
summary, and claims with confidence `reported` but no anchor.

### Step 7 — Write outputs
Write `/app/output/result.json` containing:
- every original `output_contract` key from `case.json`, verbatim and populated;
- `case_id`;
- `reading_result` — the structured note (the schema below);
- `evidence_boundary` — `sources`, `uncertainty` (unreported / undeterminable /
  conflicting items, each with a reason), and the `anchors` used;
- `status` — `ok` | `partial` | `unreadable` | `refused`, plus `status_reason`;
- `change_records` — list of edits made during self-check.

Also write a human-readable `/app/output/note.md` (the same note rendered with
inline `[pN]`/`[sN]` markers) and copy `parsed.json`/`parsed.md` into
`/app/output` as the evidence layer.

## Output schema (`reading_result`)

```json
{
  "schema": "literature-structured-note/1",
  "paper": {"title": "", "source": "", "pages": 0, "language": ""},
  "section_map": [
    {"section_id": "s1", "level": 1, "title": "", "page_start": 0, "page_end": 0}
  ],
  "paper_card": {
    "research_question": {"text": "", "anchor": "", "confidence": "reported"},
    "objectives":     [{"text": "", "anchor": "", "confidence": ""}],
    "data":           {"text": "", "anchor": "", "confidence": ""},
    "methods":        [{"text": "", "anchor": "", "confidence": ""}],
    "conditions":     [{"text": "", "anchor": "", "confidence": ""}],
    "main_findings":  [{"text": "", "anchor": "", "confidence": ""}],
    "limitations":    [{"text": "", "anchor": "", "confidence": ""}]
  },
  "chapter_summaries": [
    {
      "section_id": "s1", "title": "",
      "purpose":    {"text": "", "anchor": ""},
      "method":     {"text": "", "anchor": ""},
      "results":    [{"text": "", "anchor": ""}],
      "conclusion": {"text": "", "anchor": ""},
      "links_to": ["s3"]
    }
  ],
  "knowledge_points": [
    {"id": "kp1", "type": "concept", "term": "", "definition": "", "anchor": ""}
  ],
  "terminology": [
    {"canonical": "", "abbreviations": [""], "synonyms": [""]}
  ]
}
```

Confidence levels: `reported` (stated verbatim in the paper), `inferred`
(derived from the paper), `unreported` (not in the paper — must be said so,
never written as fact), `conflict` (the paper contradicts itself). See
`resources/FIELD_DICTIONARY.md` for the full field and anchor dictionary.

## Quality gates — check all before finishing

**对得上**
- [ ] `section_map` reproduces the paper's own headings, in order, 1:1.
- [ ] `chapter_summaries` is indexed exactly against `section_map`; no missing,
      extra, renamed, or reordered sections.
- [ ] Argument order and cross-section links match the paper, not a template.

**留得住**
- [ ] research question, data, methods, conditions, findings, limitations all present.
- [ ] Numbers and units are verbatim; conclusions carry their premises/conditions.
- [ ] Confidence is marked per claim; `unreported` is never stated as fact.

**找得回**
- [ ] Every claim has a non-empty anchor; every anchor points to an existing
      page/section/figure/table (verified by `verify_notes.py`).
- [ ] Section split and extraction steps are reproducible from `parsed.json`.

**用得上**
- [ ] Output is valid JSON with the fixed schema; terminology is normalised.
- [ ] `note.md` is human-readable and mirrors the JSON; both open and are searchable.

## Exception handling

| Situation | Action |
|---|---|
| PDF encrypted / permission-restricted | Record it; stop parsing that file; ask for a password only if the task allows. |
| Page has no text layer | OCR via `ocr-tool`; if OCR unavailable mark the page `unreadable`, never guess. |
| Two-column reading order jumbled | Re-run the parser; check `parsed.json` `uncertainties`; fix column merge manually if needed. |
| Figures / tables / formulas missing or image-only | Keep the reference to the image and mark "image figure/table/formula, manual confirmation needed". |
| Very long paper | Process section by section, save `/app/work/note.json` incrementally, status `partial` if truncated. |
| Non-Chinese / non-English paper | Keep original-language terms verbatim in `knowledge_points.term`; translate per `task.md` only. |
| Budget or time exhausted | Save partial deliverables to `/app/work` and `/app/output`, mark `status: partial`, list remaining gaps. |

## Minimal invocation example

Input (`/input/case.json`, shortened):
```json
{"case_id": "example-1", "output_contract": {"summary": "string", "key_findings": "string"}, "paper": "/input/paper.pdf"}
```

Call (inside the harness the Skill is auto-loaded; this is the agent's flow):
```bash
python3 src/parse_pdf.py /input/paper.pdf /app/work/parsed
# … build note.json per Steps 2–6 …
python3 src/verify_notes.py /app/work/note.json /app/work/parsed/parsed.json /app/work/verify
```

Example `result.json` (illustrative only — not a formal case result):
```json
{
  "case_id": "example-1",
  "summary": "Paper studies … (see reading_result).",
  "key_findings": "…",
  "reading_result": {
    "schema": "literature-structured-note/1",
    "paper": {"title": "Example Paper", "source": "paper.pdf", "pages": 8, "language": "en"},
    "section_map": [{"section_id": "s1", "level": 1, "title": "Introduction", "page_start": 1, "page_end": 2}],
    "paper_card": {"research_question": {"text": "…", "anchor": "p1 s1", "confidence": "reported"}, "data": {}, "methods": [], "conditions": [], "main_findings": [], "limitations": []},
    "chapter_summaries": [{"section_id": "s1", "title": "Introduction", "purpose": {"text": "…", "anchor": "p1"}, "links_to": ["s2"]}],
    "knowledge_points": [{"id": "kp1", "type": "concept", "term": "…", "definition": "…", "anchor": "p1"}],
    "terminology": []
  },
  "evidence_boundary": {"sources": ["paper.pdf"], "uncertainty": [], "anchors": ["p1", "s1"]},
  "status": "ok",
  "status_reason": "",
  "change_records": []
}
```

## Notes

- This Skill records the paper's claims with evidence; it does not judge or
  correct the science.
- Bundled: `src/parse_pdf.py` (layout parser), `src/verify_notes.py` (anchor/field
  verifier), `src/requirements.txt` (PyMuPDF), `resources/FIELD_DICTIONARY.md`.
- The only runtime dependency is PyMuPDF (`pip install pymupdf`); both scripts
  degrade gracefully if it is absent (the verifier still runs field/structure
  checks).
