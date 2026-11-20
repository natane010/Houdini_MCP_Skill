import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import queue
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from houdini_mcp.bridge import Bridge

HYTHON = os.environ.get("HOUDINI_MCP_TEST_HYTHON", r"C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe")


@pytest.fixture(autouse=True)
def isolate_houdini_environment(monkeypatch, tmp_path):
    """Keep spawned hython processes out of the user's packages and preferences."""
    monkeypatch.setenv("HOUDINI_PACKAGE_SKIP", "1")
    monkeypatch.setenv("HOUDINI_NO_ENV_FILE", "1")
    monkeypatch.setenv("HOUDINI_USER_PREF_DIR", str(tmp_path / "prefs__HVER__"))
    monkeypatch.delenv("HOUDINI_PATH", raising=False)


def test_python_is_opt_in():
    result = Bridge("batch").call("execute_python", {"code": "pass"})
    assert result["error"]["type"] == "PermissionError"


def test_no_implicit_reconnect():
    result = Bridge("gui").call("node_delete", {"path": "/obj/a"})
    assert result["error"]["type"] == "ConnectionError"


def test_missing_hython():
    assert Bridge("batch", "missing").reconnect()["error"]["type"] == "ConfigurationError"


def test_gui_reconnect_requires_token_file(tmp_path):
    bridge = Bridge("gui", timeout=1, gui_token_file=tmp_path / "missing.token")
    assert bridge.reconnect()["error"]["type"] == "ConfigurationError"
    assert bridge.connection is None


def test_gui_authentication_operation_allowlist_and_session_identity(monkeypatch, tmp_path):
    from houdini_mcp import gui

    operations = []

    def dispatch(payload):
        operations.append(payload["op"])
        return {"ok": True, "result": {"ui_available": True, "hip_file": "scene.hip", "unsaved_changes": True}}

    monkeypatch.setitem(sys.modules, "hou", SimpleNamespace(isUIAvailable=lambda: True))
    monkeypatch.setattr(gui, "dispatch_in_gui", dispatch)
    with socket.socket() as listener:
        listener.bind((gui.HOST, 0))
        port = listener.getsockname()[1]
    token_file = tmp_path / "session.token"
    server = gui.start_gui_server(port, token_file)
    try:
        actual_token = gui.read_token(token_file)
        wrong_file = tmp_path / "wrong.token"
        wrong_file.write_text("x" * 43, encoding="ascii")
        wrong_file.chmod(0o600)
        unauthenticated = Bridge("gui", port=port, timeout=2, gui_token_file=wrong_file)
        assert unauthenticated.reconnect()["error"]["type"] == "AuthenticationError"
        assert operations == []

        bridge = Bridge("gui", port=port, timeout=2, allow_python=True, gui_token_file=token_file)
        connected = bridge.reconnect()
        assert connected["ok"] and connected["result"]["session_id"] == server.session_id
        assert connected["result"]["hip_file"] == "scene.hip" and connected["result"]["unsaved_changes"]
        assert actual_token not in json.dumps(connected)
        python = bridge.call("execute_python", {"code": "pass"})
        assert python["error"]["type"] == "PermissionError"
        assert bridge.call("arbitrary_rpc_method")["error"]["type"] == "ValueError"
        guest = gui.GuiConnection(port, actual_token, timeout=2)
        assert guest.call({"op": "node_delete", "args": {"path": "/obj/a"}})["error"]["type"] == "SessionMismatchError"

        server.session_id = "new-session"
        stale = bridge.call("node_delete", {"path": "/obj/a"})
        assert stale["error"]["type"] == "SessionMismatchError"
        assert bridge.connection is None and operations == ["status"]
    finally:
        server.stop()


def test_gui_signature_is_bound_to_payload_and_single_use():
    from houdini_mcp import gui

    with gui._GuiServer((gui.HOST, 0), gui._GuiHandler) as server:
        server.key = b"test-key"
        now, nonce, body = int(time.time()), "a" * 32, b'{"op":"status"}'
        proof = gui._signature(server.key, b"request", f"{server.server_port}:{now}.{nonce}", body)
        assert not server.authenticate(now, nonce, proof, b'{"op":"node_list"}')
        assert server.authenticate(now, nonce, proof, body)
        assert not server.authenticate(now, nonce, proof, body)

        expired, fresh_nonce = now - gui.AUTH_WINDOW - 1, "b" * 32
        old_proof = gui._signature(server.key, b"request", f"{server.server_port}:{expired}.{fresh_nonce}", body)
        assert not server.authenticate(expired, fresh_nonce, old_proof, body)


def test_gui_client_does_not_expose_token_or_accept_unsigned_response(monkeypatch):
    from unittest.mock import MagicMock
    from houdini_mcp import gui

    http = MagicMock()
    response = http.getresponse.return_value.__enter__.return_value
    response.status = 200
    response.getheader.return_value = ""
    response.read.return_value = b'{"ok":true,"result":{}}'
    monkeypatch.setattr(gui, "HTTPConnection", lambda *args, **kwargs: http)

    token = "local-test-token"
    result = gui.GuiConnection(18811, token, timeout=1).call({"op": "status", "args": {}})
    assert result["error"]["type"] == "AuthenticationError"
    assert token not in http.request.call_args.kwargs["headers"]["Authorization"]


def test_gui_deferred_requests_keep_independent_results(monkeypatch):
    from houdini_mcp import dispatcher

    pending = queue.Queue()
    monkeypatch.setitem(sys.modules, "hdefereval", SimpleNamespace(executeDeferred=pending.put))
    monkeypatch.setattr(dispatcher, "dispatch", lambda payload: payload["op"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(dispatcher.dispatch_in_gui, {"op": "first"})
        run_first = pending.get(timeout=5)
        second = pool.submit(dispatcher.dispatch_in_gui, {"op": "second"})
        run_second = pending.get(timeout=5)
        run_second()
        run_first()
        assert first.result(timeout=5) == "first"
        assert second.result(timeout=5) == "second"


@pytest.mark.parametrize("allow_python", [False, True])
def test_stdio_protocol(allow_python):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def run():
        args = ["-m", "houdini_mcp.server", "--backend", "batch"]
        if allow_python:
            args.append("--allow-python")
        params = StdioServerParameters(command=sys.executable, args=args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert {"node_create", "node_types", "node_snapshot", "hda_publish", "batch_edit_network",
                        "connection_status"} <= names
                assert ("execute_python" in names) is allow_python
                result = await session.call_tool("connection_status", {})
                assert result.isError
                detail = json.loads(result.content[0].text)
                assert detail["error"]["type"] == "ConfigurationError" and result.structuredContent == detail
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
    changed_argv = b.call("execute_python", {"code": "import sys; sys.argv[:] = []; result = 'ok'"}, hip_input=changed["hip_output"])
    assert changed_argv["ok"] and changed_argv["result"]["value"] == "'ok'"
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
        assert kwargs["stdin"] == subprocess.DEVNULL
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
        def call(self, payload):
            raise OSError("lost")
    connection = BrokenConnection()
    bridge = Bridge("gui")
    bridge.connection = connection
    rejected = bridge.call("status", hip_input="x.hip")
    assert rejected["error"]["type"] == "ValueError"
    assert bridge.connection is connection
    failed = bridge.call("status")
    assert failed["error"]["type"] == "OSError" and "unknown" in failed["error"]["message"]
    assert bridge.connection is None


@pytest.fixture
def legacy_hip(tmp_path):
    script = tmp_path / "legacy_scene.py"
    receipt = tmp_path / "legacy_path.txt"
    script.write_text(f"""
import hou
from pathlib import Path
subnet = hou.node('/obj').createNode('subnet', 'legacy')
geo = subnet.createNode('geo', 'geometry')
box = geo.createNode('box', 'source')
wrangle = geo.createNode('attribwrangle', 'bad_vex')
wrangle.setInput(0, box)
wrangle.parm('snippet').set('this is not valid vex !!!')
python_node = geo.createNode('python', 'custom_python')
python_node.setInput(0, wrangle)
out = geo.createNode('null', 'OUT')
out.setInput(0, python_node)
out.setDisplayFlag(True)
out.setRenderFlag(True)
hou.hipFile.save(file_name={str(tmp_path / 'legacy.hip')!r})
Path({str(receipt)!r}).write_text(hou.hipFile.path(), encoding='utf-8')
""", encoding="utf-8")
    proc = subprocess.run([HYTHON, str(script)], capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    return receipt.read_text(encoding="utf-8")


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason="Houdini hython is not installed")
def test_real_hython_cook_failure_diagnostics(legacy_hip):
    b = Bridge("batch", HYTHON, timeout=60)
    cooked = b.call("node_cook", {"path": "/obj/legacy/geometry/bad_vex"}, hip_input=legacy_hip)
    assert cooked["ok"] and not cooked["result"]["cooked"], cooked
    assert cooked["result"]["errors"] or cooked["result"]["cook_exception"], cooked


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason="Houdini hython is not installed")
def test_real_hython_refuses_code_nodes_in_builds_and_artifacts(tmp_path, legacy_hip):
    bridge = Bridge("batch", HYTHON)
    geo = "/obj/legacy/geometry"
    create = bridge.call("node_create", {"parent": geo, "type_name": "python"}, hip_input=legacy_hip)
    assert create["error"]["type"] == "CodeNodeError", create
    target = tmp_path / "blocked.hip"
    saved = bridge.call("scene_save", {"path": str(target)}, hip_input=legacy_hip)
    assert saved["error"]["type"] == "CodeNodeError", saved
    assert {item["path"] for item in saved["error"]["code_nodes"]} == {
        geo + "/bad_vex", geo + "/custom_python",
    }
    wrangle = next(item for item in saved["error"]["code_nodes"] if item["path"].endswith("/bad_vex"))
    assert any(item["type_name"].startswith("attribcreate") for item in wrangle["candidate_types"])
    staged = bridge.call("node_create", {"parent": geo, "type_name": "null"},
                         hip_input=legacy_hip, hip_output=str(target))
    assert staged["error"]["type"] == "CodeNodeError", staged
    published = bridge.call("hda_publish", {"path": "/obj/legacy", "type_name": "test::blocked::1.0",
                                            "output_path": str(tmp_path / "blocked.hda")},
                            hip_input=legacy_hip)
    assert published["error"]["type"] == "CodeNodeError", published
    assert not list(tmp_path.glob("blocked.*"))


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason="Houdini hython is not installed")
def test_real_hython_publishes_standard_network_without_python_tool(tmp_path):
    bridge = Bridge("batch", HYTHON)
    created = bridge.call("node_create", {"parent": "/obj", "type_name": "subnet", "name": "clean"},
                          hip_output=str(tmp_path / "clean.hip"))
    assert created["ok"], created
    geo = bridge.call("node_create", {"parent": "/obj/clean", "type_name": "geo", "name": "geometry"},
                      hip_input=created["hip_output"], hip_output=str(tmp_path / "geometry.hip"))
    assert geo["ok"], geo
    stock = bridge.call("node_create", {"parent": "/obj/clean/geometry", "type_name": "platonic"},
                        hip_input=geo["hip_output"], hip_output=str(tmp_path / "stock.hip"))
    assert stock["ok"], stock
    published = bridge.call("hda_publish", {"path": "/obj/clean", "type_name": "test::native::1.0",
                                            "output_path": str(tmp_path / "native.hda")},
                            hip_input=stock["hip_output"])
    assert published["ok"] and published["result"]["verified"], published
    assert Path(published["result"]["output_path"]).is_file()


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason="Houdini hython is not installed")
def test_real_hython_replaces_legacy_code_with_standard_sops_in_one_batch(tmp_path, legacy_hip):
    bridge = Bridge("batch", HYTHON)
    geo = "/obj/legacy/geometry"
    original = Path(legacy_hip).read_bytes()
    steps = [
        {"op": "node_create", "args": {"parent": geo, "type_name": "attribcreate", "name": "create_pscale"}},
        {"op": "node_set_parms", "args": {"path": geo + "/create_pscale",
                                         "values": {"name1": "pscale", "class1": 2, "value1v1": 0.2}}},
        {"op": "node_connect", "args": {"path": geo + "/create_pscale", "source": geo + "/source"}},
        {"op": "node_connect", "args": {"path": geo + "/OUT", "source": geo + "/create_pscale"}},
        {"op": "node_set_flags", "args": {"path": geo + "/OUT", "display": True, "render": True}},
        {"op": "node_delete", "args": {"path": geo + "/custom_python"}},
        {"op": "node_delete", "args": {"path": geo + "/bad_vex"}},
        {"op": "node_cook", "args": {"path": geo + "/OUT"}},
    ]
    output = str(tmp_path / "repaired.hip")
    repaired = bridge.call("batch_edit_network", {"steps": steps}, hip_input=legacy_hip, hip_output=output)
    assert repaired["ok"], repaired
    assert Path(legacy_hip).read_bytes() == original
    final = repaired["hip_output"]
    snapshot = bridge.call("node_snapshot", {"path": geo + "/OUT"}, hip_input=final)
    assert snapshot["result"]["inputs"][0]["source"] == geo + "/create_pscale", snapshot
    assert snapshot["result"]["flags"] == {"display": True, "render": True}
    inspection = Bridge("batch", HYTHON, allow_python=True).call("execute_python", {"code": f"""
geo = hou.node({(geo + '/OUT')!r}).geometry()
result = (len(geo.points()), sorted(set(round(p.attribValue('pscale'), 3) for p in geo.points())))
"""}, hip_input=final)
    assert inspection["ok"] and inspection["result"]["value"] == "(8, [0.2])", inspection


def test_batch_network_steps_validate_before_dispatch(monkeypatch):
    from houdini_mcp import dispatcher

    def no_dispatch(payload):
        pytest.fail("An invalid plan must fail before dispatch")

    monkeypatch.setattr(dispatcher, "dispatch", no_dispatch)
    with pytest.raises(ValueError, match="step 2"):
        dispatcher._batch_edit_network([
            {"op": "node_create", "args": {}},
            {"op": "execute_python", "args": {}},
        ])


def test_inspection_reports_evaluation_errors_and_enforces_limit(monkeypatch):
    from houdini_mcp import dispatcher

    class EvaluationError(Exception):
        pass

    class ParmTuple(tuple):
        def name(self):
            return "t"

        def parmTemplate(self):
            return SimpleNamespace(label=lambda: "Translate", type=lambda: "Float")

    def bad_expression():
        raise EvaluationError("Cannot evaluate expression")

    translation = ParmTuple((
        SimpleNamespace(name=lambda: "tx", eval=bad_expression),
        SimpleNamespace(name=lambda: "ty", eval=lambda: 2.0),
    ))
    node = SimpleNamespace(parmTuples=lambda: [translation, None])
    hou = SimpleNamespace(node=lambda path: node, isUIAvailable=lambda: False, Error=EvaluationError)
    monkeypatch.setitem(sys.modules, "hou", hou)
    monkeypatch.setattr(dispatcher, "_info", lambda node: {})
    monkeypatch.setattr(dispatcher, "PARM_LIMIT", 1)

    inspected = dispatcher.dispatch({"op": "node_inspect", "args": {"path": "/obj/inspect_me"}})
    assert inspected["ok"], inspected
    assert inspected["result"]["parms_truncated"]
    translate, = inspected["result"]["parms"]
    assert translate["value"] == [None, "2.0"]
    assert translate["evaluation_errors"] == {"tx": "Cannot evaluate expression"}


def test_parameter_shape_is_validated_before_any_set():
    from houdini_mcp.dispatcher import _set_parms

    updates = []
    parm = SimpleNamespace(set=updates.append)
    node = SimpleNamespace(
        parm={"tx": parm}.get,
        parmTuple={"t": (None, None, None)}.get,
    )
    with pytest.raises(ValueError, match="requires 3 values"):
        _set_parms(None, node, {"tx": 5, "t": [1, 2]})
    assert updates == []


def test_batch_rechecks_original_output_before_saving(tmp_path, monkeypatch):
    from houdini_mcp import dispatcher

    destination = tmp_path / "scene.hip"
    new_directory = tmp_path / "other"
    new_directory.mkdir()
    monkeypatch.chdir(tmp_path)

    def run_operation(payload):
        monkeypatch.chdir(new_directory)
        destination.write_bytes(b"existing data")
        return {"ok": True}

    def save(file_name):
        pytest.fail(f"Unexpected scene save to {file_name}")

    monkeypatch.setitem(sys.modules, "hou", SimpleNamespace(hipFile=SimpleNamespace(save=save)))
    monkeypatch.setattr(dispatcher, "dispatch", run_operation)
    result = dispatcher.batch({"op": "execute_python", "hip_output": "scene.hip"})
    assert result["error"]["type"] == "FileExistsError"
    assert destination.read_bytes() == b"existing data"


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason="Houdini hython is not installed")
def test_real_hython_protected_parms_and_snapshot(tmp_path):
    setup_bridge = Bridge("batch", HYTHON, allow_python=True)
    setup = setup_bridge.call("execute_python", {"code": """
obj = hou.node('/obj')
source = obj.createNode('geo', 'controller')
node = obj.createNode('geo', 'client')
source.parm('tx').set(7)
node.parm('tx').set(source.parm('tx'))
node.parm('ty').setExpression('frame() * 2', hou.exprLanguage.Python)
for frame, value in ((1, 3), (10, 5)):
    key = hou.Keyframe()
    key.setFrame(frame)
    key.setValue(value)
    node.parm('tz').setKeyframe(key)
"""}, hip_output=str(tmp_path / "driven.hip"))
    assert setup["ok"], setup
    original = setup["hip_output"]
    bridge = Bridge("batch", HYTHON)
    node = "/obj/client"
    before = bridge.call("node_snapshot", {"path": node, "parm_names": ["t", "rz"]}, hip_input=original)
    assert before["ok"], before
    snapshot = {parm["name"]: parm for parm in before["result"]["parms"]}
    assert "ch(" in snapshot["tx"]["raw_value"]
    assert snapshot["ty"]["keyframes"][0]["expression"] == "frame() * 2"
    assert len(snapshot["tz"]["keyframes"]) == 2
    changed = str(tmp_path / "edited.hip")
    values = {"rz": 12, "t": [1, 2, 3]}
    blocked = bridge.call("node_set_parms", {"path": node, "values": values}, hip_input=original, hip_output=changed)
    assert blocked["error"]["type"] == "ProtectedParameterError", blocked
    protected = {parm["path"]: parm for parm in blocked["error"]["parameters"]}
    assert protected[node + "/tx"]["referenced_parm"] == "/obj/controller/tx"
    assert protected[node + "/tz"]["keyframe_count"] == 2
    assert not list(tmp_path.glob("edited.hip*"))

    replaced = bridge.call("node_set_parms", {"path": node, "values": values, "replace_driven": True},
                           hip_input=original, hip_output=changed)
    assert replaced["ok"], replaced
    for path, names, expected in [(node, ["t", "rz"], [1, 2, 3, 12]), ("/obj/controller", ["tx"], [7])]:
        check = bridge.call("node_snapshot", {"path": path, "parm_names": names}, hip_input=replaced["hip_output"])
        assert check["ok"], check
        assert [float(parm["raw_value"]) for parm in check["result"]["parms"]] == expected
        assert all(not parm["keyframes"] for parm in check["result"]["parms"])
