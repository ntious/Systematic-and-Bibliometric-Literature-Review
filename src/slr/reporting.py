"""Portable metadata exports; counts describe retrieval, not eligibility."""
import csv
import json
from pathlib import Path
import re


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# Spreadsheet applications evaluate cells starting with these characters as formulas.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_FORMULA_CELL = re.compile("'*[" + re.escape("".join(FORMULA_PREFIXES)) + "]")


def safe_cell(value):
    """Prefix a quote so spreadsheets show text; JSON artifacts keep the exact value."""
    if isinstance(value, str) and _FORMULA_CELL.match(value):
        return "'" + value
    return value


def unsafe_cell(value):
    """Invert safe_cell when re-importing an exported CSV."""
    if isinstance(value, str) and value.startswith("'") and _FORMULA_CELL.match(value[1:]):
        return value[1:]
    return value


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: safe_cell(value) for key, value in row.items()} for row in rows)


def export_records(folder, records):
    folder = Path(folder)
    rows = [record.to_dict() for record in records]
    write_json(folder / "records.json", rows)
    fields = ["source", "source_id", "title", "doi", "abstract", "authors", "year", "journal", "citations", "url", "provenance", "author_ids", "keywords", "references", "reference_count"]
    write_csv(folder / "records.csv", fields, [{key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                                               for key, value in row.items()} for row in rows])
    def bib(value):
        escapes = {"\\": r"{\textbackslash}", "{": r"\{", "}": r"\}", "%": r"\%", "&": r"\&", "#": r"\#", "_": r"\_", "$": r"\$", "~": r"{\textasciitilde}", "^": r"{\textasciicircum}"}
        return "".join(escapes.get(char, char) for char in str(value or "").replace("\n", " "))
    entries = []
    ris = []
    for index, record in enumerate(records, 1):
        fields = {"title": record.title, "author": " and ".join(record.authors), "year": record.year,
                  "journal": record.journal, "doi": record.doi, "url": record.url}
        entries.append("@article{slr" + str(index) + ",\n" + ",\n".join(
            "  " + key + " = {" + bib(value) + "}" for key, value in fields.items() if value) + "\n}")
        lines = ["TY  - JOUR", "TI  - " + record.title]
        lines += ["AU  - " + name.replace("\n", " ") for name in record.authors]
        for tag, value in [("PY", record.year), ("JO", record.journal), ("DO", record.doi), ("AB", record.abstract), ("UR", record.url)]:
            if value:
                lines.append(tag + "  - " + str(value).replace("\n", " "))
        lines += ['KW  - ' + value.replace('\n', ' ') for value in record.keywords]
        lines += ['CR  - ' + value.replace('\n', ' ') for value in record.references]
        ris.append("\n".join(lines + ["ER  -", ""]))
    (folder / "records.bib").write_text("\n\n".join(entries), encoding="utf-8")
    (folder / "records.ris").write_text("\n".join(ris), encoding="utf-8")


def write_results(folder, records, *, identity=False):
    """Shared retrieval/import artifacts, before and after deduplication."""
    from collections import Counter
    from .models import deduplicate
    folder = Path(folder)
    write_json(folder / "retrieved.json", [r.to_dict() for r in records])
    unique, duplicates = deduplicate(records, identity=identity)
    export_records(folder, unique)
    write_json(folder / "duplicates.json", duplicates)
    write_json(folder / "identification.json", {"identified": len(records), "duplicates_removed": len(duplicates),
                                                "records_for_screening": len(unique), "screening_completed": False})
    write_json(folder / "summary.json", {"publications_by_year": dict(sorted(Counter(str(r.year) for r in unique if r.year).items()))})
