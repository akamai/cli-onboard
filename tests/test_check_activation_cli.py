"""Runs the check-activation command end to end with a fake activation-status service, to confirm it reports results correctly."""
from __future__ import annotations

from types import SimpleNamespace

import activation_manifest
import activation_status
import pytest
import wrapper_api


def _stub_poll_activation_status(status_by_activation_id, status_code=200):
    def _poll(self, contractId, groupId, propertyId, activationId):
        status = status_by_activation_id[activationId]
        body = {'activations': {'items': [{'activationId': activationId, 'network': 'PRODUCTION', 'status': status}]}}
        return SimpleNamespace(status_code=status_code, json=lambda: body)
    return _poll


def _stub_poll_waf_activation_status(status_by_activation_id, status_code=200):
    def _poll(self, activationId):
        status = status_by_activation_id[activationId]
        body = {'network': 'PRODUCTION', 'status': status}
        return SimpleNamespace(status_code=status_code, json=lambda: body)
    return _poll


@pytest.fixture
def manifest_path(tmp_path):
    return str(tmp_path / 'activation-status.csv')


def test_all_active_manifest_exits_zero(runner, cli, fake_edgerc, monkeypatch, manifest_path):
    activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_1')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollActivationStatus',
                         _stub_poll_activation_status({'atv_1': 'ACTIVE'}))

    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation',
        '--file', manifest_path, '--contract', 'ctr_1', '--group', 'grp_1',
    ])

    assert result.exit_code == 0
    assert 'example-prop' in result.output
    assert 'ACTIVE' in result.output


def test_mixed_pending_and_active_exits_non_zero_and_shows_both_statuses(runner, cli, fake_edgerc, monkeypatch, manifest_path):
    activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_1')
    activation_manifest.append_activation(manifest_path, 'WAF Security File', '', 3, 'act_1')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollActivationStatus',
                         _stub_poll_activation_status({'atv_1': 'ACTIVE'}))
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollWafActivationStatus',
                         _stub_poll_waf_activation_status({'act_1': 'PENDING'}))

    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation',
        '--file', manifest_path, '--contract', 'ctr_1', '--group', 'grp_1',
    ])

    assert result.exit_code != 0
    assert 'ACTIVE' in result.output
    assert 'PENDING' in result.output


def test_manifest_with_only_waf_rows(runner, cli, fake_edgerc, monkeypatch, manifest_path):
    activation_manifest.append_activation(manifest_path, 'WAF Security File', '', 3, 'act_1')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollWafActivationStatus',
                         _stub_poll_waf_activation_status({'act_1': 'ACTIVATED'}))

    # No --contract/--group needed for a WAF-only manifest.
    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation', '--file', manifest_path,
    ])

    assert result.exit_code == 0
    assert 'WAF Security File' in result.output


def test_manifest_with_only_delivery_rows(runner, cli, fake_edgerc, monkeypatch, manifest_path):
    activation_manifest.append_activation(manifest_path, 'prop-a', 'prp_1', 1, 'atv_1')
    activation_manifest.append_activation(manifest_path, 'prop-b', 'prp_2', 1, 'atv_2')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollActivationStatus',
                         _stub_poll_activation_status({'atv_1': 'ACTIVE', 'atv_2': 'ACTIVE'}))

    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation',
        '--file', manifest_path, '--contract', 'ctr_1', '--group', 'grp_1',
    ])

    assert result.exit_code == 0
    assert 'prop-a' in result.output
    assert 'prop-b' in result.output


def test_ad_hoc_delivery_check_without_manifest_file(runner, cli, fake_edgerc, monkeypatch):
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollActivationStatus',
                         _stub_poll_activation_status({'atv_1': 'ACTIVE'}))

    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation',
        '--activation-id', 'atv_1', '--property-id', 'prp_123', '--version', '1',
        '--contract', 'ctr_1', '--group', 'grp_1',
    ])

    assert result.exit_code == 0
    assert 'atv_1' in result.output
    assert '1' in result.output


def test_ad_hoc_waf_check_without_property_id(runner, cli, fake_edgerc, monkeypatch):
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollWafActivationStatus',
                         _stub_poll_waf_activation_status({'act_1': 'ACTIVATED'}))

    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation', '--activation-id', 'act_1',
    ])

    assert result.exit_code == 0
    assert 'act_1' in result.output


def test_missing_file_and_activation_id_errors(runner, cli, fake_edgerc):
    result = runner.invoke(cli, ['--edgerc', fake_edgerc, 'check-activation'])

    assert result.exit_code != 0


def test_delivery_row_without_contract_and_group_exits_non_zero(runner, cli, fake_edgerc, monkeypatch, manifest_path):
    activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_1')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollActivationStatus',
                         _stub_poll_activation_status({'atv_1': 'ACTIVE'}))

    result = runner.invoke(cli, ['--edgerc', fake_edgerc, 'check-activation', '--file', manifest_path])

    assert result.exit_code != 0


def _stub_sequenced_poll_activation_status(sequence_by_activation_id):
    """Simulates a status changing over time, so waiting-for-completion behavior can be tested."""
    call_index: dict[str, int] = {}

    def _poll(self, contractId, groupId, propertyId, activationId):
        i = call_index.get(activationId, 0)
        call_index[activationId] = i + 1
        seq = sequence_by_activation_id[activationId]
        status = seq[min(i, len(seq) - 1)]
        body = {'activations': {'items': [{'activationId': activationId, 'network': 'PRODUCTION', 'status': status}]}}
        return SimpleNamespace(status_code=200, json=lambda: body)

    return _poll


def test_wait_polls_until_active_then_exits_zero(runner, cli, fake_edgerc, monkeypatch, manifest_path):
    activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_1')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollActivationStatus',
                         _stub_sequenced_poll_activation_status({'atv_1': ['PENDING', 'PENDING', 'ACTIVE']}))
    sleeps = []
    monkeypatch.setattr(activation_status.time, 'sleep', lambda seconds: sleeps.append(seconds))

    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation',
        '--file', manifest_path, '--contract', 'ctr_1', '--group', 'grp_1', '--wait',
    ])

    assert result.exit_code == 0
    assert 'ACTIVE' in result.output
    assert sleeps == [30, 30]


def test_without_wait_flag_checks_once_and_does_not_sleep(runner, cli, fake_edgerc, monkeypatch, manifest_path):
    activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_1')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollActivationStatus',
                         _stub_sequenced_poll_activation_status({'atv_1': ['PENDING']}))
    monkeypatch.setattr(activation_status.time, 'sleep', lambda seconds: pytest.fail('one-shot mode must not sleep'))

    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation',
        '--file', manifest_path, '--contract', 'ctr_1', '--group', 'grp_1',
    ])

    assert result.exit_code != 0
    assert 'PENDING' in result.output


def test_minimal_csv_with_only_activation_id_checks_as_waf(runner, cli, fake_edgerc, monkeypatch, csv_factory):
    path = csv_factory([{'activation_id': 'act_1'}], filename='ids.csv')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollWafActivationStatus',
                         _stub_poll_waf_activation_status({'act_1': 'ACTIVATED'}))

    result = runner.invoke(cli, ['--edgerc', fake_edgerc, 'check-activation', '--file', path])

    assert result.exit_code == 0
    assert 'act_1' in result.output


def test_minimal_csv_with_activation_id_and_property_id_checks_as_delivery(runner, cli, fake_edgerc, monkeypatch, csv_factory):
    path = csv_factory([{'activation_id': 'atv_1', 'property_id': 'prp_123'}], filename='ids.csv')
    monkeypatch.setattr(wrapper_api.apiCallsWrapper, 'pollActivationStatus',
                         _stub_poll_activation_status({'atv_1': 'ACTIVE'}))

    result = runner.invoke(cli, [
        '--edgerc', fake_edgerc, 'check-activation',
        '--file', path, '--contract', 'ctr_1', '--group', 'grp_1',
    ])

    assert result.exit_code == 0
    assert 'atv_1' in result.output


def test_csv_missing_activation_id_column_exits_with_clear_error(runner, cli, fake_edgerc, csv_factory):
    path = csv_factory([{'property_id': 'prp_123', 'version': '1'}], filename='bad.csv')

    result = runner.invoke(cli, ['--edgerc', fake_edgerc, 'check-activation', '--file', path])

    assert result.exit_code != 0
    assert 'activation_id' in result.output
