import json
import os
from pathlib import Path
import subprocess
import textwrap

import pytest

HYTHON = os.environ.get('HOUDINI_MCP_TEST_HYTHON', r'C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe')
SNAPSHOT = Path(__file__).resolve().parents[1] / 'skills/houdini-iterate/scripts/node_snapshot.py'


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason='Houdini hython is not installed')
def test_snapshot_captures_raw_state_without_evaluating_or_cooking(tmp_path):
    env = os.environ.copy()
    env.update(HOUDINI_PACKAGE_SKIP='1', HOUDINI_NO_ENV_FILE='1', HOUDINI_USER_PREF_DIR=str(tmp_path / 'prefs__HVER__'))
    env.pop('HOUDINI_PATH', None)
    result_path = tmp_path / 'result.json'
    script = tmp_path / 'run.py'
    script.write_text(textwrap.dedent(f'''
        import hou, json, runpy
        snapshot = runpy.run_path({str(SNAPSHOT)!r})['snapshot_node']
        geo = hou.node('/obj').createNode('geo', 'test')
        box = geo.createNode('box', 'source')
        node = geo.createNode('xform', 'tuned')
        sink = geo.createNode('null', 'sink')
        node.setInput(0, box)
        sink.setInput(0, node)
        node.parm('tx').setExpression('1 / 0', hou.exprLanguage.Hscript)
        k1 = hou.Keyframe(); k1.setFrame(1); k1.setValue(2)
        k2 = hou.Keyframe(); k2.setFrame(20); k2.setValue(4)
        node.parm('ty').setKeyframes([k1, k2])
        node.parm('tz').set(3.5)
        group = node.parm('group')
        group.set('$HIP/example`1+1`')
        before = node.cookCount()
        report = snapshot(node.path(), ['t', 'group', 'missing'])
        after = node.cookCount()
        limited = snapshot(node.path(), ['t'], max_parms=2)
        out = {{'report': report, 'before': before, 'after': after, 'limited': limited,
                'prefs': hou.homeHoudiniDirectory(), 'connections': [n.path() if n else None for n in node.inputs()]}}
        open({str(result_path)!r}, 'w', encoding='utf-8').write(json.dumps(out))
    '''), encoding='utf-8')
    proc = subprocess.run([HYTHON, str(script)], env=env, capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    result = json.loads(result_path.read_text(encoding='utf-8'))
    assert Path(result['prefs']).resolve().is_relative_to(tmp_path.resolve())
    assert result['before'] == result['after']
    report = result['report']
    parms = {p['name']: p for p in report['parms']}
    assert set(parms) == {'tx', 'ty', 'tz', 'group'}
    assert parms['tx']['keyframes'][0]['expression'] == '1 / 0'
    assert parms['tx']['keyframes'][0]['language'] == 'Hscript'
    assert [key['frame'] for key in parms['ty']['keyframes']] == [1.0, 20.0]
    assert float(parms['tz']['raw_value']) == 3.5
    assert parms['group']['unexpanded_string'] == '$HIP/example`1+1`'
    assert report['missing_parms'] == ['missing']
    assert report['inputs'][0]['source'] == '/obj/test/source'
    assert report['inputs'][0]['destination_input_index'] == 0
    assert report['outputs'][0]['destination'] == '/obj/test/sink'
    assert result['limited']['truncated'] and len(result['limited']['parms']) == 2
