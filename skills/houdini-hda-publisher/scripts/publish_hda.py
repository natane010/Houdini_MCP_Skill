"""Create a new HDA from a Houdini node without converting the source node."""
import argparse
import json
import os


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
