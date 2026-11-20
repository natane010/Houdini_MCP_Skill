"""Plan or install project-local Codex and Claude Code Houdini integration."""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

REPO_SKILLS = Path(__file__).resolve().parents[1] / 'skills'


def _is_link(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or (
        os.name == 'nt' and info.st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
    )


def _check_directory(path):
    if _is_link(path) or (path.exists() and not path.is_dir()):
        raise ValueError('Target parent must be a normal directory: ' + str(path))


def _files(directory):
    result = {}
    for path in directory.rglob('*'):
        if any(part == '__pycache__' for part in path.relative_to(directory).parts) or path.suffix in ('.pyc', '.pyo'):
            continue
        if _is_link(path):
            raise ValueError('Links and junctions are not supported in skill folders: ' + str(path))
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = path.read_bytes()
    return result


def _toml_parse(text):
    if tomllib is None:
        raise RuntimeError('Python 3.11+ or the tomli package is required to configure Codex')
    return tomllib.loads(text)


def plan(project_dir, client, backend, python, hython=None, allow_python=False, *, port=18811, gui_token_file=None):
    project = Path(project_dir)
    if not project.is_absolute() or not project.is_dir():
        raise ValueError('project-dir must be an existing absolute directory')
    _check_directory(project)
    executable = Path(python)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError('python must be an existing absolute executable path')
    if client not in ('both', 'codex', 'claude') or backend not in ('gui', 'batch'):
        raise ValueError('invalid client or backend')
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('port must be in [1, 65535]')
    if gui_token_file is not None and (backend != 'gui' or not Path(gui_token_file).is_absolute()):
        raise ValueError('gui-token-file requires the GUI backend and an absolute path')
    args = ['-m', 'houdini_mcp.server', '--backend', backend]
    if backend == 'batch':
        if not hython or not Path(hython).is_absolute() or not Path(hython).is_file():
            raise ValueError('batch backend requires an existing absolute hython path')
        args += ['--hython', str(hython)]
    else:
        if port != 18811:
            args += ['--port', str(port)]
        if gui_token_file is not None:
            args += ['--gui-token-file', str(gui_token_file)]
    if allow_python:
        args.append('--allow-python')
    server = {'command': str(executable), 'args': args}
    writes = []
    copies = []
    notices = []
    clients = ('codex', 'claude') if client == 'both' else (client,)
    for selected in clients:
        config = project / ('.codex/config.toml' if selected == 'codex' else '.mcp.json')
        _check_directory(config.parent)
        if _is_link(config) or (config.exists() and not config.is_file()):
            raise ValueError('Config target must be a regular file: ' + str(config))
        original = config.read_text(encoding='utf-8-sig') if config.exists() else ''
        if selected == 'codex':
            data = _toml_parse(original)
            servers = data.get('mcp_servers', {})
            if not isinstance(servers, dict):
                raise ValueError('Codex mcp_servers must be a table')
            existing = servers.get('houdini')
            if 'houdini' in servers:
                if existing != server:
                    raise ValueError('Codex houdini server already exists with different settings')
                notices.append('Codex server already configured')
            else:
                stanza = '[mcp_servers.houdini]\ncommand = ' + json.dumps(server['command'], ensure_ascii=False) + '\nargs = ' + json.dumps(args, ensure_ascii=False) + '\n'
                candidate = original.rstrip() + ('\n\n' if original.strip() else '') + stanza
                try:
                    parsed = _toml_parse(candidate)
                except Exception as exc:
                    raise ValueError('Cannot safely append Codex server to existing TOML: ' + str(exc)) from exc
                if parsed.get('mcp_servers', {}).get('houdini') != server:
                    raise ValueError('Cannot safely append Codex server to existing TOML')
                writes.append((config, candidate))
        else:
            data = json.loads(original) if original.strip() else {}
            if not isinstance(data, dict) or not isinstance(data.get('mcpServers', {}), dict):
                raise ValueError('Claude config and mcpServers must be objects')
            servers = data.setdefault('mcpServers', {})
            claude_server = {'type': 'stdio', **server}
            existing = servers.get('houdini')
            if 'houdini' in servers:
                if existing != claude_server:
                    raise ValueError('Claude houdini server already exists with different settings')
                notices.append('Claude server already configured')
            else:
                servers['houdini'] = claude_server
                writes.append((config, json.dumps(data, ensure_ascii=False, indent=2) + '\n'))
        destination = project / ('.agents/skills' if selected == 'codex' else '.claude/skills')
        _check_directory(destination.parent)
        _check_directory(destination)
        for source in sorted(REPO_SKILLS.iterdir()):
            if not source.is_dir() or not (source / 'SKILL.md').is_file():
                continue
            if _is_link(source):
                raise ValueError('Linked skill source is not supported: ' + str(source))
            target = destination / source.name
            if _is_link(target) or (target.exists() and not target.is_dir()):
                raise ValueError('Skill target must be a directory: ' + str(target))
            if target.exists():
                if _files(source) != _files(target):
                    raise ValueError('Skill already exists with different contents: ' + str(target))
                notices.append('Skill already identical: ' + str(target))
            else:
                _files(source)  # validate the complete source before any writes
                copies.append((source, target))
    return {'project_dir': str(project), 'client': client, 'backend': backend,
            'server': server, 'write_configs': [str(p) for p, _ in writes],
            'copy_skills': [{'source': str(a), 'destination': str(b)} for a, b in copies],
            'notices': notices}, writes, copies


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(content)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def setup(project_dir, client='both', backend='batch', python=sys.executable, hython=None, allow_python=False, apply=False,
          *, port=18811, gui_token_file=None):
    report, writes, copies = plan(project_dir, client, backend, python, hython, allow_python,
                                 port=port, gui_token_file=gui_token_file)
    report['applied'] = bool(apply)
    if apply:
        # Individual writes are atomic; the entire set is not a transaction.
        for path, content in writes:
            _atomic_write(path, content)
        for source, target in copies:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--client', choices=('both', 'codex', 'claude'), default='both')
    parser.add_argument('--backend', choices=('batch', 'gui'), default='batch')
    parser.add_argument('--hython')
    parser.add_argument('--port', type=int, default=18811)
    parser.add_argument('--gui-token-file')
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--allow-python', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        report = setup(args.project_dir, args.client, args.backend, args.python, args.hython,
                       args.allow_python, args.apply, port=args.port, gui_token_file=args.gui_token_file)
        print(json.dumps({'ok': True, **report}, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': {'type': type(exc).__name__, 'message': str(exc)}}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
