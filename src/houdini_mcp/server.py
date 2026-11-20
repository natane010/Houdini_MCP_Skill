import argparse
import json
from pathlib import Path
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from .bridge import Bridge
from .gui import DEFAULT_PORT


def _tool_result(payload, *, is_error=False):
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structuredContent=payload,
        isError=is_error or not payload["ok"],
    )


def create_server(bridge):
    mcp = FastMCP("Houdini MCP")

    def call(op, *args):
        payload = bridge.call(op, *args)
        cook_failed = op == "node_cook" and payload.get("result", {}).get("cooked") is False
        return _tool_result(payload, is_error=cook_failed)

    @mcp.tool()
    def connection_status() -> CallToolResult:
        """Check the Houdini version and HIP path. GUI also returns the session ID and unsaved status."""
        return call("status")

    @mcp.tool()
    def reconnect() -> CallToolResult:
        """Authenticate and identify the GUI session, or validate the batch executable."""
        return _tool_result(bridge.reconnect())

    if bridge.allow_python:
        @mcp.tool()
        def execute_python(code: str, hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> CallToolResult:
            """Execute Python in Houdini; assign `result` to return a representation."""
            return call("execute_python", {"code": code}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_types(path: str, hip_input: str = "") -> CallToolResult:
        """List available child node type names for a parent network."""
        return call("node_types", {"path": path}, hip_input)

    @mcp.tool()
    def node_create(parent: str, type_name: str, name: str = "", hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> CallToolResult:
        """Create a node under parent."""
        return call("node_create", {"parent": parent, "type_name": type_name, "name": name}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_inspect(path: str, hip_input: str = "") -> CallToolResult:
        """Inspect a node, its inputs and parameters."""
        return call("node_inspect", {"path": path}, hip_input)

    @mcp.tool()
    def node_snapshot(path: str, parm_names: list[str] | None = None, max_parms: int = 200, hip_input: str = "") -> CallToolResult:
        """Capture raw parameters, expressions, keys and wiring without evaluating the node."""
        return call("node_snapshot", {"path": path, "parm_names": parm_names, "max_parms": max_parms}, hip_input)

    @mcp.tool()
    def node_list(path: str, hip_input: str = "") -> CallToolResult:
        """List direct children (up to 1000)."""
        return call("node_list", {"path": path}, hip_input)

    @mcp.tool()
    def node_set_parms(path: str, values: dict, hip_input: str = "", hip_output: str = "", overwrite: bool = False, replace_driven: bool = False) -> CallToolResult:
        """Set local parameters. Replacing references, expressions or keys requires replace_driven."""
        return call("node_set_parms", {"path": path, "values": values, "replace_driven": replace_driven}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_connect(path: str, source: str = "", input_index: int = 0, output_index: int = 0, hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> CallToolResult:
        """Connect source to path; empty source disconnects the input."""
        return call("node_connect", {"path": path, "source": source, "input_index": input_index, "output_index": output_index}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_set_flags(path: str, display: bool | None = None, render: bool | None = None,
                       hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> CallToolResult:
        """Set an output node's display or render flag."""
        return call("node_set_flags", {"path": path, "display": display, "render": render},
                    hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_delete(path: str, hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> CallToolResult:
        """Delete a node."""
        return call("node_delete", {"path": path}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_cook(path: str, hip_input: str = "") -> CallToolResult:
        """Force a node cook and return its errors and warnings."""
        return call("node_cook", {"path": path}, hip_input)

    @mcp.tool()
    def scene_load(path: str, discard_changes: bool = False) -> CallToolResult:
        """Load a scene; in batch this is only a validation because each call is isolated."""
        return call("scene_load", {"path": path, "discard_changes": discard_changes})

    @mcp.tool()
    def scene_save(path: str, overwrite: bool = False, hip_input: str = "") -> CallToolResult:
        """Save a scene, refusing existing files unless overwrite is true."""
        return call("scene_save", {"path": path, "overwrite": overwrite}, hip_input)

    @mcp.tool()
    def hda_publish(path: str, output_path: str, type_name: str, description: str = "", hip_input: str = "") -> CallToolResult:
        """Publish a standard-node network as a new HDA library without converting its source."""
        return call("hda_publish", {"path": path, "output_path": output_path, "type_name": type_name,
                                    "description": description}, hip_input)

    if bridge.backend == "batch":
        @mcp.tool()
        def batch_edit_network(steps: list[dict], hip_input: str, hip_output: str, overwrite: bool = False) -> CallToolResult:
            """Apply up to 100 node changes in one HIP. Each step has op and args. Save the completed network."""
            return call("batch_edit_network", {"steps": steps}, hip_input, hip_output, overwrite)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="Local Houdini MCP bridge")
    parser.add_argument("--backend", choices=["batch", "gui"], default="batch")
    parser.add_argument("--hython", default="")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--gui-token-file", type=Path)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--allow-python", action="store_true")
    args = parser.parse_args()
    if not 0 < args.timeout <= 3600 or not 1 <= args.port <= 65535:
        parser.error("timeout must be in (0, 3600], port in [1, 65535]")
    if args.gui_token_file is not None and (args.backend != "gui" or not args.gui_token_file.is_absolute()):
        parser.error("--gui-token-file requires the GUI backend and an absolute path")
    bridge = Bridge(args.backend, args.hython, args.port, args.timeout, args.allow_python, args.gui_token_file)
    if args.backend == "gui":
        connected = bridge.reconnect()
        if connected["ok"]:
            status = connected["result"]
            identity = {field: status[field] for field in ("hip_file", "unsaved_changes", "session_id")}
            print(json.dumps({"houdini_gui": identity}, ensure_ascii=False), file=sys.stderr, flush=True)
    try:
        create_server(bridge).run(transport="stdio")
    finally:
        bridge.close()

if __name__ == "__main__":
    main()
