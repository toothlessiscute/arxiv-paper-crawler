"""Polite arXiv metadata + PDF crawler."""

from .arxiv_api import ArxivClient, Paper, build_search_query
from .downloader import PdfDownloader
from .storage import MetadataStore

__all__ = [
    "ArxivClient",
    "Paper",
    "build_search_query",
    "PdfDownloader",
    "MetadataStore",
]

__version__ = "0.3.1"
