"""Thin wrapper around the arXiv Atom API."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Iterator

import feedparser
import requests

log = logging.getLogger(__name__)

API_URL = "http://export.arxiv.org/api/query"
USER_AGENT = "arxiv-paper-crawler/0.3 (+research use)"


@dataclass
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    summary: str
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    pdf_url: str
    pdf_path: str | None = None
    fetched_at: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d["extra"]:
            d.pop("extra")
        return d


def build_search_query(query: str = "", categories: list[str] | None = None) -> str:
    """Build an arXiv `search_query` string.

    >>> build_search_query("diffusion", ["cs.CV", "cs.LG"])
    'all:diffusion AND (cat:cs.CV OR cat:cs.LG)'
    """
    parts: list[str] = []
    query = (query or "").strip()
    if query:
        terms = query.split()
        if len(terms) == 1:
            parts.append(f"all:{terms[0]}")
        else:
            parts.append('all:"' + " ".join(terms) + '"')

    cats = [c.strip() for c in (categories or []) if c.strip()]
    if cats:
        cat_expr = " OR ".join(f"cat:{c}" for c in cats)
        parts.append(f"({cat_expr})" if len(cats) > 1 else cat_expr)

    if not parts:
        raise ValueError("either a query or at least one category is required")
    return " AND ".join(parts)


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _parse_entry(entry) -> Paper:
    arxiv_id = entry.id.rsplit("/abs/", 1)[-1]
    pdf_url = next(
        (l.href for l in entry.get("links", []) if l.get("type") == "application/pdf"),
        f"http://arxiv.org/pdf/{arxiv_id}",
    )
    categories = [t["term"] for t in entry.get("tags", [])]
    primary = entry.get("arxiv_primary_category", {}).get("term") or (
        categories[0] if categories else ""
    )
    return Paper(
        arxiv_id=arxiv_id,
        title=_clean(entry.title),
        authors=[a.name for a in entry.get("authors", [])],
        summary=_clean(entry.summary),
        categories=categories,
        primary_category=primary,
        published=entry.published,
        updated=entry.updated,
        pdf_url=pdf_url,
    )


class ArxivClient:
    def __init__(
        self,
        request_delay: float = 3.0,
        timeout: int = 30,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        self.request_delay = max(request_delay, 0.0)
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self._last_request = 0.0

    def _throttle(self) -> None:
        wait = self.request_delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _get(self, params: dict) -> str:
        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(API_URL, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                last_err = e
                log.warning("arXiv request failed (attempt %d/%d): %s", attempt, self.max_retries, e)
                time.sleep(self.request_delay * attempt)
        raise RuntimeError(f"arXiv API unreachable after {self.max_retries} attempts") from last_err

    def search(
        self,
        search_query: str,
        max_results: int = 100,
        page_size: int = 50,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> Iterator[Paper]:
        """Yield papers matching `search_query`, paging through results."""
        page_size = max(1, min(page_size, 2000))
        fetched = 0
        start = 0
        while fetched < max_results:
            n = min(page_size, max_results - fetched)
            params = {
                "search_query": search_query,
                "start": start,
                "max_results": n,
                "sortBy": sort_by,
                "sortOrder": sort_order,
            }
            log.debug("GET %s %s", API_URL, params)
            feed = feedparser.parse(self._get(params))
            entries = feed.get("entries", [])
            if not entries:
                log.info("no more results after %d papers", fetched)
                return
            for entry in entries:
                yield _parse_entry(entry)
                fetched += 1
                if fetched >= max_results:
                    return
            start += len(entries)
