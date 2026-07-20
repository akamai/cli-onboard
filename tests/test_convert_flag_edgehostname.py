"""TC-D flag logic, Group B: utility.csv_2_property_dict_convert() (Local, §5).

Per-row edge hostname resolution — how edge_hostname_mode interacts with the CSV's
`edgeHostname` column. Split out of test_convert_flag_logic.py; see
test_convert_flag_constructor.py, test_convert_flag_setup_validation.py, and
test_convert_flag_cli_guards.py for the other three groups.
"""
from __future__ import annotations

import logging

import onboard_convert
import pytest
from model.edge_hostname_mode import EdgeHostnameMode


def test_csv_mode_with_edgehostname_column_uses_csv_values(util, click_args_factory, config_stub):
    click_args = click_args_factory(use_existing_edgehostname='CSV')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    onboard_object.csv_dict = [
        {'hostname': 'www.example.com', 'edgeHostname': 'www.example.com.edgekey.net'},
    ]
    util.csv_2_property_dict_convert(onboard_object)
    assert onboard_object.edge_hostname_list == ['www.example.com.edgekey.net']


def test_secure_by_default_mode_synthesizes_edgehostname_when_column_missing(util, click_args_factory, config_stub):
    click_args = click_args_factory(cert_mode='SBD', enrollment_id=None, use_existing_edgehostname=None)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT
    onboard_object.csv_dict = [{'hostname': 'www.example.com'}]  # no edgeHostname column
    util.csv_2_property_dict_convert(onboard_object)
    assert onboard_object.edge_hostname_list == ['www.example.com.edgesuite.net']


def test_create_cps_edgehostname_mode_synthesizes_edgehostname_when_column_missing(util, click_args_factory, config_stub):
    click_args = click_args_factory(cert_mode='CPS', enrollment_id=12345)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == EdgeHostnameMode.CREATE_CPS_EDGEHOSTNAME
    onboard_object.csv_dict = [{'hostname': 'www.example.com'}]  # no edgeHostname column
    util.csv_2_property_dict_convert(onboard_object)
    assert onboard_object.edge_hostname_list == ['www.example.com.edgesuite.net']


def test_cps_placeholder_mode_synthesizes_edgehostname_when_column_missing(util, click_args_factory, config_stub):
    click_args = click_args_factory(cert_mode='CPS', enrollment_id=None)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    assert onboard_object.edge_hostname_mode == EdgeHostnameMode.CPS_PLACEHOLDER
    onboard_object.csv_dict = [{'hostname': 'www.example.com'}]  # no edgeHostname column
    util.csv_2_property_dict_convert(onboard_object)
    assert onboard_object.edge_hostname_list == ['www.example.com.edgesuite.net']


def test_csv_mode_missing_edgehostname_column_errors(util, click_args_factory, config_stub, caplog):
    click_args = click_args_factory(use_existing_edgehostname='CSV')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    onboard_object.csv_dict = [{'hostname': 'www.example.com'}]  # no edgeHostname column
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.csv_2_property_dict_convert(onboard_object)
    assert 'edgeHostname column must exist' in caplog.text


def test_explicit_ehn_name_is_never_actually_applied(util, click_args_factory, config_stub, caplog):
    """Documents a discovered bug, not desired behavior.

    The original plan assumed `--use-existing-edgehostname my.edgekey.net` (an
    explicit single name) is a Positive case. Tracing the real code shows it isn't:
    bin/akamai-onboard.py's convert() only copies a row's `edgeHostname` value into
    the working dict when `click_args['use_existing_edgehostname'] == 'CSV'`
    (akamai-onboard.py:265) — for any other explicit string value, that condition is
    always False, so the explicit name is stored on the onboard object but never
    copied anywhere csv_2_property_dict_convert can see it. Since edge_hostname_mode
    is still 'use_existing_edgehostname', the row hits the same
    "edgeHostname column must exist" exit as TC-D14 — every run with an explicit
    single edge hostname name currently fails. Flip this test if that gets fixed.
    """
    click_args = click_args_factory(use_existing_edgehostname='my.edgekey.net')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    # Mirrors exactly what convert() hands csv_2_property_dict_convert for this case:
    # the raw CSV row's edgeHostname is dropped because the flag value isn't 'CSV'.
    onboard_object.csv_dict = [{'hostname': 'www.example.com'}]
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.csv_2_property_dict_convert(onboard_object)
    assert 'edgeHostname column must exist' in caplog.text
