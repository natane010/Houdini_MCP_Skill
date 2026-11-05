# Copernicus examples

The following Python runs inside Houdini 22.0.368. Use `execute_python` only when its `--allow-python` gate is enabled; the code assigns a JSON-compatible `result` for the bridge. In batch mode provide an explicit `hip_output` if the scene must persist. These are separate examples: run the first only when creation was requested. Paths, sizes and requested changes must be chosen for the task. No image file is written.

## Create and verify a small network

```python
import hou
parent = hou.node('/obj')
net = parent.createNode('copnet', node_name='cop_workbench')
net.parm('setres').set(1)
net.parmTuple('res').set((64, 64))
constant = net.createNode('constant')
blur = net.createNode('blur')
blur.setInput(0, constant)
blur.cook(force=True)
layer = blur.layer()  # May cook; output index 0.
result = {'network': net.path(), 'category': net.childTypeCategory().name(),
          'node': blur.path(), 'input': constant.path(), 'output_index': 0,
          'display_window': str(layer.displayWindow()),
          'buffer_resolution': list(layer.bufferResolution()),
          'channels': layer.channelCount(), 'type': str(layer.typeInfo()),
          'errors': list(blur.errors()), 'warnings': list(blur.warnings())}
```

If the requested name already exists, Houdini may assign another name; always report the returned path. `layer()` can invoke a cook and may be expensive on larger scenes. The default constant produces a single-channel image, so the network establishes connectivity rather than demonstrating a visually meaningful blur.

## Inspect and adjust an existing blur

Use the exact user-selected path and desired value. This example changes only a scalar `size`; it does not create, delete or rewire nodes. It does not evaluate animated or expressed parameters; their value is reported as unknown. Do not replace an existing expression or animation unless the requested edit authorizes it; inspect the snapshot and stop to determine the intended change if one exists. For string parameters use `unexpandedString()` rather than evaluating file paths.

```python
import hou
node = hou.node('/obj/cop_workbench/blur1')  # Replace with selected path.
new_size = 0.002  # Replace with requested value.
if node is None or node.type().category().name() != 'Cop' or node.type().name() != 'blur':
    raise ValueError('Select an existing modern Copernicus blur node')
parm = node.parm('size')
def snapshot():
    try:
        expression = parm.expression()
        language = str(parm.expressionLanguage())
    except hou.OperationFailed:
        expression, language = None, None
    keys = parm.keyframes()
    value = parm.eval() if expression is None and not keys else None
    return {'path': node.path(), 'type': node.type().name(),
            'category': node.type().category().name(), 'frame': hou.frame(),
            'parameter': parm.name(), 'value': value,
            'expression': expression, 'expression_language': language,
            'keyframes': len(keys),
            'inputs': [n.path() if n else None for n in node.inputs()],
            'outputs': [{'node': c.outputNode().path(), 'input_index': c.inputIndex(),
                         'output_index': c.outputIndex()} for c in node.outputConnections()]}
before = snapshot()
if before['expression'] is not None or before['keyframes']:
    raise ValueError('Parameter is animated or expressed; inspect before changing it')
parm.set(new_size)
after = snapshot()
result = {'before': before, 'after': after,
          'note': 'Not cooked; cook the smallest relevant node only when needed.'}
```

An interrupted or timed-out change can have an unknown outcome. Reconnect and inspect the node and scene before taking further action; do not repeat the change blindly.
