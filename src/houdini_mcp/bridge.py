import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

HERE = Path(__file__).parent


def failure(kind, message):
    return {"ok": False, "error": {"type": kind, "message": str(message)}}


class Bridge:
    def __init__(self, backend, hython=None, port=18811, timeout=60, allow_python=False):
        self.backend, self.hython, self.port = backend, hython, port
        self.timeout, self.allow_python = timeout, allow_python
        self.connection = None
        self.lock = threading.RLock()

    def close(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None

    def reconnect(self):
        with self.lock:
            self.close()
            if self.backend == "batch":
                if not self.hython or not os.path.isfile(self.hython):
                    return failure("ConfigurationError", "hython executable not found")
                return {"ok": True, "result": {"backend": "batch", "hython": self.hython}}
            try:
                import rpyc
                self.connection = rpyc.classic.connect("127.0.0.1", self.port)
                self.connection._config.update({"sync_request_timeout": self.timeout})
                # Houdini's hdefereval explicitly accepts calls from any thread
                # and schedules the callable on the main UI event loop.
                source = (HERE / "dispatcher.py").read_text(encoding="utf-8-sig")
                bootstrap = "import hou, json, hdefereval\nassert hou.isUIAvailable(), 'GUI backend requires Houdini UI'\n_hm_scope = {}\nexec(_hm_source, _hm_scope)"
                self.connection.execute("_hm_source = " + repr(source) + "\n" + bootstrap)
                return {"ok": True, "result": {"backend": "gui", "host": "127.0.0.1", "port": self.port}}
            except Exception as exc:
                self.close()
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
                expression = "json.dumps(hdefereval.executeInMainThreadWithResult(_hm_scope['dispatch'], json.loads(%r)), ensure_ascii=False, default=str)" % json.dumps(payload, ensure_ascii=False)
                return json.loads(str(self.connection.eval(expression)))
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
                    proc = subprocess.run([self.hython, str(HERE / "worker.py"), str(request), str(response)], stdout=subprocess.DEVNULL, stderr=output_stream, timeout=self.timeout)
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
