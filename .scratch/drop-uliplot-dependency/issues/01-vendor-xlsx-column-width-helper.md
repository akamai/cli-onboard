# 01 — Vendor `auto_adjust_xlsx_column_width` into `bin/xlsx_util.py`

## Parent

`.scratch/drop-uliplot-dependency-spec.md`

## What to build

`UliPlot.XLSX.auto_adjust_xlsx_column_width` (the Excel auto-column-width helper used when writing `.xlsx` report output) only depends on `openpyxl` plus stdlib `decimal`/`functools` — none of its logic touches plotting. The `matplotlib`/`PIL` cost that comes with importing `UliPlot` is entirely from `UliPlot/__init__.py` unconditionally importing unrelated figure/plotting helpers that this codebase never uses.

Add a new module, `bin/xlsx_util.py`, containing `auto_adjust_xlsx_column_width(df, writer, sheet_name, margin=3, length_factor=1.0, decimals=3, index=True)` plus its two private helpers `text_length(text)` and `_to_str_for_length(v, decimals=3)`, copied near-verbatim from `UliPlot/XLSX.py`. Function signature, defaults, and internal logic (openpyxl-vs-xlsxwriter writer-type branching, column-width computation, index-column handling) must match exactly — this ticket only adds the new module; it does not yet switch any call sites over (that's ticket 02).

This slice is independently verifiable: with `bin/xlsx_util.py` in place and tested, `UliPlot` is still imported and used everywhere it currently is — nothing observable changes yet, but the new module's output can be proven equivalent before anything switches over to it.

## Acceptance criteria

- [ ] `bin/xlsx_util.py` exists with `auto_adjust_xlsx_column_width`, `text_length`, and `_to_str_for_length`, matching `UliPlot/XLSX.py`'s signatures and behavior exactly
- [ ] `bin/xlsx_util.py` imports only `openpyxl.utils.cell` and stdlib (`decimal`, `functools`) — no `matplotlib`, no `PIL`, no `UliPlot`
- [ ] New test file `tests/test_xlsx_util.py` covers: numeric columns, string columns with embedded newlines (multi-line branch of `text_length`), float columns (`Decimal`-rounding branch of `_to_str_for_length`), and both `index=True`/`index=False`
- [ ] For each covered case, `xlsx_util.auto_adjust_xlsx_column_width`'s resulting column widths are directly compared against `UliPlot.XLSX.auto_adjust_xlsx_column_width`'s output for the same input/writer, proving equivalence before anything depends on the new module
- [ ] Both `openpyxl` and `xlsxwriter` writer engines are exercised (the function branches on `type(writer.book).__module__`)
- [ ] No existing call site (`bin/utility.py`, `bin/utility_smoketest.py`) is changed in this ticket — `UliPlot` usage there is untouched
- [ ] Existing test suite passes unchanged

## Blocked by

None - can start immediately
