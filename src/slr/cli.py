"""Run a bounded review search from a TOML configuration."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import tomllib
from . import __version__
from .models import Record
from .reporting import write_json, write_results
from .search import SearchError, search


def load_config(path):
    with Path(path).open("rb") as handle:
        config = tomllib.load(handle)
    query = config.get("query")
    sources = config.get("sources")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a nonempty string")
    if not isinstance(sources, list) or not sources or any(s not in ("openalex", "crossref", "pubmed") for s in sources) or len(set(sources)) != len(sources):
        raise ValueError("sources must contain unique openalex/crossref/pubmed names")
    limit = config.get("max_records_per_source", 100)
    if type(limit) is not int or not 1 <= limit <= 100000:
        raise ValueError("max_records_per_source must be between 1 and 100000")
    if "pubmed" in sources and limit > 10000:
        raise ValueError("PubMed max_records_per_source must not exceed 10000")
    for key in ("year_from", "year_to"):
        if key in config and (type(config[key]) is not int or not 1000 <= config[key] <= 9999):
            raise ValueError(f"{key} must be a four-digit year")
    if config.get("year_from", 1000) > config.get("year_to", 9999):
        raise ValueError("year_from must not exceed year_to")
    if not isinstance(config.get("mailto", ""), str):
        raise ValueError("mailto must be a string")
    return config


def public_config(config):
    """Manifests are shared as supplementary material; keep the contact email out of them."""
    return {**config, "mailto": "<redacted>"} if config.get("mailto") else config


def run(config_path, output, fixture=None):
    config = load_config(config_path)
    recorded = public_config(config)
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    records, logs = [], []
    try:
        if fixture:
            records = [Record(**row) for row in json.loads(Path(fixture).read_text(encoding="utf-8"))]
            write_json(folder / "fixture.json", [r.to_dict() for r in records])
        else:
            for source in config["sources"]:
                found, pages, log = search(source, config["query"], config.get("max_records_per_source", 100),
                                          config.get("year_from"), config.get("year_to"), config.get("mailto", ""))
                records.extend(found)
                logs.append(log)
                write_json(folder / f"raw-{source}.json", pages)
        write_results(folder, records)
        manifest = {"status": "complete", "mode": "offline-fixture" if fixture else "live", "protocol_approval": "unbound", "started_utc": started,
                    "finished_utc": datetime.now(timezone.utc).isoformat(), "config": recorded, "searches": logs,
                    "version": __version__, "files": {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}}
        write_json(folder / "manifest.json", manifest)
    except Exception:
        write_json(folder / "manifest.json", {"status": "failed", "started_utc": started, "config": recorded, "searches": logs})
        raise
    return folder


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("replicate", "verify"):
        from .replication import main as replication_main
        return replication_main(argv[1:], verification=argv[0]=="verify")
    if argv and argv[0] in ("plan", "questions"):
        from .workflow_cli import main as plan_main, questions_main
        return (plan_main if argv[0]=="plan" else questions_main)(argv[1:])
    if argv and argv[0] == "knowledge-ai":
        from .knowledge_ai import main as knowledge_ai_main
        return knowledge_ai_main(argv[1:])
    if argv and argv[0] == "knowledge-evaluate":
        from .knowledge_evaluation import main as evaluate_main
        return evaluate_main(argv[1:])
    if argv and argv[0] == "knowledge":
        from .analysis_knowledge import main as knowledge_main
        return knowledge_main(argv[1:])
    if argv and argv[0] == "report":
        from .manuscript import main as report_main
        return report_main(argv[1:])
    if argv and argv[0] == "pipeline":
        from .pipeline import main as pipeline_main
        return pipeline_main(argv[1:])
    if argv and argv[0] == "dashboard":
        from .dashboard import main as dashboard_main
        return dashboard_main(argv[1:])
    if argv and argv[0] == "evidence":
        from .evidence_cli import main as evidence_main
        return evidence_main(argv[1:])
    if argv and argv[0] == "analyze":
        from .bibliometrics_cli import main as analyze_main
        return analyze_main(argv[1:])
    if argv and argv[0] == "review":
        from .review_cli import main as review_main
        return review_main(argv[1:])
    if argv and argv[0] == "import":
        from .imports import main as import_main
        return import_main(argv[1:])
    if argv and argv[0] == "protocol":
        from .protocol import main as protocol_main
        return protocol_main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, epilog="Also available: slr plan --help; slr questions --help; slr knowledge-ai --help; slr knowledge-evaluate --help; slr knowledge --help; slr report --help; slr protocol --help; slr pipeline --help; slr review --help; slr import --help; slr analyze --help; slr evidence --help; slr dashboard --help")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True, help="New output directory; existing directories are never overwritten")
    parser.add_argument("--unregistered", action="store_true", help="Explicit standalone retrieval, not an approved review search")
    parser.add_argument("--fixture", help="Offline normalized-record JSON; skips API retrieval and filters")
    args = parser.parse_args(argv)
    if not args.fixture and not args.unregistered:
        parser.error("Use slr plan run for an approved review, or explicitly select --unregistered for standalone retrieval")
    try:
        folder = run(args.config, args.output, args.fixture)
    except (ValueError, OSError, SearchError, TypeError) as exc:
        parser.exit(1, f"slr: {exc}\n")
    print(f"Review artifacts written to {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
