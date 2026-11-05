"""Hython entry point. Files, not stdout, carry the protocol."""
import json
import sys
from dispatcher import batch

with open(sys.argv[1], encoding="utf-8") as stream:
    payload = json.load(stream)
result = batch(payload)
with open(sys.argv[2], "w", encoding="utf-8") as stream:
    json.dump(result, stream, ensure_ascii=False, default=str)
