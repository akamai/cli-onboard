"""TC-D flag logic, Group C: utility.validateSetupStepsConvert() (Local, §5).

GTM domain / activation ordering / email / confirm-prompt checks. Composed with a
real onboard_convert.onboard() (via the shared build_onboard_object fixture) and a
small StubWrapper (answers property_exists/getProductsByContract locally) rather than
a live PAPI wrapper. Split out of test_convert_flag_logic.py; see
test_convert_flag_constructor.py, test_convert_flag_edgehostname.py, and
test_convert_flag_cli_guards.py for the other three groups.

Every call below passes confirm_input explicitly rather than relying on
validateSetupStepsConvert's real `input` default, so no test can hang waiting on
stdin and none needs to patch builtins.input.
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
    """Reclassified vs. the original plan: this was labeled Negative, but the branch
    that auto-generates a fallback GTM domain (utility.py:489-492) never does
    `count += 1` — it's the only branch in the GTM section that doesn't. So a run with
    templates referencing GTM but no --gtm-domain logs an ERROR-level message (a
    misleading log level for something non-fatal) yet still succeeds, auto-recovering
    with a fallback domain. Confirm this is acceptable, or file it as a bug (either
    the log level is wrong, or this should actually be fatal).
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
    """A --group that doesn't exist (or isn't on this contract) must fail precheck,
    not surface as a raw API error partway through property/cpcode creation - and
    must list the groups that ARE available on that contract, same as invalid
    --product does for products. The listing itself is a rich Table printed straight
    to the console (logger.warning() goes through a shared RichHandler configured with
    markup=False, so it can't render Rich tables) - assert its content via capsys.
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
    """Reproduces the reported bug: PAPI's /papi/v1/groups always returns groupId and
    contractIds WITH their 'grp_'/'ctr_' prefix, but users commonly pass --group/--contract
    unprefixed (as in the report: group 27897, contract V-511SV19). Comparing those
    raw strings against the prefixed PAPI values matched nothing, so every group was
    filtered out of "Available valid group_id" - even ones that were actually valid.
    """
    onboard_object = build_onboard_object(click_overrides={'group': '27897', 'contract': 'V-511SV19', 'force': True})
    wrapper = stub_wrapper_factory(valid_groups={'grp_27897': ['ctr_V-511SV19']}, valid_contracts={'ctr_V-511SV19'})
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_unprefixed_invalid_group_still_lists_available_groups(util, build_onboard_object, stub_wrapper_factory, caplog, capsys):
    """Same prefix mismatch as above, but for a genuinely invalid group - the fix must
    not just stop over-rejecting valid groups, it must still populate the "available
    groups for this contract" listing instead of printing an empty table.
    """
    onboard_object = build_onboard_object(click_overrides={'group': '99999', 'contract': 'V-511SV19', 'force': True})
    wrapper = stub_wrapper_factory(valid_groups={'grp_27897': ['ctr_V-511SV19']}, valid_contracts={'ctr_V-511SV19'})
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid group_id' in caplog.text
    assert 'grp_27897' in capsys.readouterr().out


def test_group_id_wrong_contract_errors(util, build_onboard_object, stub_wrapper_factory, caplog):
    """A group that exists but belongs to a different (valid) contract must also fail
    precheck. ctr_OTHER is itself a real contract on the account so this isolates the
    group/contract-mismatch case from the separate "contract doesn't exist" case below.
    """
    onboard_object = build_onboard_object(click_overrides={'group': 'grp_456', 'contract': 'ctr_OTHER', 'force': True})
    wrapper = stub_wrapper_factory(valid_contracts={'ctr_TEST123', 'ctr_OTHER'})  # grp_456 only maps to ctr_TEST123
    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit):
            util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted)
    assert 'invalid group_id' in caplog.text
    assert 'invalid contract_id' not in caplog.text


def test_invalid_contract_suppresses_group_listing(util, build_onboard_object, stub_wrapper_factory, caplog, capsys):
    """When the contract itself is wrong, no group on the account matches it, so the
    "Available valid group_id" table would just be empty and misleading - both the
    contract AND the group are wrong here, so the listing section must not appear.
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
    """contract_id used to just be echoed as "valid" whenever a product lookup happened
    to succeed - never actually checked against the account's real contracts. A bogus
    --contract must fail precheck and list the contracts that ARE on the account, the
    same as `akamai pm list-contracts` would show.
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
    """Same prefix mismatch as groups: --contract is commonly passed unprefixed."""
    onboard_object = build_onboard_object(click_overrides={'contract': 'V-511SV19', 'group': '27897', 'force': True})
    wrapper = stub_wrapper_factory(valid_groups={'grp_27897': ['ctr_V-511SV19']}, valid_contracts={'ctr_V-511SV19'})
    assert util.validateSetupStepsConvert(onboard_object, wrapper, prefix=None, confirm_input=_fail_if_prompted) is True


def test_csv_provided_invalid_group_id_errors(util, build_onboard_object, stub_wrapper_factory, caplog, capsys):
    """Custom-solution mode: no --group passed, so each property's GroupID comes from
    the csv (onboard_object.group_list, populated by csv_2_property_array_convert).
    An invalid value there must also fail precheck (and list the contract's available
    groups) rather than only surfacing later.
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
