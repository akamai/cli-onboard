"""Checks that the convert command rejects invalid combinations of command-line options with a clear error message."""
from __future__ import annotations

import pytest


@pytest.fixture
def convert_obj(akamai_onboard_module, fake_convert_utility_cls):
    """Provides a test setup that runs the convert command without needing real credentials or a live API connection."""
    return akamai_onboard_module.Config(utility_cls=fake_convert_utility_cls)


def test_enrollment_id_without_cps_errors(runner, cli, fake_edgerc, convert_obj):
    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc,
        'convert', '--csv', 'x.csv', '-d', 'x', '--enrollment-id', '12345',
    ], obj=convert_obj)
    # exit_code is 0 even on failure here — see
    # test_convert_cli_parsing.py::test_missing_edgerc_file_exits.
    assert result.exit_code == 0
    assert '--enrollment-id requires --cert-mode CPS' in result.output


def test_dryrun_without_prefix_errors(runner, cli, fake_edgerc, convert_obj, csv_factory):
    csv_path = csv_factory([{'hostname': 'www.example.com'}])
    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc,
        'convert', '--csv', csv_path, '-d', 'x', '--dryrun',
    ], obj=convert_obj)
    assert result.exit_code == 0
    assert '--dryrun requires --prefix' in result.output


def test_prefix_without_dryrun_errors(runner, cli, fake_edgerc, convert_obj, csv_factory):
    csv_path = csv_factory([{'hostname': 'www.example.com'}])
    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc,
        'convert', '--csv', csv_path, '-d', 'x', '--prefix', 'foo',
    ], obj=convert_obj)
    assert result.exit_code == 0
    assert '--prefix is require under --dryrun mode' in result.output


def test_dryrun_prefix_synthetic_names_are_dead_code(runner, cli, fake_edgerc, akamai_onboard_module, fake_convert_utility_cls, csv_factory):
    """Known bug: --dryrun with --prefix does not actually rename hostnames/properties; the real, unprefixed CSV values are used instead."""
    captured = {}

    class _SpyUtility(fake_convert_utility_cls):
        def csv_2_property_dict_convert(self, onboard_object):
            captured['csv_dict'] = [dict(row) for row in onboard_object.csv_dict]
            raise SystemExit(0)

    csv_path = csv_factory([{
        'hostname': 'www.example.com', 'propertyName': 'example-prop',
        'product': 'prd_Site_Accel', 'GroupID': 'grp_456',
    }])
    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc,
        'convert', '--csv', csv_path, '-d', 'x', '--dryrun', '--prefix', 'foo',
    ], obj=akamai_onboard_module.Config(utility_cls=_SpyUtility))

    assert result.exit_code == 0
    assert 'csv_dict' in captured
    row = captured['csv_dict'][0]
    # If the fix ever lands, this would become 'foo1.com' / 'fooexample-prop'.
    assert row['hostname'] == 'www.example.com'
    assert row['propertyName'] == 'example-prop'
