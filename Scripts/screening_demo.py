"""Generate a complete synthetic screening example without network access."""
import argparse
from pathlib import Path

from slr.cli import run
from slr.review_cli import export_review
from slr.screening import decide, initialize, link_study, record_retrieval


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    run(root / "configs/example_review.toml", output / "retrieval", root / "Examples/demo_records.json")
    db = output / "review.sqlite"
    initialize(db, output / "retrieval", "Synthetic screening demonstration", ["alice", "bob"], "carol",
               (root / "configs/example_criteria.md").read_text(encoding="utf-8"))
    for actor in ("alice", "bob"):
        decide(db, "R000001", actor, "title", "include", expected_version=1)
        decide(db, "R000002", actor, "title", "exclude", "Wrong population/context", expected_version=1)
    record_retrieval(db, "R000001", "alice", "retrieved", expected_version=1)
    for actor in ("alice", "bob"):
        decide(db, "R000001", actor, "fulltext", "include", expected_version=1)
    link_study(db, "R000001", "carol", "S1", expected_version=1)
    counts = export_review(db, output / "report")
    print(f"Complete: {counts['complete']}; included reports: {counts['reports_included']}; studies: {counts['studies_included']}")


if __name__ == "__main__":
    main()
