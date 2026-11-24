# Field Dictionary & Anchor Format

Companion to `SKILL.md`. Defines the exact meaning of every field in the
`reading_result` schema and the anchor format used for evidence tracing.

## Anchor format

An anchor is a short, comma-separated string of locators. Each locator points to
one place in the parsed PDF (`parsed.json`). Order is free; separators are
comma or space. Valid locators:

| Locator | Meaning | Example |
|---|---|---|
| `p{page}` | 1-based page number in the PDF | `p3` |
| `s{n}` | n-th entry in `section_map` (1-based) | `s2` |
| `fig{page}_{i}` | figure id from `parsed.json` → `figures[].figure_id` | `fig3_0` |
| `t{page}_{i}` | table id from `parsed.json` → `tables[].table_id` | `t4_0` |
| `eq{page}_{i}` | formula id from `parsed.json` → `formulas[].formula_id` | `eq2_1` |
| `para{n}` | paragraph ordinal within the page (optional) | `para2` |

Examples: `"p3"`, `"s2 p3"`, `"fig3_0 p3"`, `"t4_0 p4 para1"`.

`verify_notes.py` checks that every `p{page}` is within the PDF's page range and
that every `fig*` / `t*` / `eq*` id exists in `parsed.json`. A dangling anchor
fails verification.

## Confidence levels

| Level | Meaning |
|---|---|
| `reported` | Stated verbatim in the paper. |
| `inferred` | Derived from the paper, but not stated in these words. |
| `unreported` | Not in the paper. Must be marked as such; never written as fact. |
| `conflict` | The paper contradicts itself at different places. |

## `paper_card` fields

| Field | Type | Content |
|---|---|---|
| `research_question` | claim | The problem the paper solves. |
| `objectives` | claim[] | What the paper set out to show. |
| `data` | claim | Dataset, sample, sources, size, domain, acquisition. |
| `methods` | claim[] | Approach and key procedures, in the paper's order. |
| `conditions` | claim[] | Premises/assumptions/settings/metrics/ranges under which conclusions hold. |
| `main_findings` | claim[] | Results with numbers and units verbatim. |
| `limitations` | claim[] | Stated limits, scope bounds, caveats. |

A **claim** is `{"text": string, "anchor": string, "confidence": level}`.
`text` must be a complete sentence; it must not rely on surrounding prose to be
understood. Numbers and units are copied verbatim.

## `section_map` fields

| Field | Meaning |
|---|---|
| `section_id` | Stable id `s1..sN`, in the paper's own order. |
| `level` | Heading depth (1 = top-level section). |
| `title` | The paper's own heading text. |
| `page_start` / `page_end` | First/last page where the section appears. |

`chapter_summaries` is indexed 1:1 against `section_map` via `section_id`.

## `chapter_summaries` fields

| Field | Content |
|---|---|
| `purpose` | What this section sets out to do. |
| `method` | What this section does / how. |
| `results` | claim[] — what this section finds or shows. |
| `conclusion` | What this section concludes. |
| `links_to` | section_ids this section's argument depends on or feeds into. |

Leave a field absent (not empty) when the section does not contain it.

## `knowledge_points` fields

| Field | Meaning |
|---|---|
| `id` | Unique `kp1..kpN`. |
| `type` | `concept` \| `variable` \| `method` \| `formula` \| `conclusion`. |
| `term` | Canonical term (original-language if the paper is not Chinese). |
| `definition` | One-sentence definition; include the defining condition if any. |
| `anchor` | Where the term is defined or first used. |

## `terminology` fields

| Field | Meaning |
|---|---|
| `canonical` | One canonical term per concept. |
| `abbreviations` | Abbreviations that map to the canonical term. |
| `synonyms` | Alternative phrasings used in the paper. |

Rule: one concept = one canonical term. Two knowledge points that mean the same
thing must be merged; two terms that look alike but mean different things must
not be merged.
