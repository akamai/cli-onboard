from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from time import gmtime
from time import strftime

from exceptions import setup_logger
from poll import pollActivation
from rich import print_json

logger = setup_logger()


class papiFunctions:
    def activate_and_poll(self, wrapper_object, property_name,
                        contract_id, group_id, property_id, version,
                        network, emailList: list, notes):
        """
        Function to activate a property to Akamai Staging or Production network.
        """
        logger.warning(f'Preparing to activate property {property_name} on Akamai {network} network')
        start_time = time.perf_counter()
        act_response = wrapper_object.activateConfiguration(contract_id, group_id, property_id,
                                                            version, network, emailList, notes)
        logger.debug(act_response.json())
        if act_response.status_code == 201:
            activation_status = False
            activation_id = act_response.json()['activationLink'].split('?')[0].split('/')[-1]
            while activation_status is False:
                print('Polling 30s...')
                activation_status_response = wrapper_object.pollActivationStatus(contract_id,
                                                                                 group_id,
                                                                                 property_id,
                                                                                 activation_id)
                if activation_status_response.status_code == 200:
                    for each_activation in activation_status_response.json()['activations']['items']:
                        if each_activation['activationId'] == activation_id:
                            if network in each_activation['network']:
                                if each_activation['status'] != 'ACTIVE':
                                    time.sleep(30)
                                elif each_activation['status'] == 'ACTIVE':
                                    end_time = time.perf_counter()
                                    elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
                                    msg = f'Successfully activated property {property_name} v1 on Akamai {network} network'
                                    logger.info(f'Activation Duration: {elapse_time} {msg}')
                                    activation_status = True
                                    return activation_status
                                else:
                                    logger.error('Unable to parse activation status')
                                    activation_status = False
                                    return activation_status
                else:
                    logger.error(json.dumps(activation_status_response.json(), indent=4))
                    logger.error('Unable to get activation status')
                    return False
        else:
            logger.error(json.dumps(act_response.json(), indent=4))
            return False

    def batch_activate_and_poll(self, wrapper_object, propertyDict,
                        contract_id, group_id, version,
                        network, emailList: list, notes):
        """
        Function to activate a property to Akamai Staging or Production network.
        """

        for i, activation in enumerate(propertyDict):
            logger.warning(f'Preparing to activate property {activation["propertyName"]} on Akamai {network} network')
            act_response = wrapper_object.activateConfiguration(contract_id, group_id, activation['propertyId'],
                                                                version, network, emailList, notes)
            if act_response.status_code == 201:
                activation_status = False
                activation_id = act_response.json()['activationLink'].split('?')[0].split('/')[-1]
                propertyDict[i]['activationId'] = activation_id
                logger.warning(f'Activation started for {activation["propertyName"]} on Akamai {network} network')

            else:
                logger.error(json.dumps(act_response.json(), indent=4))
                propertyDict[i]['activationId'] = 0

        all_properties_active, activationDict = pollActivation(propertyDict, wrapper_object, contract_id, group_id, network)
        failed_activations = (list(filter(lambda x: x['activationStatus'][network] not in ['ACTIVE'], activationDict)))
        successful_activations = (list(filter(lambda x: x['activationStatus'][network] in ['ACTIVE'], activationDict)))
        success_onboarded_hostnames = (list(map(lambda x: x['hostnames'], successful_activations)))
        success_onboarded_hostnames = [item for sublist in success_onboarded_hostnames for item in sublist]

        return (all_properties_active, success_onboarded_hostnames, failed_activations, activationDict)

    def create_new_cpcode(self, onboard_object, wrapper_object,
                        cpcode_name, contract_id, group_id, product_id) -> int:
        """
        Function to create new cpcode
        """
        create_cpcode_response = wrapper_object.createCpcode(contract_id,
                                                             group_id, product_id, cpcode_name)
        logger.debug(json.dumps(create_cpcode_response.json(), indent=4))
        if create_cpcode_response.status_code == 201:
            new_cpcode = create_cpcode_response.json()['cpcodeLink'].split('?')[0].split('/')[-1].replace('cpc_', '')
            onboard_object.onboard_default_cpcode = int(new_cpcode)
            logger.info(f"Created new cpcode: '{cpcode_name}', id: {new_cpcode}")
        else:
            logger.error(json.dumps(create_cpcode_response.json(), indent=4))
            sys.exit(logger.error('Unable to create new cpcode'))
        return int(new_cpcode)

    def create_update_pm(self, config, onboard_object, wrapper_object, utility_object, cli_mode: str | None = None):
        """
        Function with multiple goals:
            1. Create a property
            2. Update the property with template rules define
        """
        create_property_response = wrapper_object.createProperty(onboard_object.contract_id,
                                                                 onboard_object.group_id,
                                                                 onboard_object.product_id,
                                                                 onboard_object.property_name)
        if create_property_response.status_code == 201:
            onboard_object.onboard_property_id = create_property_response.json()['propertyLink'].split('?')[0].split('/')[-1]
            logger.info(f"Created property name: '{onboard_object.property_name}', id: {onboard_object.onboard_property_id}")
        else:
            logger.error('Unable to create property')
            sys.exit(logger.error(json.dumps(create_property_response.json(), indent=4)))

        # Do edgehostname logic
        edgeHostname_id = self.process_ehn(onboard_object, wrapper_object, utility_object, cli_mode)
        if edgeHostname_id != -1:
            secure_by_default = False
            secure_by_default_create_ehn = False
            if onboard_object.edge_hostname_mode == 'secure_by_default':
                secure_by_default = True
                if onboard_object.secure_by_default_use_existing_ehn == '':
                    secure_by_default_create_ehn = True
            edgehostname_list = wrapper_object.createEdgehostnameArray(onboard_object.public_hostnames,
                                                                       edgeHostname_id,
                                                                       secure_by_default,
                                                                       secure_by_default_create_ehn)
        else:
            sys.exit(logger.error('Unable to proceed beyond edge hostname and/or ssl certificate logic'))

        # Update property hostnames and edgehostnames
        property_update_reponse = wrapper_object.updatePropertyHostname(onboard_object.contract_id,
                                                                        onboard_object.group_id,
                                                                        onboard_object.onboard_property_id,
                                                                        json.dumps(edgehostname_list))
        if property_update_reponse.status_code == 200:
            if onboard_object.edge_hostname_mode == 'secure_by_default':
                logger.warning('Secure by default Tokens')
                property_update_response_json = property_update_reponse.json()
                for hostname in property_update_response_json['hostnames']['items']:
                    property_update_response_sbd_token = hostname['certStatus']['validationCname']
                    logger.info(f'{property_update_response_sbd_token}')
            else:
                logger.info(f'Updated public hostname {onboard_object.public_hostnames}, '
                            f"and edge hostname '{onboard_object.edge_hostname}'")
            print()
        else:
            logger.info(onboard_object.edge_hostname_mode)
            logger.error(f'Unable to update public hostname {onboard_object.public_hostnames}, '
                         f"and edge hostname '{onboard_object.edge_hostname}'")
            sys.exit(logger.error(json.dumps(property_update_reponse.json(), indent=4)))

        if onboard_object.use_file:
            # Do Akamai pipeline merge from file
            logger.debug(f'{onboard_object.onboard_default_cpcode=}')
            if utility_object.doCliPipelineMerge(config, onboard_object, create_mode=True, merge_type='pm'):
                logger.info('Merged variables and values via CLI pipeline')

                # Update property with value substituted json
                with open(os.path.join('temp_pm', 'dist', 'test.temp_pm.papi.json')) as updateTemplateFile:
                    updateContent = json.load(updateTemplateFile)
            else:
                sys.exit(logger.error('Unable to merge variables and values '
                                      'Please check temp_pm folder to see '
                                      'if merge output file was created in dist folder '
                                      'and/or devops-log.log for more details'))

        elif onboard_object.use_folder:
            # Do Akamai pipeline merge from folder path
            logger.info('Trying to create property rules json from merging files specified in folder_info')
            if utility_object.doCliPipelineMerge(config, onboard_object, create_mode=False, merge_type='pm'):
                logger.info('Successfully merged variables and values from folder_info')

                # Update property with value substituted json
                with open(os.path.join('temp_pm', 'dist',
                                       f'{onboard_object.env_name}.temp_pm.papi.json')
                         ) as updateTemplateFile:
                    updateContent = json.load(updateTemplateFile)
            else:
                sys.exit(logger.error('Unable to merge variables and values from folder_info. '
                                      'Please check temp_pm folder to see '
                                      'if merge output file was created in dist folder '
                                      'and/or devops-log.log for more details'))

        # Update the json data to include is_secure if its a secure network enabled config
        # Values have already been validated
        logger.debug(f'{onboard_object.secure_network=}')
        if onboard_object.secure_network == 'ENHANCED_TLS':
            updateContent['rules']['options'] = dict()
            updateContent['rules']['options']['is_secure'] = True
        else:
            # This is a non-secure configuration
            updateContent['rules']['options'] = dict()
            updateContent['rules']['options']['is_secure'] = False
        updateContent['comments'] = onboard_object.version_notes
        updateContent['ruleFormat'] = onboard_object.rule_format

        # Update default rule cpcode if necessary (should have already been created by this step)
        if onboard_object.onboard_default_cpcode > 0:
            try:
                # look for the cpcode behavior in the default rule and update it
                for each_behavior in updateContent['rules']['behaviors']:
                    if each_behavior['name'] == 'cpCode':
                        each_behavior['options']['value']['id'] = int(onboard_object.onboard_default_cpcode)
                        logger.info(f'Updated default rule with with cpcode: {onboard_object.onboard_default_cpcode}')
                        break
            except:
                # cp code behavior didn't exist in default rule for some reason so must be error with template and error
                sys.exit(logger.error('Unable to update default rule cpcode'))

        # Update Property Rules
        updateRulesResponse = wrapper_object.updatePropertyRules(onboard_object.contract_id,
                                                                 onboard_object.group_id,
                                                                 onboard_object.onboard_property_id,
                                                                 onboard_object.rule_format,
                                                                 ruletree=json.dumps(updateContent))

        if updateRulesResponse.ok:
            update_json = updateRulesResponse.json()
            if 'errors' in update_json.keys():
                print_json(data=update_json['errors'])
            logger.info('Updated property with rules')
        else:
            logger.error('Unable to update rules for property')
            sys.exit(logger.error(json.dumps(updateRulesResponse.json(), indent=4)))

        # Step 7: Delete the temporary pipeline directory structure for property manager merge
        if os.path.exists('temp_pm'):
            shutil.rmtree('temp_pm')
            try:
                os.remove('devops.log')
            except:
                pass

            try:
                os.remove('devops-logs.log')
            except:
                pass

    def process_ehn(self, onboard_object, wrapper_object, utility_object, cli_mode: str | None = None):
        """
        Function to determine steps on edgehostname and return edge hostname id that will be used in the new onboarded property
        Return edge hostname id should start with ehn_ because that's what subsequent apis calls need
        By time this method is called, onboard_object should already have edge_hostname_id set by validate steps up front
        """
        if onboard_object.edge_hostname_mode == 'use_existing_edgehostname':
            edgeHostnameId = f'ehn_{onboard_object.edge_hostname_id}'
            return edgeHostnameId
        elif onboard_object.edge_hostname_mode == 'new_standard_tls_edgehostname':
            domain_prefix = onboard_object.public_hostnames[0]
            # use property name for all edge hostname when no cpcode is created for all hostnames
            if cli_mode == 'multi-hosts' and not onboard_object.individual_cpcode:
                domain_prefix = onboard_object.property_name
            edgehostname_id = wrapper_object.createEdgehostname(onboard_object.product_id,
                                                                domain_prefix,
                                                                onboard_object.secure_network,
                                                                '',
                                                                onboard_object.contract_id,
                                                                onboard_object.group_id)
            # Response will be either the edgeHostnameId of -1 in case of failure
            return edgehostname_id
        elif onboard_object.edge_hostname_mode == 'new_enhanced_tls_edgehostname':
            if onboard_object.use_existing_enrollment_id > 0:
                domain_prefix = onboard_object.public_hostnames[0]
                if cli_mode == 'multi-hosts':
                    domain_prefix = onboard_object.property_name
                logger.debug(f'{cli_mode=} {onboard_object.use_existing_enrollment_id=} {domain_prefix=}')
                edgehostname_id = wrapper_object.createEdgehostname(onboard_object.product_id,
                                                                    domain_prefix,
                                                                    onboard_object.secure_network,
                                                                    onboard_object.existing_enrollment_id,
                                                                    onboard_object.contract_id,
                                                                    onboard_object.group_id)
                # Response will be either the edgeHostnameId of -1 in case of failure
                return edgehostname_id

        elif onboard_object.edge_hostname_mode == 'secure_by_default':
            edgeHostnameId = f'ehn_{onboard_object.edge_hostname_id}'
            return edgeHostnameId
        else:
            logger.error(f'Unknown edge_hostname_mode: {onboard_object.edge_hostname_mode}')
            return (-1)

    def batch_process_ehn(self, onboard_object, wrapper_object, utility_object):
        """
        Function to determine steps on edgehostname and return edge hostname list that will be used in the new onboarded property
        Return edge hostname ids should start with ehn_ because that's what subsequent apis calls need
        By time this method is called, onboard_object should already have edge_hostname_id set by validate steps up front
        """
        if onboard_object.edge_hostname_mode == 'use_existing_edgehostname':
            edgeHostnameId = f'ehn_{onboard_object.edge_hostname_id}'
            return edgeHostnameId

        elif onboard_object.edge_hostname_mode == 'secure_by_default':
            edgeHostnameId = f'ehn_{onboard_object.edge_hostname_id}'
            return edgeHostnameId

        else:
            logger.error(f'Unknown edge_hostname_mode: {onboard_object.edge_hostname_mode}')
            return (-1)

    def batch_create_update_pm(self, config, onboard_object, wrapper_object, utility_object, propertyDict, cpcodeList):
        """
        Function with multiple goals:
            1. Create a property
            2. Update the property with template rules define
        """
        propertyIds = []
        for propertyName in propertyDict:
            # set property name and hostnames the dict key value
            onboard_object.property_name = propertyName
            onboard_object.public_hostnames = propertyDict[propertyName]['hostnames']
            create_property_response = wrapper_object.createProperty(onboard_object.contract_id,
                                                                    onboard_object.group_id,
                                                                    onboard_object.product_id,
                                                                    onboard_object.property_name)
            if create_property_response.status_code == 201:
                onboard_object.onboard_property_id = create_property_response.json()['propertyLink'].split('?')[0].split('/')[-1]
                propertyIds.append({
                    'propertyId': onboard_object.onboard_property_id,
                    'propertyName': onboard_object.property_name,
                    'hostnames': onboard_object.public_hostnames
                })

                logger.info(f"Created property name: '{onboard_object.property_name}', id: {onboard_object.onboard_property_id}")
            else:
                logger.error('Unable to create property')
                sys.exit(logger.error(json.dumps(create_property_response.json(), indent=4)))

            # Do edgehostname logic
            edgeHostname_id = self.batch_process_ehn(onboard_object, wrapper_object, utility_object)

            secure_by_default = False
            secure_by_default_create_ehn = False
            if onboard_object.edge_hostname_mode == 'secure_by_default':
                secure_by_default = True
            edgehostname_list = wrapper_object.bulkCreateEdgehostnameArray(onboard_object.public_hostnames,
                                                                    propertyDict[propertyName]['edgeHostnames'],
                                                                    secure_by_default,
                                                                    secure_by_default_create_ehn)

            # Update property hostnames and edgehostnames
            property_update_reponse = wrapper_object.updatePropertyHostname(onboard_object.contract_id,
                                                                            onboard_object.group_id,
                                                                            onboard_object.onboard_property_id,
                                                                            json.dumps(edgehostname_list))
            if property_update_reponse.status_code == 200:
                if onboard_object.edge_hostname_mode == 'secure_by_default':
                    logger.warning('Secure by default Tokens')
                    property_update_response_json = property_update_reponse.json()
                    for hostname in property_update_response_json['hostnames']['items']:
                        property_update_response_sbd_token = hostname['certStatus']['validationCname']
                        logger.info(f'{property_update_response_sbd_token}')
                else:
                    logger.info(f'Updated public hostname {onboard_object.public_hostnames}, '
                                f"and edge hostname '{propertyDict[propertyName]['edgeHostnames']}'")
            else:
                logger.info(onboard_object.edge_hostname_mode)
                logger.error(f'Unable to update public hostname {onboard_object.public_hostnames}, '
                            f"and edge hostname '{propertyDict[propertyName]['edgeHostnames']}'")
                sys.exit(logger.error(json.dumps(property_update_reponse.json(), indent=4)))

            # Update the json data to include is_secure if its a secure network enabled config
            # Values have already been validated

            updateContent = propertyDict[propertyName]['ruleTree']

            if onboard_object.secure_network == 'ENHANCED_TLS':
                updateContent['rules']['options'] = dict()
                updateContent['rules']['options']['is_secure'] = True
            else:
                # This is a non-secure configuration
                updateContent['rules']['options'] = dict()
                updateContent['rules']['options']['is_secure'] = False
            updateContent['comments'] = onboard_object.version_notes
            updateContent['ruleFormat'] = onboard_object.rule_format

            try:
                # look for the cpcode and origin behavior in the default rule and update it with origin hostname and custom forwardHostHeader
                first_hostname = propertyDict[propertyName]['hostnames'][0]
                first_origin = propertyDict[propertyName]['origins'][0]
                forward_host_header = propertyDict[propertyName]['forwardHostHeader'][0]
                for each_behavior in updateContent['rules']['behaviors']:
                    if each_behavior['name'] == 'cpCode':
                        each_behavior['options']['value']['id'] = cpcodeList[first_hostname]
                        logger.info(f'Updated default rule with with cpcode name: {first_hostname} id: {cpcodeList[first_hostname]}')
                    if each_behavior['name'] == 'origin':
                        each_behavior['options']['hostname'] = first_origin
                        each_behavior['options']['forwardHostHeader'] = forward_host_header
            except:
                # cp code behavior didn't exist in default rule for some reason so must be error with template and error
                sys.exit(logger.error('Unable to update default rule cpcode and origin hostname'))

            try:
                onboard_object.level_0_rules.insert(0, propertyDict[propertyName]['originRule'])
                updateContent['rules'].update({'children': onboard_object.level_0_rules})
                self.reset_level_0_rules(onboard_object)
            except KeyError:
                updateContent['rules']['children'] = onboard_object.level_0_rules
                self.reset_level_0_rules(onboard_object)

            # Update Property Rules
            updateRulesResponse = wrapper_object.updatePropertyRules(onboard_object.contract_id,
                                                                    onboard_object.group_id,
                                                                    onboard_object.onboard_property_id,
                                                                    onboard_object.rule_format,
                                                                    ruletree=json.dumps(updateContent))

            if updateRulesResponse.status_code == 200:
                logger.info('Updated property with rules')
                print()
            else:
                logger.error('Unable to update rules for property')
                sys.exit(logger.error(json.dumps(updateRulesResponse.json(), indent=4)))

        return (propertyIds)

    def reset_level_0_rules(self, onboard_object):
        home = str(Path.home())
        cli_path = f'{home}/.akamai-cli/src/cli-onboard/templates/akamai_product_templates/behaviors'
        templateFile = onboard_object.source_template_file
        with open(templateFile) as templateHandler:
            templateData = json.load(templateHandler)

        # update template to include origin and cpCode behaviors in default rule if they don't exist
        default_behaviors = templateData['rules']['behaviors']
        onboard_object.level_0_rules = templateData['rules']['children']
