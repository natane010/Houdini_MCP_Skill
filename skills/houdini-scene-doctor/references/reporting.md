# Scene Doctor Reporting

The helper traverses a bounded subtree and returns JSON-safe data. Use a specific root such as `/obj/geo1` for a targeted question. Increase `max_nodes` only when the report is truncated and the larger scope is useful. Do not claim the whole scene is clean when inspection was capped.

`include_geometry=False` is the default for scene structure questions and does not ask Houdini for geometry. The implementation may still need Houdini to load the selected hip in batch mode. Set `include_geometry=True` only when geometry counts answer the user's question: it may trigger cooks and the helper marks this request in its report. If geometry was not requested, never cook to fill a gap.

The report contains `root`, a bounded `nodes` list, `truncated`, `geometry_requested`, and `warnings`. Each node entry includes `path`, `type`, `inputs`, existing `errors` and `warnings`, parameter `expressions` with source text/language, `expressions_truncated`, and `inspection_errors`. If geometry was explicitly requested for a SOP node, its `geometry` object contains point and primitive counts. The expression source is reported as text; it is not evaluated by this helper.

The helper does not return evaluated parameter values. When a diagnosis depends on a particular parameter, use the bridge's read-only `node_inspect` for that node and cite which tool produced each finding.

Use the helper output to separate:

- **Observed:** node paths/types, existing connections, expression source (not its evaluated value), diagnostics already present, and any returned geometry statistics. Add parameter values only when separately inspected.
- **Likely cause:** an inference supported by those observations. State it as a hypothesis.
- **Next check:** a read-only targeted inspection that would distinguish remaining hypotheses.

Do not modify nodes, invoke `node_cook`, run scene-authored Python/VEX/HScript, or save from this skill. If a repair is needed, switch to an appropriate editing workflow only after the user asks for a fix.
