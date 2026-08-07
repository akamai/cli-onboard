"""
Covers bin/activation_status.py -- the status-check engine behind the
`check-activation` command (issues 02 and 03 of
.scratch/skip-activation-polling-spec.md).

check_row_status/check_all must query each row EXACTLY once (no polling/sleep
-- that's wait_until_done's job), correctly branch delivery vs. WAF by
whether property_id is populated, and produce the is_active flag the CLI uses
for its exit code. wait_until_done (issue 03, --wait mode) must keep polling
until every row is active or hits a terminal error, sleeping between cycles.
"""
from __future__ import annotations

from types import SimpleNamespace

import activation_status
import pytest


class SpyWrapper:
    """Records call counts and args; plays back one canned response per method."""

    def __init__(self, delivery_status='ACTIVE', delivery_status_code=200,
                 waf_status='ACTIVATED', waf_network='PRODUCTION', waf_status_code=200):
        self.delivery_status = delivery_status
        self.delivery_status_code = delivery_status_code
        self.waf_status = waf_status
        self.waf_network = waf_network
        self.waf_status_code = waf_status_code
        self.delivery_calls = []
        self.waf_calls = []

    def pollActivationStatus(self, contractId, groupId, propertyId, activationId):
        self.delivery_calls.append((contractId, groupId, propertyId, activationId))
        body = {'activations': {'items': [{'activationId': activationId, 'network': 'PRODUCTION',
                                            'status': self.delivery_status}]}}
        return SimpleNamespace(status_code=self.delivery_status_code, json=lambda: body)

    def pollWafActivationStatus(self, activationId):
        self.waf_calls.append(activationId)
        body = {'network': self.waf_network, 'status': self.waf_status}
        return SimpleNamespace(status_code=self.waf_status_code, json=lambda: body)


def _delivery_row(activation_id='atv_1', property_id='prp_123', property_name='example-prop'):
    return {'property_name': property_name, 'property_id': property_id, 'version': '1', 'activation_id': activation_id}


def _waf_row(activation_id='act_1', property_name='WAF Security File'):
    return {'property_name': property_name, 'property_id': '', 'version': '3', 'activation_id': activation_id}


class TestCheckRowStatusDelivery:
    def test_active_status_is_active_true(self):
        wrapper = SpyWrapper(delivery_status='ACTIVE')

        result = activation_status.check_row_status(wrapper, _delivery_row(), 'ctr_1', 'grp_1')

        assert result['is_active'] is True
        assert result['status'] == 'ACTIVE'
        assert result['network'] == 'PRODUCTION'
        assert wrapper.delivery_calls == [('ctr_1', 'grp_1', 'prp_123', 'atv_1')]

    def test_reports_the_actual_network_from_the_response_not_a_hardcoded_default(self):
        """Delivery activations aren't always PRODUCTION -- the queried item's own
        'network' field must win over any default (regression: an earlier draft
        hardcoded 'PRODUCTION' for every delivery row regardless of what the API
        actually reported)."""
        wrapper = SpyWrapper(delivery_status='ACTIVE')
        wrapper.pollActivationStatus = lambda contractId, groupId, propertyId, activationId: SimpleNamespace(
            status_code=200,
            json=lambda: {'activations': {'items': [{'activationId': activationId, 'network': 'STAGING', 'status': 'ACTIVE'}]}},
        )

        result = activation_status.check_row_status(wrapper, _delivery_row(), 'ctr_1', 'grp_1')

        assert result['network'] == 'STAGING'

    def test_version_from_row_is_carried_through_to_result(self):
        result = activation_status.check_row_status(SpyWrapper(delivery_status='ACTIVE'),
                                                      _delivery_row(), 'ctr_1', 'grp_1')

        assert result['version'] == '1'

    def test_pending_status_is_active_false(self):
        wrapper = SpyWrapper(delivery_status='PENDING')

        result = activation_status.check_row_status(wrapper, _delivery_row(), 'ctr_1', 'grp_1')

        assert result['is_active'] is False
        assert result['status'] == 'PENDING'

    def test_queries_exactly_once(self):
        wrapper = SpyWrapper(delivery_status='PENDING')

        activation_status.check_row_status(wrapper, _delivery_row(), 'ctr_1', 'grp_1')

        assert len(wrapper.delivery_calls) == 1
        assert len(wrapper.waf_calls) == 0

    def test_missing_contract_or_group_fails_without_calling_api(self):
        wrapper = SpyWrapper()

        result = activation_status.check_row_status(wrapper, _delivery_row(), None, 'grp_1')

        assert result['is_active'] is False
        assert result['status'] == 'MISSING_CONTRACT_OR_GROUP'
        assert wrapper.delivery_calls == []

    def test_non_200_response_is_active_false(self):
        wrapper = SpyWrapper(delivery_status_code=500)

        result = activation_status.check_row_status(wrapper, _delivery_row(), 'ctr_1', 'grp_1')

        assert result['is_active'] is False
        assert result['status'] == 'UNABLE_TO_GET_STATUS'


class TestCheckRowStatusWaf:
    def test_activated_status_is_active_true(self):
        wrapper = SpyWrapper(waf_status='ACTIVATED')

        result = activation_status.check_row_status(wrapper, _waf_row(), 'ctr_1', 'grp_1')

        assert result['is_active'] is True
        assert result['status'] == 'ACTIVATED'
        assert wrapper.waf_calls == ['act_1']
        assert wrapper.delivery_calls == []

    def test_pending_status_is_active_false(self):
        wrapper = SpyWrapper(waf_status='PENDING')

        result = activation_status.check_row_status(wrapper, _waf_row(), 'ctr_1', 'grp_1')

        assert result['is_active'] is False

    def test_waf_row_does_not_require_contract_or_group(self):
        wrapper = SpyWrapper(waf_status='ACTIVATED')

        result = activation_status.check_row_status(wrapper, _waf_row(), None, None)

        assert result['is_active'] is True

    def test_non_200_response_is_active_false(self):
        wrapper = SpyWrapper(waf_status_code=500)

        result = activation_status.check_row_status(wrapper, _waf_row(), 'ctr_1', 'grp_1')

        assert result['is_active'] is False
        assert result['status'] == 'UNABLE_TO_GET_STATUS'


class TestCheckAll:
    def test_mixed_delivery_and_waf_rows_all_active(self):
        wrapper = SpyWrapper(delivery_status='ACTIVE', waf_status='ACTIVATED')
        rows = [_delivery_row(), _waf_row()]

        results = activation_status.check_all(wrapper, rows, 'ctr_1', 'grp_1')

        assert len(results) == 2
        assert all(r['is_active'] for r in results)
        assert len(wrapper.delivery_calls) == 1
        assert len(wrapper.waf_calls) == 1

    def test_mixed_pending_and_active(self):
        wrapper = SpyWrapper(delivery_status='ACTIVE', waf_status='PENDING')
        rows = [_delivery_row(activation_id='atv_1'), _waf_row(activation_id='act_1')]

        results = activation_status.check_all(wrapper, rows, 'ctr_1', 'grp_1')

        active_flags = {r['activation_id']: r['is_active'] for r in results}
        assert active_flags == {'atv_1': True, 'act_1': False}

    def test_only_delivery_rows(self):
        wrapper = SpyWrapper(delivery_status='ACTIVE')
        rows = [_delivery_row('atv_1'), _delivery_row('atv_2', property_id='prp_456')]

        results = activation_status.check_all(wrapper, rows, 'ctr_1', 'grp_1')

        assert len(results) == 2
        assert all(r['is_active'] for r in results)
        assert len(wrapper.delivery_calls) == 2

    def test_only_waf_rows(self):
        wrapper = SpyWrapper(waf_status='ACTIVATED')
        rows = [_waf_row('act_1'), _waf_row('act_2')]

        results = activation_status.check_all(wrapper, rows, None, None)

        assert len(results) == 2
        assert all(r['is_active'] for r in results)
        assert len(wrapper.waf_calls) == 2


class TestLoadManifestRows:
    def test_reads_csv_into_dicts(self, tmp_path):
        import activation_manifest
        manifest_path = str(tmp_path / 'activation-status.csv')
        activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_1')
        activation_manifest.append_activation(manifest_path, 'WAF Security File', '', 3, 'act_1')

        rows = activation_status.load_manifest_rows(manifest_path)

        assert len(rows) == 2
        assert rows[0]['property_name'] == 'example-prop'
        assert rows[0]['property_id'] == 'prp_123'
        assert rows[1]['property_id'] == ''


class TestBuildStatusTable:
    def test_renders_name_id_network_status_for_each_row(self):
        from rich.console import Console

        results = [
            {'name': 'example-prop', 'version': '1', 'activation_id': 'atv_1', 'network': 'PRODUCTION',
             'status': 'ACTIVE', 'is_active': True},
            {'name': 'WAF Security File', 'version': '3', 'activation_id': 'act_1', 'network': 'PRODUCTION',
             'status': 'PENDING', 'is_active': False},
        ]

        table = activation_status.build_status_table(results)
        console = Console(record=True, width=120)
        console.print(table)
        output = console.export_text()

        assert 'example-prop' in output
        assert 'atv_1' in output
        assert 'WAF Security File' in output
        assert 'act_1' in output
        assert 'ACTIVE' in output
        assert 'Version' in output
        assert '1' in output
        assert '3' in output
        assert 'PENDING' in output


class SequenceWrapper:
    """Plays back a per-activation-id sequence of statuses, advancing one step
    each call; the last entry repeats once a sequence is exhausted. Lets tests
    simulate a row transitioning from pending to active/errored across
    wait_until_done's repeated check_all() cycles.
    """

    def __init__(self, delivery_sequences: dict[str, list[str]] | None = None,
                 waf_sequences: dict[str, list[str]] | None = None,
                 delivery_status_codes: dict[str, list[int]] | None = None):
        self.delivery_sequences = delivery_sequences or {}
        self.waf_sequences = waf_sequences or {}
        self.delivery_status_codes = delivery_status_codes or {}
        self._delivery_index: dict[str, int] = {}
        self._waf_index: dict[str, int] = {}
        self.delivery_call_count = 0
        self.waf_call_count = 0

    def pollActivationStatus(self, contractId, groupId, propertyId, activationId):
        self.delivery_call_count += 1
        i = self._delivery_index.get(activationId, 0)
        self._delivery_index[activationId] = i + 1

        codes = self.delivery_status_codes.get(activationId)
        if codes:
            status_code = codes[min(i, len(codes) - 1)]
        else:
            status_code = 200

        seq = self.delivery_sequences[activationId]
        status = seq[min(i, len(seq) - 1)]
        body = {'activations': {'items': [{'activationId': activationId, 'network': 'PRODUCTION', 'status': status}]}}
        return SimpleNamespace(status_code=status_code, json=lambda: body)

    def pollWafActivationStatus(self, activationId):
        self.waf_call_count += 1
        i = self._waf_index.get(activationId, 0)
        self._waf_index[activationId] = i + 1
        seq = self.waf_sequences[activationId]
        status = seq[min(i, len(seq) - 1)]
        body = {'network': 'PRODUCTION', 'status': status}
        return SimpleNamespace(status_code=200, json=lambda: body)


class TestWaitUntilDone:
    def test_polls_until_pending_becomes_active(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(activation_status.time, 'sleep', lambda seconds: sleeps.append(seconds))
        wrapper = SequenceWrapper(delivery_sequences={'atv_1': ['PENDING', 'PENDING', 'ACTIVE']})

        results = activation_status.wait_until_done(wrapper, [_delivery_row(activation_id='atv_1')], 'ctr_1', 'grp_1')

        assert results[0]['is_active'] is True
        assert results[0]['status'] == 'ACTIVE'
        assert wrapper.delivery_call_count == 3
        assert sleeps == [30, 30]

    def test_stops_once_row_hits_a_terminal_error_status(self, monkeypatch):
        """UNABLE_TO_GET_STATUS (a non-200 response) is terminal -- retrying won't
        change the outcome, so the loop must not spin forever on it."""
        monkeypatch.setattr(activation_status.time, 'sleep', lambda seconds: None)
        # Cycle 1: PENDING/200 (not done, keep looping). Cycle 2: 500 -> UNABLE_TO_GET_STATUS (terminal, stop).
        wrapper = SequenceWrapper(
            delivery_sequences={'atv_1': ['PENDING', 'PENDING']},
            delivery_status_codes={'atv_1': [200, 500]},
        )

        results = activation_status.wait_until_done(wrapper, [_delivery_row(activation_id='atv_1')], 'ctr_1', 'grp_1')

        assert results[0]['is_active'] is False
        assert results[0]['status'] == 'UNABLE_TO_GET_STATUS'
        assert wrapper.delivery_call_count == 2

    def test_mixed_delivery_and_waf_rows_loop_until_both_done(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(activation_status.time, 'sleep', lambda seconds: sleeps.append(seconds))
        wrapper = SequenceWrapper(
            delivery_sequences={'atv_1': ['ACTIVE']},
            waf_sequences={'act_1': ['PENDING', 'ACTIVATED']},
        )

        results = activation_status.wait_until_done(
            wrapper, [_delivery_row(activation_id='atv_1'), _waf_row(activation_id='act_1')], 'ctr_1', 'grp_1',
        )

        by_id = {r['activation_id']: r for r in results}
        assert by_id['atv_1']['is_active'] is True
        assert by_id['act_1']['is_active'] is True
        # Delivery row was already ACTIVE on cycle 1 but keeps getting re-queried
        # each cycle until the WAF row also finishes -- matches poll.py's existing
        # "re-check everything every cycle" precedent.
        assert wrapper.delivery_call_count == 2
        assert wrapper.waf_call_count == 2
        assert sleeps == [30]

    def test_already_all_active_on_first_check_does_not_sleep(self, monkeypatch):
        monkeypatch.setattr(activation_status.time, 'sleep', lambda seconds: pytest.fail('should not sleep'))
        wrapper = SequenceWrapper(delivery_sequences={'atv_1': ['ACTIVE']})

        results = activation_status.wait_until_done(wrapper, [_delivery_row(activation_id='atv_1')], 'ctr_1', 'grp_1')

        assert results[0]['is_active'] is True
        assert wrapper.delivery_call_count == 1

    def test_custom_poll_interval_is_used(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(activation_status.time, 'sleep', lambda seconds: sleeps.append(seconds))
        wrapper = SequenceWrapper(delivery_sequences={'atv_1': ['PENDING', 'ACTIVE']})

        activation_status.wait_until_done(wrapper, [_delivery_row(activation_id='atv_1')], 'ctr_1', 'grp_1',
                                           poll_interval_seconds=5)

        assert sleeps == [5]
