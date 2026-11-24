#!/usr/bin/env python3
"""Verify a structured literature note against the parsed PDF evidence layer.

Companion script for the literature-structured-notes Skill.

Checks the four gates mechanically where possible:
  - 留得住 (retention): paper-card fields present and non-empty;
  - 对得上 (alignment): chapter_summaries indexed 1:1 against section_map;
  - 找得回 (traceability): every claim has an anchor, and every anchor points to
    a page/section/figure/table/formula that actually exists in parsed.json;
  - 用得上 (usability): knowledge-point ids unique; JSON parses.

Usage:
  python3 src/verify_notes.py NOTE_JSON PARSED_JSON OUTDIR

Writes OUTDIR/verification.json and OUTDIR/verification.md. Exit code 0 means no
blocking issues; non-zero means blocking issues remain (still writes outputs).
"""

import argparse
import json
import os
import re
import sys

REQUIRED_CARD_FIELDS = [
    "research_question",
    "data",
    "methods",
    "conditions",
    "main_findings",
    "limitations",
]

PAGE_RE = re.compile(r"\bp(\d+)\b")
SEC_RE = re.compile(r"\bs(\d+)\b")
FIG_RE = re.compile(r"\bfig(\d+)_(\d+)\b")
TBL_RE = re.compile(r"\bt(\d+)_(\d+)\b")
EQ_RE = re.compile(r"\beq(\d+)_(\d+)\b")


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _collect_claims(obj, acc):
    if isinstance(obj, dict):
        content = obj.get("text") or obj.get("definition")
        if isinstance(content, str) and content.strip():
            acc.append(obj)
        for v in obj.values():
            _collect_claims(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_claims(v, acc)
    return acc


def _content(c):
    return (c.get("text") or c.get("definition") or "")


def _parse_anchor(anchor):
    return {
        "pages": [int(m) for m in PAGE_RE.findall(anchor)],
        "sections": [int(m) for m in SEC_RE.findall(anchor)],
        "figures": [f"fig_{a}_{b}" for a, b in FIG_RE.findall(anchor)],
        "tables": [f"t{a}_{b}" for a, b in TBL_RE.findall(anchor)],
        "formulas": [f"eq{a}_{b}" for a, b in EQ_RE.findall(anchor)],
    }


def verify(note, parsed):
    issues = []
    warnings = []

    pages = (parsed.get("meta") or {}).get("pages", 0)
    fig_ids = {f.get("figure_id") for f in parsed.get("figures", [])}
    tbl_ids = {t.get("table_id") for t in parsed.get("tables", [])}
    eq_ids = {f.get("formula_id") for f in parsed.get("formulas", [])}
    sec_ids_parsed = {s.get("section_id") for s in parsed.get("sections", [])}

    reading = note.get("reading_result") or note

    # --- 用得上: structure parses and ids unique
    kps = reading.get("knowledge_points", [])
    kp_ids = [k.get("id") for k in kps if isinstance(k, dict)]
    dup = sorted({i for i in kp_ids if kp_ids.count(i) > 1})
    if dup:
        issues.append(f"duplicate knowledge_point ids: {dup}")

    # --- 对得上: section_map vs chapter_summaries 1:1
    smap = reading.get("section_map", [])
    summaries = reading.get("chapter_summaries", [])
    smap_ids = [s.get("section_id") for s in smap if isinstance(s, dict)]
    sum_ids = [c.get("section_id") for c in summaries if isinstance(c, dict)]
    missing_sum = [i for i in smap_ids if i not in sum_ids]
    extra_sum = [i for i in sum_ids if i not in smap_ids]
    if smap and not summaries:
        issues.append("section_map present but chapter_summaries empty")
    if missing_sum:
        issues.append(f"sections without a chapter summary: {missing_sum}")
    if extra_sum:
        issues.append(f"chapter summaries not in section_map: {extra_sum}")

    # --- 留得住: required paper-card fields present and non-empty
    card = reading.get("paper_card", {})
    for field in REQUIRED_CARD_FIELDS:
        if field not in card:
            issues.append(f"paper_card missing field: {field}")
            continue
        v = card[field]
        has_text = False
        if isinstance(v, dict):
            has_text = bool(str(v.get("text", "")).strip())
        elif isinstance(v, list):
            has_text = any(isinstance(x, dict) and str(x.get("text", "")).strip() for x in v)
        else:
            has_text = bool(str(v).strip())
        if not has_text:
            issues.append(f"paper_card field empty: {field}")

    # --- 找得回: every claim has an anchor that resolves
    claims = _collect_claims(reading, [])
    no_anchor = 0
    dangling = []
    for i, c in enumerate(claims):
        anchor = str(c.get("anchor", "") or "").strip()
        conf = str(c.get("confidence", "") or "").strip()
        if not anchor:
            no_anchor += 1
            if conf == "reported":
                issues.append(f"claim #{i} has confidence 'reported' but no anchor: {_content(c)[:60]!r}")
            else:
                warnings.append(f"claim #{i} has no anchor: {_content(c)[:60]!r}")
            continue
        loc = _parse_anchor(anchor)
        if not any(loc.values()):
            issues.append(f"claim #{i} anchor has no recognised locator: {anchor!r}")
            continue
        for p in loc["pages"]:
            if pages and (p < 1 or p > pages):
                dangling.append(f"claim #{i}: page {p} out of range (1..{pages})")
        for s in loc["sections"]:
            total_sec = len(smap_ids) or len(sec_ids_parsed)
            if total_sec and (s < 1 or s > total_sec):
                dangling.append(f"claim #{i}: section s{s} out of range (1..{total_sec})")
        for fg in loc["figures"]:
            if fig_ids and fg not in fig_ids:
                dangling.append(f"claim #{i}: figure {fg} not found")
        for tb in loc["tables"]:
            if tbl_ids and tb not in tbl_ids:
                dangling.append(f"claim #{i}: table {tb} not found")
        for eq in loc["formulas"]:
            if eq_ids and eq not in eq_ids:
                dangling.append(f"claim #{i}: formula {eq} not found")
    if no_anchor:
        issues.append(f"{no_anchor} claim(s) without an anchor")
    issues.extend(dangling)

    return {
        "status": "fail" if issues else "pass",
        "counts": {
            "claims": len(claims),
            "sections": len(smap_ids),
            "chapter_summaries": len(sum_ids),
            "knowledge_points": len(kps),
            "claims_without_anchor": no_anchor,
            "dangling_anchors": len(dangling),
        },
        "issues": issues,
        "warnings": warnings,
    }


def _write(outdir, report):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "verification.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    lines = [f"# Verification: {report['status'].upper()}", ""]
    lines.append("| check | value |")
    lines.append("|---|---|")
    for k, v in report["counts"].items():
        lines.append(f"| {k} | {v} |")
    if report["issues"]:
        lines.append("")
        lines.append("## Blocking issues")
        for x in report["issues"]:
            lines.append(f"- {x}")
    if report["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        for x in report["warnings"]:
            lines.append(f"- {x}")
    if not report["issues"]:
        lines.append("")
        lines.append("All checks passed.")
    with open(os.path.join(outdir, "verification.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify a structured note against parsed.pdf")
    ap.add_argument("note_json", help="structured note JSON")
    ap.add_argument("parsed_json", help="parsed.json from parse_pdf.py")
    ap.add_argument("outdir", help="output directory")
    args = ap.parse_args(argv)

    if not os.path.exists(args.note_json):
        print(f"ERROR: note not found: {args.note_json}", file=sys.stderr)
        return 2
    if not os.path.exists(args.parsed_json):
        print(f"ERROR: parsed not found: {args.parsed_json}", file=sys.stderr)
        return 2

    try:
        note = _load(args.note_json)
    except Exception as e:
        print(f"ERROR: note JSON invalid: {e}", file=sys.stderr)
        return 2
    try:
        parsed = _load(args.parsed_json)
    except Exception as e:
        print(f"ERROR: parsed JSON invalid: {e}", file=sys.stderr)
        return 2

    report = verify(note, parsed)
    _write(args.outdir, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
