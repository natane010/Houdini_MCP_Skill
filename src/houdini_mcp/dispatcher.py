"""Runs inside Houdini. All public values crossing the boundary are JSON data."""
from concurrent.futures import Future
import contextlib
from functools import lru_cache
import io
import os
from pathlib import Path
import runpy
import traceback

LIMIT = 20000
PARM_LIMIT = 1000
EDIT_OPERATIONS = {"node_create", "node_set_parms", "node_connect", "node_set_flags", "node_delete", "node_cook"}


class ProtectedParameterError(ValueError):
    def __init__(self, parameters):
        self.parameters = parameters
        paths = ", ".join(item["path"] for item in parameters)
        super().__init__("Parameters have references, expressions or keyframes: " + paths)


@lru_cache(maxsize=None)
def _skill_script(package, skill, filename):
    packaged = Path(__file__).with_name(package) / filename
    if packaged.is_file():
        return runpy.run_path(str(packaged))
    source = Path(__file__).resolve().parents[2] / "skills" / skill / "scripts" / filename
    return runpy.run_path(str(source))


def _hda_helper():
    return _skill_script("hda_helpers", "houdini-hda-publisher", "publish_hda.py")


def _error_details(exc):
    error = {"type": type(exc).__name__, "message": str(exc)[:LIMIT],
             "traceback": traceback.format_exc()[-LIMIT:]}
    if hasattr(exc, "code_nodes"):
        error["code_nodes"] = exc.code_nodes
    return error


class BoundedOutput(io.TextIOBase):
    def __init__(self):
        self.parts = []
        self.remaining = LIMIT
    def write(self, value):
        value = str(value)
        if self.remaining:
            self.parts.append(value[:self.remaining])
            self.remaining -= min(len(value), self.remaining)
        return len(value)
    def getvalue(self):
        return "".join(self.parts)


def _node(hou, path):
    node = hou.node(path)
    if node is None:
        raise ValueError("Node does not exist: " + path)
    return node


def _info(node):
    return {"path": node.path(), "name": node.name(), "type": node.type().name(),
            "children": len(node.children()),
            "inputs": [n.path() if n else None for n in node.inputs()]}


def _create_node(hou, args):
    parent = _node(hou, args["parent"])
    type_name = args["type_name"]
    category = parent.childTypeCategory()
    if category is None:
        raise ValueError("Node cannot contain child nodes: " + parent.path())
    helper = _hda_helper()
    chosen = hou.nodeType(category, type_name)
    components = chosen.nameComponents() if chosen else hou.hda.componentsFromFullNodeTypeName(type_name)
    reason = helper["code_node_reason"](category.name(), components[2])
    if reason:
        path = parent.path().rstrip("/") + "/" + (args.get("name") or type_name)
        finding = helper["code_node_finding"](category, type_name, components[2], path, reason)
        raise helper["CodeNodeError"]([finding])
    node = parent.createNode(type_name, node_name=args.get("name") or None)
    try:
        helper["validate_network"](node)
    except helper["CodeNodeError"]:
        node.destroy()
        raise
    return node


def _exists_as_hip(path):
    # Houdini may convert .hip to .hipnc/.hiplc according to license.
    root, ext = os.path.splitext(os.path.abspath(path))
    candidates = [path]
    if ext.lower() in (".hip", ".hipnc", ".hiplc"):
        candidates += [root + suffix for suffix in (".hip", ".hipnc", ".hiplc")]
    return any(os.path.lexists(p) for p in candidates)


def _check_hip_output(path, overwrite):
    if not overwrite and _exists_as_hip(path):
        raise FileExistsError("Target exists; set overwrite=true: " + path)


def _inspect_parm(hou, parm_tuple):
    template = parm_tuple.parmTemplate()
    info = {"name": parm_tuple.name(), "label": template.label(),
            "type": str(template.type()), "size": len(parm_tuple), "value": []}
    for parm in parm_tuple:
        try:
            value = str(parm.eval())[:1000]
        except hou.Error as exc:
            value = None
            info.setdefault("evaluation_errors", {})[parm.name()] = str(exc)[:1000]
        info["value"].append(value)
    return info


def _set_parms(hou, node, values, replace_driven=False):
    assignments = []
    for name, value in values.items():
        if not isinstance(name, str) or not name or "/" in name or "\\" in name:
            raise ValueError("Parameter names must be local to the requested node")
        if isinstance(value, (list, tuple)):
            target = node.parmTuple(name)
            if target is None:
                raise ValueError("Parameter tuple does not exist: " + name)
            if len(value) != len(target):
                raise ValueError(f"Parameter tuple {name} requires {len(target)} values")
            assignments.extend(zip(target, value))
        else:
            target = node.parm(name)
            if target is None:
                if node.parmTuple(name) is not None:
                    raise ValueError("Parameter tuple requires a list: " + name)
                raise ValueError("Parameter does not exist: " + name)
            assignments.append((target, value))

    checked = []
    protected = []
    for parm, value in assignments:
        if value is None:
            raise ValueError("Parameter requires a value: " + parm.path())
        if parm.isLocked():
            raise PermissionError("Parameter is locked: " + parm.path())
        keys = parm.keyframes()
        reference = parm.getReferencedParm().path()
        if reference == parm.path():
            reference = None
        inline_expression = (
            not keys and parm.parmTemplate().type() == hou.parmTemplateType.String
            and parm.unexpandedString().count("`") >= 2
        )
        if keys or reference or inline_expression:
            protected.append({"path": parm.path(), "referenced_parm": reference,
                              "keyframe_count": len(keys), "inline_expression": inline_expression})
        checked.append((parm, value, bool(keys)))
    if protected and not replace_driven:
        raise ProtectedParameterError(protected)

    for parm, value, has_keys in checked:
        if has_keys:
            parm.deleteAllKeyframes()
        parm.set(value, follow_parm_reference=False)


def _set_flags(node, args):
    assignments = []
    for flag, setter in (("display", "setDisplayFlag"), ("render", "setRenderFlag")):
        value = args.get(flag)
        if value is None:
            continue
        if type(value) is not bool:
            raise ValueError(f"{flag} must be true or false")
        method = getattr(node, setter, None)
        if method is None:
            raise ValueError(f"{flag} flag is unavailable on {node.path()}")
        assignments.append((method, value))
    if not assignments:
        raise ValueError("Specify display or render")
    for method, value in assignments:
        method(value)


def _batch_edit_network(steps):
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise ValueError("Provide between 1 and 100 network editing steps")
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict) or not isinstance(step.get("op"), str):
            raise ValueError(f"Invalid network editing step {index}")
        if step["op"] not in EDIT_OPERATIONS or not isinstance(step.get("args"), dict):
            raise ValueError(f"Invalid operation or arguments for network editing step {index}")
    edits = []
    for index, step in enumerate(steps, start=1):
        reply = dispatch(step)
        if not reply["ok"]:
            reply["error"]["step"] = index
            return reply
        if step["op"] == "node_cook" and not reply["result"]["cooked"]:
            reply["ok"] = False
            reply["error"] = {"type": "CookError", "message": "Network edit failed cook validation", "step": index}
            return reply
        edits.append({"op": step["op"], "result": reply["result"]})
    return {"ok": True, "result": {"steps": edits}}


def dispatch(payload):
    import hou
    out, err = BoundedOutput(), BoundedOutput()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), (hou.undos.group("Houdini MCP " + payload["op"]) if hou.isUIAvailable() and payload["op"] in EDIT_OPERATIONS - {"node_cook"} else contextlib.nullcontext()):
            op = payload["op"]
            args = payload.get("args", {})
            if op == "status":
                result = {"houdini_version": hou.applicationVersionString(), "hip_file": hou.hipFile.path(), "ui_available": hou.isUIAvailable()}
                if result["ui_available"]:
                    result["unsaved_changes"] = hou.hipFile.hasUnsavedChanges()
            elif op == "execute_python":
                scope = {"hou": hou}
                exec(args["code"], scope, scope)
                result = {"value": repr(scope.get("result"))[:LIMIT]}
            elif op == "node_types":
                category = _node(hou, args["path"]).childTypeCategory()
                if category is None:
                    raise ValueError("Node cannot contain child nodes: " + args["path"])
                result = {"category": category.name(), "types": sorted(category.nodeTypes().keys())[:5000]}
            elif op == "node_create":
                result = _info(_create_node(hou, args))
            elif op == "node_inspect":
                node = _node(hou, args["path"])
                result = _info(node)
                parms = node.parmTuples()
                result["parms"] = [_inspect_parm(hou, t) for t in parms[:PARM_LIMIT]]
                result["parms_truncated"] = len(parms) > PARM_LIMIT
            elif op == "node_snapshot":
                snapshot = _skill_script("skill_helpers", "houdini-iterate", "node_snapshot.py")["snapshot_node"]
                result = snapshot(args["path"], args.get("parm_names"), args.get("max_parms", 200))
            elif op == "node_list":
                result = [_info(n) for n in _node(hou, args["path"]).children()[:1000]]
            elif op == "node_set_parms":
                node = _node(hou, args["path"])
                _set_parms(hou, node, args["values"], args.get("replace_driven") is True)
                result = _info(node)
            elif op == "node_connect":
                node = _node(hou, args["path"])
                source = _node(hou, args["source"]) if args.get("source") else None
                node.setInput(args.get("input_index", 0), source, args.get("output_index", 0))
                result = _info(node)
            elif op == "node_set_flags":
                node = _node(hou, args["path"])
                _set_flags(node, args)
                result = _info(node)
            elif op == "node_delete":
                node = _node(hou, args["path"])
                path = node.path()
                node.destroy()
                result = {"deleted": path}
            elif op == "node_cook":
                node = _node(hou, args["path"])
                cook_error = None
                try:
                    node.cook(force=True)
                except hou.OperationFailed as exc:
                    cook_error = str(exc)
                errors = list(node.errors())
                result = {"path": node.path(), "cooked": cook_error is None and not errors,
                          "cook_exception": cook_error, "errors": errors,
                          "warnings": list(node.warnings()), "messages": list(node.messages())}
            elif op == "scene_load":
                if hou.isUIAvailable() and hou.hipFile.hasUnsavedChanges() and args.get("discard_changes") is not True:
                    raise RuntimeError("Scene has unsaved changes; set discard_changes=true to load")
                hou.hipFile.load(args["path"], suppress_save_prompt=True, ignore_load_warnings=False)
                result = {"path": hou.hipFile.path()}
            elif op == "scene_save":
                path = os.path.abspath(args["path"])
                _check_hip_output(path, args.get("overwrite") is True)
                _hda_helper()["validate_network"](hou.node("/"))
                hou.hipFile.save(file_name=path)
                result = {"path": hou.hipFile.path()}
            elif op == "hda_publish":
                result = _hda_helper()["publish_hda"](args["path"], args["output_path"], args["type_name"],
                                                       args.get("description", ""))
            else:
                raise ValueError("Unknown operation: " + str(op))
        return {"ok": True, "result": result, "stdout": out.getvalue()[:LIMIT], "stderr": err.getvalue()[:LIMIT]}
    except ProtectedParameterError as exc:
        return {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc),
                                       "parameters": exc.parameters},
                "stdout": out.getvalue(), "stderr": err.getvalue()}
    except Exception as exc:
        error = _error_details(exc)
        error["note"] = "Operation may have partially changed the scene."
        return {"ok": False, "error": error, "stdout": out.getvalue()[:LIMIT], "stderr": err.getvalue()[:LIMIT]}


def dispatch_in_gui(payload):
    import hdefereval

    # Each request needs its own result when multiple RPC clients are connected.
    result = Future()

    def run():
        try:
            result.set_result(dispatch(payload))
        except BaseException as exc:
            result.set_exception(exc)

    hdefereval.executeDeferred(run)
    return result.result()


def batch(payload):
    import hou
    try:
        output = payload.get("hip_output")
        source = payload.get("hip_input")
        if payload["op"] == "batch_edit_network" and (not source or not output):
            raise ValueError("batch_edit_network requires hip_input and hip_output")
        overwrite = payload.get("overwrite") is True
        if output:
            output = os.path.abspath(output)
            _check_hip_output(output, overwrite)
        if source:
            hou.hipFile.load(source, suppress_save_prompt=True, ignore_load_warnings=False)
        if payload["op"] == "batch_edit_network":
            result = _batch_edit_network(payload.get("args", {}).get("steps"))
        else:
            result = dispatch(payload)
        if result["ok"] and output:
            _check_hip_output(output, overwrite)
            _hda_helper()["validate_network"](hou.node("/"))
            hou.hipFile.save(file_name=output)
            result["hip_output"] = hou.hipFile.path()
        return result
    except Exception as exc:
        return {"ok": False, "error": _error_details(exc)}
