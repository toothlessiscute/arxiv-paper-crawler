import json
import sys
from pathlib import Path

import feedparser
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawler import MetadataStore, build_search_query  # noqa: E402
from crawler.arxiv_api import _parse_entry  # noqa: E402
from crawler.downloader import safe_filename  # noqa: E402

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2410.01234v2</id>
    <updated>2024-10-03T10:00:00Z</updated>
    <published>2024-10-01T17:59:58Z</published>
    <title>A  Sample
      Paper Title</title>
    <summary>  Some abstract
      text.  </summary>
    <author><name>Alice Example</name></author>
    <author><name>Bob Example</name></author>
    <link href="http://arxiv.org/abs/2410.01234v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2410.01234v2" rel="related" type="application/pdf"/>
    <arxiv:primary_category term="cs.CL" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.CL" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
"""


def test_build_query_keyword_and_categories():
    assert build_search_query("diffusion", ["cs.CV", "cs.LG"]) == \
        "all:diffusion AND (cat:cs.CV OR cat:cs.LG)"


def test_build_query_phrase():
    assert build_search_query("large language model", []) == 'all:"large language model"'


def test_build_query_single_category():
    assert build_search_query("", ["cs.CL"]) == "cat:cs.CL"


def test_build_query_empty():
    with pytest.raises(ValueError):
        build_search_query("", [])


def test_parse_entry():
    entry = feedparser.parse(SAMPLE_FEED).entries[0]
    p = _parse_entry(entry)
    assert p.arxiv_id == "2410.01234v2"
    assert p.title == "A Sample Paper Title"
    assert p.summary == "Some abstract text."
    assert p.authors == ["Alice Example", "Bob Example"]
    assert p.primary_category == "cs.CL"
    assert p.categories == ["cs.CL", "cs.AI"]
    assert p.pdf_url == "http://arxiv.org/pdf/2410.01234v2"


def test_safe_filename_old_style():
    assert safe_filename("hep-th/9901001v1") == "hep-th_9901001v1.pdf"


def test_store_dedupes_versions(tmp_path):
    entry = feedparser.parse(SAMPLE_FEED).entries[0]
    store = MetadataStore(tmp_path / "metadata.jsonl")
    p = _parse_entry(entry)
    assert store.add(p) is True
    p2 = _parse_entry(entry)
    p2.arxiv_id = "2410.01234v3"
    assert store.add(p2) is False

    reopened = MetadataStore(tmp_path / "metadata.jsonl")
    assert "2410.01234v1" in reopened
    assert len(reopened) == 1

    rec = json.loads((tmp_path / "metadata.jsonl").read_text(encoding="utf-8").strip())
    assert rec["fetched_at"].endswith("Z")
    assert "extra" not in rec
