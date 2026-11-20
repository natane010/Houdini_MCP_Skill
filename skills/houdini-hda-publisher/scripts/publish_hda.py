"""Create a new HDA from a Houdini node without converting the source node."""
import argparse
import json
import os
from pathlib import Path


class CodeNodeError(ValueError):
    def __init__(self, nodes):
        self.code_nodes = nodes
        super().__init__("Use standard Houdini nodes and wiring instead of code nodes: "
                         + ", ".join(item['path'] for item in nodes))


def code_node_reason(category, base):
    """Identify operator types whose purpose is to run authored VEX or Python."""
    base = base.lower()
    if base.startswith('python'):
        return 'Python operator'
    if ('wrangle' in base or base in {'attribexpression', 'groupexpression',
                                    'bakevex', 'vexfilter', 'vexgenerate', 'gen_cvex'}
            or (base == 'vex' and category in {'Sop', 'Chop'})
            or (category == 'Vop' and base == 'inline')):
        return 'VEX operator'
    return None


def code_node_finding(category, type_name, base, path, reason):
    alternatives = []
    if category.name() == 'Sop':
        requested = {
            'groupexpression': ('groupcreate', 'groupcombine', 'blast'),
            'volumewrangle': ('volumemix', 'vdbcombine', 'volumeanalysis'),
            'volumewranglecore': ('volumemix', 'vdbcombine', 'volumeanalysis'),
        }.get(base.lower(), ('attribcreate', 'attribrandomize', 'attribadjustfloat',
                             'attribpromote', 'groupcreate', 'transform'))
        available = category.nodeTypes()
        for name in requested:
            node_type = available.get(name)
            if node_type is None:
                node_type = next((item for item in available.values() if item.nameComponents()[2] == name), None)
            if node_type is not None:
                alternatives.append({'type_name': node_type.name(), 'label': node_type.description()})
    return {'path': path, 'type': type_name, 'category': category.name(),
            'reason': reason, 'candidate_types': alternatives}


def _stock_definition(definition, install_dir):
    source = Path(definition.libraryFilePath())
    return source.is_absolute() and install_dir is not None and source.resolve().is_relative_to(install_dir)


def _code_section(definition):
    options = definition.extraFileOptions()
    for name, section in definition.sections().items():
        if (name.lower() in {'pythonmodule', 'pythoncook', 'vexcode'}
                or options.get(name + '/IsPython') is True):
            if section.contents().strip():
                return name
    return None


def validate_network(root):
    import hou

    hfs = hou.getenv('HFS')
    install_dir = Path(hfs).resolve() if hfs else None
    found = []
    stack = [root]
    while stack and len(found) < 100:
        node = stack.pop()
        node_type = node.type()
        category = node_type.category()
        _, _, base, _ = node_type.nameComponents()
        reason = code_node_reason(category.name(), base)
        if reason:
            found.append(code_node_finding(category, node_type.name(), base, node.path(), reason))
            continue
        definition = node_type.definition()
        if definition is not None:
            if _stock_definition(definition, install_dir):
                if node.matchesCurrentDefinition():
                    continue
            else:
                section = _code_section(definition)
                if section:
                    found.append(code_node_finding(category, node_type.name(), base, node.path(),
                                                   'Code in asset definition: ' + section))
                    continue
        stack.extend(reversed(node.children()))
    if found:
        raise CodeNodeError(found)


def publish_hda(node_path, output_path, type_name, description=''):
    """Create one new library; this modifies the current Houdini session."""
    import hou
    if not os.path.isabs(output_path) or '$' in output_path or '`' in output_path:
        raise ValueError('output_path must be an explicit absolute path')
    output_path = os.path.abspath(output_path)
    root, extension = os.path.splitext(output_path)
    if extension.lower() not in ('.hda', '.hdanc', '.hdalc', '.otl', '.otlnc', '.otllc'):
        raise ValueError('output_path must end in .hda, .hdanc, .hdalc, .otl, .otlnc, or .otllc')
    if any(os.path.lexists(root + suffix) for suffix in ('.hda', '.hdanc', '.hdalc', '.otl', '.otlnc', '.otllc')):
        raise FileExistsError('An HDA library with this base name already exists')
    if not os.path.isdir(os.path.dirname(output_path)):
        raise ValueError('Output directory does not exist')
    if not isinstance(type_name, str) or not type_name or len(type_name) > 200 or any(c.isspace() for c in type_name) or '/' in type_name or '\\' in type_name:
        raise ValueError('type_name must be a nonempty Houdini operator type name')
    node = hou.node(node_path)
    if node is None:
        raise ValueError('Node does not exist: ' + str(node_path))
    category = node.type().category()
    if hou.nodeType(category, type_name) is not None:
        raise ValueError('Node type already exists in category ' + category.name() + ': ' + type_name)
    validate_network(node)
    original_type = node.type().name()
    node.createDigitalAsset(name=type_name, hda_file_name=output_path,
                            description=description or type_name, change_node_type=False,
                            create_backup=False, install_path='Current HIP File')
    # License restrictions can change the library suffix. Verify the actual file.
    candidates = [output_path] + [root + suffix for suffix in ('.hda', '.hdanc', '.hdalc', '.otl', '.otlnc', '.otllc')]
    actual = next((p for p in candidates if os.path.isfile(p)), None)
    if actual is None:
        raise RuntimeError('Houdini did not produce a recognizable HDA library')
    definitions = hou.hda.definitionsInFile(actual)
    matches = [d for d in definitions if d.nodeTypeName() == type_name and d.nodeTypeCategory().name() == category.name()]
    if len(matches) != 1 or node.type().name() != original_type:
        raise RuntimeError('HDA definition or source-node verification failed; inspect output: ' + actual)
    return {'output_path': actual.replace('\\', '/'), 'type_name': type_name, 'category': category.name(),
            'source_node': node.path(), 'source_type': original_type, 'verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hip', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--type-name', required=True)
    parser.add_argument('--description', default='')
    args = parser.parse_args()
    import hou
    try:
        hou.hipFile.load(args.hip, suppress_save_prompt=True, ignore_load_warnings=False)
        print(json.dumps({'ok': True, 'result': publish_hda(args.node, args.output, args.type_name, args.description)}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': {'type': type(exc).__name__, 'message': str(exc)}}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
