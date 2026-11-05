"""Run in Houdini GUI's Python shell. This server grants arbitrary local code access."""
import hrpyc
import threading
from types import SimpleNamespace

options = SimpleNamespace(host="127.0.0.1", port=18811, authenticator=None,
                          registrar=None, auto_register=False, quiet=True, logfile=None)
threading.Thread(target=hrpyc._serve_threaded, args=(options,), daemon=True).start()
