from __future__ import annotations

import json
import sys
import time
from time import gmtime
from time import strftime

from exceptions import setup_logger

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

    def addHostnames(self, wrapper_object, hostname_list, config_id, version):
        """
        Function to fetch and update Match Target
        """
        logger.info(f'{hostname_list}, config_id: {config_id}, version: {version}')
        selected_hosts_response = wrapper_object.getWafSelectedHosts(config_id, version)
        logger.debug(selected_hosts_response.url)
        logger.debug(selected_hosts_response.status_code)
        if selected_hosts_response.status_code == 200:
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
            if modify_hosts_response.status_code == 200 or \
                modify_hosts_response.status_code == 201:
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
        if version_creation_response.status_code == 200 or \
            version_creation_response.status_code == 201:
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
   
    def createWafVersion_Update(self, wrapper_object, onboard_obj, notes: str):
        """
        Function to create new waf config version
        """
        version_creation_response = wrapper_object.createWafConfigVersion(onboard_obj.config_id,
                                                                          onboard_obj.config_version,
                                                                          notes)
        if version_creation_response.status_code == 200 or \
            version_creation_response.status_code == 201:
            onboard_obj.onboard_waf_config_version = version_creation_response.json()['version']
            logger.info(f"'{onboard_obj.waf_config_name}'{dot:>8}"
                        f'id: {onboard_obj.config_id:<5}{dot:>15}'
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
            logger.info(f'Valid hostnames {onboard_obj.public_hostnames} for '
                        f'contract_id {onboard_obj.contract_id} and '
                        f'group_id {onboard_obj.group_id}')
            public_hostnames = {public_hostnames.lower() for public_hostnames in onboard_obj.public_hostnames}
            logger.debug(f'{public_hostnames}')
            logger.debug(set(hostnames))
            if (public_hostnames.issubset(set(hostnames))):
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
        logger.debug(json.dumps(resp.json(), indent=4))
        if resp.status_code == 200 or \
            resp.status_code == 201:
            logger.info(f"'{onboard_obj.waf_config_name}'{dot:>8}"
                        f'id: {onboard_obj.onboard_waf_config_id:<5}{dot:>15}'
                        f'version: {onboard_obj.onboard_waf_config_version:<5}{dot:>5}'
                        f'valid Security Configuration')
            return True
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

    def create_waf_match_target(self, wrap_api, onboard_obj):
        resp = wrap_api.create_waf_match_target(onboard_obj)
        logger.debug(json.dumps(resp.json(), indent=4))
        if resp.status_code == 200 or \
            resp.status_code == 201:
            onboard_obj.target_seq = resp.json()['sequence']
            onboard_obj.target_id = resp.json()['targetId']
            extra = (len(onboard_obj.waf_config_name) - len('sequence: 1')) + 10
            logger.info(f'sequence: {onboard_obj.target_seq}{dot:>{extra}}'
                        f'id: {onboard_obj.target_id:<5}{dot:>32}'
                        'valid match target sequence')
            return True
        logger.error('Unable to create a match target')
        return False
