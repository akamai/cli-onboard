"""
Covers the `no_wait` seam added to utility_waf.py's updateActivateAndPoll
(appsec-update/appsec-remove) and activate_and_poll/waf_poll_activation
(appsec-create) -- issue 06 of the skip-activation-polling spec. These are
the WAF-only commands: no paired delivery activation, so no ordering gate to
drop, just "skip the poll, return the ID."
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import utility_waf


class FakeUpdateWrapper:
    """Stands in for the PAPI/WAF wrapper used by updateActivateAndPoll: an
    activateWafPolicy response keyed on `.ok`, and a pollWafActivationStatus
    response for the polling loop.
    """

    def __init__(self, activate_ok=True, poll_status='ACTIVATED', poll_ok=True):
        self.activate_ok = activate_ok
        self.poll_status = poll_status
        self.poll_ok = poll_ok
        self.poll_call_count = 0

    def activateWafPolicy(self, config_id, version, network, emails, note):
        body = {'activationId': 555} if self.activate_ok else {'errors': [{'detail': 'nope'}]}
        return SimpleNamespace(ok=self.activate_ok, status_code=200 if self.activate_ok else 400,
                                json=lambda: body, url='https://example.test/activate')

    def pollWafActivationStatus(self, activationId):
        self.poll_call_count += 1
        body = {'network': 'PRODUCTION', 'status': self.poll_status}
        return SimpleNamespace(ok=self.poll_ok, status_code=200 if self.poll_ok else 500,
                                json=lambda: body, url='https://example.test/poll')


@pytest.fixture
def appsec_update_onboard_object():
    return SimpleNamespace(config_id=999, onboard_waf_config_version=3, notification_emails=['a@example.com'],
                            version_notes='notes', waf_config_name='WAF Security File')


class TestUpdateActivateAndPollNoWait:
    def test_no_wait_submitted_returns_tuple_without_polling(self, monkeypatch, appsec_update_onboard_object):
        wrapper = FakeUpdateWrapper()
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        waf = utility_waf.wafFunctions()

        result = waf.updateActivateAndPoll(wrapper, appsec_update_onboard_object, network='PRODUCTION', no_wait=True)

        assert result == (True, 555)
        assert wrapper.poll_call_count == 0

    def test_no_wait_submission_failure_returns_false_none(self, monkeypatch, appsec_update_onboard_object):
        wrapper = FakeUpdateWrapper(activate_ok=False)
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        waf = utility_waf.wafFunctions()

        result = waf.updateActivateAndPoll(wrapper, appsec_update_onboard_object, network='PRODUCTION', no_wait=True)

        assert result == (False, None)

    def test_default_behavior_unchanged_returns_plain_bool(self, monkeypatch, appsec_update_onboard_object):
        wrapper = FakeUpdateWrapper(poll_status='ACTIVATED')
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('immediate ACTIVATED should not need to sleep'))
        waf = utility_waf.wafFunctions()

        result = waf.updateActivateAndPoll(wrapper, appsec_update_onboard_object, network='PRODUCTION')

        assert result is True
        assert wrapper.poll_call_count == 1


class FakeAppsecCreateWrapper:
    """Stands in for the wrapper used by activation_detail/waf_poll_activation
    (appsec-create's batch path): activateWafPolicy keyed on `.ok`, one
    canned response for every item in the batch.
    """

    def __init__(self, activate_ok=True):
        self.activate_ok = activate_ok
        self.poll_call_count = 0

    def activateWafPolicy(self, config_id, version, network, emails, note):
        body = ({'activationId': 777, 'createDate': '2026-01-01T00:00:00Z', 'status': 'PENDING'} if self.activate_ok
                else {'detail': 'no conflict here'})
        return SimpleNamespace(ok=self.activate_ok, json=lambda: body)

    def pollWafActivationStatus(self, activationId):
        self.poll_call_count += 1
        return SimpleNamespace(status_code=200, json=lambda: {'status': 'ACTIVATED'})

    def getWafConfigVersions(self, config_id):
        return SimpleNamespace(json=lambda: {'configName': 'other-config'})


def _appsec_item(name='waf-config-a'):
    return SimpleNamespace(waf_config_name=name, onboard_waf_config_id=1, onboard_waf_config_version=1,
                            notification_emails=['a@example.com'], version_notes='notes',
                            activation_id=0, activation_status='', activation_create='', activation_end='')


class TestWafPollActivationNoWait:
    def test_no_wait_returns_immediately_without_polling(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        wrapper = FakeAppsecCreateWrapper()
        appsec_onboard = [_appsec_item()]
        waf = utility_waf.wafFunctions()

        all_active, result = waf.waf_poll_activation(wrapper, appsec_onboard, 'PRODUCTION', no_wait=True)

        assert all_active is True
        assert result is appsec_onboard
        assert wrapper.poll_call_count == 0


class TestActivateAndPollNoWait:
    """activation_detail (submission) always sleeps 1s as a pre-existing
    rate-limit between submissions -- unrelated to no_wait and not asserted
    against here. What no_wait must skip is the 60s polling loop in
    waf_poll_activation, observed via poll_call_count.
    """

    def test_production_activate_skips_only_the_production_poll(self, monkeypatch):
        """activate='production' does staging (always polls) then production
        (no_wait skips the poll) -- staging polling must still happen."""
        monkeypatch.setattr('time.sleep', lambda *_: None)
        wrapper = FakeAppsecCreateWrapper()
        appsec_onboard = [_appsec_item()]
        waf = utility_waf.wafFunctions()

        waf.activate_and_poll(wrapper, appsec_onboard, 'production', no_wait=True)

        # staging polled once (immediate ACTIVATED); production skipped polling entirely
        assert wrapper.poll_call_count == 1
        assert appsec_onboard[0].activation_id == 777

    def test_staging_only_activate_is_unaffected_by_no_wait(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: None)
        wrapper = FakeAppsecCreateWrapper()
        appsec_onboard = [_appsec_item()]
        waf = utility_waf.wafFunctions()

        waf.activate_and_poll(wrapper, appsec_onboard, 'staging', no_wait=True)

        assert wrapper.poll_call_count == 1

    def test_default_no_wait_false_polls_both_networks(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: None)
        wrapper = FakeAppsecCreateWrapper()
        appsec_onboard = [_appsec_item()]
        waf = utility_waf.wafFunctions()

        waf.activate_and_poll(wrapper, appsec_onboard, 'production')

        assert wrapper.poll_call_count == 2
