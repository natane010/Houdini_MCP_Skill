# HDA Publishing Notes

## Choose the asset boundary

Inspect the candidate subnet and its contents before publishing. The selected node becomes the HDA definition's source network; avoid including unrelated nodes. Use a namespaced, versioned operator name such as `studio::scatter_tool::1.0`, and a new descriptive `.hda` filename such as `studio_scatter_tool_1_0.hda` (Windows filenames cannot contain `:`). If no output path was specified and publication is in scope, choose a sensible new path inside the project and an existing directory.

## Helper guarantees

`hda_publish` requires an absolute path whose parent directory exists and a supported HDA/OTL suffix. It checks the asset network before writing, rejects path and type collisions, and verifies the definition in the output library. Its result has `output_path`, `type_name`, `category`, `source_node`, `source_type`, and `verified`. Use `error.code_nodes` to locate any code-based operators that need a standard-node replacement.

## Failure handling

If the helper reports an existing path or type collision, keep the existing artifact intact and choose a genuinely new destination/name only if the user has provided or authorized it. If the bridge times out or reports an unknown result, inspect whether the output file exists before retrying. Do not rerun publication blindly.

Pass `hip_input` for Batch publication. If the project also needs a separate HIP file, save it with `scene_save`.
