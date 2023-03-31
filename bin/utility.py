from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from shutil import which
from time import gmtime
from time import strftime
from urllib import parse

from cerberus import Validator
from distutils.dir_util import copy_tree
from exceptions import get_cli_root_directory
from exceptions import setup_logger
from pyisemail import is_email

logger = setup_logger()
root = get_cli_root_directory()

space = ' '
column_width = 50


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
        self.validate_prerequisite_cli()
        self.start_time = time.perf_counter()

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

    def validateSetupStepsCSV(self, onboard_object, wrapper_object, cli_mode='batch-create') -> bool:
        """
        Function to validate the input values of setup.json when in batch-create mode
        """

        count = 0
        valid_waf = True
        print()
        logger.warning('Validating setup file information. Please wait, may take a few moments')

        # check if csv is valid
        if not onboard_object.valid_csv:
            logger.error(f'{onboard_object.csv_loc:<30}{space:>20}invalid csv; check above validation errors')
            count += 1

        # check if property name exists
        for property in onboard_object.property_name:
            width = column_width - len(property)
            msg = f'{property}{space:>{width}}'
            if wrapper_object.property_exists(property):
                logger.error(f'{msg}invalid property name; already in use')
                count += 1
            else:
                logger.info(f'{msg}valid property name')

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
            logger.info(f'{onboard_object.product_id}{space:>{column_width - len(onboard_object.product_id)}}valid product_id')
            logger.info(f'{onboard_object.group_id}{space:>{column_width - len(onboard_object.group_id)}}valid group_id')
            logger.info(f'{onboard_object.contract_id}{space:>{column_width - len(onboard_object.contract_id)}}valid contract_id')
        else:
            logger.error(f'{onboard_object.product_id}{space:>{column_width - len(onboard_object.product_id)}}invalid product_id')
            logger.warning(f'Available valid product_id for contract {onboard_object.contract_id}')
            count += 1
            products_list = sorted(product_detail['products'])
            for p in products_list:
                logger.warning(p)

        # network must be either STANDARD_TLS or ENHANCED_TLS
        if onboard_object.secure_network not in ['STANDARD_TLS', 'ENHANCED_TLS']:
            logger.error(f'{onboard_object.secure_network}{space:>{column_width - len(onboard_object.secure_network)}}invalid secure_network')
            count += 1

        # ensure hostname doesn't contain special characters and is of valid length
        reg = re.compile(r'[^\.\-a-zA-Z0-9]')
        for hostname in onboard_object.public_hostnames:
            if re.search(reg, hostname):
                logger.error(f'{hostname} contains invalid character. Only alphanumeric (a-z, A-Z, 0-9) and hyphen (-) characters are supported.')
                count += 1
            if len(hostname) > 60 and len(hostname) < 4:
                logger.error(f'{hostname} is invalid length. Hostname length must be between 4-60 characters')
                count += 1
            if (hostname[0] == '-') or (hostname[-1] == '-'):
                logger.error(f'{hostname} cannot begin or end with a hyphen.')
                count += 1

        # must be one of three valid modes
        edgeHostnameList = onboard_object.edge_hostname_list
        valid_modes = ['use_existing_edgehostname', 'secure_by_default']
        logger.info(f'{onboard_object.edge_hostname_mode}{space:>{column_width - len(onboard_object.edge_hostname_mode)}}edge hostname mode')
        if onboard_object.edge_hostname_mode == 'use_existing_edgehostname':
            ehn_id = 0
            # check to see if specified edge hostname exists
            for edgeHostname in edgeHostnameList:
                ehn_id = self.validateEdgeHostnameExists(wrapper_object, str(edgeHostname))
                public_hostname_str = ', '.join(onboard_object.public_hostnames)
                if ehn_id != 0:
                    logger.info(f'{edgeHostname}{space:>{column_width - len(edgeHostname)}}valid edge hostname (ehn_{ehn_id})')
                # logger.info(f'{public_hostname_str:<30}{space:>20}valid public hostname')
                    # onboard_object.edge_hostname_id = ehn_id
                else:
                    logger.error(f'{edgeHostname}{space:>{column_width - len(edgeHostname)}}invalid edge hostname')
                    count += 1
        elif onboard_object.edge_hostname_mode == 'secure_by_default':
            ehn_id = 0
            for i, edgeHostname in enumerate(edgeHostnameList):
                # check to see if specified edge hostname exists
                ehn_id = self.validateEdgeHostnameExists(wrapper_object, str(edgeHostname))
                public_hostname_str = ', '.join(onboard_object.public_hostnames)
                if ehn_id != 0:
                    logger.info(f'{edgeHostname}{space:>{column_width - len(edgeHostname)}}valid edge hostname (ehn_{ehn_id})')
                    # logger.info(f'{public_hostname_str:<30}{space:>20}valid public hostname')
                    # onboard_object.edge_hostname_id = ehn_id
                else:
                    if edgeHostname.endswith(('edgekey.net', 'edgesuite.net')):
                        logger.warning(f'{edgeHostname}{space:>{column_width - len(edgeHostname)}}does not exist, will be created upon property activation')
                    else:
                        logger.warning(f'{edgeHostname}{space:>{column_width - len(edgeHostname)}}does not end with edgekey.net or edgesuite.net, using {hostname}.{onboard_object.ehn_suffix}')
                        # no need to error out if ehn doesn't exist for SBD - ehn will get created with property activation
                        # count += 1

        # If supposed to something with WAF, can we find waf_config_id for the specifed name
        if cli_mode == 'batch-create':
            if not onboard_object.add_selected_host:
                if onboard_object.activate_waf_policy_staging and onboard_object.waf_config_name is None:
                    logger.error('If activating WAF to STAGING, waf-config must be provided')
                    count += 1
            else:
                if not onboard_object.activate_property_staging:
                    logger.error('to activate security config, you must activate delivery config on STAGING network')
                    count += 1

                if onboard_object.activate_waf_policy_staging:
                    config_detail = self.getWafConfigIdByName(wrapper_object, onboard_object.waf_config_name)
                    if config_detail['Found']:
                        onboard_object.onboard_waf_config_id = config_detail['details']['id']
                        onboard_object.onboard_waf_prev_version = config_detail['details']['latestVersion']
                        logger.debug(f'{onboard_object.onboard_waf_config_id} {onboard_object.onboard_waf_config_version}')
                        logger.info(f'{onboard_object.waf_config_name}{space:>{column_width - len(onboard_object.waf_config_name)}}valid waf_config_name')
                        logger.info(f'{onboard_object.onboard_waf_config_id}{space:>{column_width - len(str(onboard_object.onboard_waf_config_id))}}found existing onboard_waf_config_id')
                        logger.info(f'{onboard_object.onboard_waf_prev_version}{space:>{column_width - len(str(onboard_object.onboard_waf_prev_version))}}found latest onboard_waf_prev_version')
                    else:
                        count += 1
                        logger.error(f'{onboard_object.waf_config_name}{space:>{column_width - len(onboard_object.waf_config_name)}}invalid waf_config_name, not found')

                    if onboard_object.onboard_waf_config_id is not None:
                        logger.debug(f'{onboard_object.onboard_waf_config_id} {onboard_object.onboard_waf_prev_version}')
                        _, policies = wrapper_object.get_waf_policy(onboard_object)
                        _, target_ids = wrapper_object.list_match_targets(onboard_object.onboard_waf_config_id,
                                                                          onboard_object.onboard_waf_prev_version,
                                                                          policies)
                        if (onboard_object.update_match_target) and (onboard_object.waf_match_target_id in target_ids):
                            for k in policies:
                                if onboard_object.waf_match_target_id in policies[k]:
                                    logger.info(f'{policies[k][0]}{space:>{column_width - len(policies[k][0])}}found existing policy')
                                    logger.info(f'{onboard_object.waf_match_target_id}{space:>{column_width - len(str(onboard_object.waf_match_target_id))}}found waf_match_target_id')
                        else:
                            if not (onboard_object.update_match_target):
                                logger.debug('No match target given, updating selected hosts only')
                            else:
                                logger.error(f'{onboard_object.waf_match_target_id}{space:>{column_width - len(str(onboard_object.waf_match_target_id))}}invalid waf_match_target_id')
                                count += 1
                            # we will not auto correct waf_match_target_id
                            # onboard_object.waf_match_target_id = correct_target_id
                            # logger.info(f'{onboard_object.waf_match_target_id:<30}{space:>20}auto correct waf_match_target_id')
        else:
            pass

        # valid notify_emails is required
        emails = onboard_object.notification_emails

        # check if emails are empty and activation is true - can be [""] or []
        if (onboard_object.activate_property_staging or onboard_object.activate_property_production):
            if len(emails) == 0:
                logger.error('At least one valid notification email is required for activations')
                count += 1
            if len(emails) == 1:
                if emails[0] == '':
                    logger.error('At least one valid notification email is required for activations')
                    count += 1
            # check that emails are valid
            if len(emails) > 0:
                for email in emails:
                    if not is_email(email):
                        logger.error(f'{email}{space:>{column_width - len(email)}}invalid email address')
                        count += 1

        # maximum active security config per network is 10
        '''
        # apply to akamai internal account only
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
            logger.error(f'{onboard_object.property_name}{space:>{column_width - len(onboard_object.property_name)}}invalid property name; already in use')
            count += 1
        else:
            logger.info(f'{onboard_object.property_name}{space:>{column_width - len(onboard_object.property_name)}}valid property name')

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
            logger.info(f'{onboard_object.product_id}{space:>{column_width - len(onboard_object.product_id)}}valid product_id')
            logger.info(f'{onboard_object.group_id}{space:>{column_width - len(onboard_object.group_id)}}valid group_id')
            logger.info(f'{onboard_object.contract_id}{space:>{column_width - len(onboard_object.contract_id)}}valid contract_id')
        else:
            logger.error(f'{onboard_object.product_id}{space:>{column_width - len(onboard_object.product_id)}}invalid product_id')
            logger.error(f'Available valid product_id for contract {onboard_object.contract_id}')
            count += 1
            products_list = sorted(product_detail['products'])
            for p in products_list:
                logger.error(p)

        # network must be either STANDARD_TLS or ENHANCED_TLS
        if onboard_object.secure_network not in ['STANDARD_TLS', 'ENHANCED_TLS']:
            logger.error(f'{onboard_object.secure_network}{space:>{column_width - len(onboard_object.secure_network)}}invalid secure_network')
            count += 1

        # ensure hostname doesn't contain special characters and is of valid length
        count = self.validate_hostnames(onboard_object.public_hostnames)

        # must be one of three valid modes
        valid_modes = ['use_existing_edgehostname', 'new_standard_tls_edgehostname', 'new_enhanced_tls_edgehostname', 'secure_by_default']
        logger.info(f'{onboard_object.edge_hostname_mode}{space:>{column_width - len(onboard_object.edge_hostname_mode)}}edge hostname mode')
        if onboard_object.edge_hostname_mode not in valid_modes:
            logger.error(f'{onboard_object.edge_hostname_mode}{space:>{column_width - len(onboard_object.edge_hostname_mode)}}invalid edge_hostname_mode')
            count += 1
            logger.info('valid options: use_existing_edgehostname, new_standard_tls_edgehostname, new_enhanced_tls_edgehostname')
        elif onboard_object.edge_hostname_mode == 'use_existing_edgehostname':
            ehn_id = 0
            if onboard_object.edge_hostname == '':
                logger.error(f'{onboard_object.edge_hostname}{space:>{column_width - len(onboard_object.edge_hostname)}}missing edge hostname')
                count += 1
            else:
                try:
                    # check to see if specified edge hostname exists
                    ehn_id = self.validateEdgeHostnameExists(wrapper_object, str(onboard_object.edge_hostname))
                    public_hostname_str = ', '.join(onboard_object.public_hostnames)
                    logger.info(f'ehn_{ehn_id}{space:>{column_width - len(str(ehn_id))-4}}valid edge_hostname_id')
                    logger.info(f'{onboard_object.edge_hostname}{space:>{column_width - len(onboard_object.edge_hostname)}}valid edge hostname')
                    logger.info(f'{public_hostname_str}{space:>{column_width - len(public_hostname_str)}}valid public hostname')
                    onboard_object.edge_hostname_id = ehn_id
                except:
                    logger.error(f'{onboard_object.edge_hostname}{space:>{column_width - len(onboard_object.edge_hostname)}}invalid edge hostname')
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
                    logger.error(f"{'existing_enrollment_id'}{space:>{column_width - len(str(onboard_object.existing_enrollment_id))}}missing")
                    count += 1
            else:
                logger.error('If new_enhanced_tls_edgehostname, use_existing_enrollment_id must be true')
                count += 1

            if onboard_object.create_new_ssl_cert is True:
                logger.error('Unable to create_new_ssl_cert enrollment, please use existing_enrollment_id instead')
                count += 1
        elif onboard_object.edge_hostname_mode == 'secure_by_default':
            ehn_id = 0
            if onboard_object.secure_by_default_use_existing_ehn == '' and (not onboard_object.secure_by_default_new_ehn):
                logger.error(f'{onboard_object.edge_hostname}{space:>{column_width - len(onboard_object.edge_hostname)}}missing edge hostname')
                count += 1
            if (onboard_object.secure_by_default_use_existing_ehn != '') and (onboard_object.secure_by_default_new_ehn):
                logger.error('If create_new_edge_hostnames is true, use_existing_edge_hostnames must be empty')
                count += 1
            if (not onboard_object.secure_by_default_new_ehn) and (onboard_object.secure_by_default_use_existing_ehn != ''):
                try:
                    # check to see if specified edge hostname exists
                    ehn_id = self.validateEdgeHostnameExists(wrapper_object, str(onboard_object.secure_by_default_use_existing_ehn))
                    public_hostname_str = ', '.join(onboard_object.public_hostnames)
                    logger.info(f'ehn_{ehn_id}{space:>{column_width - len(str(ehn_id))+4}}valid edge_hostname_id')
                    logger.info(f'{onboard_object.secure_by_default_use_existing_ehn}{space:>{column_width - len(onboard_object.secure_by_default_use_existing_ehn)}}valid edge hostname')
                    logger.info(f'{public_hostname_str}{space:>{column_width - len(public_hostname_str)}}valid public hostname')
                    onboard_object.edge_hostname_id = ehn_id
                except:
                    logger.error(f'{onboard_object.secure_by_default_use_existing_ehn}{space:>{column_width - len(onboard_object.secure_by_default_use_existing_ehn)}}invalid edge hostname')
                    count += 1

        # validate source and variable file is use_file mode (create only)
        if onboard_object.use_file:
            if not self.validateFile('source_template_file', onboard_object.source_template_file):
                logger.error('unable to locate source_template_file')
                count += 1
            else:
                if onboard_object.source_values_file == '':
                    logger.error('missing source_values_file')
                    count += 1

            if not self.validateFile('source_values_file', onboard_object.source_values_file):
                logger.error('unable to locate source_values_file')
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
                '''
                # not require to activate WAF
                if not onboard_object.activate_waf_policy_staging:
                    logger.error('If adding WAF selected hosts, property must be activated to STAGING')
                    count += 1

                # if onboard_object.update_match_target and onboard_object.activate_waf_policy_staging:
                '''
                config_detail = self.getWafConfigIdByName(wrapper_object, onboard_object.waf_config_name)
                if config_detail['Found']:
                    onboard_object.onboard_waf_config_id = config_detail['details']['id']
                    onboard_object.onboard_waf_prev_version = config_detail['details']['latestVersion']
                    logger.debug(f'{onboard_object.onboard_waf_config_id} {onboard_object.onboard_waf_config_version}')
                    logger.info(f'{onboard_object.waf_config_name}{space:>{column_width - len(onboard_object.waf_config_name)}}valid waf_config_name')
                    logger.info(f'{onboard_object.onboard_waf_config_id}{space:>{column_width - len(str(onboard_object.onboard_waf_config_id))}}found existing onboard_waf_config_id')
                    logger.info(f'{onboard_object.onboard_waf_prev_version}{space:>{column_width - len(str(onboard_object.onboard_waf_prev_version))}}found latest onboard_waf_prev_version')
                else:
                    count += 1
                    logger.error(f'{onboard_object.waf_config_name}{space:>{column_width - len(onboard_object.waf_config_name)}}invalid waf_config_name, not found')

                if onboard_object.onboard_waf_config_id is not None:
                    logger.debug(f'{onboard_object.onboard_waf_config_id} {onboard_object.onboard_waf_prev_version}')
                    _, policies = wrapper_object.get_waf_policy(onboard_object)
                    _, target_ids = wrapper_object.list_match_targets(onboard_object.onboard_waf_config_id,
                                                                        onboard_object.onboard_waf_prev_version,
                                                                        policies)
                    if onboard_object.waf_match_target_id in target_ids:
                        for k in policies:
                            if onboard_object.waf_match_target_id in policies[k]:
                                logger.info(f'{policies[k][0]}{space:>{column_width - len(policies[k][0])}}found existing policy')
                                logger.info(f'{onboard_object.waf_match_target_id}{space:>{column_width - len(str(onboard_object.onboard_waf_config_id))-2}}found existing onboard_waf_config_id')
                    else:
                        logger.error(f'{onboard_object.waf_match_target_id}{space:>{column_width - len(str(onboard_object.onboard_waf_config_id))}}invalid onboard_waf_config_id')
                        count += 1
                        # we will not auto correct waf_match_target_id
                        # onboard_object.waf_match_target_id = correct_target_id
                        # logger.info(f'{onboard_object.waf_match_target_id:<30}{space:>20}auto correct waf_match_target_id')
        elif cli_mode in ['single-host', 'multi-hosts']:
            if onboard_object.edge_hostname and onboard_object.existing_enrollment_id > 0:
                logger.error('Only "use_existing_edge_hostname" or "create_from_existing_enrollment_id" can be used, not both')
                count += 1
            if onboard_object.use_existing_enrollment_id > 0:
                onboard_object.edge_hostname = onboard_object.public_hostnames[0]
                if cli_mode == 'multi-hosts':
                    # all public hostname use the same edge hostname prefix with property name
                    onboard_object.edge_hostname = onboard_object.property_name
                logger.debug(f'{cli_mode} {onboard_object.edge_hostname}')

            if onboard_object.create_new_security_config:
                config_detail = self.getWafConfigIdByName(wrapper_object, onboard_object.waf_config_name)
                if config_detail['Found']:
                    count += 1
                    onboard_object.onboard_waf_config_id = config_detail['details']['id']
                    onboard_object.onboard_waf_prev_version = config_detail['details']['latestVersion']
                    logger.error(f'{onboard_object.waf_config_name}{space:>{column_width - len(onboard_object.waf_config_name)}}duplicate waf_config_name already exists')
                    logger.info(f'{onboard_object.onboard_waf_config_id}{space:>{column_width - len(str(onboard_object.onboard_waf_config_id))}}found existing onboard_waf_config_id')
                    logger.info(f'{onboard_object.onboard_waf_prev_version}{space:>{column_width - len(str(onboard_object.onboard_waf_prev_version))}}found latest onboard_waf_prev_version')
                    valid_waf = False
                else:
                    # valid means this waf name doesn't exists
                    logger.info(f'{onboard_object.waf_config_name}{space:>{column_width - len(onboard_object.waf_config_name)}}new waf_config_name')

        else:
            pass

        # valid notify_emails is required
        emails = onboard_object.notification_emails

        # check if emails are empty and activation is true - can be [""] or []
        if (onboard_object.activate_property_staging or onboard_object.activate_property_production):
            if len(emails) == 0:
                logger.error('At least one valid notification email is required for activations')
                count += 1
            if len(emails) == 1:
                if emails[0] == '':
                    logger.error('At least one valid notification email is required for activations')
                    count += 1
            # check that emails are valid
            if len(emails) > 0:
                for email in emails:
                    if not is_email(email):
                        logger.error(f'{email}{space:>{column_width - len(email)}}invalid email address')
                        count += 1

        # maximum active security config per network is 10
        '''
        # apply to akamai internal account only
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
            sys.exit(logger.error(f'Total {count} errors, please review'))

        return self.valid

    # Validate file
    def validateFile(self, source: str, file_location: str) -> bool:
        logger.debug(f'{file_location} {type(file_location)} {os.path.exists(file_location)}')
        logger.debug(os.path.abspath(file_location))
        if os.path.isfile(os.path.abspath(file_location)):
            return True
        else:
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
                    logger.debug(f'{ehn_id}{space:>{column_width - len(str(ehn_id))}}found edgeHostnameId')
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

    def get_active_sec_config(self, wrapper_object):
        config = wrapper_object.getWafConfigurations()
        config_ids, responses, stg, prd = [], [], [], []
        try:
            if len(config.json()['configurations']) > 0:
                config_list = config.json()['configurations']
                config_ids = [i['id'] for i in config_list if i['id']]
        except:
            pass

        for config_id in config_ids:
            responses.append(wrapper_object.get_waf_sec_detail(config_id).json())
        stg = [r['stagingActiveVersion'] for r in responses if 'stagingActiveVersion' in r.keys()]
        prd = [r['productionActiveVersion'] for r in responses if 'productionActiveVersion' in r.keys()]
        logger.debug(f'{len(stg)}-{len(prd)}')
        return len(stg), len(prd)

    def csv_2_origin_rules(self, csv_file_loc: str) -> dict:
        cli_path = f'{root}/templates/akamai_product_templates/behaviors'
        logger.info(f'Validating customer hostname input: {csv_file_loc}')

        if not self.validateFile('csv file', csv_file_loc):
            sys.exit(logger.error(f'{csv_file_loc}...........missing'))

        csv_file_loc = os.path.abspath(csv_file_loc)
        with open(csv_file_loc, encoding='utf-8-sig') as f:
            rows = sum(1 for row in f)
            if rows > 600:
                logger.warning(f'{rows} hostnames/origins defined. Consider splitting hostnames into multiple properties')

        public_hostnames, origin_hostnames = [], []
        with open(csv_file_loc, encoding='utf-8-sig') as f:
            parent_rule = {}
            parent_rule['name'] = 'Origin Rules'
            parent_rule['behaviors'] = []
            parent_rule['criteria'] = []
            parent_rule['children'] = []
            parent_rule['comments'] = 'Route request to appropriate origin'

            rows_reader = csv.reader(f, delimiter=',')
            for row in rows_reader:
                public_hostnames.append(row[0])
                origin_hostnames.append(row[1])
                origin_behavior_file = os.path.abspath(f'{cli_path}/origin.json')
                with open(origin_behavior_file) as t:
                    content = t.read()
                content = content.replace('$env.hostname', row[0])
                content = content.replace('$env.origin_name', row[1])
                parent_rule['children'].append(json.loads(content))
        logger.debug(json.dumps(parent_rule, indent=4))
        return parent_rule, public_hostnames, origin_hostnames

    def validate_prerequisite_cli(self) -> None:
        cli_installed = self.installedCommandCheck('akamai')
        pipeline_installed = self.executeCommand(['akamai', 'pipeline'])

        if not (pipeline_installed and (cli_installed or pipeline_installed)):
            sys.exit()

    def onboard_override_default(self, onboard, setup, cli_mode: str) -> None:
        if cli_mode == 'single-host':
            onboard.new_cpcode_name = setup.new_cpcode_name
            template_path = f'{root}/templates/akamai_product_templates'
            onboard.source_values_file = f'{template_path}/single_variable.json'
        elif cli_mode == 'multi-hosts':
            template_path = f'{root}/templates/akamai_product_templates/multi-hosts'
            onboard.source_values_file = f'{template_path}/variables.json'

        onboard.source_template_file = f'{template_path}/{setup.product_id}.json'
        logger.info(f'Rule Template Location: {onboard.source_template_file}')
        onboard.create_new_security_config = setup.create_new_security_config
        if len(setup.waf_config_name) > 0:
            onboard.waf_config_name = setup.waf_config_name
        if setup.existing_enrollment_id > 0:
            onboard.use_existing_enrollment_id = True
            onboard.edge_hostname_mode = 'new_enhanced_tls_edgehostname'
            onboard.existing_enrollment_id = setup.existing_enrollment_id
        if not (setup.version_notes == ''):
            onboard.version_notes = setup.version_notes
        if not setup.activate_production:
            onboard.activate_property_production = False
            onboard.activate_waf_policy_production = False
        if onboard.secure_by_default:
            onboard.edge_hostname_mode = 'secure_by_default'

    def csv_validator(self, onboard_object, csv_file_loc: str):
        csv_dict = []
        schema = {
            'hostname': {
                'type': 'string',
                'required': True,
                'empty': False
            },
            'origin': {
                'type': 'string',
                'required': True,
                'empty': False
            },
            'propertyName': {
                'type': 'string'
            },
            'forwardHostHeader': {
                'type': 'string',
                'nullable': True,
                'allowed': ['REQUEST_HOST_HEADER', 'ORIGIN_HOSTNAME']
            },
            'edgeHostname': {
                'type': 'string',
                'regex': (r'(.*\.edgekey\.net$|.*\.edgesuite\.net$)')}
        }

        v = Validator(schema)
        logger.warning(f'Reading customer property name input: {csv_file_loc}')

        with open(csv_file_loc, encoding='utf-8-sig', newline='') as f:
            for i, row in enumerate(csv.DictReader(f), 1):
                csv_dict.append(row)
                valid = v.validate(row)
                validation_errors = v.errors
                if validation_errors:
                    onboard_object.valid_csv = False
                    logger.warning(f'CSV Validation Error in row: {i}...')
                    for error in validation_errors:
                        logger.warning(f'{error} {validation_errors[error]}')

        onboard_object.csv_dict = csv_dict
        return onboard_object.valid_csv

    def csv_2_property_dict(self, onboard_object) -> dict:
        propertyList = []
        hostnameList = []
        edgeHostnameList = []
        ehn_suffix = onboard_object.ehn_suffix
        if onboard_object.secure_network == 'STANDARD_TLS':
            ehn_suffix = '.edgesuite.net'

        for i, row in enumerate(onboard_object.csv_dict):
            try:
                propertyName = row['propertyName']
                if (propertyName is None) or (propertyName == ''):
                    propertyName = row['hostname']
            except KeyError:
                propertyName = row['hostname']
            hostname = row['hostname']
            hostnameList.append(hostname)
            propertyList.append(propertyName)
            try:
                edgeHostname = row['edgeHostname']
                if (edgeHostname is None) or (edgeHostname == ''):
                    if onboard_object.edge_hostname_mode == 'secure_by_default':
                        edgeHostnameList.append(f'{hostname}{ehn_suffix}')
                        logger.debug(f'edgeHostname value is empty - using edge hostname {hostname}{ehn_suffix}')
                    else:
                        sys.exit(logger.error(f'No edgeHostname provided for {hostname} - row:{i+1}'))
                else:
                    edgeHostnameList.append(edgeHostname)
            except KeyError:
                if onboard_object.edge_hostname_mode == 'secure_by_default':
                    edgeHostnameList.append(f'{hostname}{ehn_suffix}')
                    logger.debug(f'edgeHostname column does not exist in csv, using edge hostname {hostname}{ehn_suffix}')
                else:
                    sys.exit(logger.error('edgeHostname column must exist in input csv unless using secure-by-default mode'))

        propertyList = list(set(propertyList))
        hostnameList = list(set(hostnameList))

        onboard_object.edge_hostname_list = edgeHostnameList
        onboard_object.property_list = propertyList
        onboard_object.public_hostnames = hostnameList

        return (propertyList, hostnameList)

    def csv_2_property_array(self, config, onboard_object, cpcodeList) -> dict:
        cli_path = f'{root}/templates/akamai_product_templates/behaviors'
        propertyJson = {}
        hostnameList = []
        templateFile = onboard_object.source_template_file

        if not self.validateFile('json file', templateFile):
            sys.exit(logger.error(f'{templateFile}...........missing'))

        with open(templateFile) as templateHandler:
            templateData = json.load(templateHandler)

        # update template to include origin and cpCode behaviors in default rule if they don't exist
        default_behaviors = templateData['rules']['behaviors']
        onboard_object.level_0_rules = templateData['rules']['children']
        default_behavior_names = list(set(list(map(lambda x: x['name'], default_behaviors))))
        if 'origin' not in default_behavior_names:
            logger.warning('No default origin behavior in provided template, adding.....')
            with open(f'{cli_path}/origin_csv.json') as t:
                content = json.load(t)
                originBehavior = content['behaviors'][0]
                originBehavior['options']['forwardHostHeader'] = 'REQUEST_HOST_HEADER'
            templateData['rules']['behaviors'].append(originBehavior)
        if 'cpCode' not in default_behavior_names:
            logger.warning('No default cpCode behavior in provided template, adding.....')
            with open(f'{cli_path}/cpCode.json') as c:
                cp_content = json.load(c)
            templateData['rules']['behaviors'].append(cp_content)

        for i, row in enumerate(onboard_object.csv_dict):

            # group by propertyName
            propertyName = row['hostname']
            edgeHostname = onboard_object.edge_hostname_list[i]

            try:
                propertyName = row['propertyName']
                if (propertyName is None) or (propertyName == ''):
                    propertyName = row['hostname']

                # check to see if property already exists in dict if it does, add hostname, origins, ehns, to hostname dict and move on to next row
                else:
                    if propertyName in propertyJson.keys():
                        propertyJson[propertyName]['hostnames'].append(row['hostname'])
                        propertyJson[propertyName]['origins'].append(row['origin'])
                        propertyJson[propertyName]['edgeHostnames'].append(edgeHostname)
                        try:
                            if row['forwardHostHeader'] is not None:
                                propertyJson[propertyName]['forwardHostHeader'].append(row['forwardHostHeader'])
                            else:
                                propertyJson[propertyName]['forwardHostHeader'].append('REQUEST_HOST_HEADER')
                        except KeyError:
                            propertyJson[propertyName]['forwardHostHeader'].append('REQUEST_HOST_HEADER')

                        hostnameList.append(row['hostname'])
                        continue

        # If property doesn't already exist, add new property json rule tree to dict
            except KeyError:
                propertyName = row['hostname']

            propertyJson[propertyName] = {}
            propertyJson[propertyName]['ruleTree'] = templateData
            propertyJson[propertyName]['hostnames'] = [row['hostname']]
            propertyJson[propertyName]['origins'] = [row['origin']]
            propertyJson[propertyName]['edgeHostnames'] = [edgeHostname]
            try:
                propertyJson[propertyName]['forwardHostHeader'] = [row['forwardHostHeader']]

                if row['forwardHostHeader'] is None:
                    propertyJson[propertyName]['forwardHostHeader'] = ['REQUEST_HOST_HEADER']
            except KeyError:
                propertyJson[propertyName]['forwardHostHeader'] = ['REQUEST_HOST_HEADER']

            hostnameList.append(row['hostname'])

        # create origin behaviors for multi-origin setup
        for propertyName in propertyJson:

            if len(propertyJson[propertyName]['origins']) > 1:
                with open(f'{cli_path}/origin_csv.json') as t:
                    content = t.read()
                with open(f'{cli_path}/cpCode.json') as c:
                    cp_content = c.read()

                parent_rule = {}
                parent_rule['name'] = 'Origin Rules'
                parent_rule['behaviors'] = []
                parent_rule['criteria'] = []
                parent_rule['children'] = []
                parent_rule['comments'] = 'Route request to appropriate origin'

                # check default rule FOSSL settings (verificationMode: CUSTOM or verificationMode: PLATFORM_SETTINGS)
                default_fossl_verification_settings = ''
                for defaultBehavior in propertyJson[propertyName]['ruleTree']['rules']['behaviors']:
                    if defaultBehavior['name'] == 'origin':
                        default_fossl_verification_settings = defaultBehavior['options']['verificationMode']

                for i in range(len(propertyJson[propertyName]['origins'])):
                    originJson = content.replace('$env.hostname', propertyJson[propertyName]['hostnames'][i])
                    originJson = originJson.replace('$env.origin_name', propertyJson[propertyName]['origins'][i])
                    originJson = originJson.replace('$env.forward_host_header', propertyJson[propertyName]['forwardHostHeader'][i])
                    originJson = json.loads(originJson)
                    cpcodeJson = json.loads(cp_content)
                    cpcodeJson['options']['value']['id'] = cpcodeList[propertyJson[propertyName]['hostnames'][i]]

                    # update new origin behaviors to match verification setting of default rule
                    if default_fossl_verification_settings == 'PLATFORM_SETTINGS':
                        originJson['behaviors'][0]['options']['verificationMode'] = 'PLATFORM_SETTINGS'
                        platform_setting_keys_to_remove = ['customValidCnValues', 'originCertsToHonor', 'standardCertificateAuthorities']
                        for key in platform_setting_keys_to_remove:
                            del originJson['behaviors'][0]['options'][key]

                    originJson['behaviors'].append(cpcodeJson)
                    parent_rule['children'].append(originJson)

                propertyJson[propertyName]['originRule'] = parent_rule

        return (propertyJson, hostnameList)

    def validate_group_id(self, onboard, groups) -> None:
        for group in groups:
            if group['contractIds'][0] == onboard.contract_id:
                onboard.group_id = group['groupId']
                exit
        if onboard.group_id is None:
            sys.exit(logger.error('Unknown Error: Cannot find top level group_id'))

    def log_cli_timing(self) -> None:
        print()
        end_time = time.perf_counter()
        elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - self.start_time)))
        logger.info(f'TOTAL DURATION: {elapse_time}, End Akamai CLI onboard')

    def validate_hostnames(self, hostnames) -> int:
        # ensure hostname doesn't contain special characters and is of valid length
        reg = re.compile(r'[^\.\-a-zA-Z0-9]')
        error_count = 0
        for hostname in hostnames:
            if re.search(reg, hostname):
                logger.error(f'{hostname} contains invalid character. Only alphanumeric (a-z, A-Z, 0-9) and hyphen (-) characters are supported.')
                error_count += 1
            if len(hostname) > 60 and len(hostname) < 4:
                logger.error(f'{hostname} is invalid length. Hostname length must be between 4-60 characters')
                error_count += 1
            if (hostname[0] == '-') or (hostname[-1] == '-'):
                logger.error(f'{hostname} cannot begin or end with a hyphen.')
                error_count += 1
        return error_count
