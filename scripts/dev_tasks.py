"""Local development tasks (argparse-based).

Replaces the legacy Click CLI with a lightweight argparse dispatcher.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from collections.abc import Callable

from rich.table import Table

from scripts.cli_utils import (
    API_PID_FILE,
    API_PORT,
    LOGS_DIR,
    PROJECT_ROOT,
    QDRANT_PORT,
    REDIS_PORT,
    check_docker,
    confirm_destructive,
    console,
    error,
    get_api_pid,
    info,
    is_api_running,
    is_qdrant_running,
    is_redis_running,
    run_command,
    section,
    success,
    warning,
)

COMPOSE_FILE = PROJECT_ROOT / "docker" / "docker-compose.yml"


def kill_process_on_port(port: int) -> bool:
    """Kill any process using the specified port."""
    try:
        result = run_command(
            [
                "lsof",
                "-ti",
                f":{port}",
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid_str in pids:
                try:
                    pid = int(pid_str)
                    info(f"Killing process {pid} on port {port}...")
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(0.5)
                except (ValueError, ProcessLookupError):
                    pass
            return True
        return False
    except Exception as exc:  # pragma: no cover - best effort cleanup
        warning(f"Could not check port {port}: {exc}")
        return False


def kill_process_forcefully(pid: int, timeout: float = 2.0) -> bool:
    """Kill a process, trying SIGTERM first, then SIGKILL if needed."""
    try:
        os.kill(pid, signal.SIGTERM)
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                return True

        warning(f"Process {pid} didn't respond to SIGTERM, using SIGKILL...")
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        return True

    except ProcessLookupError:
        return False
    except Exception as exc:
        error(f"Failed to kill process {pid}: {exc}")
        return False


def wait_for_qdrant(timeout: int = 30) -> bool:
    """Wait for Qdrant to be ready by polling its health endpoint."""
    import httpx

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = httpx.get(f"http://localhost:{QDRANT_PORT}/healthz", timeout=2.0)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_for_redis(timeout: int = 30) -> bool:
    """Wait for Redis to be ready by polling with redis-cli."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            result = run_command(
                ["docker", "exec", "ire-redis", "redis-cli", "ping"],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0 and "PONG" in result.stdout:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def cmd_start(_args: argparse.Namespace) -> None:
    """Start Qdrant, Redis, and API services."""
    section("Starting Local Services")

    if not check_docker():
        error("Docker is not running or not installed")
        console.print("\nPlease install Docker and ensure it's running:")
        console.print("  https://docs.docker.com/get-docker/")
        sys.exit(1)

    if kill_process_on_port(API_PORT):
        success(f"Cleaned up zombie process on port {API_PORT}")

    info("Starting Docker services (Qdrant + Redis)...")
    try:
        run_command(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "up",
                "-d",
            ],
            capture_output=True,
        )
        time.sleep(2)

        if is_qdrant_running():
            success("Qdrant started successfully")
        else:
            error("Failed to start Qdrant")
            result = run_command(["docker", "logs", "qdrant"], capture_output=True, check=False)
            if result.stdout:
                console.print(result.stdout)
            sys.exit(1)

        if is_redis_running():
            success("Redis started successfully")
        else:
            error("Failed to start Redis")
            result = run_command(["docker", "logs", "ire-redis"], capture_output=True, check=False)
            if result.stdout:
                console.print(result.stdout)
            sys.exit(1)

    except Exception as exc:
        error(f"Failed to start Docker services: {exc}")
        sys.exit(1)

    info("Waiting for services to be ready...")
    if not wait_for_qdrant(timeout=30):
        error("Qdrant failed to become ready")
        sys.exit(1)

    if not wait_for_redis(timeout=30):
        error("Redis failed to become ready")
        sys.exit(1)

    success("All Docker services are ready")

    if is_api_running():
        warning(f"API is already running (PID: {get_api_pid()})")
    else:
        info("Starting API...")
        try:
            LOGS_DIR.mkdir(exist_ok=True)
            env = os.environ.copy()
            env["REDIS_URL"] = f"redis://localhost:{REDIS_PORT}"

            import subprocess

            process = subprocess.Popen(
                [
                    "uv",
                    "run",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(API_PORT),
                    "--reload",
                ],
                cwd=PROJECT_ROOT,
                stdout=open(LOGS_DIR / "api.log", "w"),
                stderr=subprocess.STDOUT,
                env=env,
            )

            with open(API_PID_FILE, "w") as file:
                file.write(str(process.pid))

            time.sleep(3)

            if is_api_running():
                success(f"API started (PID: {get_api_pid()})")
            else:
                error("Failed to start API")
                if (LOGS_DIR / "api.log").exists():
                    with open(LOGS_DIR / "api.log") as file:
                        console.print(file.read()[-500:])
                sys.exit(1)
        except Exception as exc:
            error(f"Failed to start API: {exc}")
            sys.exit(1)

    console.print()
    success("All services started!")
    console.print("\n[bold cyan]Endpoints:[/bold cyan]")
    console.print(f"  Qdrant Dashboard: http://localhost:{QDRANT_PORT}/dashboard")
    console.print("  Redis CLI: docker exec -it ire-redis redis-cli")
    console.print(f"  API Docs: http://localhost:{API_PORT}/docs")
    console.print(f"  API Health: http://localhost:{API_PORT}/")
    console.print(f"  Auth Status: http://localhost:{API_PORT}/auth/status")


def cmd_stop(_args: argparse.Namespace) -> None:
    """Stop Qdrant, Redis, and API services."""
    section("Stopping Local Services")

    if is_api_running():
        pid = get_api_pid()
        if pid is not None:
            info(f"Stopping API (PID: {pid})...")
            if kill_process_forcefully(pid, timeout=2.0):
                success("API stopped")
            else:
                warning("API process not found")
            if API_PID_FILE.exists():
                API_PID_FILE.unlink()
        else:
            warning("API PID file exists but PID could not be read")
            if API_PID_FILE.exists():
                API_PID_FILE.unlink()
    else:
        info("API is not running")

    kill_process_on_port(API_PORT)

    if is_qdrant_running() or is_redis_running():
        info("Stopping Docker services (Qdrant + Redis)...")
        try:
            run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(COMPOSE_FILE),
                    "down",
                ],
                capture_output=True,
            )
            success("Docker services stopped")
        except Exception as exc:
            error(f"Failed to stop Docker services: {exc}")
    else:
        info("Docker services are not running")

    console.print()
    success("All services stopped!")


def cmd_restart(_args: argparse.Namespace) -> None:
    """Restart Qdrant, Redis, and API services."""
    section("Restarting Local Services")
    cmd_stop(_args)
    time.sleep(2)
    cmd_start(_args)


def cmd_status(_args: argparse.Namespace) -> None:
    """Show status of local services."""
    section("Service Status")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Details", style="white")

    if is_qdrant_running():
        result = run_command(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "CPU: {{.CPUPerc}}, Memory: {{.MemUsage}}",
                "qdrant",
            ],
            capture_output=True,
            check=False,
        )
        stats = result.stdout.strip() if result.returncode == 0 else "N/A"
        table.add_row("Qdrant (Docker)", "[green]Running[/green]", stats)
    else:
        table.add_row("Qdrant (Docker)", "[red]Stopped[/red]", "")

    if is_redis_running():
        result = run_command(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "CPU: {{.CPUPerc}}, Memory: {{.MemUsage}}",
                "ire-redis",
            ],
            capture_output=True,
            check=False,
        )
        stats = result.stdout.strip() if result.returncode == 0 else "N/A"
        table.add_row("Redis (Docker)", "[green]Running[/green]", stats)
    else:
        table.add_row("Redis (Docker)", "[red]Stopped[/red]", "")

    if is_api_running():
        pid = get_api_pid()
        table.add_row("API (UV/Python)", "[green]Running[/green]", f"PID: {pid}")
    else:
        table.add_row("API (UV/Python)", "[red]Stopped[/red]", "")

    console.print(table)
    console.print("\n[bold cyan]Endpoints:[/bold cyan]")
    console.print(f"  Qdrant Dashboard: http://localhost:{QDRANT_PORT}/dashboard")
    console.print("  Redis CLI: docker exec -it ire-redis redis-cli")
    console.print(f"  API Docs: http://localhost:{API_PORT}/docs")
    console.print(f"  API Health: http://localhost:{API_PORT}/")
    console.print(f"  Auth Status: http://localhost:{API_PORT}/auth/status")

    storage_path = PROJECT_ROOT / "data" / "qdrant_storage"
    if storage_path.exists():
        result = run_command(["du", "-sh", str(storage_path)], capture_output=True, check=False)
        if result.returncode == 0:
            size = result.stdout.split()[0]
            console.print(f"\n[bold cyan]Storage:[/bold cyan] {size}")


def cmd_logs(args: argparse.Namespace) -> None:
    """Show logs from local services."""
    section("Service Logs")

    if args.follow:
        console.print("[yellow]Following logs (Ctrl+C to stop)...[/yellow]\n")
        console.print("[bold cyan]API Logs:[/bold cyan]")
        if (LOGS_DIR / "api.log").exists():
            try:
                run_command(["tail", "-f", str(LOGS_DIR / "api.log")], check=False)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped following logs[/yellow]")
        else:
            warning("No API logs yet")
    else:
        console.print("[bold cyan]Qdrant Logs (last 20 lines):[/bold cyan]")
        if is_qdrant_running():
            run_command(["docker", "logs", "--tail", str(args.lines), "qdrant"], check=False)
        else:
            warning("Qdrant is not running")

        console.print(f"\n[bold cyan]API Logs (last {args.lines} lines):[/bold cyan]")
        if (LOGS_DIR / "api.log").exists():
            run_command(["tail", "-n", str(args.lines), str(LOGS_DIR / "api.log")], check=False)
        else:
            warning("No API logs yet")


def _ensure_qdrant_running() -> None:
    if not is_qdrant_running():
        error("Qdrant is not running")
        console.print("\nPlease start services first:")
        console.print("  make dev-start")
        sys.exit(1)


def cmd_index(_args: argparse.Namespace) -> None:
    """Index IRE resources into local Qdrant."""
    section("Indexing IRE Resources (Local)")
    _ensure_qdrant_running()

    info("Running unified indexing script (sequential processing)...")
    console.print()

    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.index import main as index_main

        index_main()
    except Exception as exc:
        error(f"Indexing failed: {exc}")
        sys.exit(1)


def cmd_index_test(_args: argparse.Namespace) -> None:
    """Index test fixtures into local Qdrant for E2E testing."""
    section("Indexing Test Fixtures (Local)")
    _ensure_qdrant_running()

    test_fixtures_path = PROJECT_ROOT / "data" / "fixtures.json"
    if not test_fixtures_path.exists():
        warning("Test fixtures not found")
        console.print("\nThe tracked fixtures file is missing: data/fixtures.json")
        console.print("Ensure you have pulled the repository or obtain the file from the team.")
        sys.exit(1)

    info("Running unified indexing script with test fixtures...")
    console.print()

    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.index import main as index_main

        index_main(test_data=True)
    except Exception as exc:
        error(f"Indexing failed: {exc}")
        sys.exit(1)


def cmd_clear_db(_args: argparse.Namespace) -> None:
    """Clear the local Qdrant database."""
    if not confirm_destructive(
        "clear the local Qdrant database",
        "This will delete all indexed documents from the local database.",
    ):
        console.print("\n[yellow]Operation cancelled[/yellow]")
        return

    section("Clearing Local Database")
    _ensure_qdrant_running()

    info("Clearing database...")
    console.print()

    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.clear_db import main as clear_main

        clear_main()
    except Exception as exc:
        error(f"Failed to clear database: {exc}")
        sys.exit(1)


def cmd_rebuild(args: argparse.Namespace) -> None:
    """Complete database rebuild: stop → delete storage → start → index."""
    if not args.yes and not confirm_destructive(
        "completely rebuild the local database",
        "This will:\n  1. Stop all services\n  2. Delete ALL Qdrant storage data\n  3. Restart services\n  4. Re-index all documents\n\nThis operation cannot be undone.",
    ):
        console.print("\n[yellow]Operation cancelled[/yellow]")
        return

    section("Complete Database Rebuild")

    console.print("\n[bold cyan]Step 1/4: Stopping services...[/bold cyan]")
    cmd_stop(args)
    time.sleep(2)

    console.print("\n[bold cyan]Step 2/4: Deleting Qdrant storage...[/bold cyan]")
    storage_path = PROJECT_ROOT / "data" / "qdrant_storage"

    if storage_path.exists():
        import shutil

        try:
            result = run_command(["du", "-sh", str(storage_path)], capture_output=True, check=False)
            size = result.stdout.split()[0] if result.returncode == 0 else "unknown"

            info(f"Deleting {storage_path} ({size})...")
            shutil.rmtree(storage_path)
            success("Storage directory deleted")
        except Exception as exc:
            error(f"Failed to delete storage: {exc}")
            sys.exit(1)
    else:
        info("Storage directory doesn't exist (already clean)")

    console.print("\n[bold cyan]Step 3/4: Starting services...[/bold cyan]")
    cmd_start(args)
    time.sleep(3)

    console.print("\n[bold cyan]Step 4/4: Indexing data...[/bold cyan]")
    cmd_index(args)

    console.print("\n[bold cyan]Verifying rebuild...[/bold cyan]")
    try:
        import httpx

        response = httpx.get(f"http://localhost:{API_PORT}/stats", timeout=30.0)
        if response.status_code == 200:
            stats = response.json()
            points = stats.get("total_points", 0)
            if points > 0:
                success(f"Rebuild complete! Collection has {points} points")
            else:
                warning("Rebuild completed but collection is empty")
        else:
            warning("Could not verify collection stats")
    except Exception as exc:
        warning(f"Could not verify rebuild: {exc}")

    console.print("\n[bold green]Database rebuild complete![/bold green]")
    console.print("\n[cyan]Next steps:[/cyan]")
    console.print("  • Test search: make dev-test")
    console.print("  • View stats: curl http://localhost:8000/stats")
    console.print("  • API docs: http://localhost:8000/docs")


def cmd_clear_cache(_args: argparse.Namespace) -> None:
    """Clear all API caches (search, resource, similar)."""
    section("Clearing Local API Cache")

    if not is_api_running():
        error("API is not running")
        console.print("\nPlease start services first:")
        console.print("  make dev-start")
        sys.exit(1)

    info("Clearing all caches...")

    try:
        import httpx

        response = httpx.post(f"http://localhost:{API_PORT}/admin/clear-cache", timeout=10.0)
        if response.status_code == 200:
            result = response.json()
            success(result.get("message", "Caches cleared"))
        else:
            error(f"API returned status {response.status_code}")
            sys.exit(1)

    except ImportError:
        error("httpx not installed")
        console.print("\nInstall with: uv pip install httpx")
        sys.exit(1)
    except Exception as exc:
        error(f"Failed to clear cache: {exc}")
        sys.exit(1)


def cmd_test(_args: argparse.Namespace) -> None:
    """Run a test search query."""
    section("Testing Local API")

    if not is_api_running():
        error("API is not running")
        console.print("\nPlease start services first:")
        console.print("  make dev-start")
        sys.exit(1)

    info("Testing API endpoint...")

    try:
        import httpx

        response = httpx.get(f"http://localhost:{API_PORT}/")
        if response.status_code == 200:
            success("API is responding")
            console.print(response.json())
        else:
            error(f"API returned status {response.status_code}")

        console.print("\n[bold cyan]Collection Stats:[/bold cyan]")
        response = httpx.get(f"http://localhost:{API_PORT}/stats")
        if response.status_code == 200:
            stats = response.json()
            console.print(f"  Total points: {stats.get('total_points', 0)}")
            console.print(f"  Collection: {stats.get('collection', 'N/A')}")
        else:
            warning("Could not fetch stats")

    except ImportError:
        error("httpx not installed")
        console.print("\nInstall with: uv pip install httpx")
    except Exception as exc:
        error(f"Test failed: {exc}")


def cmd_test_backend(args: argparse.Namespace) -> None:
    """Run backend pytest tests."""
    section("Running Backend Tests")

    cmd = ["uv", "run", "pytest"]

    if args.verbose:
        cmd.append("-v")

    if args.coverage:
        cmd.extend(["--cov=app", "--cov=scripts", "--cov-report=html", "--cov-report=term"])

    if args.filter:
        cmd.extend(["-k", args.filter])

    cmd.append("tests/")

    info("Running pytest...")
    console.print()
    result = run_command(cmd, check=False, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        console.print()
        success("All tests passed!")
        if args.coverage:
            console.print("\n[cyan]Coverage report generated:[/cyan]")
            console.print("  HTML: htmlcov/index.html")
    else:
        console.print()
        error("Some tests failed")
        sys.exit(result.returncode)


COMMANDS: dict[str, tuple[str, Callable[[argparse.Namespace], None]]]
COMMANDS = {
    "start": ("Start Qdrant, Redis, and API services", cmd_start),
    "stop": ("Stop Qdrant, Redis, and API services", cmd_stop),
    "restart": ("Restart Qdrant, Redis, and API services", cmd_restart),
    "status": ("Show status of local services", cmd_status),
    "logs": ("Show logs from local services", cmd_logs),
    "index": ("Index IRE resources into local Qdrant", cmd_index),
    "index-test": ("Index test fixtures into local Qdrant", cmd_index_test),
    "clear-db": ("Clear the local Qdrant database", cmd_clear_db),
    "rebuild": ("Complete database rebuild", cmd_rebuild),
    "clear-cache": ("Clear all API caches", cmd_clear_cache),
    "test": ("Run a test search query", cmd_test),
    "test-backend": ("Run backend pytest suite", cmd_test_backend),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local development tasks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("start", help=COMMANDS["start"][0])
    subparsers.add_parser("stop", help=COMMANDS["stop"][0])
    subparsers.add_parser("restart", help=COMMANDS["restart"][0])
    subparsers.add_parser("status", help=COMMANDS["status"][0])

    logs_parser = subparsers.add_parser("logs", help=COMMANDS["logs"][0])
    logs_parser.add_argument("--follow", "-f", action="store_true", help="Follow log output")
    logs_parser.add_argument("--lines", "-n", type=int, default=20, help="Number of lines to show")

    subparsers.add_parser("index", help=COMMANDS["index"][0])
    subparsers.add_parser("index-test", help=COMMANDS["index-test"][0])
    subparsers.add_parser("clear-db", help=COMMANDS["clear-db"][0])

    rebuild_parser = subparsers.add_parser("rebuild", help=COMMANDS["rebuild"][0])
    rebuild_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    subparsers.add_parser("clear-cache", help=COMMANDS["clear-cache"][0])
    subparsers.add_parser("test", help=COMMANDS["test"][0])

    test_backend_parser = subparsers.add_parser("test-backend", help=COMMANDS["test-backend"][0])
    test_backend_parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    test_backend_parser.add_argument("--coverage", "-c", action="store_true", help="Run with coverage report")
    test_backend_parser.add_argument("--filter", "-k", help="Run tests matching the given expression")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    _, handler = COMMANDS[args.command]
    handler(args)


if __name__ == "__main__":
    main()
