#!/usr/bin/env python3
"""ARM entrypoint for the literature-structured-notes Skill.

Delegates to the layout-aware parser in parse_pdf.py so the bundle exposes the
canonical `src/reproduce.py` entrypoint expected by the ARM manifest. The
structured-note synthesis itself is produced by the agent following SKILL.md;
the deterministic evidence layer and its verification live in parse_pdf.py and
verify_notes.py respectively.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parse_pdf import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
