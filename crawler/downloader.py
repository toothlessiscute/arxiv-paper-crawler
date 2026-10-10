"""PDF downloader with simple rate limiting and resume support."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

from .arxiv_api import USER_AGENT

log = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"


def safe_filename(arxiv_id: str) -> str:
    """Old-style ids contain a slash (e.g. hep-th/9901001v1)."""
    return arxiv_id.replace("/", "_") + ".pdf"


class PdfDownloader:
    def __init__(
        self,
        out_dir: str | Path,
        delay: float = 1.0,
        timeout: int = 60,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)

    def path_for(self, arxiv_id: str) -> Path:
        return self.out_dir / safe_filename(arxiv_id)

    def download(self, arxiv_id: str, url: str) -> Path | None:
        dest = self.path_for(arxiv_id)
        if dest.exists() and dest.stat().st_size > 0:
            log.debug("skip %s (already downloaded)", arxiv_id)
            return dest

        # arXiv serves PDFs over https; the API still reports http links
        if url.startswith("http://arxiv.org"):
            url = "https://" + url[len("http://"):]

        tmp = dest.with_suffix(".pdf.part")
        for attempt in range(1, self.max_retries + 1):
            try:
                with self.session.get(url, stream=True, timeout=self.timeout) as r:
                    r.raise_for_status()
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)
                with open(tmp, "rb") as f:
                    if f.read(4) != PDF_MAGIC:
                        raise ValueError("response is not a PDF")
                tmp.replace(dest)
                time.sleep(self.delay)
                return dest
            except (requests.RequestException, ValueError) as e:
                log.warning("download %s failed (attempt %d/%d): %s", arxiv_id, attempt, self.max_retries, e)
                tmp.unlink(missing_ok=True)
                time.sleep(self.delay * attempt * 2)

        log.error("giving up on %s", arxiv_id)
        return None
