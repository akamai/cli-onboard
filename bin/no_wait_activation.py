from __future__ import annotations

import logging

import activation_manifest
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
