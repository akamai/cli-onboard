# Contributing to cli-onboard

## Dev environment setup

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

### Trying your change with the real `akamai` CLI

1. Check out the branch: `git checkout -b new-branch`
2. Uninstall the existing version: `akamai uninstall onboard`
3. Get the repo's absolute path: `pwd` (e.g. `/Users/Documents/cli-onboard`)
4. Install from the local repo:
   - **macOS / Linux / Windows**: `akamai install "file://$(pwd)"`

Local artifacts are written to folders such as `logs/`, and `convert` writes an Excel workbook under `output/{account_name}/`.

## Running the tests

```bash
uv run pytest -v
```

(or plain `pytest -v` if you're using the `pip`/venv path). This is the same command CI runs (`.github/workflows/build.yml`), across Python 3.12–3.14 on Linux, macOS, and Windows.

## Running the linter

This repo uses [pre-commit](https://pre-commit.com/) (`.pre-commit-config.yaml`) for formatting and lint checks: `flake8`, `reorder-python-imports`, `pyupgrade`, `markdownlint` (for `README.md`/`CHANGELOG.md`), and two local hooks that keep generated content in sync — `sync-cli-manifest` (`cli.json` version/description from `pyproject.toml`) and `sync-readme-commands` (README's Command catalog from the CLI's actual registered commands).

The same hook set also runs three security checks, each blocking on any finding: `uv audit` (dependency vulnerability scanning), `bandit` (static analysis for insecure code patterns, medium+ severity), and `gitleaks` (secret scanning — staged changes locally, full git history in CI). CI (`.github/workflows/security.yml`) runs the same three on every push/PR.

```bash
pre-commit install       # once, so hooks run automatically on every commit
pre-commit run           # runs against your staged changes, same as a real commit
```

If a hook modifies a file (for example, rewriting a generated section), re-stage the file and commit again — that's expected, not an error. Avoid `pre-commit run --all-files` for everyday changes — it runs every hook against every file in the repo, which can surface unrelated pre-existing issues that have nothing to do with your change.

## Submitting a change

By submitting a contribution to this project, you assign the contribution and associated copyright rights to the repository owner.

1. Branch off `master`.
2. Make your change, with tests where they apply.
3. Run the test suite and `pre-commit run` locally before opening a PR.
4. Open a PR against `master`. CI (`.github/workflows/build.yml`) runs the same test suite across the supported OS/Python matrix, plus a `pip install` smoke test.

## Troubleshooting `akamai install`

If the install command fails, find the error message below and follow the fix.

**Error: `venv python package not found`**

What's happening: your computer's Python is a very new version (3.14), and your copy of `akamai-cli` is too old to work with it — this is a known bug ([akamai/cli#214](https://github.com/akamai/cli/issues/214)) that's already been fixed in newer releases.

Fix: update `akamai-cli`, then try installing again.

```bash
akamai upgrade
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

**Need to use a specific Python version (e.g. 3.12) instead of your default one?**

What's happening: `akamai-cli` always uses whatever program is named `python` on your computer. If you have multiple Python versions and need a particular one just for this install, you can temporarily point `python` at it.

Fix (using `uv`, a Python version manager):

```bash
uv python install 3.12 --default   # installs Python 3.12 and makes it the default (skipped if already installed)
PATH="$HOME/.local/bin:$PATH" PIP_BREAK_SYSTEM_PACKAGES=1 PIP_IGNORE_INSTALLED=1 \
  akamai install "file://$(pwd)"
```
