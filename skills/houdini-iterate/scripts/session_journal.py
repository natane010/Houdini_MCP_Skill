"""Explicit project-local JSONL journal; import from ordinary Python or Houdini."""
import json
import os
from pathlib import Path

MAX_RECORD_BYTES = 65536
MAX_READ_BYTES = 8 * 1024 * 1024
REQUIRED = ("run_id", "goal", "context", "before", "changed", "after", "evidence", "decisions", "next_action")


def append_record(path, record):
    if not path or not isinstance(record, dict):
        raise ValueError("explicit journal path and record object are required")
    missing = [key for key in REQUIRED if key not in record]
    if missing or not isinstance(record.get("run_id"), str) or not record["run_id"]:
        raise ValueError("missing required fields or nonempty run_id: " + ", ".join(missing))
    if not isinstance(record["context"], dict):
        raise ValueError("context must be an object")
    encoded = (json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > MAX_RECORD_BYTES:
        raise ValueError("record exceeds 65536 bytes")
    target = Path(path)
    if not target.is_absolute():
        raise ValueError("journal path must be absolute")
    if not target.parent.is_dir():
        raise FileNotFoundError("journal parent directory must already exist")
    if target.exists():
        with target.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell():
                stream.seek(-1, os.SEEK_END)
                if stream.read(1) != b"\n":
                    raise ValueError("incomplete journal line; inspect before appending")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        if os.write(fd, encoded) != len(encoded):
            raise OSError("partial append; inspect journal before continuing")
    finally:
        os.close(fd)


def read_records(path):
    if not path:
        raise ValueError("explicit journal path is required")
    if not Path(path).is_absolute():
        raise ValueError("journal path must be absolute")
    with open(path, "rb") as stream:
        data = stream.read(MAX_READ_BYTES + 1)
    if len(data) > MAX_READ_BYTES:
        raise ValueError("journal exceeds 8 MiB; inspect or rotate it explicitly")
    if data and not data.endswith(b"\n"):
        raise ValueError("incomplete journal line; inspect before continuing")
    records = []
    for line in data.splitlines():
        if len(line) + 1 > MAX_RECORD_BYTES:
            raise ValueError("journal record exceeds 65536 bytes")
        def reject_constant(value):
            raise ValueError("invalid JSON constant: " + value)
        record = json.loads(line.decode("utf-8"), parse_constant=reject_constant)
        if not isinstance(record, dict):
            raise ValueError("journal records must be objects")
        records.append(record)
    return records
