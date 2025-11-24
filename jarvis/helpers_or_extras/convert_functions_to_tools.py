#!/usr/bin/env python3
import json
from pathlib import Path
import sys

SRC = Path("jarvis_functions.json")
DST = Path("jarvis_tools.json")

if not SRC.exists():
    print(f"Source file not found: {SRC.resolve()}")
    sys.exit(1)

data = json.loads(SRC.read_text(encoding="utf-8"))
if not isinstance(data, list):
    print("Expected a list of function definitions in jarvis_functions.json")
    sys.exit(1)

tools = []
for fn in data:
    # basic validation
    if not isinstance(fn, dict) or "name" not in fn:
        print("Skipping invalid function entry:", fn)
        continue
    tools.append({
        "type": "function",
        "function": fn
    })

DST.write_text(json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {len(tools)} tools to {DST.resolve()}")
