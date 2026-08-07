"""
Regression test for batch_create's WAF production activation gate
(bin/akamai-onboard.py, the non-`--no-wait` production block).

The gate used to read `activation_status == 'ACTIVE'`, but `activation_status`
here is `utility_papi.papiFunctions.batch_activate_and_poll`'s
`all_properties_active` return value -- a plain bool, never the string
'ACTIVE' -- so the comparison was always False and WAF production activation
silently never fired, even when `--activate waf-production` was requested and
delivery production activation genuinely succeeded. See
.scratch/fix-batch-create-waf-production-gate-spec.md.

batch_create has no dependency-injection seam around this block (it's inline
in a large function alongside real cpcode/property/WAF-config API calls), so
per that spec's Testing Decisions, this exercises the corrected boolean
condition directly rather than forcing a full CLI-level run -- plus a direct
check against the real function's source, which is what actually would have
caught the original `== 'ACTIVE'` bug.
"""
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
        """Guards against literally reintroducing the original bug: a bool
        (`activation_status`) compared to the string 'ACTIVE', which is
        always False regardless of whether production activation succeeded."""
        source = inspect.getsource(akamai_onboard_module.batch_create.callback)

        assert "activation_status == 'ACTIVE'" not in source
        assert 'onboard_object.activate_waf_policy_production and activation_status:' in source
