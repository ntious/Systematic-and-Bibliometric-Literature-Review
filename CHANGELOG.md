# Changelog

## 0.6.0 — release candidate

- Add coverage-aware corpus totals and ranked publication venues to Research analytics, with complete CSV/JSON exports.
- Preserve affiliations, affiliation countries, subject taxonomies, ISSNs and publisher metadata where providers supply them.
- Import dated journal metrics and native SCImago downloads with source footnotes, explicit quartile bases, categories and missing-value handling.
- Add explicit Elsevier/Clarivate lookup jobs with exact-year and ISSN checks, server-side credentials and durable session logs. Live provider access requires approved credentials; automated SCImago access was blocked during development.
- Improve dashboard navigation, themes and responsive analytics controls.
- Add package-content auditing, clean-install smoke checks, a staged public documentation build and a prepared trusted-publishing workflow.
- Make retrieval/import manifests use the installed package version.

The software remains a trusted local application. It does not provide authenticated multi-user access. Test results establish software behavior, not systematic-review completeness, research validity or the quality of underlying evidence.

## 0.5.0 — previous repository baseline

- Provide local retrieval/import, independent screening and adjudication, bibliometric networks, evidence review and the LitAtlas dashboard.
- Provide protocol drafting/amendment tracking, reviewer agreement and practical pipeline session logs.

These entries describe the repository baseline; they do not assert that 0.5.0 was published to PyPI.
