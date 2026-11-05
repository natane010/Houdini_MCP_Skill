import argparse
from mcp.server.fastmcp import FastMCP
from .bridge import Bridge


def create_server(bridge):
    mcp = FastMCP("Houdini MCP")

    @mcp.tool()
    def connection_status() -> dict:
        """Check connection and Houdini version."""
        return bridge.call("status")

    @mcp.tool()
    def reconnect() -> dict:
        """Reconnect the GUI bridge, or validate the batch executable."""
        return bridge.reconnect()

    @mcp.tool()
    def execute_python(code: str, hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> dict:
        """Execute Python in Houdini; assign `result` to return a representation. Opt-in required."""
        return bridge.call("execute_python", {"code": code}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_types(path: str, hip_input: str = "") -> dict:
        """List available child node type names for a parent network."""
        return bridge.call("node_types", {"path": path}, hip_input)

    @mcp.tool()
    def node_create(parent: str, type_name: str, name: str = "", hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> dict:
        """Create a node under parent."""
        return bridge.call("node_create", {"parent": parent, "type_name": type_name, "name": name}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_inspect(path: str, hip_input: str = "") -> dict:
        """Inspect a node, its inputs and parameters."""
        return bridge.call("node_inspect", {"path": path}, hip_input)

    @mcp.tool()
    def node_list(path: str, hip_input: str = "") -> dict:
        """List direct children (up to 1000)."""
        return bridge.call("node_list", {"path": path}, hip_input)

    @mcp.tool()
    def node_set_parms(path: str, values: dict, hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> dict:
        """Set scalar node parameters using a mapping of names to values."""
        return bridge.call("node_set_parms", {"path": path, "values": values}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_connect(path: str, source: str = "", input_index: int = 0, output_index: int = 0, hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> dict:
        """Connect source to path; empty source disconnects the input."""
        return bridge.call("node_connect", {"path": path, "source": source, "input_index": input_index, "output_index": output_index}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_delete(path: str, hip_input: str = "", hip_output: str = "", overwrite: bool = False) -> dict:
        """Delete a node."""
        return bridge.call("node_delete", {"path": path}, hip_input, hip_output, overwrite)

    @mcp.tool()
    def node_cook(path: str, hip_input: str = "") -> dict:
        """Force a node cook and return its errors and warnings."""
        return bridge.call("node_cook", {"path": path}, hip_input)

    @mcp.tool()
    def scene_load(path: str, discard_changes: bool = False) -> dict:
        """Load a scene; in batch this is only a validation because each call is isolated."""
        return bridge.call("scene_load", {"path": path, "discard_changes": discard_changes})

    @mcp.tool()
    def scene_save(path: str, overwrite: bool = False, hip_input: str = "") -> dict:
        """Save a scene, refusing existing files unless overwrite is true."""
        return bridge.call("scene_save", {"path": path, "overwrite": overwrite}, hip_input)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="Local Houdini MCP bridge")
    parser.add_argument("--backend", choices=["batch", "gui"], default="batch")
    parser.add_argument("--hython", default="")
    parser.add_argument("--port", type=int, default=18811)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--allow-python", action="store_true")
    args = parser.parse_args()
    if not 0 < args.timeout <= 3600 or not 1 <= args.port <= 65535:
        parser.error("timeout must be in (0, 3600], port in [1, 65535]")
    bridge = Bridge(args.backend, args.hython, args.port, args.timeout, args.allow_python)
    if args.backend == "gui":
        bridge.reconnect()
    try:
        create_server(bridge).run(transport="stdio")
    finally:
        bridge.close()

if __name__ == "__main__":
    main()
