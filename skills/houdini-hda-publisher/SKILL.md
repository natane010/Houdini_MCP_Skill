---
name: houdini-hda-publisher
description: Publish a selected standard Houdini network as a new HDA library through MCP.
---

# Houdini HDA Publisher

1. Inspect the selected network and confirm the source path, new absolute library path, namespaced and versioned operator type, and description.
2. Call `hda_publish`. The tool checks the network for code-based operators and checks the file path and type name for collisions.
3. Verify `result.verified` and report the actual `result.output_path` and source node path.

```json
{"path":"/obj/geo1/asset_subnet","output_path":"C:/work/assets/studio_tool_1_0.hda","type_name":"studio::tool::1.0","description":"Studio Tool","hip_input":"C:/work/source.hip"}
```

Pass `hip_input` in Batch and omit it for the current GUI scene. Use an existing parent directory. The tool writes the asset library and preserves the source node type. It is available with the default Python execution setting. See [publishing notes](references/publishing.md) for boundaries and failure handling.
