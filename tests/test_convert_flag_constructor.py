"""Checks that the right edge hostname setup mode is chosen based on the certificate and hostname options a user provides."""
from __future__ import annotations

import onboard_convert
import pytest
from model.edge_hostname_mode import EdgeHostnameMode


def test_enrollment_id_without_cps_is_checked_in_convert_not_constructor(click_args_factory, config_stub):
    """Confirms the enrollment-id-without-CPS error is caught by the CLI command itself, not by this lower-level setup step."""
    click_args = click_args_factory(enrollment_id=12345, cert_mode='SBD')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.enrollment_id == 12345
    assert onboard_object.cert_mode == 'SBD'


def test_cps_with_enrollment_id_selects_create_cps_mode(click_args_factory, config_stub):
    click_args = click_args_factory(cert_mode='CPS', enrollment_id=12345)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == EdgeHostnameMode.CREATE_CPS_EDGEHOSTNAME


def test_cps_without_enrollment_id_selects_placeholder_mode(click_args_factory, config_stub):
    click_args = click_args_factory(cert_mode='CPS', enrollment_id=None)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == EdgeHostnameMode.CPS_PLACEHOLDER


def test_default_sbd_cert_mode_selects_secure_by_default_mode(click_args_factory, config_stub):
    click_args = click_args_factory(cert_mode='SBD', enrollment_id=None, use_existing_edgehostname=None)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT


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
    assert onboard_object.edge_hostname_mode == EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME


def test_explicit_ehn_name_also_selects_use_existing_mode(click_args_factory, config_stub):
    click_args = click_args_factory(use_existing_edgehostname='my.edgekey.net')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME
    assert onboard_object.use_existing_ehn == 'my.edgekey.net'
