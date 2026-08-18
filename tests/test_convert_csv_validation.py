"""Checks that the CSV file a user uploads for onboarding is properly validated before processing continues."""
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
    """Known gap: a CSV with only column headers and no data currently passes silently instead of showing an error."""
    path = headers_only_csv_factory(['hostname', 'propertyName'])
    valid, rows = util.csv_validator_convert(path)
    assert valid is True
    assert rows == []


def test_duplicate_hostname_rows_currently_pass_silently(util, csv_factory):
    """Known gap: a CSV with the same hostname listed twice is accepted without warning the user to fix it."""
    path = csv_factory([
        {'hostname': 'www.example.com', 'propertyName': 'prop-a'},
        {'hostname': 'www.example.com', 'propertyName': 'prop-b'},
    ])
    valid, rows = util.csv_validator_convert(path)
    assert valid is True
    assert len(rows) == 2
