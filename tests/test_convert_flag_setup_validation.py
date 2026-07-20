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
