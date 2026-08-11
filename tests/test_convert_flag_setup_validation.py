"""Checks that setting up a conversion validates GTM domains, activation order,
notification emails, groups, contracts, and confirmation prompts correctly.
"""
from __future__ import annotations

import logging

import pytest


# These tests pass force=True in click_overrides, which sets onboard_object's
# force_mode True and makes validateSetupStepsConvert skip the confirm prompt
# entirely - passing this in as confirm_input proves that (it errors instead of
# hanging on real input() if the prompt is ever reached).
def _fail_if_prompted():
    raise AssertionError('confirmation prompt should not be reached in this test')


def test_activate_production_without_staging_errors(util, build_onboard_object, stub_wrapper_factory, caplog):
    onboard_object = build_onboard_object(click_overrides={'activate': ('production',), 'force': True})
    wrapper = stub_wrapper_factory()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'Must activate property to STAGING before activating to PRODUCTION' in caplog.text


def test_activate_staging_then_production_passes(util, build_onboard_object, stub_wrapper_factory):
    onboard_object = build_onboard_object(click_overrides={'activate': ('staging', 'production'), 'force': True})
    wrapper = stub_wrapper_factory()
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_activate_staging_default_email_passes(util, build_onboard_object, stub_wrapper_factory):
    onboard_object = build_onboard_object(click_overrides={'activate': ('staging',), 'force': True})
    assert onboard_object.notification_emails == ['noreply@akamai.com']
    wrapper = stub_wrapper_factory()
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_activate_staging_invalid_email_errors(util, build_onboard_object, stub_wrapper_factory, caplog):
    onboard_object = build_onboard_object(click_overrides={'activate': ('staging',), 'email': ('not-an-email',), 'force': True})
    wrapper = stub_wrapper_factory()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid email address' in caplog.text


def test_activate_staging_empty_email_errors(util, build_onboard_object, stub_wrapper_factory, caplog):
    onboard_object = build_onboard_object(click_overrides={'activate': ('staging',), 'email': ('',), 'force': True})
    wrapper = stub_wrapper_factory()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'At least one valid notification email is required' in caplog.text


def test_gtm_domain_missing_suffix_errors(util, build_onboard_object, stub_wrapper_factory, caplog):
    onboard_object = build_onboard_object(click_overrides={'gtm_domain': 'foo', 'force': True})
    wrapper = stub_wrapper_factory()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'Domain must end with akadns.net' in caplog.text


def test_gtm_domain_leading_hyphen_errors(util, build_onboard_object, stub_wrapper_factory, caplog):
    onboard_object = build_onboard_object(click_overrides={'gtm_domain': '-foo.akadns.net', 'force': True})
    wrapper = stub_wrapper_factory()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'cannot begin or end with a hyphen' in caplog.text


def test_gtm_domain_with_gtm_refs_passes(util, build_onboard_object, stub_wrapper_factory):
    onboard_object = build_onboard_object(
        click_overrides={'gtm_domain': 'foo.akadns.net', 'force': True},
        gtm_replacement_count=2,
    )
    wrapper = stub_wrapper_factory()
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_missing_gtm_domain_with_refs_is_non_fatal(util, build_onboard_object, stub_wrapper_factory, caplog):
    """Checks that a run missing a GTM domain still succeeds by auto-generating a
    fallback domain, even though it logs the issue as an error.
    """
    onboard_object = build_onboard_object(click_overrides={'force': True}, gtm_replacement_count=3)
    assert onboard_object.gtm_domain is None
    wrapper = stub_wrapper_factory()
    with caplog.at_level(logging.ERROR):
        result = util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert result is True
    assert 'No --gtm-domain input' in caplog.text
    assert onboard_object.gtm_domain is not None  # fallback domain was generated


def test_force_skips_confirmation_prompt(util, build_onboard_object, stub_wrapper_factory):
    onboard_object = build_onboard_object(click_overrides={'force': True})
    wrapper = stub_wrapper_factory()
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_declining_confirmation_without_force_exits_cleanly(util, build_onboard_object, stub_wrapper_factory):
    onboard_object = build_onboard_object(click_overrides={'force': False})
    wrapper = stub_wrapper_factory()
    with pytest.raises(SystemExit):
        util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=lambda: 'no')


def test_invalid_group_id_errors(util, build_onboard_object, stub_wrapper_factory, caplog, capsys):
    """Checks that entering a group that doesn't exist is caught early with a clear
    error listing the valid groups for that contract.
    """
    onboard_object = build_onboard_object(click_overrides={'group': 'grp_bogus', 'force': True})
    wrapper = stub_wrapper_factory()  # only knows about 'grp_456'
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid group_id' in caplog.text
    assert 'Available valid group_id for contract ctr_TEST123' in caplog.text
    assert 'grp_456' in capsys.readouterr().out


def test_unprefixed_group_and_contract_match_prefixed_papi_response(util, build_onboard_object, stub_wrapper_factory):
    """Checks that a group and contract entered without their usual prefixes are
    still recognized as valid.
    """
    onboard_object = build_onboard_object(click_overrides={'group': '27897', 'contract': 'V-511SV19', 'force': True})
    wrapper = stub_wrapper_factory(valid_groups={'grp_27897': ['ctr_V-511SV19']}, valid_contracts={'ctr_V-511SV19'})
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_unprefixed_invalid_group_still_lists_available_groups(util, build_onboard_object, stub_wrapper_factory, caplog, capsys):
    """Checks that an invalid group entered without its usual prefix still produces
    a correct list of available groups, not an empty one.
    """
    onboard_object = build_onboard_object(click_overrides={'group': '99999', 'contract': 'V-511SV19', 'force': True})
    wrapper = stub_wrapper_factory(valid_groups={'grp_27897': ['ctr_V-511SV19']}, valid_contracts={'ctr_V-511SV19'})
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid group_id' in caplog.text
    assert 'grp_27897' in capsys.readouterr().out


def test_group_id_wrong_contract_errors(util, build_onboard_object, stub_wrapper_factory, caplog):
    """Checks that a group belonging to a different contract than the one specified
    is rejected, separately from an unknown-contract error.
    """
    onboard_object = build_onboard_object(click_overrides={'group': 'grp_456', 'contract': 'ctr_OTHER', 'force': True})
    wrapper = stub_wrapper_factory(valid_contracts={'ctr_TEST123', 'ctr_OTHER'})  # grp_456 only maps to ctr_TEST123
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid group_id' in caplog.text
    assert 'invalid contract_id' not in caplog.text


def test_invalid_contract_suppresses_group_listing(util, build_onboard_object, stub_wrapper_factory, caplog, capsys):
    """Checks that when both the group and contract are invalid, the error doesn't
    show a misleading empty list of available groups.
    """
    onboard_object = build_onboard_object(click_overrides={'group': 'grp_456', 'contract': 'ctr_BOGUS', 'force': True})
    wrapper = stub_wrapper_factory()  # only knows about ctr_TEST123
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid group_id' in caplog.text
    assert 'Available valid group_id' not in caplog.text
    assert 'invalid contract_id' in caplog.text
    assert 'Available valid contract_id' in caplog.text
    assert 'TEST123' in capsys.readouterr().out  # displayed unprefixed, same convention as the group table


def test_invalid_contract_id_lists_available_contracts(util, build_onboard_object, stub_wrapper_factory, caplog, capsys):
    """Checks that an unrecognized contract is caught with a clear error listing the
    account's actual valid contracts.
    """
    onboard_object = build_onboard_object(click_overrides={'contract': 'ctr_BOGUS', 'group': 'grp_456', 'force': True})
    wrapper = stub_wrapper_factory(valid_contracts={'ctr_TEST123', 'ctr_OTHER'})
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid contract_id' in caplog.text
    assert 'Available valid contract_id' in caplog.text
    out = capsys.readouterr().out
    assert 'TEST123' in out
    assert 'OTHER' in out


def test_unprefixed_contract_matches_prefixed_papi_response(util, build_onboard_object, stub_wrapper_factory):
    """Checks that a contract entered without its usual prefix is still recognized as valid."""
    onboard_object = build_onboard_object(click_overrides={'contract': 'V-511SV19', 'group': '27897', 'force': True})
    wrapper = stub_wrapper_factory(valid_groups={'grp_27897': ['ctr_V-511SV19']}, valid_contracts={'ctr_V-511SV19'})
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_csv_provided_invalid_group_id_errors(util, build_onboard_object, stub_wrapper_factory, caplog, capsys):
    """Checks that an invalid group supplied via the input spreadsheet, instead of a
    command flag, is still caught early with a helpful error.
    """
    onboard_object = build_onboard_object(click_overrides={'group': None, 'force': True})
    onboard_object.group_list = ['grp_bogus']
    wrapper = stub_wrapper_factory()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid group_id' in caplog.text
    assert 'Available valid group_id for contract ctr_TEST123' in caplog.text
    assert 'grp_456' in capsys.readouterr().out


def test_csv_provided_valid_group_id_passes(util, build_onboard_object, stub_wrapper_factory):
    onboard_object = build_onboard_object(click_overrides={'group': None, 'force': True})
    onboard_object.group_list = ['grp_456']
    wrapper = stub_wrapper_factory()
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_no_group_and_no_csv_groupid_errors(util, build_onboard_object, stub_wrapper_factory, caplog):
    onboard_object = build_onboard_object(click_overrides={'group': None, 'force': True})
    wrapper = stub_wrapper_factory()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'No --group provided' in caplog.text
