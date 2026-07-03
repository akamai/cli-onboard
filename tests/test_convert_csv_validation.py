"""TC-B: `csv_validator_convert` (Local).

Calls utility.utility().csv_validator_convert() directly rather than going through the
full `convert` CLI command — in the real command, CSV validation runs *after*
check_cli_prereq() (shells out to the `akamai` binary) and check_api_access() (a live
API call), so it's not actually reachable "locally" via the CLI entry point. Testing
the validator function directly is both more hermetic and more precise.
"""
from __future__ import annotations

import pytest


def test_valid_csv_all_optional_columns_passes(util, csv_factory):
    path = csv_factory([
        {'hostname': 'www.example.com', 'propertyName': 'example-prop', 'product': 'prd_SPM',
         'secureNetwork': 'ENHANCED_TLS', 'AN': '12345', 'GroupID': '98765', 'orgId': 'org1',
         'edgeHostname': 'www.example.com.edgekey.net'},
    ])
    valid, rows = util.csv_validator_convert(path)
    assert valid is True
    assert len(rows) == 1


def test_valid_csv_hostname_only_passes(util, csv_factory):
    path = csv_factory([{'hostname': 'www.example.com'}])
    valid, rows = util.csv_validator_convert(path)
    assert valid is True
    assert len(rows) == 1


def test_missing_hostname_value_errors(util, csv_factory):
    path = csv_factory([{'hostname': ''}])
    valid, rows = util.csv_validator_convert(path)
    assert valid is False


def test_invalid_edgehostname_suffix_errors(util, csv_factory):
    path = csv_factory([{'hostname': 'www.example.com', 'edgeHostname': 'www.example.com.wrong-suffix.com'}])
    valid, rows = util.csv_validator_convert(path)
    assert valid is False


def test_csv_path_not_found_errors(util, tmp_path):
    missing = tmp_path / 'does-not-exist.csv'
    with pytest.raises(SystemExit):
        util.csv_validator_convert(str(missing))


def test_empty_csv_headers_only_is_a_gap_not_an_error(util, headers_only_csv_factory):
    """Documents a gap, not desired behavior.

    Per the confirmed spec, an empty CSV (headers only, no data rows) should produce a
    clear error and exit. As coded, cerberus_validator's row loop simply never
    executes, so csv_validator_convert returns (True, []) — no error at all. This test
    pins down today's actual behavior; flip it once the "give user proper error
    message and exit" behavior is implemented.
    """
    path = headers_only_csv_factory(['hostname', 'propertyName'])
    valid, rows = util.csv_validator_convert(path)
    assert valid is True
    assert rows == []


def test_duplicate_hostname_rows_currently_pass_silently(util, csv_factory):
    """Documents a gap, not desired behavior.

    Per the confirmed spec, duplicate hostname rows should produce a warning telling
    the user to fix the input CSV. csv_validator_convert's cerberus schema has no
    uniqueness constraint, so duplicates validate cleanly with no warning at all. This
    test pins down today's actual behavior; flip it once a duplicate-hostname warning
    is implemented.
    """
    path = csv_factory([
        {'hostname': 'www.example.com', 'propertyName': 'prop-a'},
        {'hostname': 'www.example.com', 'propertyName': 'prop-b'},
    ])
    valid, rows = util.csv_validator_convert(path)
    assert valid is True
    assert len(rows) == 2
