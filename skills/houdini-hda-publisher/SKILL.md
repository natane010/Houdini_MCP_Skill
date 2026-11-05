---
name: houdini-hda-publisher
description: Publish a selected Houdini network as a new HDA library using the bundled collision-checking helper; use only for an explicitly requested HDA deliverable.
---

# Houdini HDA Publisher

Use this skill when the requested deliverable is a new Houdini Digital Asset library (`.hda`). It invokes the bundled `publish_hda` helper for a selected node and verifies the definition. The helper refuses existing output files and type-name collisions, and preserves the source node's type.

## Publish workflow

1. Confirm the exact source node path, new `.hda` output path, namespaced/versioned `type_name`, and user-visible description. Inspect the source network first and ensure it is the intended asset boundary.
2. Check that the chosen file path and operator type are new. The helper checks both and refuses collisions; select another path or type name if either is taken.
3. Run `publish_hda` via MCP `execute_python` using the skill's helper and exact requested values. Python execution requires `--allow-python`.
4. Verify that the returned HDA definition has the expected library path and type name. Report the output path and source node path.

The helper requires an absolute output path in an existing directory, a supported HDA/OTL library extension, a new library base name, and a free operator type name. It creates a new library definition, loads it into the current HIP file context, and does not rename the source node. This is a file-producing operation; do not imply that the enclosing hip file was saved. For batch, pass `hip_input` to load the scene and `hip_output` only if the user wants hip changes saved separately. Use the requested output path, or select a sensible new path in the project when publication is within scope; do not overwrite an existing library.

## Helper invocation

The helper is `scripts/publish_hda.py` inside this skill folder and exposes `publish_hda(node_path, output_path, type_name, description='')`:

```python
import runpy
publish = runpy.run_path(r"C:/path/to/skills/houdini-hda-publisher/scripts/publish_hda.py")["publish_hda"]
result = publish(
    node_path="/obj/geo1/asset_subnet",
    output_path="C:/work/assets/studio_tool_1_0.hda",
    type_name="studio::tool::1.0",
    description="Studio Tool"
)
```

Replace the script path with the absolute path of the installed skill folder. The helper returns `output_path`, `type_name`, `category`, `source_node`, `source_type`, and `verified`. The bridge formats that JSON-safe value as a representation string in `result.value`. A direct headless invocation is `hython publish_hda.py --hip PATH --node /obj/... --output ABSOLUTE_PATH --type-name NAME [--description TEXT]`; it prints JSON. Read [references/publishing.md](references/publishing.md) for naming, boundaries, and failure handling.
