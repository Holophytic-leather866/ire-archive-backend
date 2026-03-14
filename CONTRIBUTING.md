# Contributing to IRE Archive Backend

Thank you for your interest in contributing! This project is maintained by Investigative Reporters & Editors (IRE) and welcomes contributions from the community.

---

## Code of Conduct

Be respectful and constructive. We follow the spirit of the Contributor Covenant.

---

## Reporting Issues

Open an issue on GitHub with:

- A clear, descriptive title
- Steps to reproduce (if it's a bug)
- Expected vs. actual behavior
- Python version and OS
- Relevant logs or error messages

---

## Submitting Pull Requests

1. Fork the repository and create a branch from main:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes following the code style guidelines below.
3. Add tests for new functionality (pytest).
4. Run the checks before submitting:
   ```bash
   uv run ruff check .           # Lint
   uv run ruff format --check .  # Format check
   uv run pytest tests/ -v       # Tests
   ```
5. Open a PR against main with:
   - A clear description of what changed and why
   - Links to related issues if any

---

## Development Setup

```bash
git clone https://github.com/ireapps/ire-archive-backend.git
cd ire-archive-backend
cp .env.example .env
uv sync --all-extras
make dev-start
make dev-index
```

See the README for full details.

---

## Code Style

- Linter/Formatter: Ruff — `uv run ruff check .` and `uv run ruff format .`
- Line length: 120 characters
- Type hints: Use type hints for all function signatures
- Async tests: Use `@pytest.mark.asyncio` for async tests

---

## Commit Messages

We recommend Conventional Commits:

```
feat: add new search filter for date ranges
fix: correct reranking score threshold
docs: update API contract for /stats endpoint
test: add tests for cache invalidation
refactor: extract filter building into service
```

---

## Questions?

Open a discussion or reach out to the IRE team at help@ire.org.
