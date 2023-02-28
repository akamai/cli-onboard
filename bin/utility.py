from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from shutil import which
from urllib import parse

from distutils.dir_util import copy_tree
from exceptions import setup_logger
from pyisemail import is_email


logger = setup_logger()
space = ' '
len_lmt = 20


class utility:
    def __init__(self):
        """
        Function to initialize a common status indicator,
        This variable should be updated by every function
        defined in validation modules to indicate validation status.
        This avoid usage of too many IF Conditions.
        """
        # Initialize the variable to true
        self.valid = True

    def installedCommandCheck(self, command_name) -> bool:
        """
        Function to check installation of a command.
        """
        if which(command_name) is None:
            self.valid = False
            logger.error(f'This program needs {command_name} as a pre-requisite')
            if command_name == 'akamai':
                logger.warning('Please install from https://github.com/akamai/cli')
            else:
                logger.error(f'{command_name} is not installed')

        return self.valid

    def executeCommand(self, command) -> bool:
        """
        Function to execute Linux commands
        """
        childprocess = subprocess.Popen(command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT)
        stdout, stderr = childprocess.communicate()
        if 'pipeline' in command and 'akamai [global flags]' in str(stdout):
            self.valid = False
            logger.error('This program needs akamai CLI module property-manager as a pre-requisite')
            logger.warning('Please install from https://github.com/akamai/cli-property-manager')
            logger.warning('or run >> akamai install property-manager')
            return self.valid
        return self.valid

    def checkPermissions(self, session, apicalls_wrapper_object):
        """
        Function to check credentials permissions required
        """
        # This function is not used. Helpful in future if we want to check permissions of credential
        credential_details_response = apicalls_wrapper_object.checkAuthorization(session)
        print(json.dumps(credential_details_response.json(), indent=4))
        if credential_details_response.status_code == 200:
            for scope in credential_details_response.json()['scope'].split(' '):
                o = parse.urlparse(scope)
                apis = o.path.split('/')
                print(f'{apis[3]:35} {apis[5]:10}')
        else:
            pass
        # Default Return, ideally code shouldnt come here
        return self.valid

    def validateSetupSteps(self, onboard_object, wrapper_object, cli_mode='create') -> bool:
        """
        Function to validate the input values of setup.json
        """
        count = 0
        valid_waf = True
        print()
        logger.warning('Validating setup file information. Please wait, may take a few moments')

        # check if property name exists
        if wrapper_object.property_exists(onboard_object.property_name):
            logger.error(f'{onboard_object.property_name:<30}{space:>20}invalid property name; already in use')
            count += 1
        else:
            logger.info(f'{onboard_object.property_name:<30}{space:>20}valid property name')

        # use file or folder but not both
        if onboard_object.use_file and onboard_object.use_folder:
            logger.error('Both use_file and use_folder cannot be set to true')
            count += 1

        if not onboard_object.use_file and not onboard_object.use_folder:
            logger.error('Either use_file or use_folder must be set to true')
            count += 1

        # if create_new_cpcode, must specify a name
        if onboard_object.create_new_cpcode:
            if onboard_object.new_cpcode_name == '':
                logger.error('If create_new_cpcode is true, new_cpcode_name must be specified')
                count += 1

        # if use_file, template file and variable file must exist
        if onboard_object.use_file:
            if onboard_object.source_template_file == '':
                logger.error('If use_file is true, source_template_file must be specified')
                count += 1

            if onboard_object.source_values_file == '':
                logger.error('If use_file is true, source_values_file must be specified')
                count += 1

        # if use_folder, folder path and env_name must be specified
        if onboard_object.use_folder:
            if onboard_object.folder_path == '':
                logger.error('If use_folder is true, folder_path must be specified')
                count += 1

            if onboard_object.env_name == '':
                logger.error('If use_folder is true, env_name must be specified')
                count += 1

        # if activating pm to prod, must active to staging first
        if onboard_object.activate_property_production:
            if onboard_object.activate_property_staging is not True:
                logger.error('Must activate property to STAGING before activating to PRODUCTION')
                count += 1

        # must activate waf config to staging before activating waf to prodution
        if onboard_object.activate_waf_policy_production:
            if not onboard_object.activate_waf_policy_staging:
                logger.error('Must activate WAF policy to STAGING before activating to PRODUCTION.')
                count += 1

        # validate product id available per contract
        product_detail = self.validateProductId(wrapper_object,
                                                onboard_object.contract_id,
                                                onboard_object.product_id)
        if product_detail['Found']:
            logger.info(f'{onboard_object.product_id:<30}{space:>20}valid product_id')
            logger.info(f'{onboard_object.group_id:<30}{space:>20}valid group_id')
            logger.info(f'{onboard_object.contract_id:<30}{space:>20}valid contract_id')
        else:
            logger.error(f'{onboard_object.product_id:<30}{space:>20}invalid product_id')
            logger.error(f'Available valid product_id for contract {onboard_object.contract_id}')
            count += 1
            products_list = sorted(product_detail['products'])
            for p in products_list:
                logger.error(p)

        # network must be either STANDARD_TLS or ENHANCED_TLS
        if onboard_object.secure_network not in ['STANDARD_TLS', 'ENHANCED_TLS']:
            logger.error(f'{onboard_object.secure_network}{space:>20}invalid secure_network')
            count += 1

        # must be one of three valid modes
        valid_modes = ['use_existing_edgehostname', 'new_standard_tls_edgehostname', 'new_enhanced_tls_edgehostname']
        logger.info(f'{onboard_object.edge_hostname_mode:<30}{space:>20}edge hostname mode')
        if onboard_object.edge_hostname_mode not in valid_modes:
            logger.error(f'{onboard_object.edge_hostname_mode:<30}{space:>20}invalid edge_hostname_mode')
            count += 1
            logger.info('valid options: use_existing_edgehostname, new_standard_tls_edgehostname, new_enhanced_tls_edgehostname')
        elif onboard_object.edge_hostname_mode == 'use_existing_edgehostname':
            ehn_id = 0
            if onboard_object.edge_hostname == '':
                logger.error(f'{onboard_object.edge_hostname:<30}{space:>20}missing edge hostname')
                count += 1
            else:
                try:
                    # check to see if specified edge hostname exists
                    ehn_id = self.validateEdgeHostnameExists(wrapper_object, str(onboard_object.edge_hostname))
                    public_hostname_str = ', '.join(onboard_object.public_hostnames)
                    logger.info(f'ehn_{ehn_id:<26}{space:>20}valid edge_hostname_id')
                    logger.info(f'{onboard_object.edge_hostname:<30}{space:>20}valid edge hostname')
                    logger.info(f'{public_hostname_str:<30}{space:>20}valid public hostname')
                    onboard_object.edge_hostname_id = ehn_id
                except:
                    logger.error(f'{onboard_object.edge_hostname:<30}{space:>20}invalid edge hostname')
                    count += 1

        elif onboard_object.edge_hostname_mode == 'new_standard_tls_edgehostname':
            if onboard_object.secure_network != 'STANDARD_TLS':
                logger.error('For new_standard_tls_edgehostname, secure_network must be STANDARD_TLS')
                count += 1
        elif onboard_object.edge_hostname_mode == 'new_enhanced_tls_edgehostname':
            if onboard_object.secure_network != 'ENHANCED_TLS':
                logger.error('For new_enhanced_tls_edgehostname, secure_network must be ENHANCED_TLS')
                count += 1

            if onboard_object.use_existing_enrollment_id is True:
                if onboard_object.create_new_ssl_cert is True:
                    logger.error('Both use_existing_enrollment_id and create_new_ssl_cert cannot be set to true')
                    count += 1
                if onboard_object.existing_enrollment_id == 0:
                    logger.error(f"{'existing_enrollment_id':<30}{space:>20}missing")
                    count += 1
            else:
                logger.error('If new_enhanced_tls_edgehostname, use_existing_enrollment_id must be true')
                count += 1

            if onboard_object.create_new_ssl_cert is True:
                logger.error('Unable to create_new_ssl_cert enrollment, please use existing_enrollment_id instead')
                count += 1

        # validate source and variable file is use_file mode (create only)
        if onboard_object.use_file:
            if self.validateFile('source_template_file', onboard_object.source_template_file):
                if self.validateFile('source_values_file', onboard_object.source_values_file) is False:
                    count += 1
            else:
                count += 1

        # If supposed to something with WAF, can we find waf_config_id for the specifed name
        if cli_mode == 'create':
            if not onboard_object.add_selected_host:
                if onboard_object.update_match_target:
                    logger.error('If update_match_target, add_selected_host must be true')
                    count += 1
                if onboard_object.activate_waf_policy_staging:
                    logger.error('If activating WAF to STAGING, add_selected_host must be true')
                    count += 1
            else:
                if not onboard_object.activate_property_staging:
                    logger.error('If adding WAF selected hosts, property must be activated to STAGING')
                    count += 1

                if not onboard_object.activate_waf_policy_staging:
                    logger.error('If adding WAF selected hosts, property must be activated to STAGING')
                    count += 1

                if onboard_object.update_match_target and onboard_object.activate_waf_policy_staging:
                    config_detail = self.getWafConfigIdByName(wrapper_object, onboard_object.waf_config_name)
                    if config_detail['Found']:
                        onboard_object.onboard_waf_config_id = config_detail['details']['id']
                        onboard_object.onboard_waf_prev_version = config_detail['details']['latestVersion']
                        logger.debug(f'{onboard_object.onboard_waf_config_id} {onboard_object.onboard_waf_config_version}')
                        logger.info(f'{onboard_object.waf_config_name:<30}{space:>20}valid waf_config_name')
                        logger.info(f'{onboard_object.onboard_waf_config_id:<30}{space:>20}found existing onboard_waf_config_id')
                        logger.info(f'{onboard_object.onboard_waf_prev_version:<30}{space:>20}found latest onboard_waf_prev_version')
                    else:
                        count += 1
                        logger.error(f'{onboard_object.waf_config_name:<30}{space:>20}invalid waf_config_name, not found')
                        valid_waf = False

                    if onboard_object.onboard_waf_config_id is not None:
                        logger.debug(f'{onboard_object.onboard_waf_config_id} {onboard_object.onboard_waf_prev_version}')
                        _, policies = wrapper_object.get_waf_policy(onboard_object)
                        _, target_ids = wrapper_object.list_match_targets(onboard_object.onboard_waf_config_id,
                                                                          onboard_object.onboard_waf_prev_version,
                                                                          policies)
                        if onboard_object.waf_match_target_id in target_ids:
                            for k in policies:
                                if onboard_object.waf_match_target_id in policies[k]:
                                    logger.info(f'{policies[k][0]:<30}{space:>20}found existing policy')
                                    logger.info(f'{onboard_object.waf_match_target_id:<30}{space:>20}found waf_match_target_id')
                        else:
                            logger.error(f'{onboard_object.waf_match_target_id:<30}{space:>20}invalid waf_match_target_id')
                            count += 1
                            # we will not auto correct waf_match_target_id
                            # onboard_object.waf_match_target_id = correct_target_id
                            # logger.info(f'{onboard_object.waf_match_target_id:<30}{space:>20}auto correct waf_match_target_id')

        elif cli_mode == 'single_host':
            if onboard_object.edge_hostname and onboard_object.existing_enrollment_id > 0:
                logger.error('Only "use_existing_edge_hostname" or "create_from_existing_enrollment_id" can be used, not both')
                count += 1
            if onboard_object.use_existing_enrollment_id:
                onboard_object.edge_hostname = onboard_object.public_hostnames[0]

            if onboard_object.create_new_security_config:
                config_detail = self.getWafConfigIdByName(wrapper_object, onboard_object.waf_config_name)
                if config_detail['Found']:
                    count += 1
                    onboard_object.onboard_waf_config_id = config_detail['details']['id']
                    onboard_object.onboard_waf_prev_version = config_detail['details']['latestVersion']
                    logger.error(f'{onboard_object.waf_config_name:<30}{space:>20}duplicate waf_config_name already exists')
                    logger.info(f'{onboard_object.onboard_waf_config_id:<30}{space:>20}found existing onboard_waf_config_id')
                    logger.info(f'{onboard_object.onboard_waf_prev_version:<30}{space:>20}found latest onboard_waf_prev_version')
                else:
                    # valid means this waf name doesn't exists
                    logger.info(f'{onboard_object.waf_config_name:<30}{space:>20}new waf_config_name')
                    valid_waf = False

        else:
            pass

        # valid notify_emails is required
        emails = onboard_object.notification_emails
        if len(emails) == 0:
            logger.error('At least one valid notification email is required')
            count += 1
        else:
            for email in emails:
                if not is_email(email):
                    logger.error(f'{email:<30}{space:>20}invalid email address')
                    count += 1

        # maximum active security config per network is 10
        '''
        if onboard_object.activate_waf_policy_staging and valid_waf:
            stg_active_count, prd_active_count = self.get_active_sec_config(wrapper_object)
            msg = 'Deactivate another one, or contact support to raise limits.'
            if stg_active_count >= 10:
                logger.error(f'You reached your maximum allowed number of security configurations on STAGING. {msg}')
                count += 1

            if onboard_object.activate_waf_policy_staging and prd_active_count >= 10:
                logger.error(f'You reached your maximum allowed number of security configurations on PRODUCTION. {msg}')
                count += 1
        '''

        if count == 0:
            self.valid is True
            print()
            logger.warning('Onboarding Delivery Config')
        else:
            sys.exit(logger.error('Please review all errors'))

        return self.valid

    # Validate file
    def validateFile(self, source: str, file_location: str) -> bool:
        # logger.debug(f'{file_location} {type(file_location)} {os.path.exists(file_location)}')
        # logger.debug(f'{file_location} {type(file_location)} {os.path.isfile(file_location)}')
        # logger.debug(os.path.abspath(file_location))
        if os.path.isfile(os.path.abspath(file_location)):
            return True
        else:
            logger.error(f'{source} {file_location}...........missing')
            return False

    def validateProductId(self, wrapper_object, contract_id, product_id) -> dict:
        """
        Function to validate product ids for a contract
        """
        products = dict()
        products['Found'] = False
        products['products'] = []
        get_products_response = wrapper_object.getProductsByContract(contract_id)
        if get_products_response.status_code == 200:
            items = get_products_response.json()['products']['items']
            for each_item in items:
                if 'productId' in each_item:
                    if each_item['productId'] == product_id:
                        products['Found'] = True
                    products['products'].append(each_item['productId'])
                else:
                    pass
        else:
            print(json.dumps(get_products_response.json(), indent=4))
            pass

        return products

    def validateEdgeHostnameExists(self, wrapper_object, edge_hostname) -> bool:
        """
        Function to validate edge hostname
        """
        ehn_id = 0
        edgehostname_response = wrapper_object.checkEdgeHostname(edge_hostname)
        record_name = edge_hostname
        if str(edge_hostname).endswith('edgekey.net'):
            record_name = str(edge_hostname).split('.edgekey.net')[0]
        elif str(edge_hostname).endswith('edgesuite.net'):
            record_name = str(edge_hostname).split('.edgesuite.net')[0]
        if edgehostname_response.status_code == 200:
            ehns = edgehostname_response.json()['edgeHostnames']
            for every_ehn in ehns:
                if every_ehn['recordName'] == record_name:
                    ehn_id = every_ehn['edgeHostnameId']
                    logger.debug(f'{ehn_id:<30}{space:>20}found edgeHostnameId')
                    return ehn_id
                else:
                    pass
        else:
            return 0
        return ehn_id

    def getWafConfigIdByName(self, wrapper_object, config_name) -> dict:
        """
        Function to get WAF config ID and version
        """
        config_detail = dict()
        config_detail['Found'] = False
        waf_configs_response = wrapper_object.getWafConfigurations()
        if waf_configs_response.status_code == 200:
            configurations = waf_configs_response.json()['configurations']
            for each_config in configurations:
                if 'name' in each_config:
                    if each_config['name'] == config_name:
                        config_detail['Found'] = True
                        config_detail['details'] = each_config
        return config_detail

    def doCliPipelineMerge(self, config, onboard_object, create_mode=True, merge_type='pm') -> bool:
        """
        Function to use Akamai property-manager CLI and merge template
        """
        # For PM merge, it will use temp_pm folder
        # For CPS merge, it will use temp_cps folder
        # Delete these folders if they exist to start

        if os.path.exists('temp_pm'):
            shutil.rmtree('temp_pm')
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

        try:
            if create_mode:
                # Build projectInfo contents
                projectInfo = dict(environments=['test'], name=f'temp_{merge_type}')

                # Create pipeline specific folders are files
                if not os.path.exists(os.path.join(f'temp_{merge_type}', 'dist')):
                    os.makedirs(os.path.join(f'temp_{merge_type}', 'dist'))
                if not os.path.exists(os.path.join(f'temp_{merge_type}', 'environments', 'test')):
                    os.makedirs(os.path.join(f'temp_{merge_type}', 'environments', 'test'))
                if not os.path.exists(os.path.join(f'temp_{merge_type}', 'templates')):
                    os.makedirs(os.path.join(f'temp_{merge_type}', 'templates'))

                with open(os.path.join(f'temp_{merge_type}', 'projectInfo.json'), 'w') as projectFile:
                    projectFile.write(json.dumps(projectInfo, indent=4))

                if merge_type == 'pm':
                    templateFile = onboard_object.source_template_file
                    valuesFile = onboard_object.source_values_file
                else:
                    templateFile = onboard_object.ssl_cert_template_file
                    valuesFile = onboard_object.ssl_cert_template_values

                # Create main.json with contents of templateContent
                with open(templateFile) as templateHandler:
                    templateData = json.load(templateHandler)
                with open(os.path.join(f'temp_{merge_type}',
                                        'templates', 'main.json'), 'w') as mainContentHandler:
                    mainContentHandler.write(json.dumps(templateData, indent=4))

                # Create values file for test env from variables
                with open(valuesFile) as valuesHandler, \
                     open(os.path.join(f'temp_{merge_type}',
                                        'environments', 'test', 'variables.json'),
                                        'w') as testValuesHandler:
                    value_json = valuesHandler.read()
                    testValuesHandler.write(value_json)

                # Prepare the variable definitions file contents
                varDefinitions = {}
                varDefinitions['definitions'] = {}
                for eachKey in json.loads(value_json).keys():
                    varDefinitions['definitions'][eachKey] = {}
                    varDefinitions['definitions'][eachKey]['default'] = ''
                    varDefinitions['definitions'][eachKey]['type'] = 'userVariableValue'

                with open(os.path.join(f'temp_{merge_type}',
                                        'environments', 'variableDefinitions.json'),
                                        'w') as definitionHandler:
                    definitionHandler.write(json.dumps(varDefinitions, indent=4))

                # Create envInfo.json else it will error out
                testEnvInfo = dict(name='test')
                with open(os.path.join(f'temp_{merge_type}',
                                       'environments', 'test', 'envInfo.json'),
                                       'w') as testValuesHandler:
                    testValuesHandler.write(json.dumps(testEnvInfo, indent=4))

                # Run pipeline merge
                if merge_type == 'pm':
                    command = ['akamai', 'pipeline', 'merge',
                               '-n', '-p', 'temp_pm', 'test', '--edgerc',
                               config.edgerc, '--section', config.section]
                    command_str = ' '.join(command)
                    logger.debug(f'Success command: {command_str}')
                    child_process = subprocess.Popen(command,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
                    stdout, stderr = child_process.communicate()
                    rtn_code = child_process.returncode
                else:
                    command = ['akamai', 'pipeline', 'merge',
                               '-n', '-p', 'temp_cps', 'test', '--edgerc',
                               config.edgerc, '--section', config.section]
                    command_str = ' '.join(command)
                    logger.debug(f'Success command: {command_str}')
                    child_process = subprocess.Popen(command,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
                    stdout, stderr = child_process.communicate()
                    rtn_code = child_process.returncode
            else:
                # Copy the folder and run pipeline merge
                copy_tree(onboard_object.folder_path, 'temp_pm')

                # Read the projectInfo file to update the name of it
                with open(os.path.join('temp_pm', 'projectInfo.json')) as f:
                    content = json.loads(f.read())
                    content['name'] = 'temp_pm'

                # Write the projectInfo file with updated name
                with open(os.path.join('temp_pm', 'projectInfo.json'), 'w') as f:
                    f.write(json.dumps(content, indent=4))

                command = ['akamai', 'pipeline', 'merge', '-n', '-p', 'temp_pm',
                           onboard_object.env_name, '--edgerc', config.edgerc,
                           '--section', config.section]
                command_str = ' '.join(command)
                logger.debug(f'Success command: {command_str}')
                child_process = subprocess.Popen(command,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
                stdout, stderr = child_process.communicate()
                rtn_code = child_process.returncode

            # If pipeline merge command was not successful, return false
            if rtn_code != 0:
                logger.error('Merging the template file failed')
                logger.info(stdout)
                logger.error(stderr)
                return False

            # Process call worked, return true
            return True

        except Exception as e:
            logger.error(e)
            logger.error('Exception occurred while trying to merge. '
                  'Check devops-logs.log and/or temp_* folder '
                  'to see if files were copied or merged correctly')
            return False
