# Project guidance

## Houdini scene work

- Build MCP-created HIP and HDA deliverables with standard Houdini operators, parameters, and wiring. Use `scene_save`, Batch `hip_output`, and `hda_publish` so the network is checked before writing.
- When an existing scene uses Wrangles, VEX expressions, Inline Code, or Python operators, use inspection to identify their behavior. Reuse compatible nodes or use standard nodes to replace them. In Batch, use `batch_edit_network` to complete the replacement and cook before saving. Obtain direction for topology changes outside the task.
- Use the current session's hip file and inspect the targeted node or subtree before editing. For an existing-node tuning request, preserve node paths, topology, and connections by default; change only requested fields and capture relevant before/after state.
- Use the standard `node_snapshot` tool for raw parameter values, unexpanded strings, expressions, keyframes, and wiring. Compare against the live scene before resuming older work notes.
- `houdini-scene-doctor` is for bounded diagnosis. It does not mutate or cook by default; its optional geometry report may cook when explicitly requested.
- Prefer creating nodes only when the task calls for new topology. Discover available node types and inspect parameter templates before using them.
- Use Batch for repeatable, GUI-independent operations. Each request runs in a fresh hython process; pass the previous returned `hip_output` as the next request's `hip_input`. Use GUI when the task depends on an open interactive scene or UI state.
- Save hip files and HDA libraries to the requested destination, or to a sensible project-local destination when output is part of the task. Do not overwrite existing files without explicit intent.
- Enable `--allow-python` only when a requested workflow needs the `execute_python` tool. The GUI bootstrap must also opt in. Keep artifact creation and saving on the validated MCP paths.

## Skills

Choose the task-specific Houdini skill when it is available in the active client's project skills directory:

- `houdini-scene-doctor`: read-only structural and diagnostic inspection.
- `houdini-vex-workbench`: diagnosis of existing VEX nodes and standard-node replacements.
- `houdini-cop-workbench`: COP/Copernicus image-network inspection and tuning.
- `houdini-hda-publisher`: publishing a selected network as a new HDA library.
- `houdini-iterate`: minimal changes to existing work, verification, and project decision records.
- `houdini-procedural`: general node and procedural network operations.

Codex explicitly invokes skills as `$skill-name`; Claude Code uses `/skill-name`. Do not hard-code client-specific MCP tool prefixes in shared instructions.

## Continuity

When the task requests a durable decision record or continuation, use the same project-local JSONL journal across clients and chats. If no path was specified, use the project `docs/` folder when it exists, otherwise the project root. Do not create a new parent folder for the journal. Record concise context, before/after state, evidence, decisions, and next action; AI-assisted work may note model/tool version, seed, input references, settings, outputs, and verification. A journal is project data, not automatic model memory. Treat old entries as historical context and verify the current scene before repeating an action.

If multiple clients connect to the same GUI scene, serialize scene mutations and inspect the scene after each client finishes.

## Client integration

`scripts/setup_clients.py` prints a dry-run plan by default. It writes project MCP configuration and copies project skills only when `--apply` is supplied. Keep settings project-scoped; do not modify user-level MCP configuration as part of ordinary scene work. See [docs/clients.md](docs/clients.md).
