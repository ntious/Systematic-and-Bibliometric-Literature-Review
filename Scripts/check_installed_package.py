"""Smoke-test the actual wheel in an isolated environment outside the checkout."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import tomllib
from urllib.request import Request, urlopen
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    args = parser.parse_args()
    wheels = list(args.dist.resolve().glob('*.whl'))
    if len(wheels) != 1:
        raise ValueError('Choose a directory with exactly one built wheel')
    expected = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    with TemporaryDirectory(prefix='litatlas-install-') as temporary:
        folder = Path(temporary)
        envdir = folder / 'venv'
        venv.EnvBuilder(with_pip=True).create(envdir)
        scripts = envdir / ('Scripts' if os.name == 'nt' else 'bin')
        python = scripts / ('python.exe' if os.name == 'nt' else 'python')
        command = scripts / ('slr.exe' if os.name == 'nt' else 'slr')
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
        environment['PYTHONNOUSERSITE'] = '1'

        def run(*arguments):
            return subprocess.run([str(a) for a in arguments], cwd=folder, env=environment,
                                  check=True, capture_output=True, text=True, timeout=90).stdout

        run(python, '-m', 'pip', '--isolated', 'install', '--no-index', '--no-deps', wheels[0])
        run(python, '-m', 'pip', 'check')
        installed = json.loads(run(python, '-I', '-c',
            'import json,slr;print(json.dumps([slr.__version__,slr.__file__]))'))
        if installed[0] != expected or not Path(installed[1]).resolve().is_relative_to(envdir.resolve()):
            raise ValueError('Version mismatch or import leaked from source checkout')
        assert expected in run(command, '--version')
        for subcommand in ['dashboard', 'review', 'protocol', 'pipeline', 'import', 'analyze', 'evidence']:
            run(command, subcommand, '--help')
        run(command, '--config', ROOT / 'configs/example_review.toml', '--fixture',
            ROOT / 'Examples/demo_records.json', '--output', folder / 'retrieval')
        assert json.loads((folder / 'retrieval/manifest.json').read_text())['version'] == expected
        run(command, 'import', '--input', ROOT / 'Examples/corpus_records.json',
            '--source', 'Synthetic install check', '--output', folder / 'import')
        assert json.loads((folder / 'import/manifest.json').read_text())['version'] == expected
        run(command, 'analyze', '--input', ROOT / 'Examples/corpus_records.json', '--output', folder / 'analysis')
        run(command, 'protocol', 'check', '--file', ROOT / 'configs/example_protocol.json')
        with closing(socket.socket()) as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        log = folder / 'dashboard.log'
        with log.open('w') as output:
            process = subprocess.Popen([str(command), 'dashboard', '--workspace', str(folder / 'workspace'),
                '--demo', '--port', str(port)], cwd=folder, env=environment, stdout=output, stderr=output)
            try:
                base = f'http://127.0.0.1:{port}'
                for attempt in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Installed dashboard exited: ' + log.read_text())
                    try:
                        with urlopen(base, timeout=1) as response:
                            html = response.read().decode()
                        break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Installed dashboard did not start')
                token = re.search(r'name="slr-token" content="([^"]+)"', html).group(1)
                for asset in ['/app.js', '/styles.css']:
                    with urlopen(base + asset, timeout=5) as response:
                        assert len(response.read()) > 100
                def get(path):
                    with urlopen(Request(base + path, headers={'X-SLR-Token': token}), timeout=5) as response:
                        return json.load(response)
                reviews = get('/api/workspace')
                # The API's returned reviews are synthetic, created only in this temp environment.
                identifier = reviews['reviews'][0]['id'] if isinstance(reviews, dict) else reviews[0]['id']
                corpus = get('/api/corpus?review=' + identifier)
                assert corpus['totals']['papers'] > 0
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
    print(f'Clean installation passed: {expected}, entry point, offline commands, web assets and synthetic dashboard')


if __name__ == '__main__':
    main()
