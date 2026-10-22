"""Paginated scholarly API clients with bounded retries and raw responses."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .models import Record


class SearchError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    """urllib copies Authorization to any redirect target, including plain HTTP."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # The 3xx surfaces as HTTPError and is not retried.


_OPENER = build_opener(_NoRedirect)


def urlopen(request, timeout):
    """Open HTTPS only, never following redirects, so credentials stay on the named host."""
    if not request.full_url.startswith("https://"):
        raise SearchError("Only HTTPS endpoints are allowed")
    return _OPENER.open(request, timeout=timeout)


class HTTPClient:
    def __init__(self, interval=1.0, retries=3, timeout=30):
        self.interval, self.retries, self.timeout = interval, retries, timeout
        self.last_request = 0.0

    def get(self, url, params, headers=None, response_format="json"):
        request = Request(url + "?" + urlencode(params),
                          headers={"User-Agent": "slr-workbench/0.5", **(headers or {})})
        for attempt in range(self.retries + 1):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    if response_format == "text":
                        return response.read().decode("utf-8")
                    return json.load(response)
            except HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise SearchError(f"API request failed (HTTP {exc.code})") from None
                retry_after = exc.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 2 ** attempt
                time.sleep(min(delay, 60))
            except (URLError, TimeoutError):
                if attempt == self.retries:
                    raise SearchError("API connection failed after retries") from None
                time.sleep(2 ** attempt)
            except (ValueError, UnicodeError):
                raise SearchError("API returned invalid JSON") from None


def openalex_record(item):
    inverted = item.get("abstract_inverted_index") or {}
    words = sorted((position, word) for word, positions in inverted.items() for position in positions)
    location = item.get("primary_location") or {}
    return Record(source="openalex", source_id=item["id"],
                  title=item.get("display_name") or "", doi=item.get("doi"),
                  provenance=[{"source":"openalex", "source_id":item["id"], "publication_date":item.get("publication_date") or ""}],
                  abstract=" ".join(word for _, word in words),
                  authors=[(a.get("author") or {}).get("display_name", "") for a in item.get("authorships", [])],
                  year=item.get("publication_year"),
                  author_ids=[(a.get("author") or {}).get("orcid") or (a.get("author") or {}).get("id") or "" for a in item.get("authorships", [])],
                  keywords=[k["display_name"] for k in item.get("keywords", []) if k.get("display_name")],
                  references=item.get("referenced_works") or [], reference_count=item.get("referenced_works_count"),
                  journal=(location.get("source") or {}).get("display_name", ""),
                  citations=item.get("cited_by_count"), url=item.get("id", ""))


def crossref_record(item):
    parts = (item.get("published") or item.get("issued") or {}).get("date-parts", [[]])
    reported_date = "-".join(str(v) if i == 0 else f"{v:02d}" for i,v in enumerate(parts[0])) if parts and parts[0] else ""
    return Record(source="crossref", source_id=item.get("DOI", ""),
                  provenance=[{"source":"crossref", "source_id":item.get("DOI", ""), "publication_date":reported_date}],
                  title=next(iter(item.get("title") or []), ""), doi=item.get("DOI"),
                  abstract=item.get("abstract") or "",
                  authors=[" ".join(filter(None, [a.get("given"), a.get("family")])) or a.get("name", "")
                           for a in item.get("author", [])],
                  year=parts[0][0] if parts and parts[0] else None,
                  journal=next(iter(item.get("container-title") or []), ""),
                  author_ids=[a.get("ORCID") or "" for a in item.get("author", [])],
                  references=[ref["DOI"] for ref in item.get("reference", []) if ref.get("DOI")],
                  reference_count=item.get("references-count", item.get("reference-count")),
                  citations=item.get("is-referenced-by-count"), url=item.get("URL", ""))


def search(source, query, limit=100, year_from=None, year_to=None, mailto="", client=None):
    if source == "pubmed":
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be nonempty")
        from .pubmed import search_pubmed
        return search_pubmed(query, limit, year_from, year_to, mailto, client)
    if source not in ("openalex", "crossref"):
        raise ValueError("source must be openalex, crossref, or pubmed")
    if not query.strip() or type(limit) is not int or limit < 1:
        raise ValueError("query must be nonempty and limit must be a positive integer")
    client = client or HTTPClient()
    records, pages, cursor, seen = [], [], "*", set()
    key = os.environ.get("OPENALEX_API_KEY", "")
    while len(records) < limit:
        size = min(100, limit - len(records))
        params = {"cursor": cursor}
        if mailto:
            params["mailto"] = mailto
        filters = []
        if source == "openalex":
            params.update(search=query, per_page=size)
            if year_from:
                filters.append(f"from_publication_date:{year_from}-01-01")
            if year_to:
                filters.append(f"to_publication_date:{year_to}-12-31")
            url = "https://api.openalex.org/works"
        else:
            params.update(query=query, rows=size)
            if year_from:
                filters.append(f"from-pub-date:{year_from}-01-01")
            if year_to:
                filters.append(f"until-pub-date:{year_to}-12-31")
            url = "https://api.crossref.org/works"
        if filters:
            params["filter"] = ",".join(filters)
        headers = {"Authorization": f"Bearer {key}"} if key and source == "openalex" else {}
        data = client.get(url, params, headers=headers)
        pages.append(data)
        try:
            if source == "openalex":
                items = data["results"]
                next_cursor = data["meta"].get("next_cursor")
                total = data["meta"]["count"]
                convert = openalex_record
            else:
                items = data["message"]["items"]
                next_cursor = data["message"].get("next-cursor")
                total = data["message"]["total-results"]
                convert = crossref_record
            records.extend(convert(item) for item in items[:limit - len(records)])
        except (KeyError, TypeError, AttributeError, IndexError):
            raise SearchError(f"Unexpected {source} response schema") from None
        if not items or len(records) >= total or len(records) >= limit or not next_cursor:
            break
        if next_cursor in seen or next_cursor == cursor:
            raise SearchError(f"{source} returned a repeated pagination cursor")
        if source == "openalex" and not key:
            raise SearchError("Set OPENALEX_API_KEY to retrieve additional cursor pages")
        seen.add(cursor)
        cursor = next_cursor
    return records, pages, {"source": source, "query": query, "year_from": year_from,
                            "year_to": year_to, "limit": limit, "available": total,
                            "retrieved": len(records), "truncated": len(records) < total}
