"""Load with runpy in Houdini's Python Shell, then call start_server()."""
from pathlib import Path
import sys


def start_server(port=18811, token_file=None, allow_python=False):
    source = str(Path(__file__).resolve().parents[1] / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from houdini_mcp.gui import start_gui_server

    return start_gui_server(port, token_file, allow_python)
