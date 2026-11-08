"""Stage an explicit public documentation set; private Docs files are never copied."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ('Installation_Guide', 'Dashboard_Guide', 'Screening_Guide', 'Protocol_Guide',
          'Pipeline_Guide', 'Bibliometrics_Guide', 'Corpus_Analytics_Guide',
          'Evidence_Guide', 'Local_Data_Policy', 'Implementation_Roadmap', 'Release_Guide')


def stage():
    target = ROOT / 'outputs/docs-source'
    # Only this fixed generated directory is replaced; no user-supplied path.
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    files = {'README.md': 'index.md', 'CHANGELOG.md': 'CHANGELOG.md',
             'CONTRIBUTING.md': 'CONTRIBUTING.md', 'LICENSE': 'LICENSE',
             'configs/example_protocol.json': 'configs/example_protocol.json'}
    files.update({f'Docs/{name}.md': f'Docs/{name}.md' for name in GUIDES})
    for source, destination in files.items():
        path = target / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, path)
    print(f'Staged {len(files)} public documentation files')


if __name__ == '__main__':
    stage()
