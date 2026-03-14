"""Setup and installation tasks (argparse-based, backend-only)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable

from scripts.cli_utils import (
    APP_NAME,
    PROJECT_ROOT,
    check_docker,
    check_fly_cli,
    confirm_destructive,
    error,
    info,
    run_command,
    section,
    success,
    warning,
)


def cmd_install(_args: argparse.Namespace) -> None:
    """Install backend dependencies and prepare local tooling."""
    section("Installing IRE Resources Semantic Search (Backend)")

    info("Checking for required tools...")

    if not check_docker():
        error("Docker is required but not found")
        error("Install Docker from: https://docs.docker.com/get-docker/")
        sys.exit(1)

    if not check_fly_cli():
        warning("Fly CLI not found - production deployment will not be available")
        warning("Install from: https://fly.io/docs/hands-on/install-flyctl/")

    section("Installing Python dependencies")
    info("Using UV to install dependencies...")

    result = run_command(["uv", "sync"], cwd=PROJECT_ROOT, check=False)
    if result.returncode != 0:
        error("Failed to install Python dependencies")
        error("Make sure UV is installed: https://docs.astral.sh/uv/")
        sys.exit(1)

    success("Python dependencies installed")

    section("Pulling Qdrant Docker image")
    info("Pulling qdrant/qdrant:latest...")

    result = run_command(["docker", "pull", "qdrant/qdrant:latest"], check=False)
    if result.returncode == 0:
        success("Qdrant image pulled")
    else:
        warning("Failed to pull Qdrant image - will try on first start")

    section("Downloading embedding model")
    info("Downloading sentence-transformers model...")
    info("This may take a few minutes on first run...")

    download_script = """
import sys
from sentence_transformers import SentenceTransformer

try:
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print('Model downloaded successfully')
    sys.exit(0)
except Exception as e:
    print(f'Failed to download model: {e}', file=sys.stderr)
    sys.exit(1)
"""

    result = run_command(["uv", "run", "python", "-c", download_script], cwd=PROJECT_ROOT, check=False)

    if result.returncode == 0:
        success("Embedding model downloaded")
    else:
        warning("Failed to download embedding model - will try on first API start")

    section("Installation complete!")
    success("All dependencies installed successfully")
    info("")
    info("Next steps:")
    info("  1. Start local development: make dev-start")
    info("  2. Index sample data: make dev-index")
    info("  3. Test the API: make dev-test")
    info("")
    info("For production deployment:")
    info("  1. Initialize Fly.io: make setup-init-prod")
    info("  2. Deploy: make prod-push")


def cmd_init_prod(_args: argparse.Namespace) -> None:
    """Initialize Fly.io production environment."""
    section("Initializing Fly.io Production Environment")

    if not check_fly_cli():
        error("Fly CLI is required for production deployment")
        error("Install from: https://fly.io/docs/hands-on/install-flyctl/")
        sys.exit(1)

    info("Checking if app already exists...")
    result = subprocess.run(
        ["flyctl", "status", "--app", APP_NAME],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        warning(f"App '{APP_NAME}' already exists")
        if not confirm_destructive(
            "reinitialize the Fly.io app",
            "This will not delete existing data, but may update configuration",
        ):
            info("Initialization cancelled")
            return

    section("Launching Fly.io app")
    info(f"Creating app: {APP_NAME}")
    info("This will use the configuration in fly.toml")

    result = run_command(["flyctl", "launch", "--no-deploy", "--copy-config"], cwd=PROJECT_ROOT, check=False)

    if result.returncode != 0:
        error("Failed to launch app")
        error("You may need to:")
        error("  1. Log in to Fly.io: flyctl auth login")
        error("  2. Check if the app name is available")
        sys.exit(1)

    success("App launched successfully")

    section("Creating persistent volume")
    info("Creating 3GB volume for Qdrant data...")

    result = subprocess.run(
        ["flyctl", "volumes", "list", "--app", APP_NAME],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if "qdrant_data" in result.stdout:
        warning("Volume 'qdrant_data' already exists")
    else:
        create_result = subprocess.run(
            ["flyctl", "volumes", "create", "qdrant_data", "--size", "3", "--app", APP_NAME],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if create_result.returncode == 0:
            success("Volume created successfully")
        else:
            error("Failed to create volume")
            error(create_result.stderr)
            sys.exit(1)

    success("Production environment initialized")
    info("Next steps:")
    info("  1. Set secrets: flyctl secrets set ...")
    info("  2. Deploy: make prod-push")


COMMANDS: dict[str, tuple[str, Callable[[argparse.Namespace], None]]]
COMMANDS = {
    "install": ("Install backend dependencies", cmd_install),
    "init-prod": ("Initialize Fly.io production environment", cmd_init_prod),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Setup and installation tasks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("install", help=COMMANDS["install"][0])
    subparsers.add_parser("init-prod", help=COMMANDS["init-prod"][0])

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    _, handler = COMMANDS[args.command]
    handler(args)


if __name__ == "__main__":
    main()
