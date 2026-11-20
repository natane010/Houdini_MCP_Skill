"""Hython entry point. Files, not stdout, carry the protocol."""
import json
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from houdini_mcp.dispatcher import batch

# Render commands may replace sys.argv while processing the request.
request_path, response_path = sys.argv[1:3]
with open(request_path, encoding="utf-8") as stream:
    payload = json.load(stream)
result = batch(payload)
with open(response_path, "w", encoding="utf-8") as stream:
    json.dump(result, stream, ensure_ascii=False, default=str)
