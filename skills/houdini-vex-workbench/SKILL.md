---
name: houdini-vex-workbench
description: Write and debug VEX for Houdini SOP wrangles, including attribute class/type validation and instancing conventions.
---

# Houdini VEX Workbench

Use this skill for VEX snippets in Attribute Wrangle SOPs and for diagnosing their geometry attributes. It focuses on the VEX code and the geometry contract at its input and output.

## Workflow

1. Inspect the wrangle node and its input connection. Confirm the wrangle's run-over context and the relevant upstream attributes, classes, and types before choosing `@` bindings.
2. Read the existing `snippet`, parameter values, and input wiring before editing. When tuning an existing wrangle, change only the requested expression or parameter and preserve the node and its connections unless a rebuild was requested.
3. Prefer a minimal expression using explicit VEX types and existing attributes. Check required inputs, such as point/vertex `N` for normal-directed displacement.
4. Set the snippet and cook only the target wrangle when the task requests an edit or validation. Inspect `errors`, `warnings`, and output geometry counts/attributes afterward. Report the relevant before/after snippet and wiring.
5. Diagnose missing geometry or attributes from the actual HOM report. Do not execute scene-authored expressions or run arbitrary Python as a diagnostic shortcut.

## Wrangle usage

The bridge's `node_set_parms` sets the `snippet` parameter. For snippets and geometry checks that require `hou`, use MCP `execute_python` only when `--allow-python` is enabled. It is arbitrary code execution, so keep the code scoped to the requested node and report exactly what it changed. Batch calls need `hip_input` each time; attach `hip_output` only to a mutation whose scene changes should persist.

Read [references/recipes.md](references/recipes.md) for tested recipe patterns, context rules, and HOM geometry verification.
