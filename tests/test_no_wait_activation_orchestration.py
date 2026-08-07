"""
Covers bin/no_wait_activation.py's fire_single_property_production -- the
shared --no-wait production-activation orchestration extracted from
single-host and multi-hosts once both commands' inline blocks turned out to
be identical.

Delivery activation always fires (the caller already gated on
activate_property_production before calling this function); WAF activation
fires only when create_new_security_config and activate_waf_policy_production
are both true, and fires unconditionally once enabled -- even if the delivery
submission itself failed, so one activation's outcome never blocks the
other. Each successful submission writes a manifest row; failures are logged
and skipped.
"""
from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import activation_manifest
import no_wait_activation


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
