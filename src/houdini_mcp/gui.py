"""Authenticated loopback transport for the Houdini GUI."""
import hmac
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
from threading import BoundedSemaphore, Lock, Thread
import time
from uuid import uuid4

from .dispatcher import dispatch_in_gui

HOST = "127.0.0.1"
DEFAULT_PORT = 18811
ENDPOINT = "/houdini-mcp"
MAX_REQUEST = 2 * 1024 * 1024
MAX_RESPONSE = 32 * 1024 * 1024
AUTH_WINDOW = 30
MAX_NONCES = 4096
AUTH_HEADER = re.compile(r"HoudiniMCP ([0-9]{1,12})\.([0-9a-f]{32})\.([0-9a-f]{64})")
RESPONSE_SIGNATURE = "X-Houdini-MCP-Signature"
OPERATIONS = {
    "status", "node_types", "node_create", "node_inspect", "node_snapshot",
    "node_list", "node_set_parms", "node_connect", "node_set_flags", "node_delete", "node_cook",
    "scene_load", "scene_save", "hda_publish", "execute_python",
}


def failure(kind, message):
    return {"ok": False, "error": {"type": kind, "message": str(message)}}


def gui_token_path(port):
    return Path.home() / ".houdini-mcp" / f"gui-{port}.token"


def read_token(path):
    with Path(path).open(encoding="ascii") as stream:
        if os.name == "posix" and os.fstat(stream.fileno()).st_mode & 0o077:
            raise PermissionError("GUI token file must be private to its owner")
        token = stream.read(256).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token):
        raise ValueError("Invalid GUI token file")
    return token


def _load_or_create_token(path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return read_token(path)
    token = secrets.token_urlsafe(32)
    with os.fdopen(fd, "w", encoding="ascii") as stream:
        stream.write(token + "\n")
    return token


def _signature(key, direction, context, body):
    mac = hmac.new(key, direction + b"\0" + context.encode("ascii") + b"\0", "sha256")
    mac.update(body)
    return mac.hexdigest()


class GuiConnection:
    def __init__(self, port, token, timeout):
        self.port = port
        self.key = token.encode("ascii")
        self.timeout = timeout
        self.session_id = None

    def call(self, payload):
        body = json.dumps({**payload, "session_id": self.session_id}).encode("utf-8")
        if len(body) > MAX_REQUEST:
            return failure("ValueError", "GUI request exceeds the size limit")
        timestamp, nonce = int(time.time()), secrets.token_hex(16)
        signature = _signature(self.key, b"request", f"{self.port}:{timestamp}.{nonce}", body)
        connection = HTTPConnection(HOST, self.port, timeout=self.timeout)
        try:
            connection.request("POST", ENDPOINT, body=body, headers={
                "Host": f"{HOST}:{self.port}",
                "Authorization": f"HoudiniMCP {timestamp}.{nonce}.{signature}",
                "Content-Type": "application/json",
            })
            with connection.getresponse() as response:
                if response.status == 401:
                    return failure("AuthenticationError", "Houdini GUI rejected the token")
                if response.status != 200:
                    raise ConnectionError(f"Unexpected HTTP status from Houdini GUI: {response.status}")
                supplied = response.getheader(RESPONSE_SIGNATURE, "").encode("latin-1")
                encoded = response.read(MAX_RESPONSE + 1)
            if len(encoded) > MAX_RESPONSE:
                raise ConnectionError("GUI response exceeds the size limit")
            expected = _signature(self.key, b"response", signature, encoded).encode("ascii")
            if not hmac.compare_digest(supplied, expected):
                return failure("AuthenticationError", "Houdini GUI response signature did not match")
            result = json.loads(encoded)
            if not isinstance(result, dict) or type(result.get("ok")) is not bool:
                raise ConnectionError("Invalid response from Houdini GUI")
            return result
        finally:
            connection.close()


class _GuiHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass

    def _send(self, status, result, request_signature=None):
        encoded = json.dumps(result, ensure_ascii=False, default=str).encode("utf-8")
        if len(encoded) > MAX_RESPONSE:
            encoded = json.dumps(failure("ValueError", "GUI response exceeds the size limit")).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            if request_signature is not None:
                self.send_header(RESPONSE_SIGNATURE, _signature(
                    self.server.key, b"response", request_signature, encoded
                ))
            self.end_headers()
            self.wfile.write(encoded)
        except OSError:
            pass  # A client timeout does not cancel the operation in Houdini.

    def do_POST(self):
        if self.path != ENDPOINT or self.headers.get("Host") != f"{HOST}:{self.server.server_port}":
            self._send(404, failure("ValueError", "Unknown endpoint"))
            return
        match = AUTH_HEADER.fullmatch(self.headers.get("Authorization", ""))
        if match is None or abs(int(time.time()) - int(match[1])) > AUTH_WINDOW:
            self._send(401, failure("AuthenticationError", "Invalid or expired GUI signature"))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST:
                raise ValueError("Invalid GUI request size")
            body = self.rfile.read(length)
        except (OSError, ValueError) as exc:
            self._send(400, failure("ValueError", exc))
            return

        timestamp, nonce, signature = match.groups()
        if not self.server.authenticate(int(timestamp), nonce, signature, body):
            self._send(401, failure("AuthenticationError", "Invalid, expired, or repeated GUI signature"))
            return

        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("GUI request must be an object")
            op = payload.get("op")
            args = payload.get("args")
            if not isinstance(op, str) or op not in OPERATIONS or not isinstance(args, dict):
                raise ValueError("Invalid GUI operation or arguments")
        except (OSError, ValueError) as exc:
            self._send(200, failure("ValueError", exc), signature)
            return

        session_id = payload.get("session_id")
        if session_id != self.server.session_id and (session_id is not None or op != "status"):
            result = failure("SessionMismatchError", "Houdini GUI session changed; call reconnect")
        elif op == "execute_python" and not self.server.allow_python:
            result = failure("PermissionError", "Python execution is disabled in the Houdini GUI bootstrap")
        else:
            try:
                result = dispatch_in_gui({"op": op, "args": args})
            except Exception as exc:
                result = failure(type(exc).__name__, exc)
            if op == "status" and result["ok"]:
                result["result"].update(session_id=self.server.session_id, allow_python=self.server.allow_python)
        self._send(200, result, signature)


class _GuiServer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"

    def __init__(self, *args):
        self._request_slots = BoundedSemaphore(32)
        self._auth_lock = Lock()
        self._nonces = {}
        super().__init__(*args)

    def authenticate(self, timestamp, nonce, supplied, body):
        expected = _signature(self.key, b"request", f"{self.server_port}:{timestamp}.{nonce}", body)
        if not hmac.compare_digest(supplied, expected):
            return False
        with self._auth_lock:
            now = int(time.time())
            self._nonces = {used: expires for used, expires in self._nonces.items() if expires >= now}
            if abs(now - timestamp) > AUTH_WINDOW or nonce in self._nonces or len(self._nonces) >= MAX_NONCES:
                return False
            self._nonces[nonce] = timestamp + AUTH_WINDOW
            return True

    def process_request(self, request, client_address):
        if not self._request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()

    def stop(self):
        self.shutdown()
        self.server_close()


def start_gui_server(port=DEFAULT_PORT, token_file=None, allow_python=False):
    import hou

    if not hou.isUIAvailable():
        raise RuntimeError("GUI backend requires the Houdini UI")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be in [1, 65535]")
    path = Path(token_file) if token_file is not None else gui_token_path(port)
    if not path.is_absolute():
        raise ValueError("GUI token path must be absolute")
    server = _GuiServer((HOST, port), _GuiHandler)
    try:
        server.key = _load_or_create_token(path).encode("ascii")
        server.session_id = uuid4().hex
        server.allow_python = allow_python is True
        Thread(target=server.serve_forever, name="Houdini MCP GUI", daemon=True).start()
    except Exception:
        server.server_close()
        raise
    return server
