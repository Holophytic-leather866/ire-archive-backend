#!/usr/bin/env python3
"""Data loading utilities for indexing."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

# Add parent directory to path for app imports
sys.path.append(str(Path(__file__).parent.parent))

console = Console()


def find_data_file(is_production: bool = False, use_test_data: bool = False) -> Path | None:
    """Find the IRE resources data file with smart path detection.

    Handles both local development and production (Fly.io) environments.
    If the DATA_URL environment variable is set, the data file is downloaded
    from that URL instead of being read from disk. An optional DATA_URL_TOKEN
    environment variable may provide a Bearer token for authenticated downloads
    (e.g. from a private GitHub repository).
    """

    if use_test_data:
        console.print("[bold cyan]Running in TEST mode (using fixtures)[/bold cyan]")
        test_path = Path("data/fixtures.json")
        if test_path.exists():
            console.print(f"Found test fixtures at: {test_path}", style="green")
            return test_path
        console.print(f"[yellow]Test fixtures not found at: {test_path}[/yellow]")
        console.print("[yellow]Ensure data/fixtures.json is present (tracked in the repository).[/yellow]")
        return test_path  # Return expected path (will fail later with clear error)

    data_url = os.environ.get("DATA_URL")
    if data_url:
        console.print("[bold cyan]Downloading data file from DATA_URL...[/bold cyan]")
        token = os.environ.get("DATA_URL_TOKEN")
        headers: dict[str, Any] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            with tempfile.NamedTemporaryFile(suffix="-ire-archive-data.json", delete=False) as tmp:
                download_path = Path(tmp.name)

            with httpx.stream("GET", data_url, headers=headers, follow_redirects=True, timeout=300) as response:
                response.raise_for_status()
                with download_path.open("wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
            console.print(f"Downloaded data file to: {download_path}", style="green")
            return download_path
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network
            console.print(f"[red]HTTP {exc.response.status_code} error downloading data from DATA_URL[/red]")
            console.print("[yellow]Check that DATA_URL points to a valid, accessible URL[/yellow]")
            if token:
                console.print("[yellow]Check that DATA_URL_TOKEN has the required permissions[/yellow]")
            sys.exit(1)
        except Exception as exc:  # pragma: no cover - network
            console.print(f"[red]Failed to download data from DATA_URL: {exc}[/red]")
            console.print("[yellow]Set DATA_URL to a URL pointing to ire-archive-data.json[/yellow]")
            console.print("[yellow]Set DATA_URL_TOKEN to a Bearer token if the URL requires authentication[/yellow]")
            sys.exit(1)

    if is_production:
        console.print("[bold cyan]Running in PRODUCTION mode on Fly.io[/bold cyan]")
        possible_paths = [
            Path("/app/data/ire-archive-data.json"),
            Path("/data/ire-archive-data.json"),
            Path("data/ire-archive-data.json"),
        ]

        for path in possible_paths:
            if path.exists():
                console.print(f"Found data file at: {path}", style="green")
                return path

        console.print(
            "[yellow]Data file not found. Set DATA_URL (and optionally DATA_URL_TOKEN) to download it.[/yellow]"
        )
        return Path("/app/data/ire-archive-data.json")

    console.print("[bold cyan]Running in LOCAL mode[/bold cyan]")
    return Path("data/ire-archive-data.json")


def read_resources(source_path: Path, test_data: bool) -> list[dict]:
    """Load resources JSON from disk, handling fixtures format."""

    console.print(f"\n[bold cyan]Loading IRE resources from {source_path}...[/bold cyan]")

    with source_path.open() as f:
        data = json.load(f)

    if test_data and isinstance(data, dict) and "fixtures" in data:
        resources = data["fixtures"]
        console.print(
            f"[INFO] Using test fixtures (created: {data.get('_metadata', {}).get('created_at', 'unknown')})",
            style="cyan",
        )
    else:
        resources = data

    console.print(f"[SUCCESS] Loaded {len(resources):,} resources", style="green")
    return resources
