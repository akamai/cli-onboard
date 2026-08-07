"""
Covers the `no_wait` seam added to poll.py's pollActivation and
utility_papi.py's batch_activate_and_poll (issue 04 of
.scratch/skip-activation-polling-spec.md) -- the batch/multi-property
counterpart to issue 01's single-property no_wait wiring.

no_wait=True must submit every property in the batch, then return
(submitted: bool, activationDict) immediately with activationId populated
per property, without ever polling/sleeping. no_wait=False (the default, and
the only mode every pre-existing caller uses) must be byte-for-byte
unchanged: same 4-tuple return, same polling behavior.
"""
from __future__ import annotations

from types import SimpleNamespace

import poll
import pytest
import utility_papi


class FakeBatchPapiWrapper:
    """Stands in for wrapper_api's PAPI wrapper across a batch of properties:
    records every activateConfiguration call, plays back one canned
    activateConfiguration response per property (by propertyId), and one
    canned pollActivationStatus response per property (by activationId).
    """

    def __init__(self, activate_status_codes: dict[str, int] | None = None,
                 poll_statuses: dict[str, str] | None = None):
        # propertyId -> activateConfiguration status code (default 201/success)
        self.activate_status_codes = activate_status_codes or {}
        # activationId -> poll status (default ACTIVE)
        self.poll_statuses = poll_statuses or {}
        self.activate_calls = []
        self.poll_calls = []

    def activateConfiguration(self, contractId, groupId, propertyId, version, network, emailList, notes):
        self.activate_calls.append(propertyId)
        status_code = self.activate_status_codes.get(propertyId, 201)
        if status_code != 201:
            return SimpleNamespace(status_code=status_code, json=lambda: {'errors': [{'detail': 'nope'}]})
        activation_id = f'atv_{propertyId}'
        body = {'activationLink': f'/papi/v1/properties/{propertyId}/activations/{activation_id}?contractId=ctr_1'}
        return SimpleNamespace(status_code=201, json=lambda: body)

    def pollActivationStatus(self, contractId, groupId, propertyId, activationId):
        self.poll_calls.append(activationId)
        status = self.poll_statuses.get(activationId, 'ACTIVE')
        body = {'activations': {'items': [{'activationId': activationId, 'network': 'PRODUCTION', 'status': status}]}}
        return SimpleNamespace(status_code=200, json=lambda: body)


def _property_dict(property_ids):
    return [{'propertyName': f'prop-{pid}', 'propertyId': pid, 'hostnames': [f'{pid}.example.com']} for pid in property_ids]


class TestPollActivationNoWait:
    def test_no_wait_returns_immediately_without_polling(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        wrapper = FakeBatchPapiWrapper()
        activation_dict = [{'propertyName': 'prop-1', 'propertyId': 'prp_1', 'activationId': 'atv_prp_1'}]

        all_active, result = poll.pollActivation(activation_dict, wrapper, 'ctr_1', 'grp_1', 'PRODUCTION', no_wait=True)

        assert all_active is True
        assert result is activation_dict
        assert wrapper.poll_calls == []

    def test_default_behavior_unchanged(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('immediate ACTIVE should not need to sleep'))
        wrapper = FakeBatchPapiWrapper(poll_statuses={'atv_prp_1': 'ACTIVE'})
        activation_dict = [{'propertyName': 'prop-1', 'propertyId': 'prp_1', 'activationId': 'atv_prp_1'}]

        all_active, result = poll.pollActivation(activation_dict, wrapper, 'ctr_1', 'grp_1', 'PRODUCTION')

        assert all_active is True
        assert wrapper.poll_calls == ['atv_prp_1']


class TestBatchActivateAndPollNoWait:
    def test_no_wait_submits_every_property_and_returns_without_polling(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        wrapper = FakeBatchPapiWrapper()
        property_dict = _property_dict(['prp_1', 'prp_2', 'prp_3'])
        papi = utility_papi.papiFunctions()

        submitted, activation_dict = papi.batch_activate_and_poll(wrapper, property_dict, 'ctr_1', 'grp_1',
                                                                    version=1, network='PRODUCTION',
                                                                    emailList=['a@example.com'], notes='test',
                                                                    no_wait=True)

        assert submitted is True
        assert wrapper.activate_calls == ['prp_1', 'prp_2', 'prp_3']
        assert wrapper.poll_calls == []
        assert [p['activationId'] for p in activation_dict] == ['atv_prp_1', 'atv_prp_2', 'atv_prp_3']

    def test_no_wait_partial_submission_failure_is_reported_and_others_still_submit(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('no_wait must not sleep/poll'))
        wrapper = FakeBatchPapiWrapper(activate_status_codes={'prp_2': 400})
        property_dict = _property_dict(['prp_1', 'prp_2', 'prp_3'])
        papi = utility_papi.papiFunctions()

        submitted, activation_dict = papi.batch_activate_and_poll(wrapper, property_dict, 'ctr_1', 'grp_1',
                                                                    version=1, network='PRODUCTION',
                                                                    emailList=['a@example.com'], notes='test',
                                                                    no_wait=True)

        assert submitted is False
        by_property = {p['propertyId']: p['activationId'] for p in activation_dict}
        assert by_property == {'prp_1': 'atv_prp_1', 'prp_2': 0, 'prp_3': 'atv_prp_3'}
        # every property was still attempted, not short-circuited by the one failure
        assert wrapper.activate_calls == ['prp_1', 'prp_2', 'prp_3']

    def test_default_behavior_unchanged_returns_original_four_tuple(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('immediate ACTIVE should not need to sleep'))
        wrapper = FakeBatchPapiWrapper(poll_statuses={'atv_prp_1': 'ACTIVE', 'atv_prp_2': 'ACTIVE'})
        property_dict = _property_dict(['prp_1', 'prp_2'])
        for p in property_dict:
            p['hostnames'] = [f"{p['propertyId']}.example.com"]
        papi = utility_papi.papiFunctions()

        all_active, success_hostnames, failed_activations, activation_dict = papi.batch_activate_and_poll(
            wrapper, property_dict, 'ctr_1', 'grp_1', version=1, network='PRODUCTION',
            emailList=['a@example.com'], notes='test',
        )

        assert all_active is True
        assert failed_activations == []
        assert sorted(success_hostnames) == ['prp_1.example.com', 'prp_2.example.com']

    def test_omitting_no_wait_matches_explicit_false(self, monkeypatch):
        monkeypatch.setattr('time.sleep', lambda *_: pytest.fail('immediate ACTIVE should not need to sleep'))
        wrapper = FakeBatchPapiWrapper(poll_statuses={'atv_prp_1': 'ACTIVE'})
        property_dict = _property_dict(['prp_1'])
        property_dict[0]['hostnames'] = ['prp_1.example.com']
        papi = utility_papi.papiFunctions()

        result = papi.batch_activate_and_poll(wrapper, property_dict, 'ctr_1', 'grp_1', version=1,
                                               network='PRODUCTION', emailList=['a@example.com'], notes='test',
                                               no_wait=False)

        assert len(result) == 4
        assert result[0] is True
