#!/usr/bin/env python3
import sys, re
from pathlib import Path

trip = Path("/tmp/ir_triplet.txt")
state = Path("/tmp/line_state.txt")
pat = re.compile(r"\bL=(\d)\s+M=(\d)\s+R=(\d)\b")

def write_cache(L,M,R):
    trip.write_text(f"{L} {M} {R}")
    # Build a compact state like LMR / LM / R / NONE
    s = "".join(c for c,v in zip("LMR",(L,M,R)) if v=="1") or "NONE"
    state.write_text(s)

for line in sys.stdin:
    m = pat.search(line)
    if m:
        L,M,R = m.groups()
        write_cache(L,M,R)
