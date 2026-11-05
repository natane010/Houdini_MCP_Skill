---
name: houdini-scene-doctor
description: Diagnose an existing Houdini scene or procedural subtree without editing nodes or initiating cooks; use for bounded structural, parameter, and geometry-state inspection.
---

# Houdini Scene Doctor

Use this skill to investigate an existing Houdini scene without changing it. By default it reports bounded structural facts without initiating cooks; it does not fix the scene, create nodes, change parameters, or save.

## Workflow

1. Use the current session's hip path when the target is clear. In GUI, use `connection_status` to confirm it; in batch, pass that hip file as `hip_input`. Ask only if the scene or subtree is genuinely ambiguous.
2. Call the helper with a narrow root, a sensible `max_nodes` cap, and `include_geometry=False`. Enable `include_geometry=True` only when the user asks for geometry counts; that option may cause Houdini to cook geometry.
3. Correlate reported node paths, types, inputs, expression source, and existing diagnostics. The helper does not report evaluated parameter values; use read-only `node_inspect` for specific values. Distinguish observed facts from hypotheses; the helper's report is bounded and may omit nodes beyond its cap.
4. Report the most relevant findings with paths and next steps. Do not make a repair in this workflow. Offer follow-up edits only if requested.

## Helper invocation

The helper is `scripts/inspect_scene.py` inside this skill folder and exposes `inspect_scene(root_path='/obj', max_nodes=200, include_geometry=False)`. With MCP `execute_python` enabled, run:

```python
import runpy
inspect = runpy.run_path(r"C:/path/to/skills/houdini-scene-doctor/scripts/inspect_scene.py")["inspect_scene"]
result = inspect(root_path="/obj/geo1", max_nodes=200, include_geometry=False)
```

Replace the script path with the absolute path of the installed skill folder. `execute_python` requires `--allow-python`. The bridge formats the returned Python object as a representation string in `result.value`; read it as a report, not as a second executable payload.

Batch calls start a fresh hython process. Pass `hip_input` to select the scene. No `hip_output` is needed because this skill does not change the hip. A direct headless invocation is `hython inspect_scene.py --hip PATH [--root /obj] [--max-nodes 200] [--include-geometry]`; it prints JSON. The geometry flag may cook.

For detailed fields and edge cases, read [references/reporting.md](references/reporting.md).
