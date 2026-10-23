# Release preparation and publication

The first distribution target is local Python software. Hosted multi-user service, Codespaces compatibility and desktop installers are separate future work.

## Validate a candidate

```bash
python -m pip install -e '.[dev,analysis,ui-test,docs]'
python -m pytest
python -m build
python -m twine check dist/*
python Scripts/check_distribution.py --dist dist
python Scripts/check_installed_package.py --dist dist
python Scripts/build_docs.py
python -m mkdocs build --strict
python -m playwright install chromium
python Scripts/check_dashboard_browser.py --output outputs/dashboard-qa
python Scripts/check_corpus_browser.py --output outputs/dashboard-qa/corpus
```

Use a fresh `dist` directory for each candidate. The audit rejects unexpected paths, private/runtime files, version mismatches and missing web assets. This is a content allowlist and credential-pattern check, not a guarantee that arbitrary text is free of sensitive information. Inspect the staged Git diff and release assets before publication. Never upload the working tree, real workspaces, practical test logs or browser captures from real reviews.

The clean-install check creates a temporary environment, installs the actual wheel without dependencies or an index, runs commands outside the checkout, and starts an offline synthetic dashboard. CI also rebuilds the wheel from the source archive. Results apply to the tested environment; local testing alone does not establish compatibility across all operating systems.

Update `pyproject.toml` and `src/slr/__init__.py` together, update the changelog and citation version, and ensure the release tag is `v` followed by that version. Do not invent a DOI or release date before publication.

## PyPI setup — account owner action

On 2026-10-22 the PyPI JSON and Simple endpoints for `slr-workbench` returned HTTP 404. That does not guarantee or reserve availability. Recheck before publishing.

Use a [pending Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) for a first release, or an existing-project publisher for subsequent releases. Configure:

- Project: `slr-workbench`
- Owner: `ntious`
- Repository: `Systematic-and-Bibliometric-Literature-Review`
- Workflow: `release.yml`
- GitHub environment: `pypi`

Create the GitHub `pypi` environment with required reviewers and restrict it to release tags before enabling publication. Set the repository variable `PYPI_PUBLISH_ENABLED` to `true` only after the account and environment are ready. No long-lived PyPI token is needed. The workflow starts only on a published GitHub Release, verifies the tag/version and that the commit belongs to `main`, reruns tests/browser checks, audits the built distributions and uploads through OIDC. Drafting a release does not publish to PyPI. Publication to PyPI cannot be undone in the same way as a local edit; review the exact candidate first.

## GitHub Release and citation

Commit and push the reviewed candidate, then create a **draft** release targeting that exact commit. Attach only the audited wheel, source archive and `SHA256SUMS`, with notes from the changelog. Keep it a draft until checks pass and publishing is authorized. The publication workflow rebuilds its own checked artifacts and replaces same-named release assets with the exact uploaded files and checksums, so PyPI and the final release assets agree.

The account owner can connect this repository to [Zenodo's GitHub integration](https://help.zenodo.org/docs/github/) before publication. Confirm the archived version and DOI after the release event, then update citation metadata. A software DOI makes a version citable; it does not validate research performed with the software.

## Public documentation

`Scripts/build_docs.py` stages only an explicit public file list into `outputs/docs-source`; MkDocs never reads the entire `Docs` directory. The site build runs in CI and is available as an artifact. The Pages workflow is manually dispatched after selecting **GitHub Actions** as the Pages source in repository settings. It builds from `main` and publishes only `outputs/docs-site`. Do not enable it against a branch containing private material or substitute the whole repository as the deployment artifact.

Codespaces needs separate proxy/Host/Origin testing. Unsigned desktop installers and authenticated hosted deployment are not part of this release.
