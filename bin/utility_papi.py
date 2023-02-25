from __future__ import annotations

import json
import os
import shutil
import sys
import time
from time import gmtime
from time import strftime

from exceptions import setup_logger

logger = setup_logger()


class papiFunctions:
    def activateAndPoll(self, wrapper_object, property_name,
                        contract_id, group_id, property_id, version,
                        network, emailList: list, notes):
        """
        Function to activate a property to Akamai Staging or Production network.
        """
        logger.warning(f'Preparing to activate property {property_name} on Akamai {network} network')
        start_time = time.perf_counter()
        act_response = wrapper_object.activateConfiguration(contract_id, group_id, property_id,
                                                            version, network, emailList, notes)
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

    def createNewCpCode(self, onboard_object, wrapper_object,
                        cpcode_name, contract_id, group_id, product_id):
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

    def createAndUpdateProperty(self, config, onboard_object, wrapper_object, utility_object):
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
        edgeHostname_id = self.processEdgeHostnameInput(onboard_object,
                               wrapper_object, utility_object)
        if edgeHostname_id != -1:
            edgehostname_list = wrapper_object.createEdgehostnameArray(onboard_object.public_hostnames, edgeHostname_id)
        else:
            sys.exit(logger.error('Unable to proceed beyond edge hostname and/or ssl certificate logic'))

        # Update property hostnames and edgehostnames
        property_update_reponse = wrapper_object.updatePropertyHostname(onboard_object.contract_id,
                                                                        onboard_object.group_id,
                                                                        onboard_object.onboard_property_id,
                                                                        json.dumps(edgehostname_list))
        if property_update_reponse.status_code == 200:
            logger.info(f'Updated public hostname {onboard_object.public_hostnames}, '
                        f"and edge hostname '{onboard_object.edge_hostname}'")
        else:
            logger.error(f'Unable to update public hostname {onboard_object.public_hostnames}, '
                         f"and edge hostname '{onboard_object.edge_hostname}'")
            sys.exit(logger.error(json.dumps(property_update_reponse.json(), indent=4)))

        if onboard_object.use_file:
            # Do Akamai pipeline merge from file
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
        if onboard_object.secure_network == 'ENHANCED_TLS':
            updateContent['options'] = dict()
            updateContent['options']['is_secure'] = True
        else:
            # This is a non-secure configuration
            updateContent['options'] = dict()
            updateContent['options']['is_secure'] = False
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

        if updateRulesResponse.status_code == 200:
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

    def processEdgeHostnameInput(self, onboard_object, wrapper_object, utility_object):
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
            edgehostname_id = wrapper_object.createEdgehostname(onboard_object.product_id,
                                                                domain_prefix,
                                                                onboard_object.secure_network,
                                                                '',
                                                                '',
                                                                onboard_object.contract_id,
                                                                onboard_object.group_id)
            # Response will be either the edgeHostnameId of -1 in case of failure
            return edgehostname_id
        elif onboard_object.edge_hostname_mode == 'new_enhanced_tls_edgehostname':
            if onboard_object.use_existing_enrollment_id is True:
                domain_prefix = onboard_object.public_hostnames[0]
                edgehostname_id = wrapper_object.createEdgehostname(onboard_object.product_id,
                                                                    domain_prefix,
                                                                    onboard_object.secure_network,
                                                                    onboard_object.existing_enrollment_id,
                                                                    onboard_object.contract_id,
                                                                    onboard_object.group_id)
                # Response will be either the edgeHostnameId of -1 in case of failure
                return edgehostname_id
            elif onboard_object.create_new_ssl_cert is True:

                # Invoke merge
                logger.info('Trying to create ssl cert json from merging files specified in ssl_cert_info')
                if utility_object.doCliPipelineMerge(onboard_object, create_mode=True, merge_type='cps'):
                    logger.info('Successfully merged variables and values from ssl_cert_info')

                    # Read the certificate data file, created from merge
                    with open(os.path.join('temp_cps', 'dist',
                                           'test.temp_cps.papi.json')) as inputFileHandler:
                        file_content = inputFileHandler.read()
                else:
                    sys.exit(logger.error('Unable to merge variables and values from ssl_cert_info. '
                                          'Please check temp_cps folder to see '
                                          'if merge output file was created in dist folder '
                                          'and/or devops-log.log for more details'))

                json_formatted_content = json.loads(file_content)
                updated_json_content = json.dumps(json_formatted_content, indent=2)

                logger.info('Trying to create a new certificate enrollment')
                if onboard_object.contract_id.startswith('ctr_'):
                    contract_id = onboard_object.contract_id.split('_')[1]
                else:
                    contract_id = onboard_object.contract_id
                create_enrollment_response = wrapper_object.create_enrollment(contract_id,
                                                            data=updated_json_content,
                                                            allowDuplicateCn=False)
                if create_enrollment_response.status_code != 200 and \
                    create_enrollment_response.status_code != 202:
                    logger.error(create_enrollment_response.text)
                    logger.error('Unable to create certificate enrollment')
                    return -1
                else:
                    logger.info('Successfully created certificate enrollment')

                    # Delete the pipeline temporary directory used for cps merge only after certificate enrollment is successfully created.
                    # If we didn't get here, leave the temp_cps folder the so user can debug
                    if os.path.exists('temp_cps'):
                        shutil.rmtree('temp_cps')
                        try:
                            os.remove('devops.log')
                        except:
                            pass

                        try:
                            os.remove('devops-logs.log')
                        except:
                            pass

                    if onboard_object.temp_existing_edge_hostname != '':
                        logger.warning('NOTE: New edge hostname cannot be created yet from this new certificate. '
                                      'Please create edge hostname after certificate has been deployed. '
                                      'Associating specified temp_edge_hostname to property for now.')
                        edgehostname_id = 'ehn_' + str(onboard_object.edge_hostname_id)
                        return edgehostname_id
                    else:
                        # This block should never get executed because
                        #    up front validation requires temp edge_hostname
                        #    to be used if create_new_ssl_cert
                        # Akamai APIs do not allow you to create edge hostname right way
                        #    based of the new enrollment that was created. There is some delay
                        # But in the future if Akamai APIs allow you to create new edge hostname
                        #    right away after new enrollment created, hopefully should not need
                        # temp edge hostname workaround
                        domain_prefix = onboard_object.public_hostnames[0]
                        cert_enrollment_id = create_enrollment_response.json()['enrollment'].split('/')[-1]

                        # Create edgehostname
                        edgehostname_id = wrapper_object.createEdgehostname(onboard_object.product_id,
                                                                            domain_prefix,
                                                                            onboard_object.secure_network,
                                                                            cert_enrollment_id,
                                                                            '',
                                                                            onboard_object.contract_id,
                                                                            onboard_object.group_id)

                        # Response will be either the edgeHostnameId of -1 in case of failure
                        return edgehostname_id
        else:
            logger.error(f'Unknown edge_hostname_mode: {onboard_object.edge_hostname_mode}')
            return (-1)
