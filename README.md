# arxiv-paper-crawler

A small, polite command-line crawler that queries the [arXiv API](https://info.arxiv.org/help/api/index.html),
stores paper metadata as JSON Lines, and downloads the PDFs to a local folder.

Useful for building a local corpus of recent papers for summarization, RAG indexing,
or translation pipelines.

## Features

- Search by keyword, category (`cs.CL`, `cs.AI`, ...), or both
- Paging over large result sets with arXiv's recommended 3-second delay
- Resumable: already-downloaded papers are skipped
- Metadata saved to `metadata.jsonl` (one paper per line)
- Configurable through `config.yaml` or CLI flags

## Installation

```bash
git clone <repository-url>
cd arxiv-paper-crawler
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Crawl using the defaults in `config.yaml`:

```bash
python main.py
```

Override from the command line:

```bash
# 50 latest cs.CL papers mentioning "large language model"
python main.py --query "large language model" --category cs.CL --max-results 50

# metadata only, no PDFs
python main.py --category cs.AI --max-results 200 --no-pdf

# custom output directory
python main.py --category cs.CV --out ./data/cv
```

Show what is already stored:

```bash
python main.py --stats
```

## Output layout

```
data/
├── metadata.jsonl      # one JSON object per paper
└── pdfs/
    ├── 2410.01234v1.pdf
    └── ...
```

Each metadata record looks like:

```json
{
  "arxiv_id": "2410.01234v1",
  "title": "...",
  "authors": ["..."],
  "summary": "...",
  "categories": ["cs.CL", "cs.AI"],
  "primary_category": "cs.CL",
  "published": "2024-10-02T17:59:58Z",
  "updated": "2024-10-02T17:59:58Z",
  "pdf_url": "http://arxiv.org/pdf/2410.01234v1",
  "pdf_path": "data/pdfs/2410.01234v1.pdf",
  "fetched_at": "2024-10-05T09:12:44Z"
}
```

## Configuration

See [`config.yaml`](config.yaml). CLI flags always take precedence over the file.

| key | description | default |
|---|---|---|
| `query` | free-text search terms | `""` |
| `categories` | list of arXiv categories (OR-ed) | `["cs.CL"]` |
| `max_results` | total number of papers to fetch | `100` |
| `page_size` | results per API request (max 2000) | `50` |
| `sort_by` | `submittedDate`, `lastUpdatedDate`, `relevance` | `submittedDate` |
| `download_pdf` | download PDFs | `true` |
| `output_dir` | where `metadata.jsonl` and `pdfs/` go | `data` |
| `request_delay` | seconds between API calls | `3.0` |

## Being a good citizen

arXiv asks API users to wait at least 3 seconds between requests and to avoid
bulk-downloading through the main site. Keep `request_delay >= 3` and use
reasonable `max_results` values. For full-corpus access see arXiv's bulk data
options instead.

## Tests

```bash
pip install pytest
pytest
```
