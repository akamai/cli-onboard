"""TC-D flag logic, Group A: onboard_convert.onboard() constructor (Local, §5).

Pure edge_hostname_mode derivation — no CSV, no filesystem, no monkeypatching needed.
Split out of test_convert_flag_logic.py; see test_convert_flag_edgehostname.py,
test_convert_flag_setup_validation.py, and test_convert_flag_cli_guards.py for the
other three groups (they cover checks that live in different real functions).
"""
from __future__ import annotations

import onboard_convert
import pytest


def test_enrollment_id_without_cps_is_checked_in_convert_not_constructor(click_args_factory, config_stub):
    """The actual --enrollment-id/--cert-mode guard lives in bin/akamai-onboard.py's
    convert(), not in the onboard_convert.onboard() constructor — the constructor
    itself accepts the combination without complaint. Covered end-to-end in
    test_convert_flag_cli_guards.py::test_enrollment_id_without_cps_errors, since
    that's where the real check is. This test just pins down that the constructor
    alone doesn't gate it.
    """
    click_args = click_args_factory(enrollment_id=12345, cert_mode='SBD')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.enrollment_id == 12345
    assert onboard_object.cert_mode == 'SBD'


def test_cps_with_enrollment_id_selects_create_cps_mode(click_args_factory, config_stub):
    click_args = click_args_factory(cert_mode='CPS', enrollment_id=12345)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == 'create_cps_edgehostname'


@pytest.mark.skip(reason=(
    'Gap: this combination should warn about the redundant flags and prompt to confirm '
    '(or proceed silently under --force).'
    'Today onboard_convert.onboard() (bin/onboard_convert.py:64-67) silently '
    'selects use_existing_edgehostname with no warning and no prompt. Unskip once that '
    'warn+confirm behavior is implemented.'
))
def test_use_existing_ehn_with_cps_enrollment_warns_and_confirms():
    pass


def test_bare_use_existing_ehn_flag_selects_csv_mode(click_args_factory, config_stub):
    # click's flag_value='CSV' semantics (is_flag=False, flag_value set) are exercised
    # by click itself, not by the constructor — this just confirms the constructor
    # reacts correctly to the value click would produce for a bare flag.
    click_args = click_args_factory(use_existing_edgehostname='CSV')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == 'use_existing_edgehostname'


def test_explicit_ehn_name_also_selects_use_existing_mode(click_args_factory, config_stub):
    click_args = click_args_factory(use_existing_edgehostname='my.edgekey.net')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == 'use_existing_edgehostname'
    assert onboard_object.use_existing_ehn == 'my.edgekey.net'
