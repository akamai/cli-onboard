# Spec: Vendor `auto_adjust_xlsx_column_width` and drop the `UliPlot` dependency

Status: drafted from a first-time-install performance investigation, 2026-07-31.
Tracker: no issue tracker vocabulary is configured for this repo (`ready-for-agent` label doesn't exist on `akamai/cli-onboard`, `/setup-matt-pocock-skills` hasn't been run) — user asked to file this locally under `.scratch/` rather than publish to GitHub Issues. Promote it later with `/setup-matt-pocock-skills` + a tracker if desired.

## Problem Statement

The very first invocation of any `onboard` subcommand after a fresh install (e.g. `akamai onboard --version`) takes 12x longer than every subsequent call — 13.8-16.1s cold vs 1.3s warm, measured with `python -X importtime` against a freshly `uv tool install -e .`'d copy with zero `__pycache__`. The delay is CPython's one-time bytecode compilation of the entire import graph pulled in by `bin/akamai-onboard.py`'s unconditional top-level imports, which run before Click parses any subcommand — so even `--version`/`--help` pay for imports they never use.

Profiling the cold run's import costs showed:

- `pandas` — ~8.8s cumulative (expected: it's a real, used dependency for report/Excel generation)
- `UliPlot.XLSX` — ~2.8s cumulative, and it drags in `matplotlib` and `PIL`/`Pillow` as transitive deps
- `utility` (this repo's own module) — ~3.2s cumulative, mostly attributable to the `UliPlot` chain above

`UliPlot` is imported in exactly two places (`bin/utility.py:32`, `bin/utility_smoketest.py:32`) for exactly one function: `auto_adjust_xlsx_column_width`, used to auto-size Excel columns when writing `.xlsx` report output (`bin/utility.py:2664`, `:2721`, `bin/utility_smoketest.py:506`). Reading `UliPlot`'s source confirms `auto_adjust_xlsx_column_width` itself (in `UliPlot/XLSX.py`) depends only on `openpyxl` (already a direct dependency of this project) plus stdlib `decimal`/`functools` — none of its logic touches plotting. The `matplotlib`/`PIL` cost comes entirely from `UliPlot/__init__.py` unconditionally importing `Size`/`Style` (figure-sizing and `ggplot`-style helpers for matplotlib plots), which this codebase never uses — there is no plotting anywhere in `cli-onboard`.

So `UliPlot` is dead weight: a full plotting library pulled in for one 35-line, openpyxl-only helper function, adding real cost to both the first-run compile tax and (to a lesser extent) every warm run's import time.

## Solution

Vendor `auto_adjust_xlsx_column_width` (and its two small private helpers, `text_length` and `_to_str_for_length`) into a new local module, `bin/xlsx_util.py`, copied near-verbatim from `UliPlot/XLSX.py` since it already depends only on `openpyxl` + stdlib. Update the two call sites to import from `bin/xlsx_util.py` instead of `UliPlot.XLSX`. Remove `uliplot==0.2.4` from `pyproject.toml`'s dependency list. No behavior change: same column-width calculation, same function signature, same call sites, same `.xlsx` output.

## User Stories

1. As a first-time `cli-onboard` user, I want `akamai onboard --version` (and every other subcommand) to not pay import cost for a plotting library the tool never plots with, so my first invocation isn't disproportionately slow.
2. As a maintainer, I want the Excel column-auto-width logic to live in this repo's own source rather than behind a third-party package whose only used surface is one function, so the dependency footprint matches what's actually used.
3. As a maintainer auditing `pyproject.toml`, I want every listed dependency to correspond to functionality this codebase actually exercises, so I'm not left wondering why a CLI tool with no charts depends on `matplotlib`/`Pillow` (transitively, via `uliplot`).
4. As a CLI user generating `.xlsx` report output (via `convert`, `batch_create`, or `sbd_precheck`/smoke-test commands), I want the auto-sized columns in my output spreadsheet to look identical to before this change, so nothing about my workflow changes.
5. As a future contributor, I want a small, self-contained `bin/xlsx_util.py` with no external dependency beyond `openpyxl`, so its behavior is easy to read and modify without chasing into a third-party package's source.

## Implementation Decisions

- **New module: `bin/xlsx_util.py`.** Holds `auto_adjust_xlsx_column_width(df, writer, sheet_name, margin=3, length_factor=1.0, decimals=3, index=True)` plus its two helpers `text_length(text)` and `_to_str_for_length(v, decimals=3)`, copied from `UliPlot/XLSX.py` with only the import of `openpyxl.utils.cell` (already used) and stdlib `decimal`/`functools` retained. Function signature, defaults, and internal logic (openpyxl vs xlsxwriter writer-type branching, column-width computation, index-column handling) are preserved exactly.
- **Update call sites.** `bin/utility.py:32` and `bin/utility_smoketest.py:32` change `from UliPlot.XLSX import auto_adjust_xlsx_column_width` to `from xlsx_util import auto_adjust_xlsx_column_width`. The three call sites (`bin/utility.py:2664`, `:2721`, `bin/utility_smoketest.py:506`) are unchanged — same arguments, same call shape.
- **Drop the dependency.** Remove `"uliplot==0.2.4"` from `[project.dependencies]` in `pyproject.toml`. Update `uv.lock` accordingly (regenerate via `uv lock`). This also drops `matplotlib`/`Pillow`/related transitive deps that were only pulled in for `uliplot`, unless something else in the dependency tree independently needs them (verify with `uv tree` before/after).
- **No new third-party replacement needed.** `openpyxl` and `xlsxwriter` are already direct dependencies and are the only packages the vendored function touches — nothing else is added.

## Testing Decisions

- A good test here exercises observable behavior: given a small `pandas.DataFrame` written to an in-memory/temp `.xlsx` via both supported writer engines (`openpyxl` and `xlsxwriter`), confirm the resulting column widths match what the pre-vendoring `UliPlot.XLSX.auto_adjust_xlsx_column_width` produced for the same input (a golden-value or direct comparison test) — not implementation details of how the width is computed internally.
- No existing tests currently cover `write_xlsx`, `auto_adjust_xlsx_column_width`, or `UliPlot` usage in `tests/` — this is new test coverage, not an extension of prior art. Place it as `tests/test_xlsx_util.py`, following this repo's existing pytest conventions (`pythonpath = ["bin"]` per `pyproject.toml`, so `from xlsx_util import auto_adjust_xlsx_column_width` works directly in tests).
- Cover: numeric columns, string columns with embedded newlines (exercises `text_length`'s multi-line branch), float columns (exercises `_to_str_for_length`'s `Decimal` rounding), and the `index=True`/`index=False` split.
- Also worth a regression check (not a unit test, a manual/CI timing check): re-run the cold-vs-warm import timing comparison (`python -X importtime` on a fresh `uv tool install -e .`) after this change to confirm the `matplotlib`/`PIL`/`UliPlot` cost is gone from the cold-run profile.

## Out of Scope

- Any further reduction of the `pandas` import cost (~8.8s of the cold-run total) — `pandas` is genuinely used throughout this codebase for DataFrame-based report generation and CSV handling; removing or lazy-loading it is a much larger, separate effort with its own tradeoffs (e.g. deferring imports into each subcommand function body so `--version`/`--help` skip it entirely).
- Deferring/lazifying the other heavy top-level imports in `bin/akamai-onboard.py` (`jsonschema`, `cerberus`, `pyisemail`, `openpyxl`, `xlsxwriter`, `aiohttp`) so trivial commands like `--version`/`--help` don't pay for them — a related but separate fix with broader blast radius (touches every subcommand's import structure), not bundled into this dependency-removal change.
- Pre-compiling bytecode at install time (e.g. `python -m compileall` as an install-hook step) to shift the one-time compile cost from first-run to install-time — an alternative/complementary mitigation, not part of this spec.
- Any change to `akamai-cli`'s own install mechanism (the separate, already-tracked `venv`/Python-3.14 compatibility bug in `akamai-cli` itself, documented in this repo's `CONTRIBUTING.md` under "Troubleshooting `akamai install`") — unrelated to this spec.

## Further Notes

- This was surfaced while diagnosing why `akamai onboard --version` is slow only on the first call after install: root cause is one-time `.pyc` compilation of a large import graph, not per-run overhead. Vendoring this function is the cheapest, lowest-risk slice of that fix (removes a whole heavyweight, unused plotting library) and can land independently of the larger "defer imports until subcommand dispatch" effort described in Out of Scope.
- Verify via `uv tree` (before/after) whether `matplotlib`/`Pillow` are pulled in by anything else in the dependency tree — if so, the win here is smaller than expected (just `UliPlot` itself) but the dependency-hygiene argument still holds.
