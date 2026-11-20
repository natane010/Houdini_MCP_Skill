import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/setup_clients.py'
spec = importlib.util.spec_from_file_location('setup_clients', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_dry_run_no_writes_and_no_python_opt_in(tmp_path):
    report = module.setup(str(tmp_path), backend='gui')
    assert not report['applied']
    assert '--allow-python' not in report['server']['args']
    assert list(tmp_path.iterdir()) == []
    assert len(report['copy_skills']) >= 2


def test_custom_gui_settings_include_port_and_token_path(tmp_path):
    token = tmp_path / 'houdini.token'
    report = module.setup(str(tmp_path), backend='gui', port=18812, gui_token_file=str(token))
    assert report['server']['args'][-4:] == ['--port', '18812', '--gui-token-file', str(token)]
    assert not token.exists()


def test_apply_both_preserves_other_entries_and_is_idempotent(tmp_path):
    project = tmp_path / 'project with spaces'
    project.mkdir()
    (project / '.codex').mkdir()
    (project / '.codex/config.toml').write_text('[mcp_servers.other]\ncommand = "other"\n', encoding='utf-8')
    (project / '.mcp.json').write_text(json.dumps({'mcpServers': {'other': {'command': 'other'}}, 'extra': True}), encoding='utf-8')
    hython = tmp_path / 'hython with spaces.exe'
    hython.touch()
    report = module.setup(str(project), backend='batch', python=sys.executable, hython=str(hython), apply=True)
    codex = tomllib.loads((project / '.codex/config.toml').read_text(encoding='utf-8'))
    claude = json.loads((project / '.mcp.json').read_text(encoding='utf-8'))
    assert codex['mcp_servers']['other']['command'] == 'other'
    assert claude['mcpServers']['other']['command'] == 'other' and claude['extra']
    assert codex['mcp_servers']['houdini']['args'][-1] == str(hython)
    assert claude['mcpServers']['houdini']['type'] == 'stdio'
    assert (project / '.agents/skills/houdini-iterate/scripts/node_snapshot.py').is_file()
    assert (project / '.claude/skills/houdini-scene-doctor/scripts/inspect_scene.py').is_file()
    assert not list((project / '.agents/skills').rglob('__pycache__'))
    second = module.setup(str(project), backend='batch', python=sys.executable, hython=str(hython), apply=True)
    assert report['applied'] and not second['write_configs'] and not second['copy_skills']


def test_collision_blocks_every_write(tmp_path):
    (tmp_path / '.mcp.json').write_text('{"mcpServers":{"houdini":{"command":"different"}}}', encoding='utf-8')
    before = (tmp_path / '.mcp.json').read_bytes()
    with pytest.raises(ValueError, match='different settings'):
        module.setup(str(tmp_path), backend='gui', apply=True)
    assert (tmp_path / '.mcp.json').read_bytes() == before
    assert not (tmp_path / '.codex').exists() and not (tmp_path / '.agents').exists()


def test_inline_toml_conflict_rejected_before_any_write(tmp_path):
    (tmp_path / '.codex').mkdir()
    config = tmp_path / '.codex/config.toml'
    config.write_text('mcp_servers = { other = { command = "x" } }\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Cannot safely append'):
        module.setup(str(tmp_path), backend='gui', apply=True)
    assert not (tmp_path / '.mcp.json').exists()


def test_different_skill_rejected_before_configs(tmp_path):
    target = tmp_path / '.agents/skills/houdini-iterate'
    target.mkdir(parents=True)
    (target / 'SKILL.md').write_text('different', encoding='utf-8')
    with pytest.raises(ValueError, match='different contents'):
        module.setup(str(tmp_path), backend='gui', apply=True)
    assert not (tmp_path / '.codex').exists() and not (tmp_path / '.mcp.json').exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows directory junction')
def test_junction_parent_cannot_redirect_writes(tmp_path):
    project = tmp_path / 'project'
    outside = tmp_path / 'outside'
    project.mkdir()
    outside.mkdir()
    subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(project / '.codex'), str(outside)],
                   check=True, capture_output=True)

    with pytest.raises(ValueError, match='normal directory'):
        module.setup(str(project), backend='gui', apply=True)

    assert list(outside.iterdir()) == []
    assert not (project / '.mcp.json').exists()
