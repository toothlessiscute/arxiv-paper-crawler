"""JSON Lines metadata store."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .arxiv_api import Paper


def _base_id(arxiv_id: str) -> str:
    """Strip the version suffix: 2410.01234v2 -> 2410.01234."""
    head, sep, tail = arxiv_id.rpartition("v")
    return head if sep and tail.isdigit() else arxiv_id


class MetadataStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()
        if self.path.exists():
            for rec in self.iter_records():
                self._seen.add(_base_id(rec["arxiv_id"]))

    def __contains__(self, arxiv_id: str) -> bool:
        return _base_id(arxiv_id) in self._seen

    def __len__(self) -> int:
        return len(self._seen)

    def add(self, paper: Paper) -> bool:
        """Append a paper. Returns False if it was already stored."""
        if paper.arxiv_id in self:
            return False
        if paper.fetched_at is None:
            paper.fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(paper.to_dict(), ensure_ascii=False) + "\n")
        self._seen.add(_base_id(paper.arxiv_id))
        return True

    def iter_records(self):
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def stats(self) -> dict:
        if not self.path.exists():
            return {"papers": 0, "with_pdf": 0, "categories": {}}
        total = 0
        with_pdf = 0
        cats: Counter[str] = Counter()
        for rec in self.iter_records():
            total += 1
            if rec.get("pdf_path"):
                with_pdf += 1
            cats[rec.get("primary_category", "?")] += 1
        return {"papers": total, "with_pdf": with_pdf, "categories": dict(cats.most_common())}
