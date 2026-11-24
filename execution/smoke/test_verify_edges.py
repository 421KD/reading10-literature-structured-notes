import json, sys
sys.path.insert(0, r"C:\Users\碳酸铜\Desktop\bh\reading10-submission\src")
import verify_notes as v

note = {
    "reading_result": {
        "section_map": [{"section_id": "s1"}],
        "chapter_summaries": [{"section_id": "s1"}],
        "paper_card": {
            "research_question": {"text": "RQ", "anchor": "p99", "confidence": "reported"},
            "data": {"text": "D", "anchor": "", "confidence": "reported"},
            "methods": [{"text": "M", "anchor": "p1", "confidence": "reported"}],
            "conditions": [{"text": "C", "anchor": "fig99_0", "confidence": "reported"}],
            "main_findings": [{"text": "F", "anchor": "p2", "confidence": "reported"}],
            "limitations": [{"text": "L", "anchor": "p1", "confidence": "inferred"}],
        },
        "knowledge_points": [],
    }
}
parsed = {
    "meta": {"pages": 5},
    "figures": [{"figure_id": "fig1_0"}],
    "tables": [],
    "formulas": [],
    "sections": [{"section_id": "s1"}],
}
report = v.verify(note, parsed)
print(json.dumps(report, ensure_ascii=False, indent=2))
