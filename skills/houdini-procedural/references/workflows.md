# Houdini MCP Workflows

This guide is self-contained so the skill remains useful when copied outside its source repository. MCP inputs below are arguments to the named tools; do not wrap them in the worker's internal `{"op": ..., "args": ...}` envelope.

## Shared workflow

1. Call `connection_status`; for GUI, verify the current hip path before edits. Use `reconnect` only when the GUI link is down.
2. In batch, provide the same `hip_input` to each call because each request starts a fresh hython process. Include a distinct `hip_output` on the mutation call whose result should persist. Do not assume mutation state carries over across calls.
3. Inspect parent contents with `node_list`, discover valid child operators with `node_types`, and inspect node parameter tuples with `node_inspect` before edits.
4. Cook the output and inspect errors, warnings, and messages. If a request times out or returns a partial-change note, inspect current state before another mutation.
5. Save only to the requested path. `scene_load` in GUI can discard unsaved work only with explicit `discard_changes: true`; existing save targets need `overwrite: true`.

## SOP network example

First check `/obj` with `node_list` and use an unused container name. For ordinary bridge tools, the JSON below is the argument object to `node_create`:

```json
{
  "parent": "/obj",
  "type_name": "geo",
  "name": "mcp_geo",
  "hip_input": "C:/work/source.hip",
  "hip_output": "C:/work/source_mcp.hip"
}
```

For batch, use the output of one step as the next step's input. Each call starts with a fresh Houdini process. Then use `node_types(path="/obj/mcp_geo", hip_input="C:/work/source_mcp.hip")` to confirm SOP types; create `box` and `null`, connect them, and set the null as display/render output. For fewer intermediate files, build and connect the network in a single Python call:

```python
parent = hou.node("/obj")
if parent.node("mcp_geo") is not None:
    raise RuntimeError("/obj/mcp_geo already exists; inspect it before choosing another path")
geo = parent.createNode("geo", "mcp_geo")
box = geo.createNode("box", "box1")
out = geo.createNode("null", "OUT")
out.setInput(0, box)
out.setDisplayFlag(True)
out.setRenderFlag(True)
out.cook(force=True)
result = {"container": geo.path(), "output": out.path(), "errors": list(out.errors()), "points": len(out.geometry().points()), "primitives": len(out.geometry().prims())}
```

Send this as `execute_python(code=...)`; in batch attach the source `hip_input` and intended new `hip_output` to that tool call. `execute_python` requires `--allow-python` and is arbitrary code execution.

## VEX wrangle and geometry checks

Create an Attribute Wrangle only after confirming `attribwrangle` appears in `node_types(path="/obj/mcp_geo")`. Use `node_inspect` on the node to verify its `snippet` parameter. Set VEX code, cook, and inspect diagnostics:

```json
{
  "path": "/obj/mcp_geo/attribwrangle1",
  "values": {"snippet": "@pscale = 0.1;"},
  "hip_input": "C:/work/source.hip",
  "hip_output": "C:/work/source_vex.hip"
}
```

This is an argument object for `node_set_parms`. Then call `node_cook(path="/obj/mcp_geo/attribwrangle1", hip_input="C:/work/source_vex.hip")`. `node_cook` reports errors, warnings, and messages even when Houdini's cook throws `hou.OperationFailed`.

To confirm geometry content, use this through `execute_python` after cooking in the same batch call, or adapt it to the current scene:

```python
n = hou.node("/obj/mcp_geo/attribwrangle1")
n.cook(force=True)
g = n.geometry()
result = {
    "points": len(g.points()),
    "primitives": len(g.prims()),
    "point_attributes": [
        {"name": a.name(), "data_type": str(a.dataType()), "size": a.size()}
        for a in g.pointAttribs()
    ],
    "pscale_sample": [p.attribValue("pscale") for p in g.points()[:5]]
        if g.findPointAttrib("pscale") else None,
    "errors": list(n.errors()),
    "warnings": list(n.warnings())
}
```

Treat missing attributes or unexpected data types as evidence to revise the wrangle. VEX runs in the wrangle; `execute_python` runs HOM/Python and does not evaluate VEX snippets.

## HDA from a subnet

HDA creation writes an asset library and may install a node type in Houdini. Inspect the subnet and its contents, choose a unique operator name and a new `.hda` path, and ensure that path does not already exist. Execute only when HDA creation and the exact output path are within the user's requested scope. This example wraps `/obj/mcp_geo` as a new asset, preserving the existing subnet node type with `change_node_type=False`:

```python
import os
subnet = hou.node("/obj/mcp_geo")
if subnet is None or not subnet.canCreateDigitalAsset():
    raise RuntimeError("Target subnet cannot create a digital asset")
hda_path = r"C:/work/assets/mcp_geo_tool.hda"
if os.path.exists(hda_path):
    raise FileExistsError("Choose a new HDA path; existing library will not be overwritten")
original_type = subnet.type().name()
subnet.createDigitalAsset(
    name="studio::mcp_geo_tool::1.0",
    hda_file_name=hda_path,
    description="MCP Geo Tool",
    min_num_inputs=0,
    max_num_inputs=0,
    change_node_type=False,
    create_backup=True
)
definitions = hou.hda.definitionsInFile(hda_path)
definition = next(
    (d for d in definitions if d.nodeTypeName() == "studio::mcp_geo_tool::1.0"),
    None
)
if definition is None:
    raise RuntimeError("Expected HDA definition was not written to the new library")
result = {
    "node": subnet.path(),
    "source_type": original_type,
    "source_type_after_create": subnet.type().name(),
    "hda_file": definition.libraryFilePath(),
    "type_name": definition.nodeTypeName()
}
```

Run through `execute_python` with `--allow-python`. Prefer a new HDA path and unique versioned type name. Do not overwrite an existing library or change a shared installation path unless the user explicitly requested that destination. After creation, verify the file exists and inspect the installed type before reporting success.

SideFX references: [hou.OpNode.createDigitalAsset](https://www.sidefx.com/docs/houdini/hom/hou/OpNode.html), [hou.HDADefinition](https://www.sidefx.com/docs/houdini/hom/hou/HDADefinition.html), and [hou.Geometry](https://www.sidefx.com/docs/houdini/hom/hou/Geometry.html).
