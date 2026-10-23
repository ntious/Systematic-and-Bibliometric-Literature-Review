"""Common metadata and conservative, auditable DOI deduplication."""
from dataclasses import asdict, dataclass, field
from html import unescape
import re
from urllib.parse import unquote


def normalize_doi(value):
    value = unquote(str(value or "")).strip().lower()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value)
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else ""


def plain_text(value):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


@dataclass
class Record:
    source: str
    source_id: str
    title: str = ""
    doi: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str = ""
    citations: int | None = None
    url: str = ""
    provenance: list[dict] = field(default_factory=list)
    author_ids: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    reference_count: int | None = None

    venue_id: str = ""
    issns: list[str] = field(default_factory=list)
    publisher: str = ""
    affiliations: list[str] = field(default_factory=list)
    affiliation_ids: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    subject_areas: list[str] = field(default_factory=list)
    subject_taxonomy: str = ""

    def __post_init__(self):
        self.doi = normalize_doi(self.doi)
        self.title = plain_text(self.title)
        self.abstract = plain_text(self.abstract)
        for name in ('authors', 'author_ids', 'keywords', 'references', 'issns', 'affiliations', 'affiliation_ids', 'countries', 'subject_areas'):
            value = getattr(self, name)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f'{name} must be an array of strings')
        if self.author_ids and len(self.author_ids) != len(self.authors):
            raise ValueError('author_ids must align with authors (use empty strings for unknown IDs)')
        if self.affiliation_ids and len(self.affiliation_ids) != len(self.affiliations):
            raise ValueError('affiliation_ids must align with affiliations')
        for name in ('venue_id', 'publisher', 'subject_taxonomy'):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f'{name} must be a string')
        if self.reference_count is not None and (type(self.reference_count) is not int or self.reference_count < 0):
            raise ValueError('reference_count must be a nonnegative integer or null')
        if not self.provenance:
            self.provenance = [{"source": self.source, "source_id": self.source_id}]

    def to_dict(self):
        return asdict(self)


def deduplicate(records, *, identity=False):
    """Keep first matching DOI, optionally exact source/ID; never infer title matches.

    The default preserves historical manifests. Pipeline manifests opt into source
    identity handling; conflicting nonempty DOIs are never merged by identity.
    """
    unique, duplicates, seen, identities, known_dois = [], [], {}, {}, {}
    for record in records:
        key = (record.source, record.source_id) if identity and record.source and record.source_id else None
        kept = seen.get(record.doi) if record.doi else None
        basis = 'doi'
        candidate = identities.get(key) if key else None
        if kept is None and candidate is not None and not (record.doi and known_dois.get(id(candidate)) and record.doi not in known_dois[id(candidate)]):
            kept, basis = candidate, 'source-id'
        if kept is not None:
            kept.provenance.extend(p for p in record.provenance if p not in kept.provenance)
            duplicate = {"doi": record.doi, "kept": kept.source_id,
                         "removed": record.source_id, "source": record.source}
            if basis == 'source-id':
                duplicate['basis'] = basis
            duplicates.append(duplicate)
        else:
            unique.append(record)
            kept = record
        known_dois.setdefault(id(kept), set())
        if record.doi:
            known_dois[id(kept)].add(record.doi)
            seen[record.doi] = kept
        if key and key not in identities:
            identities[key] = kept
    return unique, duplicates
