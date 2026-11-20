---
name: houdini-vex-workbench
description: Diagnose existing VEX operators and identify standard Houdini nodes that can replace them.
---

# Houdini VEX Workbench

Use this skill when an existing HIP contains VEX code or when a save reports a code-based node.

1. Inspect the target with `node_snapshot` to capture its wiring, run-over settings, and raw code.
2. Identify the input and output attributes the node depends on. Cook the smallest relevant output only when validation is requested.
3. Map the behavior to standard Houdini nodes. Check the available operator types with `node_types`.
4. When replacement is in scope, reuse a suitable node already in the network or create a supported standard node. Preserve the external connections and the display and render targets. Compare output attributes and cook diagnostics.
5. In Batch, group creation, reconnection, cleanup, and cooking in one `batch_edit_network` request. In GUI, run the editing tools on the confirmed scene, then save through MCP.

See [standard node alternatives](references/recipes.md) for common SOP replacements.
