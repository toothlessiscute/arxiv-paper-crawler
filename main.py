#!/usr/bin/env python3
"""arxiv-paper-crawler command-line entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from tqdm import tqdm

from crawler import ArxivClient, MetadataStore, PdfDownloader, build_search_query

DEFAULTS = {
    "query": "",
    "categories": ["cs.CL"],
    "max_results": 100,
    "page_size": 50,
    "sort_by": "submittedDate",
    "sort_order": "descending",
    "download_pdf": True,
    "output_dir": "data",
    "request_delay": 3.0,
    "download_delay": 1.0,
    "timeout": 30,
    "max_retries": 3,
}


def load_config(path: Path) -> dict:
    cfg = dict(DEFAULTS)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            cfg.update(yaml.safe_load(f) or {})
    return cfg


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Crawl arXiv metadata and PDFs.")
    p.add_argument("-c", "--config", default="config.yaml", help="path to config file")
    p.add_argument("-q", "--query", help="free-text search terms")
    p.add_argument("--category", action="append", dest="categories",
                   help="arXiv category, can be repeated (e.g. --category cs.CL --category cs.AI)")
    p.add_argument("-n", "--max-results", type=int)
    p.add_argument("--sort-by", choices=["submittedDate", "lastUpdatedDate", "relevance"])
    p.add_argument("-o", "--out", dest="output_dir")
    p.add_argument("--no-pdf", action="store_true", help="store metadata only")
    p.add_argument("--stats", action="store_true", help="print stats for the output dir and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def merge(cfg: dict, args: argparse.Namespace) -> dict:
    for key in ("query", "categories", "max_results", "sort_by", "output_dir"):
        val = getattr(args, key)
        if val is not None:
            cfg[key] = val
    if args.no_pdf:
        cfg["download_pdf"] = False
    return cfg


def print_stats(store: MetadataStore) -> None:
    s = store.stats()
    print(f"papers   : {s['papers']}")
    print(f"with pdf : {s['with_pdf']}")
    if s["categories"]:
        print("primary categories:")
        for cat, n in s["categories"].items():
            print(f"  {cat:<12} {n}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    cfg = merge(load_config(Path(args.config)), args)

    out = Path(cfg["output_dir"])
    store = MetadataStore(out / "metadata.jsonl")

    if args.stats:
        print_stats(store)
        return 0

    try:
        search_query = build_search_query(cfg["query"], cfg["categories"])
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    logging.info("search_query=%r max_results=%d", search_query, cfg["max_results"])

    client = ArxivClient(
        request_delay=cfg["request_delay"],
        timeout=cfg["timeout"],
        max_retries=cfg["max_retries"],
    )
    downloader = None
    if cfg["download_pdf"]:
        downloader = PdfDownloader(
            out / "pdfs",
            delay=cfg["download_delay"],
            timeout=cfg["timeout"] * 2,
            max_retries=cfg["max_retries"],
        )

    added = skipped = failed = 0
    papers = client.search(
        search_query,
        max_results=cfg["max_results"],
        page_size=cfg["page_size"],
        sort_by=cfg["sort_by"],
        sort_order=cfg["sort_order"],
    )
    for paper in tqdm(papers, total=cfg["max_results"], unit="paper"):
        if paper.arxiv_id in store:
            skipped += 1
            continue
        if downloader:
            path = downloader.download(paper.arxiv_id, paper.pdf_url)
            if path is None:
                failed += 1
            else:
                paper.pdf_path = path.as_posix()
        store.add(paper)
        added += 1

    logging.info("done: %d added, %d skipped, %d pdf failures", added, skipped, failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
