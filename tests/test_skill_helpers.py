import json
import os
from pathlib import Path
import subprocess
import textwrap

import pytest

HYTHON = os.environ.get('HOUDINI_MCP_TEST_HYTHON', r'C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe')
ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / 'skills/houdini-scene-doctor/scripts/inspect_scene.py'
PUBLISHER = ROOT / 'skills/houdini-hda-publisher/scripts/publish_hda.py'


def run_hython(tmp_path, source):
    env = os.environ.copy()
    env['HOUDINI_PACKAGE_SKIP'] = '1'
    env['HOUDINI_NO_ENV_FILE'] = '1'
    env['HOUDINI_USER_PREF_DIR'] = str(tmp_path / 'prefs__HVER__')
    env.pop('HOUDINI_PATH', None)
    result_file = tmp_path / 'result.json'
    source = 'import json, runpy, hou\nRESULT_FILE = ' + repr(str(result_file)) + '\n' + textwrap.dedent(source)
    script = tmp_path / 'test_hython.py'
    script.write_text(source, encoding='utf-8')
    process = subprocess.run([HYTHON, str(script)], env=env, capture_output=True, text=True, timeout=90)
    assert process.returncode == 0, (process.stdout, process.stderr)
    result = json.loads(result_file.read_text(encoding='utf-8'))
    assert Path(result.pop('_prefs')).resolve().is_relative_to(tmp_path.resolve())
    return result


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason='Houdini hython is not installed')
def test_scene_doctor_is_bounded_and_read_only(tmp_path):
    result = run_hython(tmp_path, f'''
        inspect_scene = runpy.run_path({str(DOCTOR)!r})['inspect_scene']
        geo = hou.node('/obj').createNode('geo', 'doctor_test')
        src = geo.createNode('box', 'source')
        bad = geo.createNode('attribwrangle', 'bad_vex')
        bad.setInput(0, src)
        bad.parm('snippet').set('not valid vex !!!')
        src.parm('sizex').setExpression('1 + 2')
        try:
            bad.cook(force=True)
        except hou.OperationFailed:
            pass
        before = (hou.hipFile.hasUnsavedChanges(), tuple(n.path() for n in geo.children()), src.parm('sizex').expression())
        full = inspect_scene(geo.path(), 20)
        bounded = inspect_scene(geo.path(), 1)
        after = (hou.hipFile.hasUnsavedChanges(), tuple(n.path() for n in geo.children()), src.parm('sizex').expression())
        open(RESULT_FILE, 'w', encoding='utf-8').write(json.dumps({{'full': full, 'bounded': bounded, 'unchanged': before == after, '_prefs': hou.homeHoudiniDirectory()}}))
    ''')
    assert result['unchanged']
    assert result['bounded']['truncated'] and len(result['bounded']['nodes']) == 1
    nodes = {n['path']: n for n in result['full']['nodes']}
    assert nodes['/obj/doctor_test/bad_vex']['inputs'][0] == '/obj/doctor_test/source'
    assert nodes['/obj/doctor_test/bad_vex']['errors']
    assert any(e['parm'] == 'sizex' and e['expression'] == '1 + 2' for e in nodes['/obj/doctor_test/source']['expressions'])
    assert not result['full']['geometry_requested']


@pytest.mark.skipif(not os.path.isfile(HYTHON), reason='Houdini hython is not installed')
def test_hda_publisher_new_file_and_source_preserved(tmp_path):
    output = str(tmp_path / 'demo.hda')
    result = run_hython(tmp_path, f'''
        publish = runpy.run_path({str(PUBLISHER)!r})['publish_hda']
        node = hou.node('/obj').createNode('subnet', 'source_subnet')
        before = node.type().name()
        first = publish(node.path(), {output!r}, 'codex_demo::1.0', 'Demo')
        after = node.type().name()
        try:
            publish(node.path(), {output!r}, 'codex_other::1.0')
        except FileExistsError:
            refused = True
        else:
            refused = False
        try:
            publish(node.path(), {str(tmp_path / 'another.hda')!r}, 'codex_demo::1.0')
        except ValueError:
            duplicate = True
        else:
            duplicate = False
        with open({str(tmp_path / 'alternate.hdanc')!r}, 'wb') as file:
            file.write(b'existing')
        try:
            publish(node.path(), {str(tmp_path / 'alternate.hda')!r}, 'codex_other::1.0')
        except FileExistsError:
            alternate_refused = True
        else:
            alternate_refused = False
        try:
            publish(node.path(), 'relative.hda', 'codex_other::1.0')
        except ValueError:
            relative_refused = True
        else:
            relative_refused = False
        open(RESULT_FILE, 'w', encoding='utf-8').write(json.dumps({{'first': first, 'before': before, 'after': after, 'refused': refused, 'duplicate': duplicate, 'alternate_refused': alternate_refused, 'relative_refused': relative_refused, '_prefs': hou.homeHoudiniDirectory()}}))
    ''')
    assert result['first']['verified'] and Path(result['first']['output_path']).is_file()
    assert result['before'] == result['after'] == 'subnet'
    assert result['refused'] and result['duplicate'] and result['alternate_refused'] and result['relative_refused']
