# Houdini MCP Workflows

MCP examples below are the arguments to the named tool.

## Shared workflow

1. Call `connection_status`. In GUI, verify the HIP path and session ID before editing.
2. In Batch, pass the actual `hip_output` from each edit as the next call's `hip_input`. Each request starts a fresh Houdini process.
3. Use `node_list` to inspect the parent, `node_types` to discover operators, and `node_snapshot` to capture wiring and raw parameter state. Keep unrelated nodes and wiring in place.
4. Build the network with standard Houdini nodes. Use Attribute Create for constants, Attribute Randomize for variation, Group Create for selections, and Attribute Promote for class conversion.
5. Cook the output with `node_cook`. Check errors and warnings before saving. After a timeout, reconnect and inspect the current state before editing again.
6. Save HIP files through `scene_save` or Batch `hip_output`. Publish assets through `hda_publish`. The bridge reports code-based operators under `error.code_nodes` if an output is blocked.

## SOP network example

Use `node_create` to add an unused Geometry container under `/obj`.

```json
{"parent":"/obj","type_name":"geo","name":"mcp_geo","hip_input":"C:/work/source.hip","hip_output":"C:/work/mcp_01_geo.hip"}
```

Create a Box (`box`) and a Null (`null`) named `OUT` inside the container using separate calls. Pass a new `hip_output` to each call and use the actual returned path in the next `hip_input`. Use these arguments with `node_connect`.

```json
{"path":"/obj/mcp_geo/OUT","source":"/obj/mcp_geo/box1","hip_input":"C:/work/mcp_03_null.hip","hip_output":"C:/work/mcp_04_connected.hip"}
```

Cook `/obj/mcp_geo/OUT` with the returned connected HIP as `hip_input`. Use that same HIP to publish or save the verified scene. For GUI calls, omit the Batch file arguments and work in the confirmed live HIP.

## HDA from a subnet

Use `hda_publish` with a selected network, an absolute path to a new library, and a unique namespaced operator type. For Batch, pass the HIP that contains the selected network.

```json
{"path":"/obj/mcp_geo","output_path":"C:/work/assets/mcp_geo_tool.hda","type_name":"studio::mcp_geo_tool::1.0","description":"MCP Geo Tool","hip_input":"C:/work/mcp_04_connected.hip"}
```

Check `result.verified` and `result.output_path`. Publication keeps the source node type intact. Use `scene_save` when a HIP file is also part of the deliverable.
