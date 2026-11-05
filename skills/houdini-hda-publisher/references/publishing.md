# HDA Publishing Notes

## Choose the asset boundary

Inspect the candidate subnet and its contents before publishing. The selected node becomes the HDA definition's source network; avoid including unrelated nodes. Use a namespaced, versioned operator name such as `studio::scatter_tool::1.0`, and a new descriptive `.hda` filename such as `studio_scatter_tool_1_0.hda` (Windows filenames cannot contain `:`). If no output path was specified and publication is in scope, choose a sensible new path inside the project and an existing directory.

## Helper guarantees

`publish_hda(node_path, output_path, type_name, description='')` requires an absolute path whose parent directory exists and a supported HDA/OTL suffix. It refuses existing libraries with the same basename and node-type collisions, creates the digital asset with `change_node_type=False`, installs it in the current HIP file context, and verifies the written definition by reading definitions from the output library. Its JSON-safe result has `output_path`, `type_name`, `category`, `source_node`, `source_type`, and `verified`. Do not manually edit `houdini.env`, global package paths, or shared libraries as part of this skill.

## Failure handling

If the helper reports an existing path or type collision, keep the existing artifact intact and choose a genuinely new destination/name only if the user has provided or authorized it. If the bridge times out or reports an unknown result, inspect whether the output file exists before retrying. Do not rerun publication blindly.

The helper publishes the HDA library, not an enclosing `.hip` file. Batch-scene persistence remains controlled by the bridge's explicit `hip_input` and `hip_output` arguments.
