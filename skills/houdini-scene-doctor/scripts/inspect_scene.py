"""Bounded scene inspection. Run with hython or load with runpy inside Houdini."""
import argparse
import json


def inspect_scene(root_path='/obj', max_nodes=200, include_geometry=False):
    """Inspect a subtree without changing it; geometry=True may trigger cooking."""
    import hou
    if not isinstance(max_nodes, int) or isinstance(max_nodes, bool) or not 1 <= max_nodes <= 10000:
        raise ValueError('max_nodes must be an integer from 1 to 10000')
    root = hou.node(root_path)
    if root is None:
        raise ValueError('Node does not exist: ' + str(root_path))
    report = {'root': root.path(), 'nodes': [], 'truncated': False,
              'geometry_requested': bool(include_geometry), 'warnings': []}
    if include_geometry:
        report['warnings'].append('Reading geometry can trigger a cook.')
    stack = [root]
    while stack:
        if len(report['nodes']) >= max_nodes:
            report['truncated'] = True
            break
        node = stack.pop()
        item = {'path': node.path(), 'type': node.type().name(), 'inputs': [],
                'errors': [], 'warnings': [], 'expressions': [], 'expressions_truncated': False, 'inspection_errors': []}
        try:
            item['inputs'] = [n.path() if n else None for n in node.inputs()]
        except hou.Error as exc:
            item['inspection_errors'].append('inputs: ' + str(exc))
        for field in ('errors', 'warnings'):
            try:
                item[field] = list(getattr(node, field)())
            except hou.Error as exc:
                item['inspection_errors'].append(field + ': ' + str(exc))
        try:
            for index, parm in enumerate(node.parms()):
                if index >= 1000 or len(item['expressions']) >= 256:
                    item['expressions_truncated'] = True
                    break
                try:
                    expression = parm.expression()
                    item['expressions'].append({'parm': parm.name(), 'expression': expression[:4000],
                                                'language': str(parm.expressionLanguage())})
                except hou.OperationFailed:
                    pass  # ordinary parameters have no expression
        except hou.Error as exc:
            item['inspection_errors'].append('expressions: ' + str(exc))
        if include_geometry and isinstance(node, hou.SopNode):
            try:
                geometry = node.geometry()
                item['geometry'] = {'points': len(geometry.points()), 'primitives': len(geometry.prims())}
            except hou.Error as exc:
                item['inspection_errors'].append('geometry: ' + str(exc))
        report['nodes'].append(item)
        try:
            stack.extend(reversed(node.children()))
        except hou.Error as exc:
            item['inspection_errors'].append('children: ' + str(exc))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hip', required=True, help='HIP file to load for inspection')
    parser.add_argument('--root', default='/obj')
    parser.add_argument('--max-nodes', type=int, default=200)
    parser.add_argument('--include-geometry', action='store_true', help='may cause geometry to cook')
    args = parser.parse_args()
    import hou
    try:
        hou.hipFile.load(args.hip, suppress_save_prompt=True, ignore_load_warnings=False)
        print(json.dumps({'ok': True, 'report': inspect_scene(args.root, args.max_nodes, args.include_geometry)}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': {'type': type(exc).__name__, 'message': str(exc)}}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
