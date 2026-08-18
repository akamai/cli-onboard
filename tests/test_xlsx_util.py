from __future__ import annotations

import openpyxl.utils.cell
import pandas as pd
import pytest
from xlsx_util import _to_str_for_length
from xlsx_util import auto_adjust_xlsx_column_width
from xlsx_util import text_length


# ---------------------------------------------------------------------------
# text_length
# ---------------------------------------------------------------------------

def test_text_length_empty_and_falsy_returns_zero():
    assert text_length('') == 0
    assert text_length(None) == 0


def test_text_length_single_line():
    assert text_length('hello') == 5


def test_text_length_multiline_returns_longest_line():
    # The longest line ("a much longer middle line") should win, not the
    # total length or the first/last line.
    text = 'short\na much longer middle line\nmid'
    assert text_length(text) == len('a much longer middle line')


# ---------------------------------------------------------------------------
# _to_str_for_length
# ---------------------------------------------------------------------------

def test_to_str_for_length_rounds_floats_to_decimals():
    assert _to_str_for_length(3.14159, decimals=2) == '3.14'
    assert _to_str_for_length(3.1, decimals=3) == '3.1'


def test_to_str_for_length_leaves_non_floats_unchanged():
    assert _to_str_for_length(5) == '5'
    assert _to_str_for_length('abc') == 'abc'


# ---------------------------------------------------------------------------
# auto_adjust_xlsx_column_width — equivalence with UliPlot.XLSX's version,
# proving the vendored copy behaves identically before any call site
# switches over to it.
# ---------------------------------------------------------------------------

def _sample_df():
    return pd.DataFrame({
        'id': [1, 22, 333],
        'name': ['short', 'a much longer middle line\nwith a newline', 'x'],
        'ratio': [1.0, 3.14159, 22.5],
    })


def _widths(writer, sheet_name, engine, num_cols, index):
    sheet = writer.sheets[sheet_name]
    widths = []
    start = 1 if index else 0
    col_range = ([0] + list(range(1, num_cols + 1))) if index else range(start, start + num_cols)
    for col_idx in col_range:
        if engine == 'openpyxl':
            letter = openpyxl.utils.cell.get_column_letter(col_idx + 1)
            widths.append(sheet.column_dimensions[letter].width)
        else:  # xlsxwriter
            widths.append(sheet.col_info[col_idx][0])
    return widths


# Expected widths for `_sample_df()`, keyed by (engine, index). Pinned as
# golden values rather than compared live against UliPlot.XLSX, since this
# module was vendored specifically to drop the UliPlot dependency - equivalence
# with UliPlot.XLSX.auto_adjust_xlsx_column_width was proven at vendoring time
# (see the commit that added this file) via this same parametrized comparison.
_EXPECTED_WIDTHS = {
    ('openpyxl', True): [1.0, 3.0, 25.0, 5.0],
    ('openpyxl', False): [3.0, 25.0, 5.0],
    ('xlsxwriter', True): [1.0, 3.0, 25.0, 5.0],
    ('xlsxwriter', False): [3.0, 25.0, 5.0],
}


@pytest.mark.parametrize('engine', ['openpyxl', 'xlsxwriter'])
@pytest.mark.parametrize('index', [True, False])
def test_auto_adjust_produces_expected_widths(tmp_path, engine, index):
    df = _sample_df()
    path = tmp_path / f'test_{engine}_{index}.xlsx'

    with pd.ExcelWriter(path, engine=engine) as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=index)
        auto_adjust_xlsx_column_width(df, writer, sheet_name='Sheet1', margin=0, index=index)
        actual_widths = _widths(writer, 'Sheet1', engine, len(df.columns), index)

    assert actual_widths == _EXPECTED_WIDTHS[(engine, index)]


def test_auto_adjust_raises_on_unsupported_writer():
    class _FakeBook:
        pass

    class _FakeWriter:
        book = _FakeBook()
        sheets = {}

    with pytest.raises(ValueError):
        auto_adjust_xlsx_column_width(_sample_df(), _FakeWriter(), sheet_name='Sheet1')
