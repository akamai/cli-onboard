from __future__ import annotations

import json
import time
from time import gmtime
from time import strftime

from exceptions import setup_logger
from rich.live import Live
from rich.table import Table

logger = setup_logger()


def generate_table(activationDict, network) -> Table:

    """Make a new table."""
    table = Table()
    table.add_column('Property Name')
    table.add_column('Property Id')
    table.add_column('Activation Id')
    table.add_column('Status')

    for propertyStatus in activationDict:
        try:
            activation_status = propertyStatus['activationStatus'][network]
        except:
            activation_status = '....Checking Status....'
        table.add_row(
            f"{propertyStatus['propertyName']}", f"{propertyStatus['propertyId']}", f"{propertyStatus['activationId']}", f'[red]{activation_status}' if activation_status != 'ACTIVE' else '[green]ACTIVE'
        )
    return table


def pollActivation(activationDict, wrapper_object, contract_id, group_id, network):
    start_time = time.perf_counter()
    all_properties_active = False
    elapse_time = 0
    with Live(generate_table(activationDict, network), refresh_per_second=1) as live:
        while (not all_properties_active):
            end_time = time.perf_counter()
            elapse_time = (end_time - start_time)
            for i, propertyActivation in enumerate(activationDict):
                activation_id = propertyActivation['activationId']
                property_id = propertyActivation['propertyId']
                property_name = propertyActivation['propertyName']
                activationStatus = {'STAGING': '',
                                    'PRODUCTION': ''}
                if activation_id != 0:
                    activation_status_response = wrapper_object.pollActivationStatus(contract_id,
                                                                                    group_id,
                                                                                    property_id,
                                                                                    activation_id)
                    if activation_status_response.status_code == 200:
                        for each_activation in activation_status_response.json()['activations']['items']:
                            if each_activation['activationId'] == activation_id:
                                if network in each_activation['network']:
                                    if each_activation['status'] != 'ACTIVE':
                                        activationStatus[network] = 'PENDING_ACTIVATION'
                                        all_properties_active = False
                                    elif each_activation['status'] == 'ACTIVE':
                                        end_time = time.perf_counter()
                                        elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
                                        # msg = f'Successfully activated property {property_name} v1 on Akamai {network} network'
                                        # logger.info(f'Activation Duration: {elapse_time} {msg}')
                                        activationStatus[network] = 'ACTIVE'
                                    else:
                                        logger.error('Unable to parse activation status')
                                        activationStatus[network] = 'UNABLE_TO_UPDATE_STATUS'
                                        all_properties_active = False
                    else:
                        logger.error(json.dumps(activation_status_response.json(), indent=4))
                        logger.error(f'Unable to get activation status for {property_name}')
                        activationStatus[network] = 'UNABLE_TO_UPDATE_STATUS'
                        all_properties_active = False

                else:
                    activationStatus[network] = 'ACTIVATION_ERROR'

            # check to see if all are active, if so - set variable to true
                activationDict[i]['activationStatus'] = activationStatus
            pending_activations = (list(filter(lambda x: x['activationStatus'][network] not in ['ACTIVE', 'ACTIVATION_ERROR'], activationDict)))
            live.update(generate_table(activationDict, network))
            if len(pending_activations) == 0:
                all_properties_active = True
                break
            logger.info('Polling 30s...')
            time.sleep(30)
        return (all_properties_active, activationDict)
