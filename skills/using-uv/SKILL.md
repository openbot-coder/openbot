---
name: "using-uv"
description: "Guide for using uv Python package manager. Invoke when working with Python dependencies, creating virtual environments, or managing Python projects with uv."
---

# Using uv - Python Package Manager

uv is an extremely fast Python package installer and resolver, written in Rust. This skill provides guidance on using uv for Python dependency management.

## When to Use This Skill

- Creating or managing Python virtual environments
- Installing Python packages
- Managing project dependencies
- Running Python scripts with dependency isolation
- Working with pyproject.toml

## Common Commands

### Project Initialization

```bash
# Initialize a new Python project with package structure
uv init --package [project-name]

# Initialize a new Python project (simple)
uv init [project-name]

# Create a new project in current directory
uv init
```

### Virtual Environment Management

```bash
# Create a virtual environment
uv venv

# Create venv with specific Python version
uv venv --python 3.11

# Create venv with custom name
uv venv .venv-name

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Activate virtual environment (Unix/macOS)
source .venv/bin/activate
```

### Package Management

```bash
# Add a package to dependencies
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Add a package with version constraint
uv add "package>=1.0.0"

# Remove a package
uv remove <package-name>

# Install all dependencies from pyproject.toml
uv sync

# Install only production dependencies
uv sync --no-dev
```

### Running Commands

```bash
# Run a Python script
uv run python script.py

# Run a command in the virtual environment
uv run <command>

# Run pytest
uv run pytest

# Run with specific Python version
uv run --python 3.11 python script.py
```

### Package Installation (pip-like)

```bash
# Install a package (one-off)
uv pip install <package-name>

# Install from requirements.txt
uv pip install -r requirements.txt

# Install from pyproject.toml
uv pip install -e .

# List installed packages
uv pip list

# Show package info
uv pip show <package-name>

# Uninstall a package
uv pip uninstall <package-name>
```

### Python Version Management

```bash
# List available Python versions
uv python list

# Install a Python version
uv python install 3.11

# Pin Python version for project
uv python pin 3.11
```

### Tool Installation

```bash
# Install a tool globally
uv tool install <tool-name>

# Run a tool without installing
uvx <tool-name>

# Example: Run ruff without installing
uvx ruff check .
```

### Lock File Management

```bash
# Generate/update lock file
uv lock

# Upgrade all dependencies
uv lock --upgrade

# Upgrade specific package
uv lock --upgrade-package <package-name>
```

## Complete Project Initialization Workflow

Follow this workflow to set up a new Python project from scratch:

### Step 1: Initialize Project Directory

```bash
# Create project with package structure (recommended)
uv init --package my-project

# Or initialize in existing directory
cd my-project
uv init --package .
```

This creates:
- `pyproject.toml` - Project configuration
- `src/my_project/__init__.py` - Package entry point
- `.python-version` - Pinned Python version
- `README.md` - Project readme

### Step 2: Create Virtual Environment

```bash
# Create venv with specific Python version
uv venv --python 3.13

# The venv is created at .venv/
# Activate: .venv\Scripts\activate (Windows)
# Activate: source .venv/bin/activate (Unix/macOS)
```

### Step 3: Install Development Dependencies

```bash
# Install common development tools
uv add --dev ruff black pytest pytest-cov mypy

# Or install specific versions
uv add --dev "ruff>=0.15.0" "pytest>=9.0.0"
```

Recommended development packages:
| Package | Purpose |
|---------|---------|
| ruff | Linting and formatting |
| black | Code formatting |
| pytest | Testing framework |
| pytest-cov | Test coverage |
| mypy | Type checking |

### Step 4: Create Project Directories

```bash
# Create standard project directories
mkdir docs tests examples

# Or on Windows PowerShell
New-Item -ItemType Directory -Force -Path docs, tests, examples
```

Directory purposes:
| Directory | Purpose |
|-----------|---------|
| docs/ | Documentation files |
| tests/ | Test files |
| examples/ | Example code and usage |

### Step 5: Configure .gitignore

Ensure `.gitignore` includes these entries:

```gitignore
# Distribution
dist/

# Environment
.env
.venv

# Logs
logs/

# IDE/Tools
.trae/
```

### Step 6: Initialize Git Repository

```bash
# Initialize git
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial commit"
```

### Complete Example

```bash
# Full initialization workflow
uv init --package myproject
cd myproject
uv venv --python 3.13
uv add --dev ruff black pytest pytest-cov mypy
mkdir docs tests examples
git init
git add .
git commit -m "Initial commit"
```

### Resulting Project Structure

```
myproject/
├── .git/              # Git repository
├── .gitignore         # Git ignore rules
├── .python-version    # Python version (3.13)
├── .venv/             # Virtual environment
├── pyproject.toml     # Project config & dependencies
├── uv.lock            # Lock file
├── README.md
├── LICENSE
├── docs/              # Documentation
├── tests/             # Test files
├── examples/          # Example code
└── src/
    └── myproject/
        └── __init__.py
```

## Best Practices

1. **Use pyproject.toml**: Prefer `uv add` over `uv pip install` for project dependencies to maintain proper dependency tracking.

2. **Lock Files**: Always commit `uv.lock` to version control for reproducible builds.

3. **Virtual Environments**: Let uv manage virtual environments automatically with `uv venv` or `uv run`.

4. **Development Dependencies**: Use `--dev` flag for tools only needed during development (pytest, ruff, mypy, etc.).

5. **Python Version**: Pin Python version in project using `uv python pin` for consistency.

## Project Structure Example

```
my-project/
├── .python-version    # Pinned Python version
├── pyproject.toml     # Project configuration and dependencies
├── uv.lock            # Lock file for reproducible installs
├── .venv/             # Virtual environment (auto-created)
├── docs/              # Documentation
├── tests/             # Test files
├── examples/          # Example code
└── src/
    └── my_package/
        └── __init__.py
```

## pyproject.toml Example

```toml
[project]
name = "my-project"
version = "0.1.0"
description = "My Python project"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.28.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
```

## Migration from pip/poetry

```bash
# From requirements.txt
uv add $(cat requirements.txt)

# From poetry - just use existing pyproject.toml
uv sync
```

## Troubleshooting

- **Slow installs**: uv should be very fast. If slow, check network or try `--no-cache`
- **Version conflicts**: Use `uv lock --upgrade` to resolve
- **Python not found**: Use `uv python install <version>` to install Python
