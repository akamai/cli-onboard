# Contributing to cli-onboard

> Guide for developers who want to modify cli-onboard's source: dev environment setup, testing, linting, and submitting changes.

## 🔗 Quick Links

**External Documentation:**

- [← Back to README](README.md)
- [📖 CHANGELOG.md](CHANGELOG.md) - Reference

**Within This Document:**

- [🎯 Dev environment setup](#dev-environment-setup)
- [🎯 Trying your change with the real `akamai` CLI](#trying-your-change-with-the-real-akamai-cli)
- [🎯 Running the tests](#running-the-tests)
- [🎯 Running the linter](#running-the-linter)
- [🎯 Submitting a change](#submitting-a-change)
- [💡 Troubleshooting `akamai install`](#troubleshooting-akamai-install)

---

## 🎯 Dev environment setup

The plugin metadata requires a minimum of Python 3.12.

**Using `uv`** (matches what CI uses):

```bash
git clone https://github.com/akamai/cli-onboard.git
cd cli-onboard
uv sync --all-groups --locked
```

**Using `pip`**:

```bash
git clone https://github.com/akamai/cli-onboard.git
cd cli-onboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 🎯 Trying your change with the real `akamai` CLI

1. Check out the branch: `git checkout -b new-branch`
2. Uninstall the existing version: `akamai uninstall onboard`
3. Get the repo's absolute path: `pwd` (e.g. `/Users/Documents/cli-onboard`)
4. Install from the local repo:
   - **macOS / Linux / Windows**: `akamai install "file://$(pwd)"`

Local artifacts are written to folders such as `logs/`, and `convert` writes an Excel workbook under `output/{account_name}/`.

## 🎯 Running the tests

```bash
uv run pytest -v
```

(or plain `pytest -v` if you're using the `pip`/venv path). This is the same command CI runs (`.github/workflows/build.yml`), across Python 3.12–3.14 on Linux, macOS, and Windows.

## 🎯 Running the linter

This repo uses [pre-commit](https://pre-commit.com/) (`.pre-commit-config.yaml`) for formatting and lint checks: `flake8`, `reorder-python-imports`, `pyupgrade`, `markdownlint` (for `README.md`/`CHANGELOG.md`), and two local hooks that keep generated content in sync — `sync-cli-manifest` (`cli.json` version/description from `pyproject.toml`) and `sync-readme-commands` (README's [📖 Command catalog](README.md#command-catalog) from the CLI's actual registered commands).

```bash
pre-commit install       # once, so hooks run automatically on every commit
pre-commit run           # runs against your staged changes, same as a real commit
```

If a hook modifies a file (for example, rewriting a generated section), re-stage the file and commit again — that's expected, not an error. Avoid `pre-commit run --all-files` for everyday changes — it runs every hook against every file in the repo, which can surface unrelated pre-existing issues that have nothing to do with your change.

## 🎯 Submitting a change

By submitting a contribution to this project, you assign the contribution and associated copyright rights to the repository owner.

1. Branch off `master`.
2. Make your change, with tests where they apply.
3. Run the test suite and `pre-commit run` locally before opening a PR.
4. Open a PR against `master`. CI (`.github/workflows/build.yml`) runs the same test suite across the supported OS/Python matrix, plus a `pip install` smoke test.
5. See [📖 CHANGELOG.md](CHANGELOG.md) to see how past changes were documented — add an entry there for user-facing changes.

## 💡 Troubleshooting `akamai install`

If the install command fails, find the error message below and follow the fix.

**Error: `venv python package not found`**

What's happening: your computer's Python is a very new version (3.14), and your copy of `akamai-cli` is too old to work with it — this is a known bug ([akamai/cli#214](https://github.com/akamai/cli/issues/214)) that's already been fixed in newer releases.

Fix: update `akamai-cli`, then try installing again.

```bash
akamai upgrade
```

**Error: `Package directory already exists (...\.akamai-cli\src\cli-<name>). To reinstall this package, first run 'akamai uninstall' command.`**

What's happening: `akamai install property-manager onboard` installs every listed package in one call. If any one of them (e.g. `property-manager`) is already installed, `akamai install` aborts the whole command instead of skipping it — so `onboard` never gets installed either. Run `akamai list` to see which packages you already have.

Fix: only pass the package(s) that are missing.

```bash
akamai install onboard
```

**Error: `externally-managed-environment`**

What's happening: modern versions of Python (3.11+) protect themselves from having packages installed into them by outside tools, to avoid breaking your system. The install command trips this protection.

Fix: edit your pip config to allow it, then rerun the install. This option installs libraries directly into your operating system's global Python environment.

```bash
# macOS;
# Linux: ~/.config/pip/pip.conf,
# Windows: %APPDATA%\pip\pip.ini
code ~/Library/Application\ Support/pip/pip.conf
```

```ini
[global]
break-system-packages = true
```

```bash
akamai install "file://$(pwd)"
```

If it still fails, fall back to passing the same setting inline for just this one install:

```bash
PIP_BREAK_SYSTEM_PACKAGES=1 PIP_IGNORE_INSTALLED=1 akamai install "file://$(pwd)"
```

If that still fails, install with `uv` directly instead of going through `akamai install`:

```bash
uv tool install -e .
onboard --version
```

**Windows error: `Dependency validation failed: higher version is required to install this command: required: ...\WindowsApps\python3.exe:3.12.0, have: 3.10.11`**

What's happening: on Windows, `akamai-cli` looks specifically for a program named `python3` (not just `python`). If you only installed Python via python.org, there's no real `python3.exe` — the one that resolves is `%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe`, a Windows "app execution alias" that can be registered to point at an older Python install (e.g. 3.10) even when a newer one (e.g. 3.12) is also installed. Run `where.exe python3` to confirm it only resolves to the WindowsApps path.

Fix: create a `python3.exe` copy next to your Python 3.12 install, in the same folder as `python.exe`, so it's found on `PATH` before the WindowsApps alias:

```powershell
Copy-Item "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" "$env:LOCALAPPDATA\Programs\Python\Python312\python3.exe"
where.exe python3   # should now list the Python312 folder first
```

Then retry `akamai install`.

**Need to use a specific Python version (e.g. 3.12) instead of your default one?**

What's happening: `akamai-cli` always uses whatever program is named `python` on your computer. If you have multiple Python versions and need a particular one just for this install, you can temporarily point `python` at it.

Fix (using `uv`, a Python version manager):

```bash
uv python install 3.12 --default   # installs Python 3.12 and makes it the default (skipped if already installed)
PATH="$HOME/.local/bin:$PATH" PIP_BREAK_SYSTEM_PACKAGES=1 PIP_IGNORE_INSTALLED=1 \
  akamai install "file://$(pwd)"
```

[← Back to README](README.md)
