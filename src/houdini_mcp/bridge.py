import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from .gui import DEFAULT_PORT, HOST, GuiConnection, failure, gui_token_path, read_token

HERE = Path(__file__).parent


class Bridge:
    def __init__(self, backend, hython=None, port=DEFAULT_PORT, timeout=60, allow_python=False, gui_token_file=None):
        self.backend, self.hython, self.port = backend, hython, port
        self.timeout, self.allow_python = timeout, allow_python
        self.gui_token_file = Path(gui_token_file) if gui_token_file is not None else gui_token_path(port)
        self.connection = None
        self.lock = threading.RLock()

    def close(self):
        with self.lock:
            self.connection = None

    def reconnect(self):
        with self.lock:
            self.close()
            if self.backend == "batch":
                if not self.hython or not os.path.isfile(self.hython):
                    return failure("ConfigurationError", "hython executable not found")
                return {"ok": True, "result": {"backend": "batch", "hython": self.hython}}
            try:
                token = read_token(self.gui_token_file)
                connection = GuiConnection(self.port, token, self.timeout)
                reply = connection.call({"op": "status", "args": {}})
                if not reply["ok"]:
                    return reply
                status = reply["result"]
                session_id = status.get("session_id")
                if (
                    status.get("ui_available") is not True
                    or not isinstance(session_id, str) or not session_id
                    or not isinstance(status.get("hip_file"), str)
                    or type(status.get("unsaved_changes")) is not bool
                ):
                    return failure("ConnectionError", "Endpoint did not identify a Houdini GUI session")
                connection.session_id = session_id
                self.connection = connection
                return {"ok": True, "result": {**status, "backend": "gui", "host": HOST, "port": self.port}}
            except FileNotFoundError:
                return failure("ConfigurationError", f"Start the Houdini GUI bootstrap to create {self.gui_token_file}")
            except Exception as exc:
                return failure(type(exc).__name__, exc)

    def call(self, op, args=None, hip_input=None, hip_output=None, overwrite=False):
        if op == "execute_python" and not self.allow_python:
            return failure("PermissionError", "Python execution is disabled; start with --allow-python")
        payload = {"op": op, "args": args or {}}
        with self.lock:
            if self.backend == "batch":
                payload.update(hip_input=hip_input, hip_output=hip_output, overwrite=overwrite)
                return self._batch(payload)
            if hip_input or hip_output:
                return failure("ValueError", "hip_input and hip_output are batch-only")
            if self.connection is None:
                return failure("ConnectionError", "Not connected; call reconnect")
            try:
                result = self.connection.call(payload)
                if not result["ok"] and result["error"]["type"] in ("SessionMismatchError", "AuthenticationError"):
                    self.close()
                return result
            except Exception as exc:
                self.close()
                return failure(type(exc).__name__, str(exc) + "; operation outcome may be unknown and it may still complete")

    def _batch(self, payload):
        if not self.hython or not os.path.isfile(self.hython):
            return failure("ConfigurationError", "hython executable not found")
        try:
            with tempfile.TemporaryDirectory(prefix="houdini_mcp_") as temp:
                request, response = Path(temp) / "request.json", Path(temp) / "response.json"
                request.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                log = Path(temp) / "worker.log"
                with log.open("wb") as output_stream:
                    # Do not let hython consume or wait on the MCP server's stdin.
                    proc = subprocess.run(
                        [self.hython, str(HERE / "worker.py"), str(request), str(response)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=output_stream,
                        timeout=self.timeout,
                    )
                if not response.exists():
                    with log.open("rb") as stream:
                        stream.seek(0, os.SEEK_END)
                        stream.seek(max(0, stream.tell() - 4000))
                        tail = stream.read(4000).decode(errors="replace")
                    return failure("WorkerError", "hython exit %s: %s" % (proc.returncode, tail))
                return json.loads(response.read_text(encoding="utf-8-sig"))
        except subprocess.TimeoutExpired:
            return failure("TimeoutError", "hython exceeded timeout and was terminated; output file state may be unknown")
        except Exception as exc:
            return failure(type(exc).__name__, exc)
