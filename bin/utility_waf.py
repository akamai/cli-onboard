from __future__ import annotations

import datetime
import json
import re
import sys
import time
from time import gmtime
from time import strftime

from exceptions import setup_logger
from rich.live import Live
from rich.table import Table

logger = setup_logger()
dot = ' '


class wafFunctions:
    def activateAndPoll(self, wrap_api, onboard_object, network):
        """
        Function to activate WAF configuration to Akamai Staging or Production network.
        """
        print()
        logger.warning(f'Preparing to activate WAF to Akamai {network} network')
        start_time = time.perf_counter()
        act_response = wrap_api.activateWafPolicy(onboard_object.onboard_waf_config_id,
                                                  onboard_object.onboard_waf_config_version,
                                                  network,
                                                  onboard_object.notification_emails,
                                                  note='Onboard CLI Activation')

        if act_response.status_code == 200:
            activation_status = False
            activation_id = act_response.json()['activationId']
            while activation_status is False:
                print('Polling 30s...')
                polling_status_response = wrap_api.pollWafActivationStatus(activation_id)

                logger.debug(json.dumps(polling_status_response.json(), indent=4))
                logger.debug(polling_status_response.url)
                if polling_status_response.status_code == 200:
                    if network in polling_status_response.json()['network']:
                        if 'status' not in polling_status_response.json():
                            time.sleep(30)
                        elif polling_status_response.json()['status'] != 'ACTIVATED':
                            time.sleep(30)
                        elif polling_status_response.json()['status'] == 'ACTIVATED':
                            end_time = time.perf_counter()
                            elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
                            msg = f'Successfully activated WAF configuration to Akamai {network} network'
                            logger.info(f'Activation Duration: {elapse_time} {msg}')
                            print()
                            activation_status = True
                            return activation_status
                        else:
                            logger.error(json.dumps(polling_status_response.json(), indent=4))
                            logger.error('Unable to parse activation status')
                            activation_status = False
                            return activation_status
                else:
                    logger.error(json.dumps(act_response.json(), indent=4))
                    logger.error('Unable to get activation status')
                    return False

        logger.error(json.dumps(act_response.json(), indent=4))
        logger.error('Unable to get activation status')
        logger.debug(act_response.url)
        return False

    def updateActivateAndPoll(self, wrap_api, onboard_object, network):
        """
        Function to activate WAF configuration to Akamai Staging or Production network when in appsec-update mode.
        """
        print()
        logger.warning(f'Preparing to activate WAF to Akamai {network} network')
        start_time = time.perf_counter()
        act_response = wrap_api.activateWafPolicy(onboard_object.config_id,
                                                onboard_object.onboard_waf_config_version,
                                                network,
                                                onboard_object.notification_emails,
                                                note=onboard_object.version_note)

        if act_response.ok:
            activation_status = False
            activation_id = act_response.json()['activationId']
            while activation_status is False:
                print('Polling 30s...')
                polling_status_response = wrap_api.pollWafActivationStatus(activation_id)

                logger.debug(json.dumps(polling_status_response.json(), indent=4))
                logger.debug(polling_status_response.url)
                if polling_status_response.ok:
                    if network in polling_status_response.json()['network']:
                        if 'status' not in polling_status_response.json():
                            time.sleep(30)
                        elif polling_status_response.json()['status'] != 'ACTIVATED':
                            time.sleep(30)
                        elif polling_status_response.json()['status'] == 'ACTIVATED':
                            end_time = time.perf_counter()
                            elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
                            msg = f'Successfully activated WAF configuration to Akamai {network} network'
                            logger.info(f'Activation Duration: {elapse_time} {msg}')
                            print()
                            activation_status = True
                            return activation_status
                        else:
                            logger.error(json.dumps(polling_status_response.json(), indent=4))
                            logger.error('Unable to parse activation status')
                            activation_status = False
                            return activation_status
                else:
                    logger.error(json.dumps(act_response.json(), indent=4))
                    logger.error('Unable to get activation status')
                    return False

        logger.error(json.dumps(act_response.json(), indent=4))
        logger.error('Unable to get activation status')
        logger.debug(act_response.url)
        return False

    def addHostnames(self, wrapper_object, hostname_list, config_id, version):
        """
        Function to fetch and update Match Target
        """
        logger.debug(f'{hostname_list}, config_id: {config_id}, version: {version}')
        selected_hosts_response = wrapper_object.getWafSelectedHosts(config_id, version)
        logger.debug(selected_hosts_response.url)
        logger.debug(selected_hosts_response.status_code)
        if selected_hosts_response.ok:
            # Update the hostnames here
            updated_json_data = selected_hosts_response.json()
            logger.debug(json.dumps(updated_json_data, indent=4))
            for every_hostname in hostname_list:
                host_entry = dict()
                host_entry['hostname'] = every_hostname
                updated_json_data['hostnameList'].append(host_entry)

            # Now update the match target
            modify_hosts_response = wrapper_object.modifyWafHosts(config_id,
                                                                  version,
                                                                  json.dumps(updated_json_data))
            if modify_hosts_response.ok:
                logger.info(f'Created WAF configuration version: {version}')
                return True
            else:
                logger.debug(modify_hosts_response.url)
                logger.debug(modify_hosts_response.status_code)
                logger.error(json.dumps(modify_hosts_response.json(), indent=4))
                return False
        else:
            logger.error(json.dumps(selected_hosts_response.json(), indent=4))
            return False

    def updateMatchTarget(self, wrapper_object, hostname_list, config_id, version, target_id):
        """
        Function to fetch and update Match Target
        """
        match_target_response = wrapper_object.getMatchTarget(config_id, version, target_id)
        logger.debug(json.dumps(match_target_response.json(), indent=4))
        if match_target_response.status_code == 200:
            # Update the hostnames here
            updated_json_data = match_target_response.json()
            if 'hostnames' in updated_json_data.keys():

                for every_hostname in hostname_list:
                    updated_json_data['hostnames'].append(every_hostname)
                logger.debug(json.dumps(updated_json_data, indent=4))

                # Now update the match target
                modify_match_target_response = wrapper_object.modifyMatchTarget(config_id,
                                                                                version, target_id,
                                                                                json.dumps(updated_json_data))
                if modify_match_target_response.status_code == 200:
                    return True
                else:
                    logger.error(json.dumps(modify_match_target_response.json(), indent=4))
                    return False
            else:
                logger.info('This WAF policy already uses "ALL HOSTNAMES" as match target.')
                return True
        else:
            logger.error(json.dumps(match_target_response.json(), indent=4))
            return False

    def createWafVersion(self, wrapper_object, onboard_obj, notes: str):
        """
        Function to create new waf config version
        """
        version_creation_response = wrapper_object.createWafConfigVersion(onboard_obj.onboard_waf_config_id,
                                                                          onboard_obj.onboard_waf_prev_version,
                                                                          notes)
        if version_creation_response.ok:
            onboard_obj.onboard_waf_config_version = version_creation_response.json()['version']
            logger.info(f"'{onboard_obj.waf_config_name}'{dot:>8}"
                        f'id: {onboard_obj.onboard_waf_config_id:<5}{dot:>15}'
                        f'new version: {onboard_obj.onboard_waf_config_version:<4}{dot:>2}'
                        f'existing Security Configuration')
            return True
        else:
            logger.error(json.dumps(version_creation_response.json(), indent=4))
            logger.error(f'Unable to create a new version for WAF Configuration: {onboard_obj.waf_config_name}')
            return False

    def valid_hostnames(self, wrap_api, onboard_obj):
        resp = wrap_api.valid_hostnames_waf_config(onboard_obj)
        if resp.status_code == 200:
            hostnames = []
            for dic in resp.json()['availableSet']:
                for key in dic:
                    if key == 'hostname':
                        hostnames.append(dic[key])
            logger.debug(f'Valid hostnames {onboard_obj.public_hostnames} for '
                        f'contract_id {onboard_obj.contract_id} and '
                        f'group_id {onboard_obj.group_id}')
            public_hostnames = {public_hostnames.lower() for public_hostnames in onboard_obj.public_hostnames}
            logger.debug(f'{public_hostnames}')
            logger.debug(set(hostnames))
            if onboard_obj.public_hostnames == []:
                # ALL Hostnames
                return True
            elif (public_hostnames.issubset(set(hostnames))):
                return True
            else:
                logger.error(f'Invalid {onboard_obj.public_hostnames} for '
                             f'contract_id {onboard_obj.contract_id} and '
                             f'group_id {onboard_obj.group_id}')
                return False
        else:
            logger.error(json.dumps(resp.json(), indent=4))
            logger.error(f'Unable to validate hostnames for WAF Configuration: {onboard_obj.waf_config_name}')
            return False

    def create_waf_config(self, wrap_api, onboard_obj):
        print()
        logger.warning('Onboarding Security Config')
        if self.valid_hostnames(wrap_api, onboard_obj) is False:
            sys.exit()

        resp = wrap_api.create_waf_configurations(onboard_obj)
        if resp.status_code == 200 or \
            resp.status_code == 201:
            logger.info(f"'{onboard_obj.waf_config_name}'{dot:>8}"
                        f'id: {onboard_obj.onboard_waf_config_id:<5}{dot:>15}'
                        f'version: {onboard_obj.onboard_waf_config_version:<5}{dot:>4}'
                        f'valid Security Configuration')
            return True
        logger.error(json.dumps(resp.json(), indent=4))
        logger.error(f'Unable to create a new version for WAF Configuration: '
                     f'{onboard_obj.waf_config_name}')
        return False

    def create_waf_policy(self, wrap_api, onboard_obj):
        resp = wrap_api.create_waf_policy(onboard_obj)
        logger.debug(json.dumps(resp.json(), indent=4))
        if resp.status_code == 200 or \
            resp.status_code == 201:
            onboard_obj.policy_id = resp.json()['policyId']
            onboard_obj.policy_name = resp.json()['policyName']
            extra = (len(onboard_obj.waf_config_name) - len(onboard_obj.policy_name)) + 8
            logger.info(f"'{onboard_obj.policy_name}'{dot:>{extra}}"
                        f"id: '{onboard_obj.policy_id}'{dot:<5}{dot:>21}"
                        'valid WAF policy')
            return True
        logger.error(resp.json()['detail'])
        return False

    def create_waf_match_target(self, wrap_api, onboard_obj, wag_target_hostnames: list | None = None):
        resp = wrap_api.create_waf_match_target(onboard_obj, wag_target_hostnames)
        logger.debug(json.dumps(resp.json(), indent=4))
        if resp.status_code == 200 or \
            resp.status_code == 201:
            onboard_obj.target_seq = resp.json()['sequence']
            onboard_obj.target_id = resp.json()['targetId']
            extra = (len(onboard_obj.waf_config_name) - len('sequence: 1')) + 10
            logger.info(f'sequence: {onboard_obj.target_seq}{dot:>{extra}}'
                        f'id: {onboard_obj.target_id:<5}{dot:>32}'
                         'valid match target sequence')
            original_extra = extra + 56
            if not wag_target_hostnames:
                hosts = onboard_obj.public_hostnames
                extra = original_extra - len(str(onboard_obj.public_hostnames)) - 2
                if extra <= 0:
                    extra = original_extra + 7
                    logger.info(f'{hosts}\n{dot:>{extra}}valid public hostnames')
                else:
                    logger.info(f'{hosts}{dot:>{extra}}'
                                f'valid public hostnames')
            else:
                if len(wag_target_hostnames) == 0:
                    hosts = wag_target_hostnames
                    logger.info(f'ALL Hostnames{dot:>{54}}valid public hostnames')
                else:
                    hosts = onboard_obj.public_hostnames
                    extra = original_extra - len(str(onboard_obj.public_hostnames)) - 2
                    if extra <= 0:
                        extra = original_extra + 7
                        logger.info(f'{hosts}\n{dot:>{extra}}valid public hostnames')
                    else:
                        logger.info(f'{hosts}{dot:>{extra}}'
                                    f'valid public hostnames')

            return True
        logger.error('Unable to create a match target')
        return False

    def activation_detail(self, wrap_api, onboard_object, activate):
        logger.warning(f'Activating Security Config on {activate} network')
        count = 0
        for i, appsec in enumerate(onboard_object):
            config_id = onboard_object[i].onboard_waf_config_id
            response = wrap_api.activateWafPolicy(config_id,
                                            onboard_object[i].onboard_waf_config_version,
                                            network='STAGING',
                                            emails=onboard_object[i].notification_emails,
                                            note=onboard_object[i].version_notes)
            if response.ok:
                onboard_object[i].activation_id = response.json()['activationId']
                onboard_object[i].activation_create = response.json()['createDate']
                onboard_object[i].activation_status = response.json()['status']
                logger.debug(onboard_object[i])
                logger.debug(f'wag_config_id {config_id} {onboard_object[i].activation_id}')
            else:
                count += 1
                activation_status = 'ACTIVATION_ERROR'
                try:
                    err_msg = response.json()['detail']
                except:
                    logger.error(response.json())

                if 'MultipleConfigs' in err_msg:
                    if 'another pending process' in err_msg:
                        activation_status = f'{activation_status}\nHostnames involved in another pending process'
                    else:
                        try:
                            old_config_id = re.findall(r'\d+', err_msg)
                            old_config_id = int(old_config_id[0])
                            old_config_name = wrap_api.getWafConfigVersions(old_config_id).json()['configName']
                            activation_status = f'{activation_status}\nhostname conflict with config "{old_config_name}" [{old_config_id}]'
                        except:
                            logger.error(f'wag_config_id {config_id} {err_msg}')
                            activation_status = f'{activation_status}\nconflict with multiple configs'
                else:
                    # logger.error(f'wag_config_id {config_id} {err_msg}')
                    activation_status = f'{activation_status} - unable to process request'
                onboard_object[i].activation_status = activation_status
        time.sleep(1)

    def activate_and_poll(self, wrap_api, onboard_object, activate):
        print()
        self.activation_detail(wrap_api, onboard_object, activate)
        self.waf_poll_activation(wrap_api, onboard_object, network='STAGING')

        if activate == 'production':
            print()
            self.activation_detail(wrap_api, onboard_object, activate)
            self.waf_poll_activation(wrap_api, onboard_object, network='PRODUCTION')

    def waf_poll_activation(self, wrapper_api, appsec_onboard, network):
        all_waf_configs_active = False
        with Live(self.waf_activation_table(appsec_onboard, network), refresh_per_second=1) as live:
            while (not all_waf_configs_active):
                for i, appsec in enumerate(appsec_onboard):
                    response = wrapper_api.pollWafActivationStatus(appsec_onboard[i].activation_id)
                    if response.status_code == 200:
                        try:
                            if response.json()['status'] == 'ACTIVATED':
                                appsec_onboard[i].activation_end = datetime.datetime.utcnow().isoformat().replace('+00:00', 'Z')
                                appsec_onboard[i].activation_status = response.json()['status']
                        except:
                            'no change to previous status'
                live.update(self.waf_activation_table(appsec_onboard, network))
                total_status = [appsec_onboard[i].activation_status for i, appsec in enumerate(appsec_onboard)]
                pending = list(filter(lambda x: not x.startswith('ACTIVATION_ERROR') and x not in ['ACTIVATED'], total_status))
                if len(pending) == 0:
                    all_waf_configs_active = True
                    break
                logger.info('Polling 1m...')
                time.sleep(60)
        return all_waf_configs_active, appsec_onboard

    def waf_activation_table(self, appsec_onboard, network) -> Table:
        table = Table()
        table.add_column('waf config name')
        table.add_column('config id')
        table.add_column('version')
        table.add_column('network', width=12)
        table.add_column('activation id')
        table.add_column('activation started (UTC)')
        table.add_column('activation ended (UTC)')
        table.add_column('status')

        for i, appsec in enumerate(appsec_onboard):
            if appsec_onboard[i].activation_status == '':
                status = '....Checking Status....'
            else:
                status = appsec_onboard[i].activation_status
            table.add_row(f'{appsec_onboard[i].waf_config_name}', f'{appsec_onboard[i].onboard_waf_config_id}', f'{appsec_onboard[i].onboard_waf_config_version}',
                        f'{network}',
                        f'{appsec_onboard[i].activation_id}',
                        f'{appsec_onboard[i].activation_create}',
                        '' if status != 'ACTIVATED' else f'{appsec_onboard[i].activation_end}',
                        f'[red]{status}' if status != 'ACTIVATED' else '[green]ACTIVATED',
                        )
        return table
