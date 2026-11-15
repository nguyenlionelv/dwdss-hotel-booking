"""Execute the real frontend API client against a temporary local FastAPI server."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    evidence = ROOT / 'artifacts/ml_serving'
    evidence.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    with (evidence / 'client_server.log').open('w', encoding='utf-8') as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app',
            '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, stdout=log, stderr=log)
        try:
            for _ in range(200):
                if server.poll() is not None:
                    raise RuntimeError('Temporary API process exited; inspect client_server.log')
                try:
                    with urllib.request.urlopen(base + '/api/dss/models', timeout=2) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(.2)
            else:
                raise RuntimeError('Temporary API did not become ready')
            result = subprocess.run([shutil.which('node') or 'node', '--test', 'frontend/tests/dssApi.test.mjs'],
                cwd=ROOT, env={**os.environ, 'DWDSS_API_BASE_URL': base}, capture_output=True, text=True, encoding='utf-8')
            (evidence / 'frontend_client_tests.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            (evidence / 'frontend_client_verification.json').write_text(json.dumps({
                'passed': result.returncode == 0, 'live_http': True, 'client': 'frontend/src/services/dssApi.js',
                'exit_code': result.returncode}, indent=2), encoding='utf-8')
            print(result.stdout)
            return result.returncode
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()

if __name__ == '__main__':
    raise SystemExit(main())
