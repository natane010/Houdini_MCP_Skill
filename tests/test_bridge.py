import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from houdini_mcp.bridge import Bridge

HYTHON = os.environ.get("HOUDINI_MCP_TEST_HYTHON", r"C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe")


def test_python_is_opt_in():
    result = Bridge("batch").call("execute_python", {"code": "pass"})
    assert result["error"]["type"] == "PermissionError"


def test_no_implicit_reconnect():
    result = Bridge("gui").call("node_delete", {"path": "/obj/a"})
    assert result["error"]["type"] == "ConnectionError"


def test_missing_hython():
    assert Bridge("batch", "missing").reconnect()["error"]["type"] == "ConfigurationError"


def test_gui_failed_reconnect_closes_connection(monkeypatch):
    import rpyc
    def fail(*a, **k):
        raise ConnectionRefusedError("no server")
    monkeypatch.setattr(rpyc.classic, "connect", fail)
    bridge = Bridge("gui", timeout=1)
    assert not bridge.reconnect()["ok"]
    assert bridge.connection is None


def test_gui_reconnect_configures_timeout(monkeypatch):
    import rpyc
    class FakeConnection:
        def __init__(self):
            self._config = {}
            self.executed = []
        def execute(self, code):
            self.executed.append(code)
        def close(self):
            pass
    connection = FakeConnection()
    monkeypatch.setattr(rpyc.classic, "connect", lambda host, port: connection)
    bridge = Bridge("gui", timeout=7)
    assert bridge.reconnect()["ok"]
    assert connection._config["sync_request_timeout"] == 7
    assert "hdefereval" in connection.executed[0]


def test_stdio_protocol():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "houdini_mcp.server", "--backend", "batch"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert {"node_create", "node_types", "execute_python", "connection_status"} <= names
                result = await session.call_tool("connection_status", {})
                assert json.loads(result.content[0].text)["error"]["type"] == "ConfigurationError"
    asyncio.run(run())


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason="Houdini hython is not installed")
def test_real_hython_roundtrip(tmp_path):
    b = Bridge("batch", HYTHON, timeout=60, allow_python=True)
    first = str(tmp_path / "first.hip")
    second = str(tmp_path / "second.hip")
    status = b.call("status")
    assert status["ok"] and not status["result"]["ui_available"]
    types = b.call("node_types", {"path": "/obj"})
    assert types["ok"] and "geo" in types["result"]["types"]
    create = b.call("node_create", {"parent": "/obj", "type_name": "geo", "name": "mcp_test"}, hip_output=first)
    assert create["ok"], create
    first = create["hip_output"]
    assert b.call("node_inspect", {"path": "/obj/mcp_test"}, hip_input=first)["ok"]
    changed = b.call("node_set_parms", {"path": "/obj/mcp_test", "values": {"t": [1, 2, 3]}}, hip_input=first, hip_output=second)
    assert changed["ok"], changed
    protected = b.call("node_delete", {"path": "/obj/mcp_test"}, hip_input=first, hip_output=first)
    assert protected["error"]["type"] == "FileExistsError"
    py = b.call("execute_python", {"code": "print('hello'); result = hou.node('/obj/mcp_test').parmTuple('t').eval()"}, hip_input=changed["hip_output"])
    assert py["ok"] and py["stdout"].strip() == "hello" and "1.0, 2.0, 3.0" in py["result"]["value"]
    bad = b.call("node_inspect", {"path": "/obj/nonexistent"}, hip_input=first)
    assert bad["error"]["type"] == "ValueError"


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason="Houdini hython is not installed")
def test_real_hython_sop_connect_cook_delete(tmp_path):
    b = Bridge("batch", HYTHON, timeout=60, allow_python=True)
    hip1, hip2, hip3 = [str(tmp_path / (str(i) + ".hip")) for i in range(3)]
    setup = b.call("execute_python", {"code": "geo=hou.node('/obj').createNode('geo','integration'); geo.createNode('box','source'); geo.createNode('null','sink')"}, hip_output=hip1)
    assert setup["ok"], setup
    link = b.call("node_connect", {"path": "/obj/integration/sink", "source": "/obj/integration/source"}, hip_input=setup["hip_output"], hip_output=hip2)
    assert link["ok"] and link["result"]["inputs"][0] == "/obj/integration/source", link
    cook = b.call("node_cook", {"path": "/obj/integration/sink"}, hip_input=link["hip_output"])
    assert cook["ok"] and cook["result"]["cooked"] and not cook["result"]["errors"], cook
    delete = b.call("node_delete", {"path": "/obj/integration/source"}, hip_input=link["hip_output"], hip_output=hip3)
    assert delete["ok"], delete
    missing = b.call("node_cook", {"path": "/obj/integration/source"}, hip_input=delete["hip_output"])
    assert not missing["ok"] and missing["error"]["type"] == "ValueError"


def test_bounded_output():
    from houdini_mcp.dispatcher import BoundedOutput, LIMIT
    output = BoundedOutput()
    assert output.write("x" * (LIMIT + 100)) == LIMIT + 100
    output.write("ignored")
    assert output.getvalue() == "x" * LIMIT


def test_batch_timeout(monkeypatch, tmp_path):
    import subprocess
    executable = tmp_path / "hython.exe"
    executable.touch()
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    result = Bridge("batch", str(executable), timeout=1).call("status")
    assert result["error"]["type"] == "TimeoutError"
    assert "unknown" in result["error"]["message"]


def test_batch_worker_failure_reads_tail(monkeypatch, tmp_path):
    import subprocess
    from types import SimpleNamespace
    executable = tmp_path / "hython.exe"
    executable.touch()
    def fail(*args, **kwargs):
        kwargs["stderr"].write(b"a" * 9000 + b"tail")
        kwargs["stderr"].flush()
        return SimpleNamespace(returncode=7)
    monkeypatch.setattr(subprocess, "run", fail)
    result = Bridge("batch", str(executable)).call("status")
    assert result["error"]["type"] == "WorkerError"
    assert result["error"]["message"].endswith("tail")
    assert len(result["error"]["message"]) < 4100


def test_gui_call_failure_disconnect_and_reject_batch_paths():
    class BrokenConnection:
        closed = False
        def eval(self, expression):
            raise OSError("lost")
        def close(self):
            self.closed = True
    connection = BrokenConnection()
    bridge = Bridge("gui")
    bridge.connection = connection
    rejected = bridge.call("status", hip_input="x.hip")
    assert rejected["error"]["type"] == "ValueError"
    assert not connection.closed
    failed = bridge.call("status")
    assert failed["error"]["type"] == "OSError" and "unknown" in failed["error"]["message"]
    assert connection.closed and bridge.connection is None


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason="Houdini hython is not installed")
def test_real_hython_cook_failure_diagnostics(tmp_path):
    b = Bridge("batch", HYTHON, timeout=60, allow_python=True)
    hip = str(tmp_path / "bad_cook.hip")
    code = "geo=hou.node('/obj').createNode('geo','bad'); n=geo.createNode('attribwrangle','bad_vex'); n.parm('snippet').set('this is not valid vex !!!'); n.cook(force=True)"
    # Create and save a broken network without explicitly cooking it.
    code = code.rsplit(';', 1)[0]
    setup = b.call("execute_python", {"code": code}, hip_output=hip)
    assert setup["ok"], setup
    cooked = b.call("node_cook", {"path": "/obj/bad/bad_vex"}, hip_input=setup["hip_output"])
    assert cooked["ok"] and not cooked["result"]["cooked"], cooked
    assert cooked["result"]["errors"] or cooked["result"]["cook_exception"], cooked
