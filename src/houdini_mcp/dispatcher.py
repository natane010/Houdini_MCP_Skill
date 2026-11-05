"""Runs inside Houdini. All public values crossing the boundary are JSON data."""
import contextlib
import io
import os
import traceback

LIMIT = 20000

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


def _exists_as_hip(path):
    # Houdini may convert .hip to .hipnc/.hiplc according to license.
    root, ext = os.path.splitext(os.path.abspath(path))
    candidates = [path]
    if ext.lower() in (".hip", ".hipnc", ".hiplc"):
        candidates += [root + suffix for suffix in (".hip", ".hipnc", ".hiplc")]
    return any(os.path.exists(p) for p in candidates)


def dispatch(payload):
    import hou
    out, err = BoundedOutput(), BoundedOutput()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), (hou.undos.group("Houdini MCP " + payload["op"]) if hou.isUIAvailable() and payload["op"] in ("node_create", "node_set_parms", "node_connect", "node_delete") else contextlib.nullcontext()):
            op = payload["op"]
            args = payload.get("args", {})
            if op == "status":
                result = {"houdini_version": hou.applicationVersionString(), "hip_file": hou.hipFile.path(), "ui_available": hou.isUIAvailable()}
            elif op == "execute_python":
                scope = {"hou": hou}
                exec(args["code"], scope, scope)
                result = {"value": repr(scope.get("result"))[:LIMIT]}
            elif op == "node_types":
                category = _node(hou, args["path"]).childTypeCategory()
                result = {"category": category.name(), "types": sorted(category.nodeTypes().keys())[:5000]}
            elif op == "node_create":
                node = _node(hou, args["parent"]).createNode(args["type_name"], node_name=args.get("name") or None)
                result = _info(node)
            elif op == "node_inspect":
                node = _node(hou, args["path"])
                result = _info(node)
                result["parms"] = [{"name": t.name(), "label": t.parmTemplate().label(),
                                    "type": str(t.parmTemplate().type()), "size": len(t),
                                    "value": [str(p.eval())[:1000] for p in t]} for t in node.parmTuples()][:1000]
            elif op == "node_list":
                result = [_info(n) for n in _node(hou, args["path"]).children()[:1000]]
            elif op == "node_set_parms":
                node = _node(hou, args["path"])
                for name, value in args["values"].items():
                    if node.parm(name) is None and node.parmTuple(name) is None:
                        raise ValueError("Parameter does not exist: " + name)
                for name, value in args["values"].items():
                    parm = node.parm(name)
                    if isinstance(value, (list, tuple)):
                        parm_tuple = node.parmTuple(name)
                        if parm_tuple is None:
                            raise ValueError("Parameter tuple does not exist: " + name)
                        parm_tuple.set(value)
                    elif parm is not None:
                        parm.set(value)
                    else:
                        raise ValueError("Parameter tuple requires a list: " + name)
                result = _info(node)
            elif op == "node_connect":
                node = _node(hou, args["path"])
                source = _node(hou, args["source"]) if args.get("source") else None
                node.setInput(args.get("input_index", 0), source, args.get("output_index", 0))
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
                if hou.isUIAvailable() and hou.hipFile.hasUnsavedChanges() and not args.get("discard_changes", False):
                    raise RuntimeError("Scene has unsaved changes; set discard_changes=true to load")
                hou.hipFile.load(args["path"], suppress_save_prompt=True, ignore_load_warnings=False)
                result = {"path": hou.hipFile.path()}
            elif op == "scene_save":
                path = os.path.abspath(args["path"])
                if _exists_as_hip(path) and not args.get("overwrite", False):
                    raise FileExistsError("Target exists; set overwrite=true: " + path)
                hou.hipFile.save(file_name=path)
                result = {"path": hou.hipFile.path()}
            else:
                raise ValueError("Unknown operation: " + str(op))
        return {"ok": True, "result": result, "stdout": out.getvalue()[:LIMIT], "stderr": err.getvalue()[:LIMIT]}
    except Exception as exc:
        return {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)[:LIMIT], "traceback": traceback.format_exc()[-LIMIT:], "note": "Operation may have partially changed the scene."}, "stdout": out.getvalue()[:LIMIT], "stderr": err.getvalue()[:LIMIT]}


def batch(payload):
    import hou
    try:
        if payload.get("hip_input"):
            hou.hipFile.load(payload["hip_input"], suppress_save_prompt=True, ignore_load_warnings=False)
        output = payload.get("hip_output")
        if output and _exists_as_hip(output) and not payload.get("overwrite", False):
            raise FileExistsError("Target exists; set overwrite=true: " + output)
        result = dispatch(payload)
        if result["ok"] and output:
            hou.hipFile.save(file_name=os.path.abspath(output))
            result["hip_output"] = hou.hipFile.path()
        return result
    except Exception as exc:
        return {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)[:LIMIT], "traceback": traceback.format_exc()[-LIMIT:]}}
