#!/usr/bin/env python3
"""Clear the Qdrant database by properly deleting the collection via API."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from rich.console import Console

console = Console()

# Configuration
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "nonprofit_knowledge"


def clear_database():
    """Clear the Qdrant database by deleting the collection."""

    console.print("\n[bold cyan]Clearing Qdrant Database[/bold cyan]")
    console.print("=" * 60)

    # Connect to Qdrant
    console.print(f"\n[cyan]Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...[/cyan]")
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        console.print("[SUCCESS] Connected to Qdrant", style="green")
    except Exception as e:
        console.print(f"[ERROR] Failed to connect to Qdrant: {e}", style="red")
        console.print("\n[yellow]Please ensure Qdrant is running:[/yellow]")
        console.print("  make dev-start")
        console.print("  or: docker compose up -d")
        return False

    # Check if collection exists
    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if COLLECTION_NAME not in collection_names:
            console.print(f"\n[yellow]Collection '{COLLECTION_NAME}' does not exist - nothing to clear[/yellow]")
            return True

        # Get collection info
        info = client.get_collection(COLLECTION_NAME)
        console.print(f"\n[cyan]Found collection '{COLLECTION_NAME}' with {info.points_count} points[/cyan]")

    except Exception as e:
        console.print(f"[ERROR] Failed to check collection: {e}", style="red")
        return False

    # Delete the collection
    console.print(f"\n[yellow]Deleting collection '{COLLECTION_NAME}'...[/yellow]")
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        console.print(
            f"[SUCCESS] Collection '{COLLECTION_NAME}' deleted successfully!",
            style="green",
        )
        return True
    except Exception as e:
        console.print(f"[ERROR] Failed to delete collection: {e}", style="red")
        return False


def main():
    """Main entry point."""
    success = clear_database()

    if success:
        console.print("\n[bold green][SUCCESS] Database cleared successfully![/bold green]")
        sys.exit(0)
    else:
        console.print("\n[bold red][ERROR] Failed to clear database[/bold red]\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
