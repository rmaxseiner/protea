# Contributing to Protea

Thanks for your interest in contributing to Protea! This document outlines the process for contributing to the project.

## Ways to Contribute

- **Report bugs** - Found something broken? Open an issue
- **Suggest features** - Have an idea? Start a discussion
- **Fix bugs** - Pick up an open issue and submit a PR
- **Improve docs** - Typos, clarifications, examples
- **Add tests** - Help improve coverage

## Reporting Bugs

Before opening a bug report:
1. Check existing issues to avoid duplicates
2. Try the latest version to see if it's already fixed

When reporting, include:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Protea version and environment (Python version, OS, Docker or local)
- Relevant logs or error messages

## Suggesting Features

Open a discussion or issue with:
- The problem you're trying to solve
- Your proposed solution
- Alternatives you've considered

Not all features will be accepted - Protea aims to stay focused and simple. Don't be discouraged if your idea doesn't fit the project direction.

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/protea.git
cd protea

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests to verify setup
pytest
```

## Making Changes

### 1. Create a branch

```bash
git checkout -b your-branch-name
```

Use descriptive branch names:
- `fix-search-duplicates`
- `add-csv-export`
- `docs-update-readme`

### 2. Make your changes

- Keep changes focused - one feature or fix per PR
- Follow the existing code style
- Add tests for new functionality
- Update documentation if needed

### 3. Run tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=protea

# Run linter
ruff check src/
```

All tests must pass before submitting.

### 4. Commit your changes

Write clear commit messages:

```
Add CSV export for items

- Add export_items_csv() function
- Add /export endpoint to web UI
- Add tests for CSV generation
```

### 5. Push and open a PR

```bash
git push origin your-branch-name
```

Then open a Pull Request on GitHub/Gitea.

## Pull Request Guidelines

### PR Title
Use a clear, descriptive title:
- `Fix: Search returns duplicates for quoted queries`
- `Add: CSV export functionality`
- `Docs: Update MCP configuration examples`

### PR Description
Include:
- What the PR does
- Why the change is needed
- How to test it
- Screenshots for UI changes

### Review Process

1. Maintainer will review your PR
2. May request changes or ask questions
3. CI must pass (tests, linting)
4. Once approved, maintainer will merge

Be patient - reviews may take a few days. Feel free to ping if it's been a week.

## Code Style

### Python

- Python 3.11+ features are fine
- Use type hints
- Follow existing patterns in the codebase
- Run `ruff check` and `ruff format` before committing

### General

- Keep functions focused and small
- Prefer clarity over cleverness
- Add comments for non-obvious logic
- No unnecessary dependencies

### Tests

- Add tests for new features
- Add regression tests for bug fixes
- Use descriptive test names: `test_search_handles_special_characters`

## Project Structure

```
src/protea/
├── server.py          # MCP server entry point
├── config.py          # Configuration
├── db/                # Database layer
│   ├── connection.py  # SQLite connection
│   ├── models.py      # Pydantic models
│   └── migrations/    # SQL migrations
├── tools/             # MCP tool implementations
├── services/          # Business logic
└── web/               # FastAPI web application
    ├── routes/        # HTTP endpoints
    ├── templates/     # Jinja2 templates
    └── static/        # CSS, JS, images
```

## MCP Tools

When adding or modifying MCP tools:
- Follow existing naming conventions (`get_`, `create_`, `update_`, `delete_`)
- Return Pydantic models for success, dicts with `error` key for failures
- Add tool to `server.py` routing
- Document parameters clearly

## Questions?

Open an issue or discussion if you're unsure about anything. We're happy to help!

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
