import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).parents[1] / "skills/houdini-iterate/scripts/session_journal.py"
spec = importlib.util.spec_from_file_location("session_journal", path)
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


def record():
    return {"run_id": "r1", "goal": "調整", "context": {"version": "22"}, "before": {}, "changed": {}, "after": {}, "evidence": {}, "decisions": [], "next_action": "inspect"}


def test_append_and_read_preserves_order_and_unicode(tmp_path):
    target = tmp_path / "journal.jsonl"
    journal.append_record(target, record())
    second = record(); second["run_id"] = "r2"
    journal.append_record(target, second)
    assert journal.read_records(target) == [record(), second]


def test_rejects_bad_or_oversize_input_without_creating_file(tmp_path):
    target = tmp_path / "journal.jsonl"
    with pytest.raises(ValueError): journal.append_record(target, {"run_id": "r"})
    big = record(); big["goal"] = "x" * 70000
    with pytest.raises(ValueError): journal.append_record(target, big)
    assert not target.exists()
    with pytest.raises(FileNotFoundError): journal.append_record(tmp_path / "missing" / "a", record())


def test_incomplete_or_malformed_journal_rejected(tmp_path):
    target = tmp_path / "journal.jsonl"
    target.write_bytes(b'{"incomplete":')
    with pytest.raises(ValueError): journal.read_records(target)
    before = target.read_bytes()
    with pytest.raises(ValueError): journal.append_record(target, record())
    assert target.read_bytes() == before
    target.write_bytes(b'not-json\n')
    with pytest.raises(ValueError): journal.read_records(target)
    target.write_bytes(b'{"value":NaN}\n')
    with pytest.raises(ValueError): journal.read_records(target)


def test_relative_journal_paths_are_rejected():
    with pytest.raises(ValueError): journal.append_record("journal.jsonl", record())
    with pytest.raises(ValueError): journal.read_records("journal.jsonl")
