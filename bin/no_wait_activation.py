from __future__ import annotations

import logging
import sys

import activation_manifest
import onboard_appsec_update
from model.appsec import AppSec
from model.multi_hosts import MultiHosts
from model.single_host import SingleHost

logger = logging.getLogger(__name__)


def fire_single_property_production(util_papi, util_waf, wrapper_object, onboard: SingleHost | MultiHosts,
                                     manifest_path: str) -> None:
    """
    Fire production delivery activation, then (if enabled) WAF production
    activation, without waiting for either to reach ACTIVE -- WAF fires
    unconditionally once enabled, even if the delivery submission above it
    failed, so one activation's outcome never blocks the other. Logs and
    writes a manifest row for each activation that submits successfully.

    Shared by single-host and multi-hosts's --no-wait production block; both
    build a SingleHost/MultiHosts onboard object with matching field names
    (property_name, contract_id, group_id, onboard_property_id,
    notification_emails, create_new_security_config,
    activate_waf_policy_production, waf_config_name,
    onboard_waf_config_version).
    """
    submitted, activation_id = util_papi.activate_and_poll(
        wrapper_object=wrapper_object,
        property_name=onboard.property_name,
        contract_id=onboard.contract_id,
        group_id=onboard.group_id,
        property_id=onboard.onboard_property_id,
        version=1,
        network='PRODUCTION',
        emailList=onboard.notification_emails,
        notes='Onboard CLI Activation',
        no_wait=True,
    )
    if submitted:
        logger.info(f'Property {onboard.property_name} production activation submitted, activation id: {activation_id}')
        activation_manifest.append_activation(manifest_path, onboard.property_name, onboard.onboard_property_id,
                                               1, activation_id)
    else:
        logger.error('Unable to submit property activation to production network')

    if onboard.create_new_security_config and onboard.activate_waf_policy_production:
        waf_submitted, waf_activation_id = util_waf.activateAndPoll(wrapper_object, onboard, network='PRODUCTION',
                                                                      no_wait=True)
        if waf_submitted:
            logger.info(f'WAF configuration production activation submitted, activation id: {waf_activation_id}')
            activation_manifest.append_activation(manifest_path, onboard.waf_config_name, '',
                                                   onboard.onboard_waf_config_version, waf_activation_id)
        else:
            logger.error('Unable to submit WAF configuration activation to production network')
    else:
        logger.info('Activate Security configuration on Staging: PRODUCTION')


def fire_appsec_update_activations(util_waf, wrapper_object, onboard_object: onboard_appsec_update.onboard,
                                    networks, no_wait: bool, manifest_path: str) -> None:
    """
    Activate WAF for each requested network (appsec-update/appsec-remove's
    --activate, multiple=True). Any non-production network always polls to
    completion, exiting on failure -- unchanged from before no_wait existed.
    production, when no_wait is set, submits and returns immediately instead,
    writing a manifest row.

    Shared by appsec-update and appsec-remove, whose activation blocks are
    otherwise identical.
    """
    for network in networks:
        if no_wait and network == 'production':
            submitted, activation_id = util_waf.updateActivateAndPoll(wrapper_object, onboard_object,
                                                                        network=network.upper(), no_wait=True)
            if submitted:
                logger.info(f'WAF configuration {onboard_object.waf_config_name} production activation submitted, '
                            f'activation id: {activation_id}')
                activation_manifest.append_activation(manifest_path, onboard_object.waf_config_name, '',
                                                       onboard_object.onboard_waf_config_version, activation_id)
            else:
                logger.error('Unable to submit WAF configuration activation to production network')
        else:
            waf_activation_status = util_waf.updateActivateAndPoll(wrapper_object, onboard_object, network=network.upper())
            if waf_activation_status is False:
                sys.exit(logger.error(f'Unable to activate WAF configuration to {network.upper()} network'))


def fire_appsec_create_activations(util_waf, wrapper_object, appsec_onboard: list[AppSec], activate: str,
                                    no_wait: bool, manifest_path: str) -> None:
    """
    Activate every security config in appsec_onboard for appsec-create's
    single --activate choice ('staging'/'production'/''). Delegates to
    wafFunctions.activate_and_poll, which always polls staging to completion
    and only reaches production if activate == 'production'; no_wait is
    forwarded there and only ever affects that production leg. Writes a
    manifest row for each config that submitted successfully.
    """
    util_waf.activate_and_poll(wrapper_object, appsec_onboard, activate, no_wait=no_wait)
    if not (no_wait and activate == 'production'):
        return

    for appsec in appsec_onboard:
        if appsec.activation_status.startswith('ACTIVATION_ERROR'):
            logger.error(f'Unable to submit WAF configuration {appsec.waf_config_name} activation to production network')
            continue
        logger.info(f'WAF configuration {appsec.waf_config_name} production activation submitted, '
                    f'activation id: {appsec.activation_id}')
        activation_manifest.append_activation(manifest_path, appsec.waf_config_name, '',
                                               appsec.onboard_waf_config_version, appsec.activation_id)
