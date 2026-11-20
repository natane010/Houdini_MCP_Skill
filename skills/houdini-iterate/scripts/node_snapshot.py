"""Capture one Houdini node's unevaluated parameters and wiring for comparison."""


def snapshot_node(path, parm_names=None, max_parms=200):
    """Return a JSON-safe snapshot without evaluating parameters or cooking nodes.

    parm_names may contain scalar names or tuple names (e.g. ``t``). With
    None, record up to max_parms scalar parameters in Houdini's order.
    """
    import hou
    if not isinstance(max_parms, int) or isinstance(max_parms, bool) or not 1 <= max_parms <= 1000:
        raise ValueError('max_parms must be an integer from 1 to 1000')
    if parm_names is not None and (not isinstance(parm_names, (list, tuple)) or any(not isinstance(n, str) or not n for n in parm_names)):
        raise ValueError('parm_names must be a list of nonempty strings or None')
    node = hou.node(path)
    if node is None:
        raise ValueError('Node does not exist: ' + str(path))

    def path_or_none(item):
        return item.path() if item is not None else None

    def wire(connection):
        return {'source': path_or_none(connection.inputNode()), 'source_item': path_or_none(connection.inputItem()),
                'source_output_index': connection.outputIndex(),
                'destination': path_or_none(connection.outputNode()), 'destination_item': path_or_none(connection.outputItem()),
                'destination_input_index': connection.inputIndex()}

    report = {'path': node.path(), 'session_id': node.sessionId(), 'type': node.type().name(),
              'category': node.type().category().name(), 'frame': hou.frame(),
              'inputs': [wire(c) for c in node.inputConnections()],
              'outputs': [wire(c) for c in node.outputConnections()],
              'parms': [], 'missing_parms': [], 'truncated': False}
    report['flags'] = {}
    for flag, name in (('display', 'isDisplayFlagSet'), ('render', 'isRenderFlagSet')):
        read_flag = getattr(node, name, None)
        if read_flag is not None:
            report['flags'][flag] = read_flag()
    selected = []
    seen = set()
    if parm_names is None:
        selected = list(node.parms())
    else:
        for name in parm_names:
            tuple_parm = node.parmTuple(name)
            scalar = node.parm(name)
            matches = list(tuple_parm) if tuple_parm is not None else ([scalar] if scalar is not None else [])
            if not matches:
                report['missing_parms'].append(name)
            for parm in matches:
                if parm.name() not in seen:
                    selected.append(parm)
                    seen.add(parm.name())
    report['truncated'] = len(selected) > max_parms
    for parm in selected[:max_parms]:
        item = {'name': parm.name(), 'template_type': str(parm.parmTemplate().type()),
                'raw_value': None, 'unexpanded_string': None, 'keyframes': [],
                'keyframes_truncated': False, 'unsupported': []}
        try:
            keys = parm.keyframes()
            item['keyframes_truncated'] = len(keys) > 1000
            for key in keys[:1000]:
                # asJSON captures stored frame, expression, language and tangent
                # data without computing the parameter's value.
                item['keyframes'].append(key.asJSON(save_keys_in_frames=True))
        except (hou.Error, TypeError) as exc:
            item['unsupported'].append('keyframes: ' + str(exc))
        try:
            item['raw_value'] = parm.rawValue()
        except hou.Error as exc:
            item['unsupported'].append('raw_value: ' + str(exc))
        if parm.parmTemplate().type() == hou.parmTemplateType.String and not item['keyframes']:
            try:
                item['unexpanded_string'] = parm.unexpandedString()
            except hou.Error as exc:
                item['unsupported'].append('unexpanded_string: ' + str(exc))
        report['parms'].append(item)
    return report
