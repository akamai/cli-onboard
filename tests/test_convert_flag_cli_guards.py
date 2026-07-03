"""TC-D flag logic, Group D: the real `convert` CLI command (Local, §5).

Drives the early flag guards (--dryrun/--prefix, --enrollment-id/--cert-mode) through
the actual CLI command, with the two network/shell seams (check_cli_prereq,
check_api_access) replaced by conftest.FakeConvertUtility — injected via
Config(utility_cls=...) and passed as `obj=` to CliRunner.invoke() — so these run
exactly as a user would trigger them, without live credentials or a live API, and
without monkeypatching utility.utility. Split out of test_convert_flag_logic.py; see
test_convert_flag_constructor.py, test_convert_flag_edgehostname.py, and
test_convert_flag_setup_validation.py for the other three groups.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def convert_obj(akamai_onboard_module, fake_convert_utility_cls):
    """Config(utility_cls=FakeConvertUtility), passed as `obj=` on CliRunner.invoke()
    so convert() builds a FakeConvertUtility instead of a real utility.utility() -
    see conftest.FakeConvertUtility for which seams that replaces.
    """
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
    """Documents a discovered bug, not desired behavior.

    The original plan assumed `--dryrun --prefix foo` generates synthetic
    hostnames/property names (bin/akamai-onboard.py:249-257 does build them). But the
    very next block (akamai-onboard.py:259-268) unconditionally rebuilds
    onboard_object.csv_dict from the *original* loaded_properties again — regardless
    of dryrun — overwriting the synthetic values before anything downstream ever sees
    them. As coded, --dryrun only skips the "must supply --prefix" guard; it has no
    other effect; the run proceeds with the real, unprefixed hostnames from the CSV.

    Verified here via a spy that captures onboard_object.csv_dict right where
    csv_2_property_dict_convert receives it (the next real step after the dead
    dryrun block), then stops the run there rather than reaching further network
    calls (cpcode search/create) that are out of scope for a Local test.

    Side finding while building this: the "dead" synthetic-name loop
    (akamai-onboard.py:249-257) still fully executes before being overwritten, and it
    indexes `_prop['product']` / `_prop['GroupID']` unconditionally — even though the
    CSV schema documents both as optional columns (CONVERT_TEST_PLAN.md §3). A CSV
    with just a `hostname` column (valid per the CSV-validation tests) crashes this
    block with an uncaught KeyError under --dryrun. The fixture below includes both
    columns so this test isolates the dead-code finding rather than that separate
    crash.
    """
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
