"""Audit release archive paths, metadata and common credential patterns before upload."""
import argparse
from email.parser import BytesParser
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = {'Implementation_Roadmap.md', 'Screening_Guide.md', 'Bibliometrics_Guide.md',
        'Evidence_Guide.md', 'Dashboard_Guide.md', 'Pipeline_Guide.md',
        'Local_Data_Policy.md', 'Protocol_Guide.md', 'Corpus_Analytics_Guide.md',
        'Installation_Guide.md', 'Release_Guide.md'}
EXAMPLES = {'demo_records.json', 'bibliometrics_records.json', 'evidence_report.txt',
            'corpus_records.json', 'synthetic_venue_metrics.csv'}
CONFIGS = {'example_review.toml', 'pubmed_review.toml', 'example_criteria.md',
           'evidence_framework.json', 'example_pipeline.json', 'example_calibration.json', 'example_protocol.json'}
SCRIPTS = {'literature_search.py', 'screening_demo.py', 'evidence_demo.py',
           'check_dashboard_browser.py', 'check_corpus_browser.py', 'check_distribution.py',
           'check_installed_package.py', 'build_docs.py'}
FORBIDDEN = {'research', 'outputs', 'private', 'local', 'downloads', '.git', '.codex', '.agents',
             '.claude', '__pycache__', 'Practical_Test_Log.md', 'platform_enhancement_plan.md',
             'reviewer_feedback.md', 'workspace.json', 'jobs.json', 'SESSION.md', 'session.json',
             'scimago-original.csv', 'external-venue-metrics.csv', 'input-records.json'}
SECRETS = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}|\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}')


def allowed(path, wheel):
    parts = path.parts
    if any(p in FORBIDDEN or p.startswith('.env') for p in parts):
        return False
    if path.suffix.lower() in {'.sqlite', '.db', '.log', '.pem', '.key', '.pfx', '.p12', '.pyc'}:
        return False
    if wheel:
        return parts[0] == 'slr' or parts[0].endswith('.dist-info')
    if len(parts) == 1:
        return path.name in {'pyproject.toml', 'MANIFEST.in', 'README.md', 'LICENSE', 'PKG-INFO',
                             'setup.cfg', 'CHANGELOG.md', 'CONTRIBUTING.md', 'CITATION.cff', 'mkdocs.yml'}
    if parts[:2] == ('src', 'slr'):
        return True
    if len(parts) == 3 and parts[0] == 'src' and parts[1].endswith('.egg-info'):
        return True
    if len(parts) == 2:
        return ((parts[0] == 'Docs' and path.name in DOCS) or
                (parts[0] == 'Examples' and path.name in EXAMPLES) or
                (parts[0] == 'configs' and path.name in CONFIGS) or
                (parts[0] == 'Scripts' and path.name in SCRIPTS) or
                (parts[0] == 'tests' and path.name.startswith('test_') and path.suffix == '.py'))
    return False


def audit(archive, expected_version):
    wheel = archive.suffix == '.whl'
    if wheel:
        with zipfile.ZipFile(archive) as z:
            entries = [(i.filename, z.read(i)) for i in z.infolist() if not i.is_dir()]
    else:
        with tarfile.open(archive, 'r:gz') as t:
            if any(not (i.isfile() or i.isdir()) for i in t.getmembers()):
                raise ValueError('Source archive contains links or special files')
            entries = [(i.name, t.extractfile(i).read()) for i in t.getmembers() if i.isfile()]
    paths = set()
    metadata = None
    roots = {PurePosixPath(name).parts[0] for name, _ in entries}
    if not wheel and roots != {'slr_workbench-' + expected_version}:
        raise ValueError('Unexpected source archive root')
    for name, data in entries:
        raw = PurePosixPath(name)
        if raw.is_absolute() or '..' in raw.parts or '\\' in name:
            raise ValueError('Unsafe archive path')
        path = raw if wheel else PurePosixPath(*raw.parts[1:])
        if str(path) in paths or not allowed(path, wheel):
            raise ValueError(f'Unexpected or duplicate package member: {path}')
        paths.add(str(path))
        if SECRETS.search(data):
            raise ValueError(f'Possible credential in package member: {path}')
        if path.name == ('METADATA' if wheel else 'PKG-INFO'):
            metadata = BytesParser().parsebytes(data)
    if metadata is None or metadata['Name'] != 'slr-workbench' or metadata['Version'] != expected_version:
        raise ValueError('Distribution name/version metadata mismatch')
    prefix = 'slr/' if wheel else 'src/slr/'
    for required in ['__init__.py', 'cli.py', 'dashboard.py', 'corpus.py', 'venue_metrics.py',
                     'web/index.html', 'web/app.js', 'web/styles.css']:
        if prefix + required not in paths:
            raise ValueError('Missing package asset: ' + required)
    print(f'{archive.name}: audited {len(paths)} files')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    args = parser.parse_args()
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    archives = sorted([*args.dist.glob('*.whl'), *args.dist.glob('*.tar.gz')])
    if len(archives) != 2 or sum(p.suffix == '.whl' for p in archives) != 1:
        raise ValueError('Expected exactly one wheel and one source archive in a fresh dist directory')
    for archive in archives:
        audit(archive, version)
    (args.dist / 'SHA256SUMS').write_text(''.join(f'{sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in archives))


if __name__ == '__main__':
    main()
