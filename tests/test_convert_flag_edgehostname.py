"""Checks how each row's edge hostname is worked out based on the chosen certificate/hostname settings and the CSV data."""
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


def test_row_missing_product_secureNetwork_and_edgehostname_columns_defaults_all_three(util, click_args_factory, config_stub):
    """Checks that a row missing several optional CSV columns still gets sensible default values for all of them."""
    click_args = click_args_factory(cert_mode='SBD', enrollment_id=None, use_existing_edgehostname=None)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    onboard_object.csv_dict = [{'hostname': 'www.example.com'}]  # only hostname present
    util.csv_2_property_dict_convert(onboard_object)
    assert onboard_object.product_list == ['prd_Site_Accel']
    assert onboard_object.edge_hostname_list == ['www.example.com.edgesuite.net']
    assert onboard_object.property_list == ['www.example.com']


def test_missing_secureNetwork_column_carries_over_previous_rows_ehn_suffix(util, click_args_factory, config_stub):
    """Checks that a row with no security-network column keeps the previous row's edge hostname suffix instead of resetting it."""
    click_args = click_args_factory(cert_mode='SBD', enrollment_id=None, use_existing_edgehostname=None)
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    onboard_object.csv_dict = [
        {'hostname': 'first.example.com', 'secureNetwork': 'ENHANCED_TLS'},
        {'hostname': 'second.example.com'},  # no secureNetwork column at all
    ]
    util.csv_2_property_dict_convert(onboard_object)
    assert onboard_object.edge_hostname_list == ['first.example.com.edgekey.net', 'second.example.com.edgekey.net']


def test_csv_mode_missing_edgehostname_column_errors(util, click_args_factory, config_stub, caplog):
    click_args = click_args_factory(use_existing_edgehostname='CSV')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    onboard_object.csv_dict = [{'hostname': 'www.example.com'}]  # no edgeHostname column
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.csv_2_property_dict_convert(onboard_object)
    assert 'edgeHostname column must exist' in caplog.text


def test_explicit_ehn_name_is_never_actually_applied(util, click_args_factory, config_stub, caplog):
    """Documents a known bug: providing one specific existing edge hostname by name currently still fails with a missing-column error."""
    click_args = click_args_factory(use_existing_edgehostname='my.edgekey.net')
    onboard_object = onboard_convert.onboard(config_stub, click_args)
    # Mirrors exactly what convert() hands csv_2_property_dict_convert for this case:
    # the raw CSV row's edgeHostname is dropped because the flag value isn't 'CSV'.
    onboard_object.csv_dict = [{'hostname': 'www.example.com'}]
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.csv_2_property_dict_convert(onboard_object)
    assert 'edgeHostname column must exist' in caplog.text
