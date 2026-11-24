#!/usr/bin/env python3
"""Layout-aware parser for scientific PDFs.

Companion script for the literature-structured-notes Skill.

Produces, inside OUTDIR:
  parsed.json   structured blocks, sections, tables, figures, formulas,
                reading order and uncertainties (with page/bbox provenance)
  parsed.md     human-readable Markdown with [pN] page markers
  result.json   summary skeleton to be completed by the calling agent

Preferred engine: PyMuPDF. Falls back to a pure-text extraction that keeps page
provenance but has no column-aware reordering or table parsing.
"""

import argparse
import json
import os
import re
import sys

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24
    HAS_FITZ = True
except Exception:
    try:
        import fitz  # legacy import name
        HAS_FITZ = True
    except Exception:
        fitz = None
        HAS_FITZ = False

FITZ_VERSION = getattr(fitz, "__version__", "") if HAS_FITZ else ""

MATH_CHARS = set(
    "∑∫∏√∂∇∞±≤≥≠≈×·∈∉⊂⊆∀∃→⇒⇔"
    "αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ"
)

HEADING_RE = re.compile(
    r"^\s*("
    r"\d+(?:\.\d+)*[\.\)]?\s*[A-Z\u0391-\u03a9]"
    r"|\d+(?:\.\d+)*[\.\)]?\s+\S"
    r"|(?:abstract|introduction|conclusion[s]?|references?|bibliography|"
    r"acknowledg?e?ments?|appendix|method[s]?|results?|discussion|"
    r"experiments?|related\s+work|background|summary|future\s+work|"
    r"supplementary|materials?\s+and\s+methods?)\b"
    r")",
    re.IGNORECASE,
)

CAPTION_RE = re.compile(r"^\s*(fig(?:ure)?\.?\s*\d+|table\.?\s*\d+)", re.IGNORECASE)


def _span_text(spans):
    return "".join(s.get("text", "") for s in spans)


def _block_text(block):
    return _span_text([s for line in block.get("lines", []) for s in line.get("spans", [])])


def _is_mathy(text):
    n = sum(1 for c in text if c in MATH_CHARS)
    if n >= 1:
        return True
    return re.search(r"[A-Za-z]\s*[_\^]\s*[A-Za-z0-9]", text) is not None


def _classify_block(block, page_w, page_h, body_size):
    bbox = block.get("bbox", (0, 0, 0, 0))
    x0, y0, x1, y1 = bbox
    text = (block.get("text") or "").strip()
    if not text:
        return "empty"
    max_size = block.get("max_size") or 0
    bold = bool(block.get("bold"))

    if _is_mathy(text) and (x0 > 0.25 * page_w and x1 < 0.75 * page_w):
        return "equation"
    if len(text) <= 140 and (
        HEADING_RE.match(text)
        or max_size >= body_size + 1.5
        or (bold and max_size >= body_size + 1.0)
    ):
        return "heading"
    if y1 < 0.12 * page_h or y0 > 0.92 * page_h:
        return "header_footer"
    return "paragraph"


def _cluster_columns(xs, tolerance=18):
    if not xs:
        return []
    xs = sorted(xs)
    clusters = [[xs[0]]]
    for x in xs[1:]:
        if x - clusters[-1][-1] <= tolerance:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [sum(c) / len(c) for c in clusters]


def _extract_page_blocks(page, page_idx):
    d = page.get_text("dict")
    pw = d.get("width", 0) or 0
    ph = d.get("height", 0) or 0
    blocks = []
    images = []
    for b in d.get("blocks", []):
        if b.get("type") == 0:
            text = _block_text(b).strip()
            if text:
                spans = [s for ln in b.get("lines", []) for s in ln.get("spans", [])]
                blocks.append(
                    {
                        "page": page_idx,
                        "bbox": [round(v, 2) for v in b.get("bbox", (0, 0, 0, 0))],
                        "text": text,
                        "max_size": max((s.get("size", 0) for s in spans), default=0),
                        "bold": any(s.get("flags", 0) & 16 for s in spans),
                    }
                )
        elif b.get("type") == 1:
            images.append(
                {"page": page_idx, "bbox": [round(v, 2) for v in b.get("bbox", (0, 0, 0, 0))]}
            )
    return pw, ph, blocks, images


def _extract_tables(page, page_idx):
    tables = []
    try:
        finder = page.find_tables()
        for t in finder.tables:
            try:
                md = t.to_markdown()
            except Exception:
                rows = t.extract()
                md = "\n".join(
                    "| " + " | ".join("" if c is None else str(c) for c in r) + " |"
                    for r in rows
                )
            tables.append(
                {
                    "table_id": f"t{page_idx}_{len(tables)}",
                    "page": page_idx,
                    "bbox": [round(v, 2) for v in t.bbox],
                    "rows": t.row_count,
                    "cols": t.col_count,
                    "markdown": md,
                }
            )
    except Exception:
        pass
    return tables


def _assign_reading_order(blocks, page_w):
    if not blocks:
        return blocks
    if page_w <= 0:
        return sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))

    col_xs = _cluster_columns([b["bbox"][0] for b in blocks])
    left_center = right_center = None
    if len(col_xs) >= 2:
        left_center, right_center = min(col_xs), max(col_xs)
        if right_center - left_center < 0.20 * page_w:
            right_center = None

    spanning, left, right = [], [], []
    for b in blocks:
        w = b["bbox"][2] - b["bbox"][0]
        if w >= 0.60 * page_w:
            spanning.append(b)
        elif right_center is not None and abs(b["bbox"][0] - right_center) <= abs(b["bbox"][0] - left_center):
            right.append(b)
        else:
            left.append(b)

    if right_center is None:
        return sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))

    first_col_y = min((b["bbox"][1] for b in left + right), default=0)
    top = [b for b in spanning if b["bbox"][1] <= first_col_y]
    bottom = [b for b in spanning if b["bbox"][1] > first_col_y]
    top.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    bottom.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    left.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    right.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    return top + left + right + bottom


def _build_sections(blocks_in_order):
    sections = []
    current = []
    counter = {"n": 0}
    for b in blocks_in_order:
        if b.get("type") == "heading":
            title = b["text"]
            level = 1
            m = re.match(r"^(\d+(?:\.\d+)*)", title)
            if m:
                level = min(m.group(1).count(".") + 1, 5)
            sec_id = f"s{counter['n']}"
            counter["n"] += 1
            while current and current[-1][1] >= level:
                current.pop()
            sections.append(
                {
                    "section_id": sec_id,
                    "level": level,
                    "title": title,
                    "page": b["page"],
                    "heading_block_id": b.get("block_id"),
                }
            )
            current.append((sec_id, level, title))
        b["section"] = current[-1][0] if current else None
    return sections


def _extract_figures(blocks, images):
    figs = []
    for img in images:
        ix0, iy0, ix1, iy1 = img["bbox"]
        caption = None
        best = None
        for b in blocks:
            bx0, by0, bx1, by1 = b["bbox"]
            if by0 >= iy1 and abs(bx0 - ix0) < 40 and CAPTION_RE.match(b["text"]):
                if best is None or by0 < best["bbox"][1]:
                    best = b
        if best is not None:
            caption = best["text"]
        figs.append(
            {
                "figure_id": f"fig_{img['page']}_{len(figs)}",
                "page": img["page"],
                "bbox": img["bbox"],
                "caption": caption,
            }
        )
    return figs


def _median(values):
    if not values:
        return 0
    values = sorted(values)
    return values[len(values) // 2]


def parse_with_fitz(path, outdir):
    doc = fitz.open(path)
    all_blocks, all_tables, all_images, all_uncertainties = [], [], [], []
    body_sizes = []
    per_page = []

    for idx in range(doc.page_count):
        page = doc[idx]
        pw, ph, blocks, images = _extract_page_blocks(page, idx + 1)
        body_sizes.extend([b["max_size"] for b in blocks if b["max_size"] > 0])
        tables = _extract_tables(page, idx + 1)
        char_count = sum(len(b["text"]) for b in blocks)
        if char_count == 0:
            all_uncertainties.append(f"page {idx + 1}: no text layer detected; OCR required")
        ordered = _assign_reading_order(blocks, pw)
        for i, b in enumerate(ordered):
            b["block_id"] = f"b{idx + 1}_{i}"
            b["type"] = _classify_block(b, pw, ph, _median(body_sizes) if body_sizes else 10)
            b["reading_index"] = len(all_blocks)
            all_blocks.append(b)
        all_tables.extend(tables)
        all_images.extend(images)
        per_page.append(
            {
                "page": idx + 1,
                "width": pw,
                "height": ph,
                "text_chars": char_count,
                "blocks": [b["block_id"] for b in ordered],
                "tables": [t["table_id"] for t in tables],
            }
        )

    sections = _build_sections(all_blocks)
    figures = _extract_figures(all_blocks, all_images)

    parsed = {
        "schema": "literature-pdf-parser/1",
        "meta": {"source": os.path.basename(path), "pages": doc.page_count, "parser": "pymupdf", "parser_version": FITZ_VERSION},
        "sections": sections,
        "blocks": all_blocks,
        "tables": all_tables,
        "figures": figures,
        "formulas": [
            {"formula_id": f"eq{b['page']}_{i}", "page": b["page"], "bbox": b["bbox"], "text": b["text"]}
            for i, b in enumerate(all_blocks)
            if b.get("type") == "equation"
        ],
        "reading_order": [b["block_id"] for b in all_blocks],
        "uncertainties": all_uncertainties,
    }
    _write_outputs(parsed, outdir)
    return parsed


def parse_text_fallback(path, outdir):
    pages, blocks, uncertainties = [], [], []
    if HAS_FITZ:
        doc = fitz.open(path)
        for idx in range(doc.page_count):
            txt = doc[idx].get_text("text")
            pages.append({"page": idx + 1, "text": txt})
            if not txt.strip():
                uncertainties.append(f"page {idx + 1}: no text layer; OCR required")
            blocks.append(
                {
                    "block_id": f"b{idx + 1}_0",
                    "page": idx + 1,
                    "bbox": [0, 0, doc[idx].rect.width, doc[idx].rect.height],
                    "text": txt,
                    "type": "paragraph",
                    "reading_index": idx,
                }
            )
    else:
        raw = open(path, "rb").read()
        txt = re.sub(rb"[^\x09\x0a\x0d\x20-\x7e]", b" ", raw).decode("ascii", "ignore")
        pages = [{"page": 1, "text": txt}]
        blocks = [{"block_id": "b1_0", "page": 1, "bbox": [0, 0, 0, 0], "text": txt, "type": "paragraph", "reading_index": 0}]
        uncertainties.append("no PDF text library available; raw byte fallback used")

    parsed = {
        "schema": "literature-pdf-parser/1",
        "meta": {"source": os.path.basename(path), "pages": len(pages), "parser": "text-fallback", "parser_version": ""},
        "sections": [],
        "blocks": blocks,
        "tables": [],
        "figures": [],
        "formulas": [],
        "reading_order": [b["block_id"] for b in blocks],
        "uncertainties": uncertainties,
    }
    _write_outputs(parsed, outdir)
    return parsed


def _write_outputs(parsed, outdir):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "parsed.json"), "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, "parsed.md"), "w", encoding="utf-8") as f:
        f.write(_render_markdown(parsed))
    result = {
        "status": "ok" if not parsed["uncertainties"] else "partial",
        "case_id": None,
        "sources": [parsed["meta"]["source"]],
        "uncertainty": parsed["uncertainties"],
        "change_records": [],
    }
    with open(os.path.join(outdir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def _render_markdown(parsed):
    lines = [f"# Parsed: {parsed['meta']['source']}", "", f"_pages: {parsed['meta']['pages']}, parser: {parsed['meta']['parser']}_", ""]
    by_page = {}
    for b in parsed["blocks"]:
        by_page.setdefault(b["page"], []).append(b)
    for pg in sorted(by_page):
        lines.append(f"## Page {pg}")
        lines.append("")
        for b in by_page[pg]:
            marker = f"[p{pg}]"
            if b["type"] == "heading":
                lines.append(f"### {b['text']}  {marker}")
            elif b["type"] == "equation":
                lines.append(f"```math\n{b['text']}\n```  {marker}")
            elif b["type"] == "header_footer":
                continue
            else:
                lines.append(f"{b['text']}  {marker}")
            lines.append("")
    if parsed["tables"]:
        lines.append("## Tables")
        for t in parsed["tables"]:
            lines.append(f"### Table p{t['page']} ({t['rows']}x{t['cols']})")
            lines.append(t["markdown"])
            lines.append("")
    if parsed["figures"]:
        lines.append("## Figures")
        for fg in parsed["figures"]:
            lines.append(f"- p{fg['page']} bbox={fg['bbox']}: {fg['caption'] or '(no caption)'}")
    if parsed["uncertainties"]:
        lines.append("")
        lines.append("## Uncertainties")
        for u in parsed["uncertainties"]:
            lines.append(f"- {u}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Layout-aware scientific PDF parser")
    ap.add_argument("pdf", help="input PDF path")
    ap.add_argument("outdir", help="output directory")
    ap.add_argument("--force-text", action="store_true", help="force pure-text fallback")
    args = ap.parse_args(argv)

    if not os.path.exists(args.pdf):
        print(f"ERROR: input not found: {args.pdf}", file=sys.stderr)
        return 2

    parsed = parse_with_fitz(args.pdf, args.outdir) if (HAS_FITZ and not args.force_text) else parse_text_fallback(args.pdf, args.outdir)

    print(
        json.dumps(
            {
                "pages": parsed["meta"]["pages"],
                "blocks": len(parsed["blocks"]),
                "sections": len(parsed["sections"]),
                "tables": len(parsed["tables"]),
                "figures": len(parsed["figures"]),
                "formulas": len(parsed["formulas"]),
                "uncertainties": len(parsed["uncertainties"]),
                "outdir": args.outdir,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
