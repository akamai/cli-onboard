"""
Covers bin/no_wait_activation.py -- the shared --no-wait production-activation
orchestration extracted once commands' inline blocks turned out to be
identical or shaped alike:

- fire_single_property_production (single-host/multi-hosts): delivery
  activation always fires (the caller already gated on
  activate_property_production before calling this function); WAF activation
  fires only when create_new_security_config and activate_waf_policy_production
  are both true, and fires unconditionally once enabled -- even if the
  delivery submission itself failed, so one activation's outcome never blocks
  the other.
- fire_appsec_update_activations (appsec-update/appsec-remove): loops over
  --activate's requested networks; only 'production' is affected by no_wait.
- fire_appsec_create_activations (appsec-create): delegates to
  wafFunctions.activate_and_poll for the actual activation (staging always
  polls, production only reached when activate == 'production'), then writes
  manifest rows for whichever configs submitted successfully under no_wait.

Each successful submission writes a manifest row; failures are logged and
skipped.
"""
from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import activation_manifest
import no_wait_activation
import pytest


class FakePapi:
    def __init__(self, submitted=True, activation_id='atv_1'):
        self.submitted = submitted
        self.activation_id = activation_id if submitted else None
        self.calls = []

    def activate_and_poll(self, **kwargs):
        self.calls.append(kwargs)
        return self.submitted, self.activation_id


class FakeWaf:
    def __init__(self, submitted=True, activation_id='act_1'):
        self.submitted = submitted
        self.activation_id = activation_id if submitted else None
        self.calls = []

    def activateAndPoll(self, wrapper_object, onboard, network, no_wait=False):
        self.calls.append((onboard, network, no_wait))
        return self.submitted, self.activation_id


def _onboard(**overrides):
    defaults = dict(property_name='example-prop', contract_id='ctr_1', group_id='grp_1',
                     onboard_property_id='prp_123', notification_emails=['a@example.com'],
                     create_new_security_config=True, activate_waf_policy_production=True,
                     waf_config_name='WAF Security File', onboard_waf_config_version=3)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _manifest_rows(manifest_path):
    if not Path(manifest_path).exists():
        return []
    with open(manifest_path, newline='') as f:
        return list(csv.DictReader(f))


class TestFireSinglePropertyProduction:
    def test_delivery_only_waf_disabled_writes_one_manifest_row(self, tmp_path):
        onboard = _onboard(create_new_security_config=False)
        util_papi = FakePapi(submitted=True, activation_id='atv_1')
        util_waf = FakeWaf()
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_single_property_production(util_papi, util_waf, 'wrap', onboard, manifest_path)

        rows = _manifest_rows(manifest_path)
        assert len(rows) == 1
        assert rows[0]['property_name'] == 'example-prop'
        assert rows[0]['activation_id'] == 'atv_1'
        assert util_waf.calls == []

    def test_delivery_and_waf_both_enabled_writes_two_manifest_rows(self, tmp_path):
        onboard = _onboard()
        util_papi = FakePapi(submitted=True, activation_id='atv_1')
        util_waf = FakeWaf(submitted=True, activation_id='act_1')
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_single_property_production(util_papi, util_waf, 'wrap', onboard, manifest_path)

        rows = _manifest_rows(manifest_path)
        assert len(rows) == 2
        assert rows[0]['activation_id'] == 'atv_1'
        assert rows[0]['property_id'] == 'prp_123'
        assert rows[1]['activation_id'] == 'act_1'
        assert rows[1]['property_id'] == ''
        assert util_waf.calls == [(onboard, 'PRODUCTION', True)]

    def test_waf_fires_even_when_delivery_submission_fails(self, tmp_path):
        """Per the 'WAF fires regardless of delivery outcome' decision -- WAF
        production activation is not gated on delivery's result."""
        onboard = _onboard()
        util_papi = FakePapi(submitted=False)
        util_waf = FakeWaf(submitted=True, activation_id='act_1')
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_single_property_production(util_papi, util_waf, 'wrap', onboard, manifest_path)

        assert util_waf.calls == [(onboard, 'PRODUCTION', True)]
        rows = _manifest_rows(manifest_path)
        assert len(rows) == 1
        assert rows[0]['activation_id'] == 'act_1'
        assert rows[0]['property_id'] == ''

    def test_waf_disabled_via_activate_waf_policy_production_flag(self, tmp_path):
        onboard = _onboard(activate_waf_policy_production=False)
        util_papi = FakePapi(submitted=True, activation_id='atv_1')
        util_waf = FakeWaf()
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_single_property_production(util_papi, util_waf, 'wrap', onboard, manifest_path)

        assert util_waf.calls == []
        rows = _manifest_rows(manifest_path)
        assert len(rows) == 1

    def test_both_submissions_fail_writes_no_manifest_rows(self, tmp_path):
        onboard = _onboard()
        util_papi = FakePapi(submitted=False)
        util_waf = FakeWaf(submitted=False)
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_single_property_production(util_papi, util_waf, 'wrap', onboard, manifest_path)

        assert _manifest_rows(manifest_path) == []

    def test_delivery_activate_and_poll_called_with_no_wait_true_and_correct_fields(self, tmp_path):
        onboard = _onboard()
        util_papi = FakePapi(submitted=True, activation_id='atv_1')
        util_waf = FakeWaf(submitted=True)
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_single_property_production(util_papi, util_waf, 'wrap-object', onboard, manifest_path)

        assert len(util_papi.calls) == 1
        call = util_papi.calls[0]
        assert call['wrapper_object'] == 'wrap-object'
        assert call['property_name'] == 'example-prop'
        assert call['contract_id'] == 'ctr_1'
        assert call['group_id'] == 'grp_1'
        assert call['property_id'] == 'prp_123'
        assert call['network'] == 'PRODUCTION'
        assert call['no_wait'] is True


class FakeAppsecWaf:
    """Stands in for utility_waf.wafFunctions for
    fire_appsec_update_activations: records every updateActivateAndPoll call
    and plays back a canned result keyed on network."""

    def __init__(self, production_result=(True, 555)):
        self.production_result = production_result
        self.calls = []

    def updateActivateAndPoll(self, wrapper_object, onboard_object, network, no_wait=False):
        self.calls.append((network, no_wait))
        if network == 'PRODUCTION' and no_wait:
            return self.production_result
        return True


def _appsec_update_onboard():
    return SimpleNamespace(waf_config_name='WAF Security File', onboard_waf_config_version=3)


class TestFireAppsecUpdateActivations:
    def test_staging_only_no_wait_true_never_writes_manifest_row(self, tmp_path):
        util_waf = FakeAppsecWaf()
        onboard = _appsec_update_onboard()
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_update_activations(util_waf, 'wrap', onboard, ('staging',), True, manifest_path)

        assert util_waf.calls == [('STAGING', False)]
        assert _manifest_rows(manifest_path) == []

    def test_production_no_wait_true_submits_and_writes_manifest_row(self, tmp_path):
        util_waf = FakeAppsecWaf(production_result=(True, 555))
        onboard = _appsec_update_onboard()
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_update_activations(util_waf, 'wrap', onboard, ('production',), True,
                                                            manifest_path)

        assert util_waf.calls == [('PRODUCTION', True)]
        rows = _manifest_rows(manifest_path)
        assert len(rows) == 1
        assert rows[0]['property_name'] == 'WAF Security File'
        assert rows[0]['property_id'] == ''
        assert rows[0]['activation_id'] == '555'

    def test_staging_and_production_together_writes_only_one_manifest_row(self, tmp_path):
        util_waf = FakeAppsecWaf(production_result=(True, 555))
        onboard = _appsec_update_onboard()
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_update_activations(util_waf, 'wrap', onboard, ('staging', 'production'), True,
                                                            manifest_path)

        assert util_waf.calls == [('STAGING', False), ('PRODUCTION', True)]
        assert len(_manifest_rows(manifest_path)) == 1

    def test_production_submission_failure_logs_and_writes_no_manifest_row(self, tmp_path):
        util_waf = FakeAppsecWaf(production_result=(False, None))
        onboard = _appsec_update_onboard()
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_update_activations(util_waf, 'wrap', onboard, ('production',), True,
                                                            manifest_path)

        assert _manifest_rows(manifest_path) == []

    def test_production_no_wait_false_uses_blocking_path_and_exits_on_failure(self, tmp_path):
        class FailingWaf:
            def updateActivateAndPoll(self, wrapper_object, onboard_object, network, no_wait=False):
                return False

        with pytest.raises(SystemExit):
            no_wait_activation.fire_appsec_update_activations(
                FailingWaf(), 'wrap', _appsec_update_onboard(), ('production',), False, str(tmp_path / 'unused.csv'))

    def test_production_no_wait_false_succeeds_without_touching_manifest(self, tmp_path):
        util_waf = FakeAppsecWaf()
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_update_activations(util_waf, 'wrap', _appsec_update_onboard(), ('production',),
                                                            False, manifest_path)

        assert util_waf.calls == [('PRODUCTION', False)]
        assert _manifest_rows(manifest_path) == []


class FakeAppsecCreateWaf:
    """Stands in for wafFunctions.activate_and_poll for
    fire_appsec_create_activations: mutates appsec_onboard in place (setting
    activation_id/activation_status per item), matching how the real
    activation_detail/waf_poll_activation pair it wraps behaves."""

    def __init__(self, activation_id=888, status='PENDING'):
        self.activation_id = activation_id
        self.status = status
        self.calls = []

    def activate_and_poll(self, wrapper_object, appsec_onboard, activate, no_wait=False):
        self.calls.append((activate, no_wait))
        for appsec in appsec_onboard:
            appsec.activation_id = self.activation_id
            appsec.activation_status = self.status


def _appsec_create_item(name='waf-config-a'):
    return SimpleNamespace(waf_config_name=name, onboard_waf_config_id=1, onboard_waf_config_version=2,
                            activation_id=0, activation_status='')


class TestFireAppsecCreateActivations:
    def test_delegates_to_activate_and_poll_with_activate_and_no_wait(self, tmp_path):
        util_waf = FakeAppsecCreateWaf()
        appsec_onboard = [_appsec_create_item()]
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_create_activations(util_waf, 'wrap', appsec_onboard, 'production', True,
                                                            manifest_path)

        assert util_waf.calls == [('production', True)]

    def test_no_wait_production_writes_manifest_row_per_submitted_config(self, tmp_path):
        util_waf = FakeAppsecCreateWaf(activation_id=888, status='PENDING')
        appsec_onboard = [_appsec_create_item('waf-config-a'), _appsec_create_item('waf-config-b')]
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_create_activations(util_waf, 'wrap', appsec_onboard, 'production', True,
                                                            manifest_path)

        rows = _manifest_rows(manifest_path)
        assert len(rows) == 2
        assert {r['property_name'] for r in rows} == {'waf-config-a', 'waf-config-b'}
        assert all(r['property_id'] == '' for r in rows)
        assert all(r['activation_id'] == '888' for r in rows)

    def test_activation_error_status_is_skipped_and_logged(self, tmp_path):
        class MixedResultWaf:
            def activate_and_poll(self, wrapper_object, appsec_onboard, activate, no_wait=False):
                appsec_onboard[0].activation_id = 111
                appsec_onboard[0].activation_status = 'PENDING'
                appsec_onboard[1].activation_id = 0
                appsec_onboard[1].activation_status = 'ACTIVATION_ERROR - unable to process request'

        appsec_onboard = [_appsec_create_item('waf-config-ok'), _appsec_create_item('waf-config-bad')]
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_create_activations(MixedResultWaf(), 'wrap', appsec_onboard, 'production',
                                                            True, manifest_path)

        rows = _manifest_rows(manifest_path)
        assert len(rows) == 1
        assert rows[0]['property_name'] == 'waf-config-ok'

    def test_staging_only_activate_never_writes_manifest_even_with_no_wait_true(self, tmp_path):
        util_waf = FakeAppsecCreateWaf()
        appsec_onboard = [_appsec_create_item()]
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_create_activations(util_waf, 'wrap', appsec_onboard, 'staging', True,
                                                            manifest_path)

        assert _manifest_rows(manifest_path) == []

    def test_no_wait_false_never_writes_manifest(self, tmp_path):
        util_waf = FakeAppsecCreateWaf()
        appsec_onboard = [_appsec_create_item()]
        manifest_path = str(tmp_path / 'activation-status.csv')

        no_wait_activation.fire_appsec_create_activations(util_waf, 'wrap', appsec_onboard, 'production', False,
                                                            manifest_path)

        assert util_waf.calls == [('production', False)]
        assert _manifest_rows(manifest_path) == []
