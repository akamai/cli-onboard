# 02 — Switch call sites to `xlsx_util` and drop the `UliPlot` dependency

## Parent

`.scratch/drop-uliplot-dependency-spec.md`

## What to build

With `bin/xlsx_util.py` in place and proven equivalent (ticket 01), switch both real call sites over and remove the now-unused dependency:

- `bin/utility.py:32` and `bin/utility_smoketest.py:32`: change `from UliPlot.XLSX import auto_adjust_xlsx_column_width` to `from xlsx_util import auto_adjust_xlsx_column_width`. The three call sites (`bin/utility.py:2664`, `:2721`, `bin/utility_smoketest.py:506`) keep their existing arguments and call shape — only the import changes.
- Remove `"uliplot==0.2.4"` from `[project.dependencies]` in `pyproject.toml`, and regenerate `uv.lock` (`uv lock`).
- Check via `uv tree` (before/after) whether `matplotlib`/`Pillow` are pulled in by anything else in the dependency tree, so the actual removed footprint is documented — even if something else still needs one of them, `UliPlot` itself is confirmed gone.

This slice is the end-to-end, demoable one: after it lands, `UliPlot` no longer appears anywhere in the installed dependency tree, and a cold-install `python -X importtime` profile (`uv tool uninstall cli-onboard && uv tool install -e .` then `python -X importtime onboard --version`) should show no `UliPlot`/`matplotlib`/`PIL` entries and a measurably shorter first-run time versus the pre-change baseline (13.8–16.1s cold).

## Acceptance criteria

- [ ] `bin/utility.py` and `bin/utility_smoketest.py` import `auto_adjust_xlsx_column_width` from `xlsx_util`, not `UliPlot.XLSX`
- [ ] All three call sites unchanged in arguments/behavior; generated `.xlsx` report output (column widths) is identical to before this change
- [ ] `uliplot` removed from `pyproject.toml` and `uv.lock` regenerated
- [ ] `uv tree` no longer lists `uliplot`; result of checking whether `matplotlib`/`Pillow` survive via another dependency is noted (in the PR description or a code comment, not required to be in a file)
- [ ] Existing test suite passes unchanged
- [ ] Manual/CI regression check: fresh cold-install `-X importtime` profile confirms `UliPlot`/`matplotlib`/`PIL` no longer appear in the cold-run import graph

## Blocked by

01 (vendor `auto_adjust_xlsx_column_width` into `bin/xlsx_util.py`) — this ticket switches real call sites over to the new module, so it must exist and be proven equivalent first.
