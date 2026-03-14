"""Shared utility functions for the IRE CLI."""

import os
import subprocess
from pathlib import Path
from shutil import which

from rich.console import Console
from rich.panel import Panel

console = Console()
error_console = Console(stderr=True, style="red")

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)

# Common constants
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
API_PORT = int(os.getenv("PORT", "8000"))
API_PID_FILE = LOGS_DIR / "api.pid"
# Default Fly.io app name; override with IRE_APP_NAME for your deployment
APP_NAME = os.getenv("IRE_APP_NAME", "ire-semantic-search")

# Resolve Fly CLI binary name (flyctl on CI runners)
FLY_BIN = os.getenv("FLY_BIN") or ("fly" if which("fly") else "flyctl" if which("flyctl") else "fly")


def success(message: str) -> None:
    """Print a success message."""
    console.print(f"[SUCCESS] {message}", style="green")


def error(message: str) -> None:
    """Print an error message."""
    console.print(f"[ERROR] {message}", style="red")


def warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[WARNING] {message}", style="yellow")


def info(message: str) -> None:
    """Print an info message."""
    console.print(f"[INFO] {message}", style="cyan")


def section(title: str) -> None:
    """Print a section header."""
    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    console.print("=" * 60)


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = False,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Run a command and handle errors.

    Args:
        cmd: Command and arguments as a list
        cwd: Working directory (defaults to PROJECT_ROOT)
        check: Whether to raise on non-zero exit
        capture_output: Whether to capture stdout/stderr
        env: Environment variables to add/override

    Returns:
        CompletedProcess instance

    Raises:
        RuntimeError: If command fails and check=True
    """
    if cwd is None:
        cwd = PROJECT_ROOT

    # Merge environment variables
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)

    result = subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=capture_output,
        text=True,
        env=cmd_env,
    )

    if check and result.returncode != 0:
        error(f"Command failed: {' '.join(cmd)}")
        if capture_output and result.stderr:
            console.print(result.stderr, style="red")
        raise RuntimeError(f"Command failed with exit code {result.returncode}")

    return result


def confirm(prompt: str, default: bool = False) -> bool:
    """Prompt for a yes/no confirmation.

    Args:
        prompt: Question to present to the user
        default: Default choice when user presses Enter

    Returns:
        True if user confirms, False otherwise
    """
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def confirm_destructive(action: str, details: str | None = None) -> bool:
    """Prompt for confirmation before destructive operations.

    Args:
        action: Description of the action (e.g., "clear database")
        details: Additional details to show

    Returns:
        True if user confirms, False otherwise
    """
    console.print()
    console.print(
        Panel(
            f"[bold yellow]WARNING: Destructive Operation[/bold yellow]\n\n"
            f"You are about to: [bold]{action}[/bold]\n"
            f"{details or ''}\n\n"
            f"This action cannot be undone.",
            border_style="yellow",
        )
    )

    return confirm("\nDo you want to continue?", default=False)


def check_docker() -> bool:
    """Check if Docker is available and running.

    Returns:
        True if Docker is available, False otherwise
    """
    try:
        # Use shell=True to ensure PATH is properly resolved
        # This is safe because we're not using user input
        result = subprocess.run(
            "docker info",
            capture_output=True,
            check=False,
            shell=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_fly_cli() -> bool:
    """Check if Fly CLI is installed.

    Returns:
        True if Fly CLI is available, False otherwise
    """
    try:
        result = subprocess.run(
            [FLY_BIN, "version"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def is_api_running() -> bool:
    """Check if the API is currently running.

    Returns:
        True if API is running, False otherwise
    """
    if not API_PID_FILE.exists():
        return False

    try:
        with open(API_PID_FILE) as f:
            pid = int(f.read().strip())

        # Check if process exists
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file exists but process doesn't
        if API_PID_FILE.exists():
            API_PID_FILE.unlink()
        return False


def is_qdrant_running() -> bool:
    """Check if Qdrant is running in Docker.

    Returns:
        True if Qdrant is running, False otherwise
    """
    try:
        # Use shell=True to ensure PATH is properly resolved
        result = subprocess.run(
            "docker ps --filter name=qdrant --format '{{.Names}}'",
            capture_output=True,
            text=True,
            check=False,
            shell=True,
        )
        return "qdrant" in result.stdout
    except FileNotFoundError:
        return False


def get_api_pid() -> int | None:
    """Get the PID of the running API process.

    Returns:
        PID if API is running, None otherwise
    """
    if not is_api_running():
        return None

    try:
        with open(API_PID_FILE) as f:
            return int(f.read().strip())
    except (ValueError, FileNotFoundError):
        return None


def is_redis_running() -> bool:
    """Check if Redis is running in Docker.

    Returns:
        True if Redis is running, False otherwise
    """
    try:
        # Use shell=True to ensure PATH is properly resolved
        result = subprocess.run(
            "docker ps --filter name=ire-redis --format '{{.Names}}'",
            capture_output=True,
            text=True,
            check=False,
            shell=True,
        )
        return "ire-redis" in result.stdout
    except FileNotFoundError:
        return False
