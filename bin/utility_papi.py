from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from time import gmtime
from time import strftime

import util_emojis as emoji
from exceptions import setup_logger
from model.edge_hostname_mode import EdgeHostnameMode
from poll import pollActivation
from rich import print_json

logger = setup_logger()
space = ' '


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
            logger.warning(f'Preparing to activate property {activation['propertyName']} on Akamai {network} network')
            act_response = wrapper_object.activateConfiguration(contract_id, group_id, activation['propertyId'],
                                                                version, network, emailList, notes)
            if act_response.status_code == 201:
                activation_status = False
                activation_id = act_response.json()['activationLink'].split('?')[0].split('/')[-1]
                propertyDict[i]['activationId'] = activation_id
                logger.warning(f'Activation started for {activation['propertyName']} on Akamai {network} network')

            else:
                logger.error(json.dumps(act_response.json(), indent=4))
                propertyDict[i]['activationId'] = 0

        all_properties_active, activationDict = pollActivation(propertyDict, wrapper_object, contract_id, group_id, network)
        failed_activations = (list(filter(lambda x: x['activationStatus'][network] not in ['ACTIVE'], activationDict)))
        successful_activations = (list(filter(lambda x: x['activationStatus'][network] in ['ACTIVE'], activationDict)))
        success_onboarded_hostnames = (list(map(lambda x: x['hostnames'], successful_activations)))
        success_onboarded_hostnames = [item for sublist in success_onboarded_hostnames for item in sublist]

        return (all_properties_active, success_onboarded_hostnames, failed_activations, activationDict)

    def _sanitize_cpcode_name(self, cpcode_name: str) -> str:
        special_characters = ['"', '^', '_', ',', '#', '%', "'", '\\']
        for character in special_characters:
            cpcode_name = cpcode_name.replace(character, '.')
        return cpcode_name

    def _unwrap_cpcode_response(self, response, action: str, error_message: str) -> dict:
        """
        Shared shape behind create_new_cpcode and search_for_cpcode: unwrap a
        PAPI response's JSON body, exiting with `error_message` on any non-2xx
        or non-JSON response. The caller decides what a *successful* body
        means (e.g. search's "no matches" is a legitimate outcome, not an
        error, so it's handled by the caller, not here).
        """
        try:
            resp_body = response.json()
        except Exception:
            resp_body = None

        if response.ok and resp_body:
            logger.debug(json.dumps(resp_body, indent=4))
            return resp_body

        if resp_body:
            logger.debug(json.dumps(resp_body, indent=4))
        else:
            logger.debug(f'cpcode {action} response status={response.status_code} body={response.text[:500]}')
        sys.exit(logger.error(error_message))

    def _log_cpcode_result(self, message_with_path, message_without_path, path):
        """
        Shared shape behind create_new_cpcode and search_for_cpcode: both log
        one result line, with a trailing path suffix if the caller passed one
        and a fallback message otherwise.
        """
        logger.info(message_with_path if path else message_without_path)

    def create_new_cpcode(self, onboard_object, wrapper_object,
                        cpcode_name, contract_id, group_id, product_id, path=None) -> int:
        """
        Function to create new cpcode
        """
        cpcode_name = self._sanitize_cpcode_name(cpcode_name)
        create_cpcode_response = wrapper_object.createCpcode(contract_id,
                                                             group_id, product_id, cpcode_name)
        resp_body = self._unwrap_cpcode_response(create_cpcode_response, 'create', 'Unable to create new cpcode')

        new_cpcode = resp_body['cpcodeLink'].split('?')[0].split('/')[-1].replace('cpc_', '')
        onboard_object.onboard_default_cpcode = int(new_cpcode)
        # PAPI returns 201 when it actually creates a cpcode, and 200 when a
        # cpcode with this name already exists and it's just handing back that one
        cpcode_verb = 'New' if create_cpcode_response.status_code == 201 else 'Reused existing'
        self._log_cpcode_result(
            f'{space}{space}{emoji.point_right} {cpcode_verb} cpcode: {new_cpcode:<28}{path}',
            f'{space}{space}{emoji.point_right} {cpcode_verb} cpcode: {new_cpcode:<28}{cpcode_name}',
            path,
        )
        return int(new_cpcode)

    def search_for_cpcode(self, onboard_object, wrapper_object,
                        cpcode_name, contract_id, group_id, product_id, path=None) -> int:
        """
        Function to search for existing cpcode
        """
        cpcode_name = self._sanitize_cpcode_name(cpcode_name)
        logger.info(f"searching for existing cpcode: '{cpcode_name}'")
        search_cpcode_response = wrapper_object.searchCpcode(contract_id,
                                                             group_id, product_id, cpcode_name)
        resp_body = self._unwrap_cpcode_response(search_cpcode_response, 'search', 'Unable to search for existing cpcode')

        existing_cpcode = 0
        # Without a productId filter, match cpcodeName exactly rather than
        # blindly trusting cpcodes[0], since more than one product/group
        # combination can share the same name in the unfiltered results
        matches = [c for c in resp_body['cpcodes'] if c['cpcodeName'].casefold() == cpcode_name.casefold()]
        if len(matches) > 1:
            logger.warning(f'{len(matches)} existing cpcodes named "{cpcode_name}" found, using the first match')
        if matches:
            existing_cpcode = matches[0]['cpcodeId']
            onboard_object.onboard_default_cpcode = int(existing_cpcode)
            self._log_cpcode_result(
                f'{space}{space}{emoji.point_right} Existing cpcode found: {existing_cpcode} for path: {path}',
                f'{space}{space}{emoji.point_right} Existing cpcode found: {existing_cpcode}',
                path,
            )
        return int(existing_cpcode)

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
            if onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
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
            if onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
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
        def _use_existing_edgehostname():
            return f'ehn_{onboard_object.edge_hostname_id}'

        def _new_standard_tls_edgehostname():
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

        def _new_enhanced_tls_edgehostname():
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
            return None

        def _secure_by_default():
            return f'ehn_{onboard_object.edge_hostname_id}'

        handlers = {
            EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME: _use_existing_edgehostname,
            EdgeHostnameMode.NEW_STANDARD_TLS_EDGEHOSTNAME: _new_standard_tls_edgehostname,
            EdgeHostnameMode.NEW_ENHANCED_TLS_EDGEHOSTNAME: _new_enhanced_tls_edgehostname,
            EdgeHostnameMode.SECURE_BY_DEFAULT: _secure_by_default,
        }
        handler = handlers.get(onboard_object.edge_hostname_mode)
        if handler is None:
            logger.error(f'Unknown edge_hostname_mode: {onboard_object.edge_hostname_mode}')
            return (-1)
        return handler()

    def batch_process_ehn(self, onboard_object, wrapper_object, utility_object):
        """
        Function to determine steps on edgehostname and return edge hostname list that will be used in the new onboarded property
        Return edge hostname ids should start with ehn_ because that's what subsequent apis calls need
        By time this method is called, onboard_object should already have edge_hostname_id set by validate steps up front
        """
        if onboard_object.edge_hostname_mode in (EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME, EdgeHostnameMode.SECURE_BY_DEFAULT):
            return f'ehn_{onboard_object.edge_hostname_id}'

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
            if onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
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
                if onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
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

    def batch_create_update_pm_convert(self, config,
                                       onboard_object,
                                       papi,
                                       propertyDict,
                                       dryrun: bool | None = False) -> list:
        """
        Function with multiple goals:
            1. Create a property
            2. Create shared certed hostname (akamized.net)
            3. Prep public hostname
            4. Update property public hostname
            5. Update the property with template rules define
        """
        propertyIds = []
        skip_property = []
        custom_solution = False

        for propertyName in propertyDict:
            propertyDict[propertyName]['error_flags'] = []
            # set property name and hostnames the dict key value
            '''
            CHECK IF HOSTNAME ALREADY ON EXISTSING PROPERTY
            '''
            hostnames_to_onboard = []
            onboard_object.public_hostname = propertyDict[propertyName]['hostnames']
            # Check if property name already exists (single API call per property
            # instead of per-hostname search_property_by_hostname calls)
            property_exists = papi.property_exists(propertyName)
            if property_exists:
                logger.warning(f"{emoji.pass_green} Property already exists: '{propertyName}'")
                print()
                print('_' * 120)
                print()
                logger.warning('Do you want to skip this property? (yes/no)')
                print('_' * 120)
                string = str(input())
                skip_hostname_variables = ['yes', 'y', 'Y', 'YES', 'Yes']
                if string in skip_hostname_variables:
                    logger.warning(f'{emoji.ok_hand} Skipping property')
                    print()
                    continue
            hostnames_to_onboard = list(onboard_object.public_hostname)

            onboard_object.property_name = propertyName
            # 1. Create a property
            logger.debug(f'{propertyName=} {onboard_object.group_id=}')
            if onboard_object.group_id is None:
                logger.debug(f"{propertyDict[propertyName].keys()=}")
                onboard_object.group_id = propertyDict[propertyName]['group']
                custom_solution = True

            if not dryrun:
                create_resp = papi.createProperty(onboard_object.contract_id,
                                                  onboard_object.group_id,
                                                  propertyDict[propertyName]['product'],
                                                  onboard_object.property_name)
                if create_resp.ok:
                    onboard_object.onboard_property_id = create_resp.json()['propertyLink'].split('?')[0].split('/')[-1]
                    onboard_object.public_hostname = hostnames_to_onboard
                    propertyIds.append({
                        'propertyId': onboard_object.onboard_property_id,
                        'propertyName': onboard_object.property_name,
                        'hostnames': onboard_object.public_hostnames
                    })

                    logger.warning(f'{emoji.pass_green} Created property id: {onboard_object.onboard_property_id}, property name: {onboard_object.property_name}')
                elif create_resp.status_code == 429:
                    logger.critical('Hit rate limit when creating property, skipping property for now')
                    propertyDict[propertyName]['error_flags'].append('rate_limit_create')
                    skip_property.append(onboard_object.onboard_property_id)
                    logger.critical(f'{space}{emoji.stop}{emoji.stop} Property requires manual intervention! {space}{emoji.stop}{emoji.stop}')
                    logger.info(f'{space}{emoji.pencil} Unable to create property due to rate limit')
                    continue

                else:
                    # branch
                    logger.debug(create_resp.json().keys())
                    print_json(data=create_resp.json())
                    logger.critical('Unable to create property')

                    try:
                        errors = [err for err in create_resp.json()['errors']]
                    except:
                        errors = ['unknown error during create']

                    propertyDict[propertyName]['error_flags'].extend(errors)
                    skip_property.append(onboard_object.onboard_property_id)
                    logger.critical(f'{space}{emoji.stop}{emoji.stop} Property requires manual intervention! {space}{emoji.stop}{emoji.stop}')
                    logger.info(f'{space}{emoji.pencil} Unable to create property')
                    continue

                # 2. Create/assign edge hostnames
                onboard_object.public_hostnames = propertyDict[propertyName]['hostnames']
                logger.debug(onboard_object.public_hostnames)
                logger.debug(propertyDict[propertyName]['edgeHostnames'])

                if onboard_object.edge_hostname_mode == EdgeHostnameMode.CREATE_CPS_EDGEHOSTNAME:
                    # --cert-mode CPS --enrollment-id N: create one EHN per property
                    domain_prefix = propertyName
                    domain_suffix = 'edgekey.net' if onboard_object.secure_network == 'ENHANCED_TLS' else 'edgesuite.net'
                    cname_to = f'{domain_prefix}.{domain_suffix}'

                    ehn_id = papi.findExistingEdgeHostname(domain_prefix, domain_suffix)
                    if ehn_id is None:
                        ehn_id = papi.createEdgehostname(
                            propertyDict[propertyName]['product'], domain_prefix,
                            onboard_object.secure_network, onboard_object.enrollment_id,
                            onboard_object.contract_id, onboard_object.group_id)
                        if ehn_id == -1:
                            propertyDict[propertyName]['error_flags'].append('ehn_create_failed')
                            skip_property.append(onboard_object.onboard_property_id)
                            logger.critical(f'{space}{emoji.stop}{emoji.stop} Failed to create edge hostname {cname_to}')
                            continue
                        logger.info(f'{space}{emoji.blue_globe} Created CPS_MANAGED EHN: {cname_to} (id: {ehn_id})')
                    else:
                        logger.info(f'{space}{emoji.blue_globe} Reusing CPS_MANAGED EHN: {cname_to} (id: {ehn_id})')

                    edgehostname_list = papi.buildCpsManagedHostnameArray(
                        onboard_object.public_hostnames, cname_to, edge_hostname_id=ehn_id)

                elif onboard_object.edge_hostname_mode == EdgeHostnameMode.CPS_PLACEHOLDER:
                    # --cert-mode CPS, no enrollment-id, no use-existing: create a real placeholder EHN
                    account_id = onboard_object.ASK.split(':')[0] if onboard_object.ASK else 'unknown'
                    domain_prefix = f'{account_id}-placeholder'
                    domain_suffix = 'edgekey.net' if onboard_object.secure_network == 'ENHANCED_TLS' else 'edgesuite.net'
                    cname_to = f'{domain_prefix}.{domain_suffix}'

                    ehn_id = papi.findExistingEdgeHostname(domain_prefix, domain_suffix)
                    if ehn_id is None:
                        # Create a real STANDARD_TLS EHN (no enrollment needed)
                        ehn_id = papi.createEdgehostname(
                            propertyDict[propertyName]['product'], domain_prefix,
                            onboard_object.secure_network, '',
                            onboard_object.contract_id, onboard_object.group_id)
                        if ehn_id == -1:
                            propertyDict[propertyName]['error_flags'].append('placeholder_ehn_create_failed')
                            skip_property.append(onboard_object.onboard_property_id)
                            logger.critical(f'{space}{emoji.stop}{emoji.stop} Failed to create placeholder edge hostname {cname_to}')
                            continue
                        logger.info(f'{space}{emoji.construction} Created placeholder EHN: {cname_to} (id: {ehn_id})')
                    else:
                        logger.info(f'{space}{emoji.construction} Reusing placeholder EHN: {cname_to} (id: {ehn_id})')

                    edgehostname_list = papi.buildCpsManagedHostnameArray(
                        onboard_object.public_hostnames, cname_to, edge_hostname_id=ehn_id)

                elif onboard_object.edge_hostname_mode == EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME and onboard_object.use_existing_ehn != 'CSV':
                    # --use-existing-edgehostname <ehn-value>: single EHN for all hostnames
                    cname_to = onboard_object.use_existing_ehn
                    cert_prov_type = 'CPS_MANAGED' if onboard_object.cert_mode == 'CPS' else 'DEFAULT'

                    # Look up EHN ID via HAPI
                    parts = cname_to.rsplit('.', 2)
                    domain_prefix = '.'.join(parts[:-2]) if len(parts) > 2 else parts[0]
                    domain_suffix = '.'.join(parts[-2:]) if len(parts) >= 2 else ''
                    ehn_id = papi.findExistingEdgeHostname(domain_prefix, domain_suffix)

                    edgehostname_list = []
                    for hostname in onboard_object.public_hostnames:
                        entry = {'cnameType': 'EDGE_HOSTNAME',
                                 'cnameFrom': hostname,
                                 'cnameTo': cname_to,
                                 'certProvisioningType': cert_prov_type}
                        if ehn_id is not None:
                            entry['edgeHostnameId'] = ehn_id
                        edgehostname_list.append(entry)
                    logger.info(f'{space}{emoji.blue_globe} Using existing EHN: {cname_to} (cert: {cert_prov_type})')

                else:
                    # Existing logic: SBD or use-existing from CSV
                    try:
                        x = propertyDict[propertyName]['secureNetwork']
                    except:
                        x = 0

                    if x == 0:
                        secure_by_default = False
                        secure_by_default_create_ehn = False
                        if onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
                            secure_by_default = True
                        edgehostname_list = papi.bulkCreateEdgehostnameArray(onboard_object.public_hostnames,
                                                                             propertyDict[propertyName]['edgeHostnames'],
                                                                             secure_by_default,
                                                                             secure_by_default_create_ehn)
                    else:
                        shared_ehn_list, all_edgehostnames = papi.create_edge_hostname(onboard_object.public_hostnames,
                                                                                       propertyDict[propertyName]['product'],
                                                                                       onboard_object.contract_id,
                                                                                       onboard_object.group_id,
                                                                                       onboard_object.secure_network,
                                                                                       propertyDict[propertyName]['secureNetwork'],
                                                                                       option=onboard_object.ehn_option)
                        shared_ehns = []
                        for ehn in shared_ehn_list:
                            for key, value in ehn.items():
                                try:
                                    ehn_id = value['edgeHostnameId']
                                    if ehn_id != -1:
                                        shared_ehns.append(
                                            papi.get_edge_hostname(ehn_id,
                                                                   onboard_object.contract_id,
                                                                   onboard_object.group_id))
                                except KeyError:
                                    logger.error(print_json(data=ehn))
                        if len(shared_ehns) > 0:
                            shared = [x['edgeHostnameDomain'] for x in shared_ehns]
                            if len(shared) > 0:
                                logger.debug('create shared cert edge hostname')
                                logger.debug(shared)
                                for i, each_share in enumerate(shared, start=1):
                                    logger.info(f'{space}{emoji.blue_globe} akamaized: {i:>3}. {each_share}')

                        # 3. Prep public hostname
                        edgehostname_list = [x for x in all_edgehostnames if x['certProvisioningType'] in ('DEFAULT', 'CPS_MANAGED')]
                        logger.debug('edge hostname to be created with property manager activation')

                        for edge in edgehostname_list:
                            del edge['productId']
                            del edge['ipVersionBehavior']
                            edge_copy = edge.copy()
                            for key, value in edge_copy.items():
                                if key == 'domainPrefix':
                                    edge['cnameFrom'] = edge.pop('domainPrefix')
                                if key == 'domainSuffix':
                                    edge['cnameTo'] = edge.pop('domainSuffix')
                                    edge['cnameTo'] = f"{edge['cnameFrom']}.{edge['cnameTo']}"
                        logger.debug('rename dictionary key')

                # 4. Update the property public hostname
                hostname_resp = papi.updatePropertyHostname(onboard_object.contract_id,
                                                            onboard_object.group_id,
                                                            onboard_object.onboard_property_id,
                                                            json.dumps(edgehostname_list))
                if hostname_resp.ok:
                    update_resp = hostname_resp.json()
                    if onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
                        for hostname in update_resp['hostnames']['items']:
                            property_update_response_sbd_token = hostname['certStatus']['validationCname']
                            logger.info(f'{space}{emoji.home} hostname:    {hostname['cnameFrom']}')  # noqa
                            logger.info(f'{space}{emoji.key} sbd_record:  {property_update_response_sbd_token['hostname']}')   # noqa
                            logger.info(f'{space}{emoji.dart} sbd_target:  {property_update_response_sbd_token['target']}')   # noqa
                            print()
                    else:
                        logger.info(f'Updated public hostname {onboard_object.public_hostnames}')
                        logger.info(f"Updated edge hostname   {sorted(list(set(propertyDict[propertyName]['edgeHostnames'])))}")
                else:
                    # branch
                    try:
                        resp_body = hostname_resp.json()
                        errors = [err for err in resp_body.get('errors', [])]
                    except Exception:
                        resp_body = None
                        errors = ['unknown error during property update']

                    logger.debug(f'Hostname update failed with status {hostname_resp.status_code}')
                    if resp_body:
                        logger.debug(json.dumps(resp_body, indent=2))
                    else:
                        logger.debug(hostname_resp.text[:500])
                    logger.debug(f'edgehostname_list sent: {json.dumps(edgehostname_list, indent=2)}')

                    propertyDict[propertyName]['error_flags'].extend(errors)
                    skip_property.append(onboard_object.onboard_property_id)
                    logger.critical(f'{space}{emoji.stop}{emoji.stop} Property requires manual intervention! {space}{emoji.stop}{emoji.stop}')
                    logger.info(f'{space}{emoji.pencil} Unable to update public hostname {onboard_object.public_hostnames}, '
                                f"and edge hostname '{propertyDict[propertyName]['edgeHostnames']}'")
                    print()
                    continue

                # 5. Update the property with template rules define
                updateContent = propertyDict[propertyName]['ruleTree']

                if onboard_object.secure_network == 'ENHANCED_TLS':
                    updateContent['rules']['options'] = dict()
                    updateContent['rules']['options']['is_secure'] = True
                else:
                    # This is a non-secure configuration
                    updateContent['rules']['options'] = dict()
                    updateContent['rules']['options']['is_secure'] = False
                updateContent['comments'] = propertyDict[propertyName]['comments']
                updateContent['ruleFormat'] = onboard_object.rule_format

                comment_flags = ['secret key', 'non-converted', 'contains stage incompatible behaviors and criteria']
                for comment in comment_flags:
                    if comment in updateContent['comments']:
                        logger.critical(f'{space}{emoji.stop}{emoji.stop} Property requires manual intervention! {space}{emoji.stop}{emoji.stop}')
                        logger.info(f'{space}{emoji.pencil} Comment: {updateContent['comments']}')
                        propertyDict[propertyName]['error_flags'].append(comment)
                        skip_property.append(onboard_object.onboard_property_id)
                        continue

                rules_resp = papi.updatePropertyRules(onboard_object.contract_id,
                                                      onboard_object.group_id,
                                                      onboard_object.onboard_property_id,
                                                      onboard_object.rule_format,
                                                      ruletree=json.dumps(updateContent))
                if not rules_resp.ok:
                    logger.error(f'{rules_resp} {rules_resp.text}')
                    print(rules_resp.headers)
                errors = []
                if not rules_resp.ok:
                    try:
                        errors = [err['detail'] for err in rules_resp.json()['errors']]
                    except KeyError:
                        errors = ['unknown error during property rule update']
                    unique_error = list(set(errors))
                    print(*unique_error, sep='\n')
                    propertyDict[propertyName]['error_flags'].extend(list(set(errors)))
                    skip_property.append(onboard_object.onboard_property_id)
                    logger.debug(propertyDict[propertyName]['error_flags'])
                    logger.critical(f'{space}{emoji.stop}{emoji.stop} Property requires manual intervention! {space}{emoji.stop}{emoji.stop}')
                    logger.info(f'{space}{emoji.pencil} Unable to update rules')
                    print()

            # reset
            if custom_solution:
                onboard_object.group_id = None

        return (propertyIds, skip_property)

    def reset_level_0_rules(self, onboard_object):
        home = str(Path.home())
        cli_path = f'{home}/.akamai-cli/src/cli-onboard/templates/akamai_product_templates/behaviors'
        templateFile = onboard_object.source_template_file
        with open(templateFile) as templateHandler:
            templateData = json.load(templateHandler)

        # update template to include origin and cpCode behaviors in default rule if they don't exist
        default_behaviors = templateData['rules']['behaviors']
        onboard_object.level_0_rules = templateData['rules']['children']

    def get_acme_challenges(self, config, onboard_object, wrapper_object):
        """
        Function to get all all acme challenges:
        """
        # CHUNK FOR >1000 ACME CHALLENGES
        chunk_size = 999
        chunks = [onboard_object.unique_hostnames[i:i + chunk_size] for i in range(0, len(onboard_object.unique_hostnames), chunk_size)]
        for i, chunk in enumerate(chunks):
            logger.debug(chunk)
            onboard_object.acme_challenges.extend(wrapper_object.get_acme_tokens(chunk))

    def get_level1_rulename(self, current_rule: dict) -> list:
        rule_name = [rule['name'] for rule in current_rule['rules']['children']]
        return rule_name

    def inject_cpcode_behavior(self, single_rule: dict, cpcode_value: int) -> dict:
        """
        inject cpcode behavior to a single rule
        """
        cpcode_behavior = self.get_behavior_template('cpCode')
        cpcode_behavior['options']['value']['id'] = cpcode_value
        original_behavior = single_rule['behaviors']
        found = False
        for i, behave in enumerate(original_behavior):
            if behave['name'] == 'cpCode':
                original_behavior[i] = cpcode_behavior
                found = True
        if not found:
            original_behavior.insert(0, cpcode_behavior)
        single_rule['behaviors'] = original_behavior
        return single_rule

    def get_path_value(self, single_rule: dict) -> str:
        if len(single_rule['criteria']) > 0:
            for each_criteria in single_rule['criteria']:
                if each_criteria['name'] == 'path':
                    return each_criteria['options']['values'][0]
        return None

    def get_level1_rule(self, current_rule: dict, rulename: str) -> list:
        for member in current_rule['rules']['children']:
            if member['name'] == rulename:
                return member

    def get_level1_rule_count(self, current_rule: dict) -> list:
        rule_name = [rule['name'] for rule in current_rule['rules']['children']]
        return len(rule_name)

    def rebuild_level1_ruletree(self, ruletree_template: dict, behavior: str) -> dict:
        level1_rulename = self.get_level1_rulename(ruletree_template)
        all_child_rules = []
        template = self.get_behavior_template_location(behavior)
        for each_rulename in level1_rulename:
            single_rule_json = self.get_level1_rule(ruletree_template, each_rulename)
            path = self.get_path_value(single_rule_json)
            if path:
                # cpcode = # create cpcode
                update_single_rule_json = self.inject_cpcode_behavior(single_rule_json, 1235, template)
                all_child_rules.append(update_single_rule_json)
        ruletree_template['children'] = all_child_rules
        return ruletree_template

    def get_behavior_template(self, behavior_name: str):
        home = str(Path.home())
        cli_path = f'{home}/.akamai-cli/src/cli-onboard/templates/akamai_product_templates/behaviors'

        if not Path(cli_path).exists():
            cli_path = 'templates/akamai_product_templates/behaviors'
        template_file = f'{cli_path}/{behavior_name}.json'
        behavior_json = {}
        try:
            with open(template_file) as file:
                behavior_json = json.load(file)
        except FileNotFoundError as e:
            print(e)
        return behavior_json

    def get_behavior_template_location(self, behavior_name: str):
        home = str(Path.home())
        cli_path = f'{home}/.akamai-cli/src/cli-onboard/templates/akamai_product_templates/behaviors'
        if not Path(cli_path).exists():
            cli_path = 'templates/akamai_product_templates/behaviors'
        template_file = f'{cli_path}/{behavior_name}.json'
        if Path(template_file).exists():
            return template_file
        else:
            return ''

    def get_active_staging_version(self, versions: list):
        for version in versions:
            if version['stagingStatus'] == 'ACTIVE':
                version = version['propertyVersion']
                return version

    def get_active_production_version(self, versions: list):
        for version in versions:
            if version['productionStatus'] == 'ACTIVE':
                version = version['propertyVersion']
                return version
