---
name: houdini-procedural
description: Build, inspect, and debug Houdini procedural networks through the local Houdini MCP bridge, including SOP workflows and explicit scene persistence.
---

# Houdini Procedural Work

Use this skill when a task asks you to create or modify Houdini nodes, inspect a scene, run a cook, or debug a procedural network through Houdini MCP.

## Working guidance

- Read [references/workflows.md](references/workflows.md) for standard SOP and HDA procedures. Build deliverables with standard operators and wiring. Use `hda_publish` for HDA libraries and the MCP save tools for HIP files.
- Check connection and scene state before making changes. Inspect existing nodes before choosing paths or names.
- When the task is to tune an existing node, record its current parameters and input connections first. Make the smallest requested change and preserve network topology unless rebuilding it was requested; summarize the before/after values and wiring.
- Build networks in a dedicated, non-conflicting container. Validate node types and parameter names with `node_inspect` before setting parameters.
- Cook the smallest relevant node, inspect errors and warnings, and verify resulting state before reporting completion.
- Treat `execute_python` as arbitrary code execution. It requires the bridge's `--allow-python` option and is not sandboxed; use it only when the requested work needs HOM/Python and the option is enabled.
- Batch calls use isolated processes. Supply `hip_input` and an explicit `hip_output` when persistence is requested; do not assume in-memory changes survive a call.
- Save only to the user-specified destination. Existing files require explicit overwrite intent. Node deletion, scene loading, and HDA definition changes can be destructive; verify the exact target and preserve the user's stated scope.
- GUI RPC is unauthenticated local access. Do not expose it to untrusted networks. A GUI timeout does not cancel an in-progress operation; inspect the scene before taking another mutation action and never blindly retry it.

For bridge-specific backend behavior and trust boundaries, consult the repository's `docs/architecture.md` when available.
