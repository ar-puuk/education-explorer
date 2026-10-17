"""Dev tool: extract categorical value labels from a PSS public-use codebook PDF into
nces_pipeline/schemas/pss/value_labels.yml.   uv run --with pypdf python scripts/pss_value_labels.py <codebook.pdf>

Codebook blocks look like:
    Variable / NAME / Label / <text> / ... / Category Label Frequency Percent ... / <code> <label> <n> <pct> <wn> <wpct>
"""
import re
import sys
from pathlib import Path

import yaml
from pypdf import PdfReader

pdf = Path(sys.argv[1])
text = "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
lines = [ln.strip() for ln in text.splitlines()]
row = re.compile(r"^(-?\d+)\s+(.+?)\s+[\d,]+\s+[\d.]+\s+[\d,]+(?:\.\d+)?\s+[\d.]+$")
out: dict[str, dict[str, str]] = {}
i = 0
while i < len(lines):
    if lines[i] == "Variable" and i + 1 < len(lines):
        name = lines[i + 1].strip()
        j = i + 2
        codes: dict[str, str] = {}
        while j < len(lines) and lines[j] != "Variable":
            m = row.match(lines[j])
            if m:
                codes[m.group(1)] = m.group(2).strip()
            j += 1
        if 1 < len(codes) <= 80 and re.fullmatch(r"[A-Za-z0-9_]+", name):
            out[name.upper()] = codes
        i = j
    else:
        i += 1
dest = Path(__file__).resolve().parents[1] / "nces_pipeline" / "schemas" / "pss" / "value_labels.yml"
doc = {"source": f"codebook {pdf.name}; applies to the same variable names in other survey years, where code definitions may differ",
       "values": out}
dest.write_text(yaml.safe_dump(doc, sort_keys=True, width=140, allow_unicode=True), encoding="utf-8", newline="\n")
print(len(out), "variables with value labels ->", dest)
