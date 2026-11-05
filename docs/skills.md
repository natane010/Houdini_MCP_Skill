# Houdini workflow skills

This repository includes task-specific skills for Codex and Claude Code. They are repository assets; the setup helper copies them only into project-local discovery folders.

| Skill | Use it for | Invocation |
| --- | --- | --- |
| `houdini-procedural` | General node creation, procedural network edits, cooking, and persistence guidance | `$houdini-procedural` |
| `houdini-scene-doctor` | Read-only, bounded diagnosis of an existing scene subtree; no edits and no implicit cooks | `$houdini-scene-doctor` |
| `houdini-vex-workbench` | Authoring and debugging SOP wrangle VEX and validating attribute classes/types | `$houdini-vex-workbench` |
| `houdini-hda-publisher` | Publishing a selected node network as a new HDA library | `$houdini-hda-publisher` |
| `houdini-cop-workbench` | COP/Copernicus image processing and version-aware network tuning | `$houdini-cop-workbench` |
| `houdini-iterate` | Iterative scene work with before/after evidence and concise decision records | `$houdini-iterate` |

COP workbench covers Houdini's COP/Copernicus networks; it does not call an AI image-generation service. For AI-assisted Houdini production, use `houdini-iterate` to capture the model/tool and version, seed when available, referenced inputs, key settings, outputs, verification, and reasons for important decisions.

## Use a repository skill

Codex discovers project skills from `.agents/skills/<skill-name>/`; Claude Code discovers them from `.claude/skills/<skill-name>/`. Run `scripts/setup_clients.py` in dry-run mode to preview project-local MCP configuration and skill copies, then add `--apply` to apply the plan. Keep `SKILL.md`, `references/`, and `scripts/` together. Personal skills can instead use Codex's `~/.agents/skills/` or Claude Code's `~/.claude/skills/`, but the setup helper intentionally does not write there. See [clients.md](clients.md) for client-specific MCP settings, project trust, invocation syntax, and cloud/desktop boundaries.

When tuning an existing network, start from the relevant skill, inspect the current node parameters and wiring, and preserve that topology by default. Record the requested before/after changes rather than replacing a working network wholesale.

The scene doctor and HDA publisher use bundled helper scripts through `execute_python`. The scripts are scoped to their specific task: scene inspection is read-only and does not cook by default; requesting geometry counts may cook. HDA publishing creates a new library and refuses path/type collisions. Both require the bridge to start with `--allow-python`. See each skill's `SKILL.md` for exact invocation and backend persistence details.

### Helper interfaces

- Scene inspection: `inspect_scene(root_path='/obj', max_nodes=200, include_geometry=False)` returns `root`, bounded `nodes`, `truncated`, `geometry_requested`, and `warnings`. Nodes include paths, types, input paths, existing errors/warnings, expression source text, truncation flags, and inspection errors. `include_geometry=True` may cook. Direct hython CLI: `inspect_scene.py --hip PATH [--root /obj] [--max-nodes 200] [--include-geometry]`.
- HDA publication: `publish_hda(node_path, output_path, type_name, description='')` returns `output_path`, `type_name`, `category`, `source_node`, `source_type`, and `verified`. It requires an absolute path in an existing directory and a new library base/type name. Direct hython CLI: `publish_hda.py --hip PATH --node /obj/... --output ABS --type-name NAME [--description TEXT]`.
- Node snapshot: `snapshot_node(path, parm_names=None, max_parms=200)` records selected parameters' raw values, unexpanded strings, expressions and keyframes, inputs/outputs, and scene context. It does not evaluate expressions, cook, or edit. Invoke with `runpy.run_path(absolute_path_to_node_snapshot_py)['snapshot_node'](...)` from Houdini Python/hython, or through `execute_python` when enabled; ordinary Python without Houdini's `hou` module cannot call it.
- Project journal: standard Python `append_record(path, record)` appends one JSONL record and `read_records(path)` returns its records. The record requires `run_id`, `goal`, `context`, `before`, `changed`, `after`, `evidence`, `decisions`, and `next_action`. The parent directory must already exist.

## Continuing work across chats

Houdini decisions are not automatically retained as project memory between Codex chats. When recording is requested or continuity is in scope, use `$houdini-iterate` with the specified journal path. If none is specified, state a project-local absolute path: `<project>/docs/houdini-journal.jsonl` when `docs` exists, otherwise `<project>/houdini-journal.jsonl`. Its parent directory must already exist. At the start of a later chat, read that same JSONL file and treat entries as historical evidence, then verify them against the current scene and request.

Journal only the information needed to reproduce decisions. For AI-assisted generation that can include model/tool and version, seed when available, input asset references, key settings, output paths, verification, and decision rationale. Keep only a minimal prompt excerpt or prompt reference; mark unknown settings as unknown. This explicit JSONL is a project file, not Codex memory or a global config.
