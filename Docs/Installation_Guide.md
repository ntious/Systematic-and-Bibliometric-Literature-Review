# Install and run LitAtlas

LitAtlas requires Python 3.11 or newer. The core application has no required third-party runtime dependencies. It runs on your own computer; keep its workspace in a directory you own and back it up.

## Release candidate

Download the `slr_workbench-0.6.0-py3-none-any.whl` asset from the project's GitHub Release when available. Until publication, the same wheel can be built from the repository with `python -m build`. Compare its SHA-256 hash with the release's `SHA256SUMS` file.

With [pipx](https://pipx.pypa.io/stable/installation/) installed:

```bash
pipx install ./slr_workbench-0.6.0-py3-none-any.whl
slr --version
slr dashboard --workspace ~/litatlas-workspace --demo
```

After a PyPI release is published, use `pipx install slr-workbench`. That command is not a promise that a package is already published. On Windows, use an explicit path such as `C:/Users/YOUR_NAME/LitAtlas` for the workspace. If `slr` is not found, follow pipx's PATH instructions and reopen the terminal.

Without pipx, use a virtual environment:

```bash
python -m venv .venv
# Linux/macOS:
.venv/bin/python -m pip install ./slr_workbench-0.6.0-py3-none-any.whl
.venv/bin/python -m slr dashboard --workspace ~/litatlas-workspace --demo
# Windows PowerShell equivalents:
# .venv\Scripts\python.exe -m pip install .\slr_workbench-0.6.0-py3-none-any.whl
# .venv\Scripts\python.exe -m slr dashboard --workspace C:/Users/YOUR_NAME/LitAtlas --demo
```

Open the loopback URL printed in the terminal. Use `--port 8766` if the default port is occupied. Stop the server with Ctrl+C. The dashboard deliberately accepts only local connections. Reviewer names are trusted labels, not logins. Do not expose it as a shared hosted service.

## Your data and optional services

`--demo` seeds an empty workspace with synthetic examples. Omit it for an empty workspace. Create a new review for your own research. Back up the entire workspace with the server stopped so SQLite data and sidecar files are consistent. Restoring the folder restores local files; no cloud sync is provided.

Live metadata retrieval requires network access and is subject to provider policies, quotas and credentials. SCImago's downloaded CSV can be imported without a paid API subscription. Optional model calls can incur charges and transmit the selected source packet to the configured service. Manual evidence review works without model credentials.

Optional dependencies may be installed using the wheel's extras, for example `pipx inject slr-workbench matplotlib` for figures, or `python -m pip install 'slr-workbench[analysis]'` after publication. These are separate downloads; they are not bundled in the core wheel.

## Upgrade and rollback

Stop the dashboard and copy the workspace before upgrading. With pipx, install a downloaded newer wheel using `pipx install --force PATH_TO_WHEEL`; after publication, `pipx upgrade slr-workbench` checks PyPI. Keep the previous wheel and pre-upgrade backup. If rollback is necessary, reinstall that wheel and restore the matching backup. Do not assume an older application understands files written by a newer version.

See the [dashboard guide](Dashboard_Guide.md) and [local data policy](Local_Data_Policy.md).
