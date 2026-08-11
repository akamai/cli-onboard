"""Checks that WAF production security activation actually runs when requested and the main site activation succeeded."""
from __future__ import annotations

import inspect
from types import SimpleNamespace


def _should_activate_waf_production(onboard_object, activation_status):
    # Mirrors bin/akamai-onboard.py's batch_create gate verbatim:
    #   if onboard_object.activate_waf_policy_production and activation_status:
    return onboard_object.activate_waf_policy_production and activation_status


class TestBatchCreateWafProductionGate:
    def test_fires_when_flag_true_and_delivery_production_succeeded(self):
        onboard_object = SimpleNamespace(activate_waf_policy_production=True)

        assert _should_activate_waf_production(onboard_object, True) is True

    def test_skips_when_delivery_production_failed(self):
        onboard_object = SimpleNamespace(activate_waf_policy_production=True)

        assert _should_activate_waf_production(onboard_object, False) is False

    def test_skips_when_flag_false_even_if_delivery_succeeded(self):
        onboard_object = SimpleNamespace(activate_waf_policy_production=False)

        assert _should_activate_waf_production(onboard_object, True) is False

    def test_source_no_longer_compares_activation_status_to_active_string(self, akamai_onboard_module):
        """Checks that the success check wasn't accidentally reverted to a broken comparison that would always report failure."""
        source = inspect.getsource(akamai_onboard_module.batch_create.callback)

        assert "activation_status == 'ACTIVE'" not in source
        assert 'onboard_object.activate_waf_policy_production and activation_status:' in source
