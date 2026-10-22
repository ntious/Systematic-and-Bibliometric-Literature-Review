# Local research data and public repository files

Public candidates are application source, tests using synthetic fixtures, generic example configurations and usage documentation. Keep actual research protocols, source documents, queries, run plans, retrieved metadata, review decisions, evidence, internal feedback and session/error logs local until deliberately reviewed for sharing.

## Local locations

- `research/`: actual protocols, plans, calibration policies and portable session notes.
- `outputs/`: application workspaces, raw responses, review databases, exports, screenshots and practical-test evidence.
- `private/`, `local/`, `downloads/`, `exports/`, `runs/`, `workspaces/`, `logs/`, `artifacts/`: additional ignored local artifact locations.
- `Docs/Practical_Test_Log.md` and `reviewer_feedback.md`: private local observations/feedback.

`.gitignore` also excludes environment credentials, private keys, local configuration, common database sidecars and standalone application state/diagnostic filenames. The `configs/` directory is private by default, with an explicit allowlist of the seven generic examples shipped with the repository; release manifests use the same allowlist. Generic, sanitized `.env.example` / `.env.template` files remain possible public examples; review their contents before sharing.

## Git and package boundaries

Git ignore rules affect untracked files. They do not remove files already tracked or erase prior commits. Check `git status --short` and `git ls-files` before publication. A local audit verified the current private paths and checked for tracked paths matching the new rules; no tracked private-path match was found.

Source distributions use `MANIFEST.in` independently of Git ignores. It explicitly prunes research/output/private folders and excludes local session logs, feedback, the study-specific helper, credentials and runtime files. Fresh wheel and source archives are inspected during the practical privacy audit. Older local archives are not retroactively rewritten; only deliberately reviewed, freshly verified packages should be shared.

A credential-pattern scan is supplementary. It does not establish that every possible sensitive value is absent. Keep new real data in the ignored directories and review public diffs deliberately. Actual study records are not replaced by synthetic examples merely to pass a publication check.

The application remains a loopback local workbench. Ignoring files does not provide encryption, backup or remote-service authentication. No deployment or publication is part of a practical test unless explicitly requested.
