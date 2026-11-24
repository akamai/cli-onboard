"""Checks that skipping the wait-for-completion step still submits activations correctly, while normal runs behave as before."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import utility_papi
import utility_waf


class FakePapiWrapper:
    """A stand-in delivery-activation service that records calls and returns preset responses."""

    def __init__(self, activate_status_code=201, poll_statuses=None):
        self.activate_status_code = activate_status_code
        # Each pollActivationStatus call pops the next status off this list.
        self.poll_statuses = list(poll_statuses or [])
        self.poll_call_count = 0

    def activateConfiguration(self, contractId, groupId, propertyId, version, network, emailList, notes):
        body = {'activationLink': '/papi/v1/properties/prp_123/activations/atv_456?contractId=ctr_1'}
        if self.activate_status_code != 201:
            body = {'errors': [{'detail': 'nope'}]}
        return SimpleNamespace(status_code=self.activate_status_code, json=lambda: body)

    def pollActivationStatus(self, contractId, groupId, propertyId, activationId):
        self.poll_call_count += 1
        status = self.poll_statuses[self.poll_call_count - 1]
        body = {'activations': {'items': [{'activationId': activationId, 'network': 'PRODUCTION', 'status': status}]}}
        return SimpleNamespace(status_code=200, json=lambda: body)


class FakeWafWrapper:
    def __init__(self, activate_status_code=200, poll_statuses=None):
        self.activate_status_code = activate_status_code
        self.poll_statuses = list(poll_statuses or [])
        self.poll_call_count = 0

    def activateWafPolicy(self, config_id, version, network, emails, note):
        body = {'activationId': 789}
        if self.activate_status_code != 200:
            body = {'errors': [{'detail': 'nope'}]}
        return SimpleNamespace(status_code=self.activate_status_code, json=lambda: body, url='https://example.test/waf')

    def pollWafActivationStatus(self, activationId):
        self.poll_call_count += 1
        status = self.poll_statuses[self.poll_call_count - 1]
        body = {'network': 'PRODUCTION', 'status': status}
        return SimpleNamespace(status_code=200, json=lambda: body, url='https://example.test/waf/poll')


@pytest.fixture
def waf_onboard_object():
    return SimpleNamespace(onboard_waf_config_id=999, onboard_waf_config_version=3,
                            notification_emails=['a@example.com'])


def _activate_and_poll_kwargs(wrapper, no_wait):
    return dict(wrapper_object=wrapper, property_name='example-prop', contract_id='ctr_1',
                group_id='grp_1', property_id='prp_123', version=1, network='PRODUCTION',
                emailList=['a@example.com'], notes='test', no_wait=no_wait)


class TestPapiActivateAndPollNoWait:
    def test_no_wait_submitted_returns_tuple_without_polling(self, monkeypatch):
        wrapper = FakePapiWrapper()
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        papi = utility_papi.papiFunctions()

        result = papi.activate_and_poll(**_activate_and_poll_kwargs(wrapper, no_wait=True))

        assert result == (True, 'atv_456')
        assert wrapper.poll_call_count == 0

    def test_no_wait_submission_failure_returns_false_none(self, monkeypatch):
        wrapper = FakePapiWrapper(activate_status_code=400)
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        papi = utility_papi.papiFunctions()

        result = papi.activate_and_poll(**_activate_and_poll_kwargs(wrapper, no_wait=True))

        assert result == (False, None)

    def test_default_behavior_unchanged_returns_plain_bool(self, monkeypatch):
        wrapper = FakePapiWrapper(poll_statuses=['ACTIVE'])
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('immediate ACTIVE should not need to sleep'))
        papi = utility_papi.papiFunctions()

        result = papi.activate_and_poll(**_activate_and_poll_kwargs(wrapper, no_wait=False))

        assert result is True
        assert wrapper.poll_call_count == 1

    def test_omitting_no_wait_matches_explicit_false(self, monkeypatch):
        wrapper = FakePapiWrapper(poll_statuses=['ACTIVE'])
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('immediate ACTIVE should not need to sleep'))
        papi = utility_papi.papiFunctions()
        kwargs = _activate_and_poll_kwargs(wrapper, no_wait=False)
        del kwargs['no_wait']

        result = papi.activate_and_poll(**kwargs)

        assert result is True


class TestWafActivateAndPollNoWait:
    def test_no_wait_submitted_returns_tuple_without_polling(self, monkeypatch, waf_onboard_object):
        wrapper = FakeWafWrapper()
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        waf = utility_waf.wafFunctions()

        result = waf.activateAndPoll(wrapper, waf_onboard_object, network='PRODUCTION', no_wait=True)

        assert result == (True, 789)
        assert wrapper.poll_call_count == 0

    def test_no_wait_submission_failure_returns_false_none(self, monkeypatch, waf_onboard_object):
        wrapper = FakeWafWrapper(activate_status_code=400)
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        waf = utility_waf.wafFunctions()

        result = waf.activateAndPoll(wrapper, waf_onboard_object, network='PRODUCTION', no_wait=True)

        assert result == (False, None)

    def test_default_behavior_unchanged_returns_plain_bool(self, monkeypatch, waf_onboard_object):
        wrapper = FakeWafWrapper(poll_statuses=['ACTIVATED'])
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('immediate ACTIVATED should not need to sleep'))
        waf = utility_waf.wafFunctions()

        result = waf.activateAndPoll(wrapper, waf_onboard_object, network='PRODUCTION')

        assert result is True
        assert wrapper.poll_call_count == 1
