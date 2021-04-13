import json
import time
from time import strftime
from time import gmtime

class wafFunctions(object):
    def activateAndPoll(self, session, wrapper_object, onboard_object, network):
        """
        Function to activate WAF configuration to Akamai Staging or Production network.
        """
        print('\nPreparing to activate WAF to Akamai ' + network + ' network')
        start_time = round(time.time())
        act_response = wrapper_object.activateWafPolicy(session, onboard_object.onboard_waf_config_id, \
                            onboard_object.onboard_waf_config_version,network, onboard_object.notification_emails,note="Onboard CLI Activation")
        if act_response.status_code == 200:
            activation_status = False
            activation_id = act_response.json()['activationId']
            while activation_status is False:
                print('Polling 30s... (' + str(activation_id) + ')')
                activation_status_response = wrapper_object.pollWafActivationStatus(session, onboard_object.contract_id, onboard_object.group_id, onboard_object.onboard_property_id, activation_id)
                if activation_status_response.status_code == 200:
                    if network in activation_status_response.json()['network']:
                        if 'status' not in activation_status_response.json():
                            time.sleep(30) 
                        elif activation_status_response.json()['status'] != 'ACTIVATED':
                            time.sleep(30)
                        elif activation_status_response.json()['status'] == 'ACTIVATED':
                            end_time = round(time.time())
                            command_time = end_time - start_time
                            print('Duration: ' + str(strftime("%H:%M:%S", gmtime(command_time))))
                            print('Successfully activated WAF configuration to Akamai ' + network + ' network')
                            activation_status = True
                            return activation_status
                        else:
                            print('Unknown Error: Unable to parse activation status')
                            activation_status = False
                            return activation_status
                else:
                    print(json.dumps(act_response.json(), indent=4))
                    print('Unknown Error: Unable to get activation status')
                    return False
        else:
            print(json.dumps(act_response.json(), indent=4))
            return False


    def addHostnames(self, session, wrapper_object, hostname_list, config_id, version):
        """
        Function to fetch and update Match Target
        """
        selected_hosts_response = wrapper_object.getWafSelectedHosts(session, config_id, version)
        if selected_hosts_response.status_code == 200:
            #Update the hostnames here
            updated_json_data = selected_hosts_response.json()
            for every_hostname in hostname_list:
                host_entry = dict()
                host_entry['hostname'] = every_hostname
                updated_json_data['hostnameList'].append(host_entry)
            #Now update the match target
            modify_hosts_response = wrapper_object.modifyWafHosts(session, config_id, version, json.dumps(updated_json_data))
            if modify_hosts_response.status_code == 200 or modify_hosts_response.status_code == 201:
                return True
            else:
                print(json.dumps(modify_hosts_response.json(), indent=4))
                return False
        else:
            print(json.dumps(selected_hosts_response.json(), indent=4))
            return False

    def updateMatchTarget(self, session, wrapper_object, hostname_list, config_id, version, target_id):
        """
        Function to fetch and update Match Target
        """
        match_target_response = wrapper_object.getMatchTarget(session, config_id, version, target_id)
        if match_target_response.status_code == 200:
            #Update the hostnames here
            updated_json_data = match_target_response.json()
            for every_hostname in hostname_list:
                updated_json_data['hostnames'].append(every_hostname)
            #Now update the match target
            modify_match_target_response = wrapper_object.modifyMatchTarget(session, config_id, version, target_id, json.dumps(updated_json_data))
            if modify_match_target_response.status_code == 200:
                return True
            else:
                print(json.dumps(modify_match_target_response.json(), indent=4))
                return False
        else:
            print(json.dumps(match_target_response.json(), indent=4))
            return False

    def createWafVersion(self, session, setup_json_content, utility_object, wrapper_object, onboard_object):
        """
        Function to create new waf config version
        """

        version_creation_response = wrapper_object.createWafConfigVersion(session, onboard_object.onboard_waf_config_id, onboard_object.onboard_waf_prev_version)
        if version_creation_response.status_code == 200 or version_creation_response.status_code == 201:
            onboard_object.onboard_waf_config_version = version_creation_response.json()['version']
            return True
        else:
            print(json.dumps(version_creation_response.json(), indent=4))
            print('ERROR: Unable to create a new version for WAF Configuration: ' + onboard_object.waf_config_name)
            return False

