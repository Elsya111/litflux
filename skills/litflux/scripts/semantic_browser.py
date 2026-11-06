"""Run the installed browser tool against a generated viewer, without target execution."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid


def decode(raw):
    """Accept a JSON value, a JSON string of that value, or a plain word."""
    value = (raw or '').strip()
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return value
    if isinstance(parsed, str):
        try:
            return json.loads(parsed)
        except (ValueError, TypeError):
            return parsed
    return parsed


def browser_check(html_path, revision):
    executable = shutil.which('agent-browser')
    if executable and os.name == 'nt':
        native = Path(executable).parent / 'node_modules/agent-browser/bin/agent-browser-win32-x64.exe'
        if native.is_file():
            executable = str(native)
    if not executable:
        return {'status': 'not-run', 'revision': revision,
                'failures': ['agent-browser is not installed; no runtime is installed automatically']}
    session = 'litflux-semantic-' + uuid.uuid4().hex[:10]

    def run(*args):
        # A background browser daemon can inherit stdout on Windows. Files avoid
        # waiting indefinitely for inherited pipe handles after the CLI exits.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            result = subprocess.run([executable, '--session', session, *args], stdout=stdout,
                                    stderr=stderr, timeout=60)
            stdout.seek(0)
            stderr.seek(0)
            output = stdout.read().decode('utf-8', errors='replace')
            error = stderr.read().decode('utf-8', errors='replace')
        if result.returncode:
            raise ValueError((error or output)[-1200:])
        return output

    try:
        run('open', Path(html_path).as_uri())
        run('eval', 'window.litflux.startEntryAudit()')
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            status = decode(run('eval', 'window.litflux.entryAuditStatus()'))
            if isinstance(status, dict):
                status = status.get('status')
            if status and status != 'running':
                break
            time.sleep(.2)
        else:
            return {'status': 'failed', 'revision': revision,
                    'failures': ['Browser audit timed out; the page did not finish checking']}
        result = decode(run('eval', 'window.litflux.entryAuditResult()'))
        if not isinstance(result, dict):
            return {'status': 'failed', 'revision': revision,
                    'failures': ['Browser audit returned no structured result']}
        result.setdefault('revision', revision)
        return result
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {'status': 'failed', 'revision': revision, 'failures': [str(error)]}
    finally:
        try:
            run('close')
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
