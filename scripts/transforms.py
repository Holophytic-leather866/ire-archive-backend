#!/usr/bin/env python3
"""Resource transformation helpers for indexing."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from urllib.parse import urlparse

from rich.console import Console

from app.config import VALID_CATEGORIES

console = Console()

ALLOWED_DOWNLOAD_DOMAINS = ["resources.ire.org"]


def generate_id(django_id: str | int, title: str, text: str) -> str:
    """Generate a stable Qdrant point ID."""

    return hashlib.md5(f"{django_id}_{title}_{text[:100]}".encode()).hexdigest()


def _filter_downloads(downloads, allowed_domains: list[str] | None = None) -> list[dict]:
    """Filter downloads to an allowed domain list."""

    if not downloads or not isinstance(downloads, list):
        return []

    allowed_set = set(domain.lower() for domain in (allowed_domains or ALLOWED_DOWNLOAD_DOMAINS))
    filtered: list[dict] = []

    for item in downloads:
        if not isinstance(item, dict):
            continue

        url = item.get("url")
        if not url or not isinstance(url, str):
            continue

        parsed = urlparse(url.strip())
        if not parsed.netloc:
            parsed = urlparse(f"http://{url.strip()}")

        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]

        if host in allowed_set:
            filtered.append(item)

    return filtered


def transform_resource(resource: dict, allowed_download_domains: list[str] | None = None) -> dict:
    """Transform an IRE resource record into the Document format."""

    text_parts = []

    if resource.get("title"):
        text_parts.append(f"Title: {resource['title']}")
    if resource.get("authors"):
        text_parts.append(f"Authors: {resource['authors']}")
    if resource.get("affiliations"):
        text_parts.append(f"Affiliations: {resource['affiliations']}")

    subject_value = resource.get("subject", "")
    if subject_value and not resource.get("subject_excluded"):
        text_parts.append(f"Subject: {subject_value}")

    if resource.get("category"):
        text_parts.append(f"Category: {resource['category']}")

    if resource.get("tags"):
        tags_str = ", ".join(resource["tags"]) if isinstance(resource["tags"], list) else resource["tags"]
        text_parts.append(f"Tags: {tags_str}")

    if resource.get("keywords"):
        keywords_str = (
            ", ".join(resource["keywords"]) if isinstance(resource["keywords"], list) else resource["keywords"]
        )
        text_parts.append(f"Keywords: {keywords_str}")

    if resource.get("conference"):
        text_parts.append(f"Conference: {resource['conference']}")
    if resource.get("conference_year"):
        text_parts.append(f"Year: {resource['conference_year']}")

    if resource.get("contest_name"):
        text_parts.append(f"Contest: {resource['contest_name']}")

    clean_desc = resource.get("description", "")
    if clean_desc:
        text_parts.append(f"Content: {clean_desc}")

    searchable_text = "\n\n".join(text_parts)

    authors_extracted_list = []
    affiliations_extracted_list = []
    if resource.get("authors_extracted"):
        for author_obj in resource["authors_extracted"]:
            if isinstance(author_obj, dict):
                if author_obj.get("name"):
                    authors_extracted_list.append(author_obj["name"])
                if author_obj.get("affiliation"):
                    affiliations_extracted_list.append(author_obj["affiliation"])

    resource_year = resource.get("year_computed")

    validated_category = resource.get("category", "")
    if validated_category and validated_category not in VALID_CATEGORIES:
        print(
            f"WARNING: Invalid category '{validated_category}' for resource {resource.get('id', 'unknown')}",
            flush=True,
        )
        validated_category = ""

    filtered_downloads = _filter_downloads(resource.get("downloads", []), allowed_download_domains)

    metadata = {
        "id": resource.get("id"),
        "resource_id": resource.get("resource_id"),
        "authors": resource.get("authors", ""),
        "authors_extracted": resource.get("authors_extracted", []),
        "authors_extracted_list": authors_extracted_list,
        "affiliations": resource.get("affiliations", ""),
        "affiliations_extracted_list": affiliations_extracted_list,
        "description": clean_desc,
        "subject": subject_value,
        "category": validated_category,
        "tags": resource.get("tags", []),
        "keywords": resource.get("keywords", []),
        "conference": resource.get("conference", ""),
        "conference_year": resource.get("conference_year", ""),
        "published": resource.get("published", ""),
        "year_computed": resource_year,
        "date_created": resource.get("date_created"),
        "date_updated": resource.get("date_updated"),
        "contest_name": resource.get("contest_name", ""),
        "contest_entry_status": resource.get("contest_entry_status", ""),
        "downloads": filtered_downloads,
    }

    metadata = {k: v for k, v in metadata.items() if v is not None}

    return {
        "text": searchable_text,
        "title": resource.get("title", "Untitled"),
        "doc_type": "ire_resource",
        "metadata": metadata,
    }


def transform_documents(resources: list[dict], errors: list[str]) -> tuple[list[dict], list[tuple[int, str]]]:
    """Transform raw resources to documents, collecting errors."""

    console.print("\n[bold cyan]Transforming resources to documents...[/bold cyan]")
    documents: list[dict] = []
    transform_errors: list[tuple[int, str]] = []

    for i, resource in enumerate(resources):
        try:
            doc = transform_resource(resource)
            documents.append(doc)
        except Exception as exc:  # noqa: BLE001
            transform_errors.append((i, str(exc)))
            errors.append(f"Transform error at resource {i}: {str(exc)[:100]}")

    console.print(f"[SUCCESS] Transformed {len(documents):,} documents", style="green")
    if transform_errors:
        console.print(
            f"[WARNING] {len(transform_errors)} resources failed transformation",
            style="yellow",
        )

    return documents, transform_errors


def prepare_points(documents: Iterable[dict]) -> list[dict]:
    """Convert documents into Qdrant point payloads."""

    all_points: list[dict] = []
    for doc in documents:
        text = doc["text"]
        django_id = doc["metadata"].get("id", "")
        point_id = generate_id(django_id, doc["title"], text)

        all_points.append(
            {
                "id": point_id,
                "text": text,
                "title": doc["title"],
                "doc_type": doc["doc_type"],
                "metadata": doc["metadata"],
            }
        )

    return all_points
