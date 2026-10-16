"""Markdown and PDF policy ingestion with stable source metadata."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from capstone.settings import POLICY_DIR


def _markdown_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem.replace("-", " ").title()
    return {
        "title": title,
        "source": path.name,
        "path": str(path),
        "format": "markdown",
        "category": _category_for(path.stem),
        "text": text.strip(),
    }


def _pdf_document(path: Path) -> dict[str, Any]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n\n".join(pages).strip()
    if not text:
        raise ValueError(f"Policy PDF has no extractable text: {path.name}")
    return {
        "title": path.stem.replace("-", " ").title(),
        "source": path.name,
        "path": str(path),
        "format": "pdf",
        "category": _category_for(path.stem),
        "text": text,
    }


def _category_for(stem: str) -> str | None:
    if not stem.startswith("category-"):
        return None
    return stem.removeprefix("category-").replace("-", " ").title()


def load_documents(
    directory: str | Path | None = None,
    *,
    source_format: str = "all",
) -> list[dict[str, Any]]:
    """Load policies; Markdown takes precedence when an equivalent PDF exists."""
    root = Path(directory) if directory else POLICY_DIR
    if not root.exists():
        raise FileNotFoundError(f"Policy corpus does not exist: {root}")
    if source_format not in {"all", "markdown", "pdf"}:
        raise ValueError("source_format must be 'all', 'markdown', or 'pdf'.")
    documents: list[dict[str, Any]] = []
    markdown_files = sorted(root.glob("*.md"))
    pdf_files = sorted(root.glob("*.pdf"))
    if source_format in {"all", "markdown"}:
        documents.extend(_markdown_document(path) for path in markdown_files if path.name != ".gitkeep")
    if source_format == "pdf":
        documents.extend(_pdf_document(path) for path in pdf_files if path.name != ".gitkeep")
    elif source_format == "all":
        markdown_stems = {path.stem for path in markdown_files}
        documents.extend(
            _pdf_document(path) for path in pdf_files
            if path.name != ".gitkeep" and path.stem not in markdown_stems
        )
    return documents
