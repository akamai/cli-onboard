from __future__ import annotations

import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from shutil import which
from time import gmtime
from time import strftime
from urllib import parse

import pandas as pd
import util_emojis as emoji
from cerberus import Validator
from exceptions import get_cli_root_directory
from exceptions import setup_logger
from jsonschema import validate
from jsonschema import ValidationError
from model.edge_hostname_mode import EdgeHostnameMode
from pyisemail import is_email
from rich import print
from rich import print_json
from tabulate import tabulate
from UliPlot.XLSX import auto_adjust_xlsx_column_width

logger = setup_logger()
root = get_cli_root_directory()

space = ' '
column_width = 50


class utility:
    def __init__(self, check_prereqs: bool = True):
        """
        Function to initialize a common status indicator,
        This variable should be updated by every function
        defined in validation modules to indicate validation status.
        This avoid usage of too many IF Conditions.

        check_prereqs=False skips the `akamai`/pipeline shell-out below - used by
        tests that need a real utility() instance without a live `akamai` CLI on PATH.
        """
        # Initialize the variable to true
        self.valid = True
        if check_prereqs:
            self.validate_prerequisite_cli()
        self.start_time = time.perf_counter()

    def check_cli_prereq(self, click_args, config) -> None:
        cli_installed = self.installedCommandCheck('akamai')
        pipeline_installed = self.executeCommand(['akamai', 'pipeline'])
        if not (pipeline_installed and (cli_installed or pipeline_installed)):
            sys.exit()

        # If groupId, contractId or productId is missing, list them
        if click_args['group'] is None:
            command = (f'akamai pm -s default lg -a {config.account_key}') if config.account_key is not None else ('akamai pm lg')
            logger.warning(f'Group ID is required.  Running akamai property manager cli command: {command}')
            # sys.exit(os.system(command))

        if click_args['contract'] is None:
            command = (f'akamai pm lc -s default -a {config.account_key}') if config.account_key is not None else ('akamai pm lc')
            logger.warning(f'Contract ID is required.  Running akamai property manager cli command: {command}')
            sys.exit(os.system(command))

    def check_sbd_quota(self, papi, click_args, total_needed) -> bool:
        contract_id = click_args['contract']
        group_id = click_args['group']
        csv_file = click_args['csv']
        props = papi.list_properties(contract_id, group_id)

        if not props:
            return None
        else:
            sbc_init_prop = [x for x in props if x['propertyName'].startswith('sbd_vcd_init')]
            logger.debug(sbc_init_prop)
            # either sbd_vcd_init property was deleted or never created
            if len(sbc_init_prop) == 0:
                return None

        property_id = sbc_init_prop[0]['propertyId']
        property_name = sbc_init_prop[0]['propertyName']

        base_version = 1
        status = papi.get_edittable_property_version(property_id, base_version)

        if status == 'ACTIVE':
            base_version = papi.create_new_property_version(property_id, base_version)
            if base_version == -1:
                base_version = 1

        items = papi.get_property_version_hostname(property_id, base_version)
        logger.debug(f'{property_id} {property_name} {status} {items}')

        if not items:
            return False

        sbd = [x for x in items if x['cnameTo'].startswith('sbd-vcd-init')]
        logger.debug(f'{property_id} {property_name} {status} {items} {sbd}')
        # if not sbd:
        #    return False

        if len(sbd) > 0:
            test_sbd = {'cnameType': 'EDGE_HOSTNAME',
                        'cnameFrom': 'testlumen.com',
                        'cnameTo': 'testlumen.com.edgesuite.net',
                        'certProvisioningType': 'DEFAULT'}

            sbd_resp = papi.add_property_hostname(contract_id, group_id, property_id, base_version,
                                            {'add': [test_sbd]})

            if sbd_resp.status_code == 403:
                msg = 'SBD certificates are being provisioned by product team, please try again later'
                logger.error(f'{emoji.fail} {msg}')
                msg_1 = 'If you see this message again after for more than 4 hours waiting, '
                msg_2 = 'please share account name in the '
                webex = 'Mob Programming webex'
                url = 'webexteams://im?space=24bba630-70c1-11ed-b903-b9ad3cd4462a'
                msg_3 = self.console_hyperlink(url, webex)
                logger.info(f'{msg_1} {msg_2}{msg_3} space')
                logger.info(f'{webex} space {url}')
                return False
            elif sbd_resp.status_code == 429:
                limit = sbd_resp.json()['limit']
                msg = f'Please request for more SBD certificates. Account has reached a limit of {limit}'
                msg = f'{msg}, or try again after 60 minutes'
                logger.error(f'{emoji.fail} {msg}')
                return False
            else:
                try:
                    # limit = int(sbd_resp.headers['x-limit-default-certs-per-contract-limit'])
                    # print_json(data=sbd_resp.json())
                    remaining = int(sbd_resp.headers['x-limit-default-certs-per-contract-remaining'])
                    if total_needed > remaining:
                        additional_sbd = total_needed - remaining
                        msg = f'{additional_sbd} more SBD are needed to create {total_needed} configs'
                        logger.info(f' {emoji.fail} {msg}')
                        logger.info('    or You can ignore this if you only create properties with sharecert edge hostname')
                        return False
                except KeyError:
                    logger.error(KeyError)
                    print_json(data=sbd.json())

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

    def check_read_write_v1(self, accessLevels: list):
        for x in accessLevels:
            if x['name'] == 'READ-WRITE':
                return True
        return False

    def check_read_write_v3(self, accessLevels: list):
        return 'READ-WRITE' in accessLevels

    def check_api_access(self, papi):
        resp = papi.get_api_client()
        if not resp.ok:
            return False
        else:
            username = resp.json()['authorizedUsers'][0]
            access_token = resp.json()['accessToken']
            resp_v3 = papi.all_api_permission(username)
            if not resp_v3.ok:
                logger.error(resp_v3.json()['title'])
                return False

        df = pd.DataFrame(resp_v3.json())
        df = df[['apiName', 'accessLevels']].sort_values(by='apiName')
        logger.debug(f'\n{df.to_string()}')
        required = ['CPS',
                    'Property Manager (PAPI)',
                    'Edge Hostnames API (hapi)',
                    'CPcode and Reporting group (cprg)']
        df_3 = df[df['apiName'].isin(required)].copy()
        df_3['RW'] = df_3['accessLevels'].apply(lambda x: self.check_read_write_v3(x))
        logger.debug(f"\n{df_3[['apiName', 'accessLevels', 'RW']]}")

        resp_v1 = papi.allowed_api_permission(access_token)
        if not resp_v1.ok:
            return False

        df = pd.json_normalize(resp_v1.json()['authorization']['services'])
        df = df[df['serviceName'].isin(required)].copy()
        df = df[['serviceName', 'grantScopes']].copy()
        df['RW'] = df['grantScopes'].apply(lambda x: self.check_read_write_v1(x))
        df_1 = df[df['RW']].copy()
        logger.debug(f'\n{df_1.to_string()}')

        missing = set(df_3['apiName'].tolist()) - set(df_1['serviceName'].tolist())
        if missing:
            logger.error(f'Missing READ-WRITE access on API: {missing}\n')
            return True
        else:
            return False

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
        reg = re.compile(r'[^\.\-\*a-zA-Z0-9]')
        for hostname in onboard_object.public_hostnames:
            if re.search(reg, hostname):
                logger.error(f'{hostname} contains invalid character. Only alphanumeric (a-z, A-Z, 0-9), hyphen (-) and asterisk (*) characters are supported.')
                count += 1
            if len(hostname) > 60 and len(hostname) < 4:
                logger.error(f'{hostname} is invalid length. Hostname length must be between 4-60 characters')
                count += 1
            if (hostname[0] == '-') or (hostname[-1] == '-'):
                logger.error(f'{hostname} cannot begin or end with a hyphen.')
                count += 1

        # must be one of three valid modes
        edgeHostnameList = onboard_object.edge_hostname_list
        valid_modes = [EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME, EdgeHostnameMode.SECURE_BY_DEFAULT]
        logger.info(f'{onboard_object.edge_hostname_mode}{space:>{column_width - len(onboard_object.edge_hostname_mode)}}edge hostname mode')
        if onboard_object.edge_hostname_mode == EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME:
            ehn_id = 0
            # check to see if specified edge hostname exists
            for edgeHostname in edgeHostnameList:
                ehn_id = self.validateEdgeHostnameExists(wrapper_object, str(edgeHostname))
                public_hostname_str = ', '.join(onboard_object.public_hostnames)
                if ehn_id != 0:
                    logger.info(f'{edgeHostname} valid edge hostname (ehn_{ehn_id})')
                # logger.info(f'{public_hostname_str:<30}{space:>20}valid public hostname')
                    # onboard_object.edge_hostname_id = ehn_id
                else:
                    logger.error(f'{edgeHostname} invalid edge hostname')
                    count += 1
        elif onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
            ehn_id = 0
            for i, edgeHostname in enumerate(edgeHostnameList):
                # check to see if specified edge hostname exists
                ehn_id = self.validateEdgeHostnameExists(wrapper_object, str(edgeHostname))
                public_hostname_str = ', '.join(onboard_object.public_hostnames)
                if ehn_id != 0:
                    logger.info(f'{edgeHostname} valid edge hostname (ehn_{ehn_id})')
                    # logger.info(f'{public_hostname_str:<30}{space:>20}valid public hostname')
                    # onboard_object.edge_hostname_id = ehn_id
                else:
                    if edgeHostname.endswith(('edgekey.net', 'edgesuite.net')):
                        logger.warning(f'{edgeHostname} does not exist, will be created upon property activation')
                    else:
                        logger.warning(f'{edgeHostname} does not end with edgekey.net or edgesuite.net, using {hostname}.{onboard_object.ehn_suffix}')
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
                        _, target_ids, _ = wrapper_object.list_match_targets(onboard_object.onboard_waf_config_id,
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

    def validateSetupStepsConvert(self, onboard_object, wrapper_object, prefix, cli_mode='convert', confirm_input=input) -> bool:
        """
        Function to validate the input values of {hostname}.json when in convert mode
        """

        count = 0

        # check if csv is valid
        csv_file = onboard_object.csv_loc.split('/')[-1]
        if not onboard_object.valid_csv:
            logger.error(f'{space}{emoji.fail} {onboard_object.csv_loc:<30}{space:>20}invalid csv')
            count += 1
        else:
            logger.info(f'{space}{emoji.tada} {csv_file:<30}')

        print()
        logger.warning(f'{emoji.looking} Checking for all required JSON files in directory')
        self.json_input_file_validator(onboard_object, prefix)

        if not onboard_object.all_template_json_exists:
            logger.error(f'{space}{emoji.fail} {onboard_object.source_directory:<30}{space:>20}missing some template json')
            count += 1
        else:
            logger.info(f'{space}{emoji.tada} {onboard_object.source_directory}')

        print()
        logger.warning(f'{emoji.looking} Validating all hostnames')
        reg = re.compile(r'[^\.\-\*a-zA-Z0-9]')
        hostname_error_count = 0
        for hostname in onboard_object.public_hostnames:
            if re.search(reg, hostname):
                logger.error(f'{space}{emoji.thumbdown} {hostname} contains invalid character. Only alphanumeric (a-z, A-Z, 0-9), hyphen (-) and asterisk (*) characters are supported.')
                count += 1
                hostname_error_count += 1
            if len(hostname) > 60 and len(hostname) < 4:
                logger.error(f'{space}{emoji.thumbdown} {hostname} is invalid length. Hostname length must be between 4-60 characters')
                count += 1
                hostname_error_count += 1
            if (hostname[0] == '-') or (hostname[-1] == '-'):
                logger.error(f'{space}{emoji.thumbdown} {hostname} cannot begin or end with a hyphen.')
                count += 1
                hostname_error_count += 1
        if hostname_error_count == 0:
            logger.info(f'{space}{emoji.tada} all hostnames valid ')

        # check if gtm domain is valid
        print()
        logger.warning(f'{emoji.looking} Validating GTM domain')
        gtm_domain_error_count = 0
        if not onboard_object.gtm_domain:
            if onboard_object.gtm_replacement_count > 0:
                onboard_object.gtm_domain = f'{((onboard_object.ASK).replace(':', '-')).lower()}.akadns.net'
                logger.error(f'{space}{emoji.thumbdown} No --gtm-domain input ---> properties have [{onboard_object.gtm_replacement_count}] references to gtm. Using {onboard_object.gtm_domain}')

        else:
            if re.search(reg, onboard_object.gtm_domain):
                logger.error(f'{space}{emoji.thumbdown} {onboard_object.gtm_domain} contains invalid character. Only alphanumeric (a-z, A-Z, 0-9) and hyphen (-) characters are supported.')
                count += 1
                gtm_domain_error_count += 1
            if (onboard_object.gtm_domain[0] == '-') or (onboard_object.gtm_domain[-1] == '-'):
                logger.error(f'{space}{emoji.thumbdown} {onboard_object.gtm_domain} cannot begin or end with a hyphen.')
                count += 1
                gtm_domain_error_count += 1

            if not onboard_object.gtm_domain.endswith('.akadns.net'):
                logger.error('Domain must end with akadns.net')
                count += 1
                gtm_domain_error_count += 1

        if gtm_domain_error_count == 0:
            logger.info(f'{space}{emoji.tada} valid gtm domain ')

        # check if property name exists
        print()
        logger.warning(f'{emoji.looking} Validating all {len(onboard_object.property_list)} property names')
        for property in onboard_object.property_list:
            width = column_width - len(property)
            if width < 0:
                msg = f'{property}'
            else:
                msg = f'{property}{space:>{width}}'
            if wrapper_object.property_exists(property):
                logger.error(f'{space}{emoji.thumbdown} {msg}invalid property name; already in use {emoji.shrug}')
                count += 1
            else:
                logger.info(f'{space}{emoji.thumbup} {msg}')

        # if activating pm to prod, must active to staging first
        print()
        logger.warning(f'{emoji.looking} Validating activation details')
        if onboard_object.activate_property_production:
            if onboard_object.activate_property_staging is True:
                width = column_width - len('Activating on STAGING')
                msg = f'Activating on STAGING{space:>{width}}'
                logger.info(f'{space}{emoji.pass_green} {msg}')

                width = column_width - len('Activating on PRODUCTION')
                msg = f'Activating on PRODUCTION{space:>{width}}'
                logger.info(f'{space}{emoji.pass_green} {msg}')
            else:
                logger.error(f'{space}{emoji.fail}Must activate property to STAGING before activating to PRODUCTION')
                count += 1
        elif onboard_object.activate_property_staging:
            width = column_width - len('Activating on STAGING only')
            msg = f'Activating on STAGING only{space:>{width}}'
            logger.info(f'{space}{emoji.pass_green} {msg}')

        else:
            width = column_width - len('No activations set')
            msg = f'No activations set{space:>{width}}'
            logger.info(f'{space}{emoji.attention} {msg}')

        print()
        logger.warning(f'{emoji.looking} Validating product, group and contract details')
        # validate product id available per contract

        for product in onboard_object.product_list:
            product_detail = self.validateProductId(wrapper_object,
                                                    onboard_object.contract_id,
                                                    product)
            if product_detail['Found']:
                logger.info(f'{space}{emoji.thumbup} {product}{space:>{column_width - len(product)}}valid product_id')
                logger.info(f'{space}{emoji.thumbup} {onboard_object.contract_id}{space:>{column_width - len(onboard_object.contract_id)}}valid contract_id')
                # entitlement relies on contract, not group
                # logger.info(f'{space}{emoji.thumbup} {onboard_object.group_id}{space:>{column_width - len(onboard_object.group_id)}}valid group_id')
            else:
                logger.error(f'{space}{emoji.thumbdown} {product}{space:>{column_width - len(product)}}invalid product_id')
                logger.warning(f'Available valid product_id for contract {onboard_object.contract_id}')
                count += 1
                products_list = sorted(product_detail['products'])
                for p in products_list:
                    logger.warning(p)

        print()
        # network must be either STANDARD_TLS or ENHANCED_TLS
        logger.warning(f'{emoji.looking} Validating network')
        if onboard_object.secure_network not in ['STANDARD_TLS', 'ENHANCED_TLS']:
            width = column_width - len(onboard_object.secure_network)
            msg = f'{onboard_object.secure_network}{space:>{width}}'
            logger.error(f'{emoji.thumbdown} {msg}invalid secure_network')
            count += 1
        else:
            logger.info(f'{space}{emoji.tada} {onboard_object.secure_network}')

        print()
        logger.warning(f'{emoji.looking} Validating edge hostname setup')
        # must be one of three valid modes
        edgeHostnameList = onboard_object.edge_hostname_list
        valid_modes = [EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME, EdgeHostnameMode.SECURE_BY_DEFAULT, EdgeHostnameMode.CREATE_CPS_EDGEHOSTNAME, EdgeHostnameMode.CPS_PLACEHOLDER]
        width = column_width - len(onboard_object.edge_hostname_mode)
        msg = f'{onboard_object.edge_hostname_mode}{space:>{width}}'
        logger.info(f'{space}{emoji.pushpin} {msg}edge hostname mode')

        # Validate edge hostname format locally (no HAPI API calls)
        # PAPI will validate on hostname assignment, and SBD creates missing edge hostnames on activation
        if onboard_object.edge_hostname_mode == EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME:
            for edgeHostname in edgeHostnameList:
                edgeHostname_log = column_width - len(edgeHostname) - 1
                if edgeHostname_log < 0:
                    edgeHostname_log = f'{edgeHostname}'
                else:
                    edgeHostname_log = f'{edgeHostname}{space:>{edgeHostname_log}}'

                if edgeHostname.endswith(('edgekey.net', 'edgesuite.net', 'akamaized.net')):
                    logger.info(f'{space}{emoji.thumbup} {edgeHostname_log} edge hostname format valid')
                else:
                    logger.error(f'{space}{emoji.thumbdown} {edgeHostname_log} invalid edge hostname suffix')
                    count += 1
        elif onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
            for edgeHostname in edgeHostnameList:
                edgeHostname_log = column_width - len(edgeHostname) - 1
                if edgeHostname_log < 0:
                    edgeHostname_log = f'{edgeHostname}'
                else:
                    edgeHostname_log = f'{edgeHostname}{space:>{edgeHostname_log}}'

                if edgeHostname.endswith(('edgekey.net', 'edgesuite.net')):
                    logger.info(f'{space}{emoji.thumbup} {edgeHostname_log} will be created upon property activation')
                else:
                    logger.warning(f'{space}{emoji.construction} {edgeHostname_log} does not end with edgekey.net or edgesuite.net, using {edgeHostname}')
        elif onboard_object.edge_hostname_mode == EdgeHostnameMode.CREATE_CPS_EDGEHOSTNAME:
            logger.info(f'{space}{emoji.pushpin} CPS_MANAGED: edge hostnames will be created per property using enrollment ID {onboard_object.enrollment_id}')
        elif onboard_object.edge_hostname_mode == EdgeHostnameMode.CPS_PLACEHOLDER:
            logger.info(f'{space}{emoji.pushpin} CPS_MANAGED: placeholder edge hostnames will be assigned (no enrollment ID provided)')

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
                        logger.error(f'{emoji.thumbdown} {email}{space:>{column_width - len(email)}}invalid email address')
                        count += 1

        if count == 0:
            self.valid is True
            if not onboard_object.iteractive_mode:
                print()
                print('_' * 120)
                print()
                logger.warning('Please review all settings. Do you want to proceed? (yes/no)')
                print('_' * 120)
                string = str(confirm_input())
                proceed_variations = ['yes', 'y', 'Y', 'YES', 'Yes']
                if string in proceed_variations:
                    logger.warning(f'{emoji.ok_hand} Proceeding with Onboarding')
                    print()
                else:
                    sys.exit(logger.info(f'{emoji.disappointed} ...Exiting...{emoji.disappointed}'))

        else:
            print()
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
        valid_modes = [EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME, EdgeHostnameMode.NEW_STANDARD_TLS_EDGEHOSTNAME, EdgeHostnameMode.NEW_ENHANCED_TLS_EDGEHOSTNAME, EdgeHostnameMode.SECURE_BY_DEFAULT]
        logger.info(f'{onboard_object.edge_hostname_mode}{space:>{column_width - len(onboard_object.edge_hostname_mode)}}edge hostname mode')
        if onboard_object.edge_hostname_mode not in valid_modes:
            logger.error(f'{onboard_object.edge_hostname_mode}{space:>{column_width - len(onboard_object.edge_hostname_mode)}}invalid edge_hostname_mode')
            count += 1
            logger.info('valid options: use_existing_edgehostname, new_standard_tls_edgehostname, new_enhanced_tls_edgehostname')
        elif onboard_object.edge_hostname_mode == EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME:
            ehn_id = 0
            if onboard_object.edge_hostname == '':
                logger.error(f'{onboard_object.edge_hostname}{space:>{column_width - len(onboard_object.edge_hostname)}}missing edge hostname')
                count += 1
            else:
                try:
                    # check to see if specified edge hostname exists
                    ehn_id = self.validateEdgeHostnameExists(wrapper_object, str(onboard_object.edge_hostname))
                    public_hostname_str = ', '.join(onboard_object.public_hostnames)
                    logger.info(f'ehn_{ehn_id}{space:>{column_width - len(str(ehn_id)) - 4}}valid edge_hostname_id')
                    logger.info(f'{onboard_object.edge_hostname}{space:>{column_width - len(onboard_object.edge_hostname)}}valid edge hostname')
                    if column_width - len(public_hostname_str) <= 0:
                        logger.info(f'{public_hostname_str} valid public hostname')
                    else:
                        logger.info(f'{public_hostname_str}{space:>{column_width - len(public_hostname_str)}}valid public hostname')
                    onboard_object.edge_hostname_id = ehn_id
                except:
                    logger.error(f'{onboard_object.edge_hostname}{space:>{column_width - len(onboard_object.edge_hostname)}}invalid edge hostname')
                    count += 1
        elif onboard_object.edge_hostname_mode == EdgeHostnameMode.NEW_STANDARD_TLS_EDGEHOSTNAME:
            if onboard_object.secure_network != 'STANDARD_TLS':
                logger.error('For new_standard_tls_edgehostname, secure_network must be STANDARD_TLS')
                count += 1
        elif onboard_object.edge_hostname_mode == EdgeHostnameMode.NEW_ENHANCED_TLS_EDGEHOSTNAME:
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
        elif onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
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
                    logger.info(f'ehn_{ehn_id}{space:>{column_width - len(str(ehn_id)) + 4}}valid edge_hostname_id')
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
                    _, target_ids, _ = wrapper_object.list_match_targets(onboard_object.onboard_waf_config_id,
                                                                        onboard_object.onboard_waf_prev_version,
                                                                        policies)
                    if onboard_object.waf_match_target_id in target_ids:
                        for k in policies:
                            if onboard_object.waf_match_target_id in policies[k]:
                                logger.info(f'{policies[k][0]}{space:>{column_width - len(policies[k][0])}}found existing policy')
                                logger.info(f'{onboard_object.waf_match_target_id}{space:>{column_width - len(str(onboard_object.onboard_waf_config_id)) - 2}}found existing onboard_waf_config_id')
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

    def validateAppsecSteps(self, onboard_object, wrapper_object, cli_mode='appsec-update'):
        """
        Function to validate inputs for appsec-update
        """

        count = 0
        valid_waf = True
        print()
        logger.warning('Validating inputs. Please wait, may take a few moments')

        # check if csv is valid
        if not onboard_object.valid_csv:
            logger.error(f'{onboard_object.csv:<30}{space:>20}invalid CSV file; check above validation errors')
            count += 1

        if cli_mode in ['appsec-update', 'appsec-remove']:
            # check if config id exists
            msg = f'{onboard_object.config_id}{space:>{column_width - len(onboard_object.config_id)}}'
            appsec_configs = wrapper_object.getWafConfigurations()
            if appsec_configs.status_code == 200:
                appsec_configs = appsec_configs.json()
            else:
                sys.exit(logger.error('unable to get waf configurations....'))
            try:
                appsec_config_exists = list(filter(lambda x: int(x['id']) == int(onboard_object.config_id), appsec_configs['configurations']))
            except KeyError:
                sys.exit(logger.error('unable to get waf configurations....'))

            # return list of valid appsec ids if appsec id invalid
            if not appsec_config_exists:
                logger.error(f'{msg}invalid config id')
                valid_waf = False
                count += 1
                # listing valid waf configs and ids
                logger.warning('Showing all available configs...')
                logger.info(f'Config Name:{space:>38}Config Id:')
                for waf_config in appsec_configs['configurations']:
                    logger.info(f"{waf_config['name']}{space:>{column_width - len(waf_config['name'])}}{waf_config['id']}")
                sys.exit(logger.error('Exiting....'))
            else:
                onboard_object.waf_config_name = appsec_config_exists[0]['name']
                logger.info(f'{onboard_object.waf_config_name} {space:>{column_width - (len(onboard_object.waf_config_name))}}valid config name')
                logger.info(f'{onboard_object.config_id} {space:>{column_width - (len(onboard_object.config_id))}}valid config id')

            # check if config id base version exists
            if valid_waf:
                msg = f'{onboard_object.onboard_waf_prev_version}{space:>{column_width - len(onboard_object.onboard_waf_prev_version)}}'
                if onboard_object.onboard_waf_prev_version == 'latest':
                    onboard_object.onboard_waf_prev_version = appsec_config_exists[0]['latestVersion']
                    logger.info(f'{msg} using config id version {onboard_object.onboard_waf_prev_version}')
                else:
                    if int(onboard_object.onboard_waf_prev_version) > appsec_config_exists[0]['latestVersion']:
                        logger.error(f'{msg} invalid config version')
                        count += 1
                        valid_waf = False
                    else:
                        logger.info(f'{msg} valid config id version')

            # check if policy match targets are valid
            if valid_waf:
                # first get all policies
                policies = wrapper_object.get_waf_policy_update(onboard_object.config_id, onboard_object.onboard_waf_prev_version)

                if policies:
                    resp, waf_match_target_ids, _ = wrapper_object.list_match_targets(onboard_object.config_id, onboard_object.onboard_waf_prev_version, policies)
                    if resp.status_code != 200:
                        sys.exit(logger.error('unable to get waf match targets....'))
                    if cli_mode != 'appsec-remove':
                        unique_match_target_list = list(set(list(map(lambda x: x['matchTargetId'], onboard_object.csv_dict))))
                        for unique_match_target in unique_match_target_list:
                            msg = f'{unique_match_target}{space:>{column_width - len(unique_match_target)}}'
                            if int(unique_match_target) in waf_match_target_ids:
                                logger.info(f'{msg} valid match target id')
                            else:
                                logger.error(f'{msg} invalid match target id')
                                count += 1
                else:
                    sys.exit(logger.error('unable to get waf policies....'))

                # validate that hostnames are either already selected or selectable
                available_hostnames = wrapper_object.getWAFSelectableHosts(onboard_object.config_id, onboard_object.onboard_waf_prev_version)
                selectable_hosts_list = list(set(list(map(lambda x: x['hostname'], available_hostnames['availableSet']))))
                try:
                    selected_host_list = list(set(list(map(lambda x: x['hostname'], available_hostnames['selectedSet']))))
                except KeyError:
                    selected_host_list = []

                if cli_mode == 'appsec-remove':
                    onboard_object.existing_selected_hosts = selected_host_list

                else:
                    if available_hostnames:
                        logger.debug(f'{onboard_object.hostname_list=}')
                        logger.debug(f'{selectable_hosts_list=}')
                        logger.debug(f'{selected_host_list=}')
                        for hostname in onboard_object.hostname_list:
                            if column_width - len(hostname) < 0:
                                msg = hostname
                            else:
                                msg = f'{hostname}{space:>{column_width - len(hostname)}}'
                            if hostname in selectable_hosts_list:
                                logger.info(f'{msg} valid selectable hostnames')
                            elif hostname in selected_host_list:
                                logger.warning(f'{msg} existing hostname')
                            else:
                                count += 1
                                logger.error(f'{msg} invalid selectable hostnames')
                                onboard_object.skip_selected_hosts.append(hostname)
                    else:
                        sys.exit(logger.error('unable to get available hostnames'))

        if not self.validate_email(onboard_object.notification_emails):
            count += 1

        if count == 0:
            self.valid is True
            print()
            logger.warning('Updating Appsec Config')
        else:
            sys.exit(logger.error(f'Total {count} errors, please review'))

        return self.valid

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
            logger.error(f'Product validation failed with status {get_products_response.status_code}')
            try:
                logger.debug(json.dumps(get_products_response.json(), indent=4))
            except Exception:
                logger.debug(get_products_response.text[:500])

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
                shutil.copytree(onboard_object.folder_path, 'temp_pm')

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

            rows_reader = csv.reader(f, delimiter=', ')
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
            onboard.group_id = setup.group_id
            onboard.secure_network = 'STANDARD_TLS' if setup.edge_hostname.endswith('edgesuite.net') else onboard.secure_network
            template_path = f'{root}/templates/akamai_product_templates'
            onboard.source_values_file = f'{template_path}/single_variable.json'
        elif cli_mode == 'multi-hosts':
            onboard.group_id = setup.group_id
            template_path = f'{root}/templates/akamai_product_templates/multi-hosts'
            onboard.source_values_file = f'{template_path}/variables.json'

        onboard.source_template_file = f'{template_path}/{setup.product_id}.json'
        logger.info(f'Rule Template Location: {onboard.source_template_file}')
        onboard.create_new_security_config = setup.create_new_security_config
        if len(setup.waf_config_name) > 0:
            onboard.waf_config_name = setup.waf_config_name
        if setup.existing_enrollment_id > 0:
            onboard.use_existing_enrollment_id = True
            onboard.edge_hostname_mode = EdgeHostnameMode.NEW_ENHANCED_TLS_EDGEHOSTNAME
            onboard.existing_enrollment_id = setup.existing_enrollment_id
        if not (setup.version_notes == ''):
            onboard.version_notes = setup.version_notes
        if not setup.activate_production:
            onboard.activate_property_production = False
            onboard.activate_waf_policy_production = False
        if onboard.secure_by_default:
            onboard.edge_hostname_mode = EdgeHostnameMode.SECURE_BY_DEFAULT

    def json_input_file_validator(self, onboard_object, prefix: str):

        for hostname in onboard_object.csv_dict:
            try:
                if prefix:
                    sub = len(prefix)
                    filename = f'{hostname['templateName'][sub:]}.json'
                else:
                    filename = f'{hostname['templateName']}.json'
            except KeyError:
                filename = f'{hostname['hostname']}.json'

            if not self.validateFile('json file', f'{onboard_object.source_directory}/{filename}'):
                width = column_width - len(filename)
                if width < 0:
                    msg = f'{filename}'
                else:
                    msg = f'{filename}{space:>{width}}'
                host_name = hostname['hostname']
                logger.error(f'{space}{emoji.thumbdown} {msg}missing ruletree json file for hostname {host_name}')
                onboard_object.all_template_json_exists = False
            else:
                hostname['jsonFile'] = filename
        return onboard_object.all_template_json_exists

    def load_csv_input(self, filepath: str, function: str) -> list:
        if function == 'delete':
            valid, output = self.csv_validator_delete(filepath)
        elif function == 'add_hostname':
            valid, output = self.csv_validator_addhostname(filepath)
        elif function == 'convert':
            valid, output = self.csv_validator_convert(filepath)
        elif function == 'activate':
            valid, output = self.csv_validator_activate(filepath)

        if not valid:
            sys.exit(logger.error('Invalid data found in CSV input'))
        return output

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

        logger.warning(f'Reading customer property name input: {csv_file_loc}')

        with open(csv_file_loc, encoding='utf-8-sig', newline='') as f:
            for i, row in enumerate(csv.DictReader(f), 1):
                csv_dict.append(row)
                try:
                    validate(instance=row, schema=schema)
                except ValidationError as e:
                    onboard_object.valid_csv = False
                    logger.warning(f'CSV Validation Error in row: {i} - {e}')

        onboard_object.csv_dict = csv_dict
        return onboard_object.valid_csv

    def csv_validator_convert(self, csv_file_loc: str) -> tuple:
        schema = {
            'hostname': {
                'type': 'string',
                'required': True,
                'empty': False
            },
            'propertyName': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'product': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'edgeHostname': {
                'type': 'string',
                'required': False,
                'regex': (r'(.*\.edgekey\.net$|.*\.edgesuite\.net$|.*\.akamaized\.net$)'),
                'empty': True
            },
            'secureNetwork': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'AN': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'GroupID': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'orgId': {
                'type': 'string',
                'required': False,
                'empty': True
            }
        }

        logger.warning(f'{emoji.bow} Fetching properties')
        error_count, data_output = self.cerberus_validator(schema, csv_file_loc)
        if error_count > 0:
            return False, data_output
        else:
            return True, data_output

    def csv_validator_delete(self, csv_file_loc: str) -> tuple:
        schema = {
            'propertyName': {
                'type': 'string',
                'required': True,
                'empty': False
            },
            'hostname': {
                'type': 'string',
                'required': False,
                'empty': False
            },
            'product': {
                'type': 'string',
                'required': False,
                'empty': False
            },
            'network': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'version': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'propertyId': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'activation_id': {
                'type': 'string',
                'required': False,
                'empty': True
            },
            'activation_status': {
                'type': 'string',
                'required': False,
                'empty': True
            }
        }

        error_count, temp1 = self.cerberus_validator(schema, csv_file_loc)

        temp2 = [{'propertyName': x['propertyName']} for x in temp1]
        data_output = []
        seen_names = set()
        for item in temp2:
            property_name = item['propertyName']
            if property_name not in seen_names:
                data_output.append({'propertyName': property_name})
                seen_names.add(property_name)

        if error_count > 0:
            return False, data_output
        else:
            logger.warning(f'{emoji.bow} Fetching {len(data_output)} properties')
            return True, data_output

    def csv_validator_smoke_test(self, onboard_object, csv_file_loc: str):
        schema = {
            'hostname': {
                'type': 'string',
                'required': True,
                'empty': False
            },
            'scope': {
                'type': 'string',
                'required': True,
                'empty': True
            },
            'cpcode': {
                'type': 'string'
            }
        }

        logger.warning(f'{emoji.gem} Using Smoke-test input file: {csv_file_loc}')
        error_count, onboard_object.csv_dict = self.cerberus_validator(schema, csv_file_loc)

        if error_count > 0:
            onboard_object.valid_csv = False
        else:
            onboard_object.valid_csv = True

        return onboard_object.valid_csv

    def csv_validator_appsec(self, onboard_object, csv_file_loc: str):
        csv_dict = []
        schema = {
            'hostname': {
                'type': 'string',
                'required': True,
                'empty': False
            },
            'matchTargetId': {
                'required': False,
                'empty': True
            }
        }

        logger.warning(f'Reading csv input: {csv_file_loc}')

        with open(csv_file_loc, encoding='utf-8-sig', newline='') as f:
            for i, row in enumerate(csv.DictReader(f), 1):
                csv_dict.append(row)
                try:
                    validate(instance=row, schema=schema)
                except ValidationError as e:
                    onboard_object.valid_csv = False
                    logger.warning(f'CSV Validation Error in row: {i} - {e}')

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
                    if onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
                        edgeHostnameList.append(f'{hostname}{ehn_suffix}')
                        logger.debug(f'edgeHostname value is empty - using edge hostname {hostname}{ehn_suffix}')
                    else:
                        sys.exit(logger.error(f'No edgeHostname provided for {hostname} - row:{i + 1}'))
                else:
                    edgeHostnameList.append(edgeHostname)
            except KeyError:
                if onboard_object.edge_hostname_mode == EdgeHostnameMode.SECURE_BY_DEFAULT:
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

    def insert_gtm_hostname(self, data, target, replacement, count=0):
        """
        Recursively replaces all occurrences of a target value in a nested JSON object.

        Args:
            data (dict, list, str): The JSON object.
            target (str): The value to replace.
            replacement (str): The value to replace with.

        Returns:
            dict, list, or str: The modified JSON object.
        """

        if isinstance(data, dict):
            new_data = {}
            for key, value in data.items():
                new_data[key], count = self.insert_gtm_hostname(value, target, replacement, count)
            return new_data, count
        elif isinstance(data, list):
            new_list = []
            for item in data:
                modified_item, count = self.insert_gtm_hostname(item, target, replacement, count)
                new_list.append(modified_item)
            return new_list, count
        elif isinstance(data, str) and target in data:
            count += data.count(target)
            return data.replace(target, replacement), count
        return data, count

    def csv_2_property_array_convert(self, onboard_object, prefix) -> dict:
        propertyJson = {}
        for i, row in enumerate(onboard_object.csv_dict):
            logger.debug(f'{row=}')
            if prefix:
                templateFile = f'{onboard_object.source_directory}/{row['templateName'][len(prefix):]}.json'
            else:
                templateFile = f'{onboard_object.source_directory}/{row['templateName']}.json'
            # group by propertyName
            propertyName = row['propertyName']
            edgeHostname = onboard_object.edge_hostname_list[i]
            try:
                with open(templateFile) as file:
                    templateData = json.load(file)
            except FileNotFoundError:
                logger.error(f"Template file not found: {templateFile}")
                continue

            # replace all gtm references with GTM hostname

            templateData, gtm_replacement_count = self.insert_gtm_hostname(templateData, 'gtm_edgio_replace_me.akadns.net', onboard_object.gtm_domain if onboard_object.gtm_domain else (f'{(onboard_object.ASK.replace(':', '-')).lower()}.akadns.net'))
            onboard_object.gtm_replacement_count = onboard_object.gtm_replacement_count + gtm_replacement_count

            if (propertyName is None) or (propertyName == ''):
                logger.warning(propertyName)
                propertyName = row['hostname']

            # check to see if property already exists in dict
            # if it does, add hostname, origins, ehns, to hostname dict and move on to next row
            else:
                if propertyName in propertyJson.keys():
                    hostname = row['hostname']
                    propertyJson[propertyName]['hostnames'].append(hostname)
                    propertyJson[propertyName]['edgeHostnames'].append(edgeHostname)
                    try:
                        secureNetwork = row['secureNetwork']
                        propertyJson[propertyName]['secureNetwork'].append(secureNetwork)
                    except KeyError:
                        msg = 'no secureNetwork column'
                    continue

            propertyJson[propertyName] = {}
            propertyJson[propertyName]['ruleTree'] = templateData
            propertyJson[propertyName]['product'] = row['product']
            if row.get('GroupID'):
                propertyJson[propertyName]['group'] = row['GroupID']
            hostname = row['hostname']
            propertyJson[propertyName]['hostnames'] = [hostname]
            propertyJson[propertyName]['edgeHostnames'] = [edgeHostname]
            try:
                secureNetwork = row['secureNetwork']
                propertyJson[propertyName]['secureNetwork'] = [secureNetwork]
            except:
                msg = 'no secureNetwork column'
        '''
        for prop, value in propertyJson.items():
            keys = propertyJson[prop].keys()
            for key in keys:
                if key != 'ruleTree':
                    data = propertyJson[prop][key]
                    logger.debug(f'{prop:<30} {key:<20} {data}')
        '''

        return propertyJson

    def csv_2_property_dict_convert(self, onboard_object) -> tuple:
        propertyList = []
        hostnameList = []
        edgeHostnameList = []
        secureNetworkList = []
        productList = []
        ehn_suffix = onboard_object.ehn_suffix
        if onboard_object.secure_network == 'STANDARD_TLS':
            ehn_suffix = '.edgesuite.net'

        for i, row in enumerate(onboard_object.csv_dict):
            try:
                propertyName = row['propertyName']
                row['templateName'] = row['propertyName']
                propertyName = propertyName.replace(' ', '_')
                row['propertyName'] = propertyName
                if (propertyName is None) or (propertyName == ''):
                    propertyName = row['hostname']
                    row['propertyName'] = propertyName
                    row['templateName'] = propertyName
            except KeyError:
                propertyName = row['hostname']
                row['propertyName'] = propertyName
                row['templateName'] = propertyName

            hostname = row['hostname']
            hostnameList.append(hostname)
            propertyList.append(propertyName)
            try:
                secureNetworkList.append(row['secureNetwork'])
            except KeyError:
                msg = 'csv does not have KeyError column'

            try:
                product = row['product']
                if not product.startswith('prd_'):
                    product = f'prd_{product}'
                    row['product'] = product
                if (product is None) or (product == ''):
                    product = 'prd_Site_Accel'
                    row['product'] = product
            except KeyError:
                product = 'prd_Site_Accel'
                row['product'] = product

            if product not in productList:
                productList.append(product)

            try:
                if row['secureNetwork'] == 'SHARED_CERT':
                    ehn_suffix = '.akamaized.net'
                elif row['secureNetwork'] == 'STANDARD_TLS':
                    ehn_suffix = '.edgesuite.net'
                elif row['secureNetwork'] == 'ENHANCED_TLS':
                    ehn_suffix = '.edgekey.net'
                else:
                    ehn_suffix = '.edgesuite.net'  # default
            except KeyError:
                msg = 'csv does not have KeyError column'

            try:
                edgeHostname = row['edgeHostname']
                if (edgeHostname is None) or (edgeHostname == ''):
                    if onboard_object.edge_hostname_mode in (EdgeHostnameMode.SECURE_BY_DEFAULT, EdgeHostnameMode.CREATE_CPS_EDGEHOSTNAME, EdgeHostnameMode.CPS_PLACEHOLDER):
                        edgeHostnameList.append(f'{hostname}{ehn_suffix}')
                        logger.debug(f'using edge hostname {hostname}{ehn_suffix}')
                    else:
                        sys.exit(logger.error(f'No edgeHostname provided for {hostname} - row:{i + 1}'))
                else:
                    edgeHostnameList.append(edgeHostname)
            except KeyError:
                if onboard_object.edge_hostname_mode in (EdgeHostnameMode.SECURE_BY_DEFAULT, EdgeHostnameMode.CREATE_CPS_EDGEHOSTNAME, EdgeHostnameMode.CPS_PLACEHOLDER):
                    edgeHostnameList.append(f'{hostname}{ehn_suffix}')
                    logger.debug(f'using edge hostname {hostname}{ehn_suffix}')
                else:
                    sys.exit(logger.error('edgeHostname column must exist in input csv unless using secure-by-default or CPS mode'))

        propertyList = list(set(propertyList))
        hostnameList = list(set(hostnameList))

        onboard_object.edge_hostname_list = edgeHostnameList
        onboard_object.property_list = propertyList
        onboard_object.public_hostnames = hostnameList
        onboard_object.product_list = productList

        logger.debug(f'{propertyList} {hostnameList}')
        return (propertyList, hostnameList)

    def csv_2_appsec_create_by_hostname(self, csv_file_loc: str):
        schema = {'waf_config_name': {'type': 'string',
                                      'empty': False,
                                      'required': False},
                  'waf_policy_name': {'type': 'string',
                                      'empty': False,
                                      'required': False},
                  'hostname': {'type': 'string',
                               'empty': False,
                               'required': False}}

        logger.warning(f'Reading customer security configuration input: {csv_file_loc}')
        error_count, data_output = self.cerberus_validator(schema, csv_file_loc)

        if error_count > 0:
            return False, data_output
        else:
            return True, data_output

    def csv_2_appsec_create_by_propertyname(self, csv_file_loc: str):
        schema = {'property_name': {'type': 'string',
                                    'empty': False,
                                    'required': True},
                  'waf_config_name': {'type': 'string',
                                      'empty': False,
                                      'required': True},
                  'waf_policy_name': {'type': 'string',
                                       'empty': False,
                                       'required': True},
                  'hostname': {'type': 'string',
                               'nullable': True,
                               'required': False}
                 }
        logger.warning(f'Reading customer security configuration input: {csv_file_loc}')
        error_count, data_output = self.cerberus_validator(schema, csv_file_loc)

        if error_count > 0:
            return False, data_output
        else:
            return True, data_output

    def cerberus_validator(self, schema: dict, csv_file_loc: str) -> tuple:
        v = Validator(schema)
        error_count = 0
        data_output = []
        try:
            with open(csv_file_loc, encoding='utf-8-sig', newline='') as f:
                for i, row in enumerate(csv.DictReader(f), 1):
                    data_output.append(row)
                    self.valid = v.validate(row)
                    validation_errors = v.errors
                    if validation_errors:
                        self.valid = False
                        logger.warning(f'CSV Validation Error in row: {i}...')
                        for error in validation_errors:
                            logger.warning(f'{error} {validation_errors[error]}')
                            error_count += 1
        except FileNotFoundError as e:
            print()
            sys.exit(logger.error(e, exc_info=False))

        return error_count, data_output

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
        reg = re.compile(r'[^\.\-\*a-zA-Z0-9]')
        error_count = 0
        for hostname in hostnames:
            if re.search(reg, hostname):
                logger.error(f'{hostname} contains invalid character. Only alphanumeric (a-z, A-Z, 0-9), hyphen (-) and asterisk (*) characters are supported.')
                error_count += 1
            if len(hostname) > 60 and len(hostname) < 4:
                logger.error(f'{hostname} is invalid length. Hostname length must be between 4-60 characters')
                error_count += 1
            if (hostname[0] == '-') or (hostname[-1] == '-'):
                logger.error(f'{hostname} cannot begin or end with a hyphen.')
                error_count += 1
        return error_count

    def csv_2_appsec_array(self, onboard_object, delete=False) -> dict:
        hostname_list = []
        appsec_json = {}

        if delete:
            for i, row in enumerate(onboard_object.csv_dict):

                hostname_list.append(row['hostname'])

        else:
            for i, row in enumerate(onboard_object.csv_dict):
                policyName = row['matchTargetId']
                # Check if policyName already exists in dictionary and append hostname to list
                if policyName in appsec_json.keys():
                    appsec_json[policyName]['hostnames'].append(row['hostname'])
                    hostname_list.append(row['hostname'])

                # If policy doesn't already exist in dict, add policy to dictionary and add hostname to list
                else:
                    appsec_json[policyName] = {}
                    appsec_json[policyName]['hostnames'] = [row['hostname']]
                    hostname_list.append(row['hostname'])

            onboard_object.appsec_json = appsec_json

        onboard_object.hostname_list = hostname_list

    def validate_waf_config_name(self, wrapper_object, config_name: str | None = None) -> int:
        if config_name:
            config_detail = self.getWafConfigIdByName(wrapper_object, config_name)
            if config_detail['Found']:
                onboard_waf_config_id = config_detail['details']['id']
                onboard_waf_prev_version = config_detail['details']['latestVersion']
                logger.info(f'{config_name}{space:>{column_width - len(config_name)}}valid waf_config_name')
                logger.info(f'{onboard_waf_config_id}{space:>{column_width - len(str(onboard_waf_config_id))}}found existing onboard_waf_config_id')
                logger.info(f'{onboard_waf_prev_version}{space:>{column_width - len(str(onboard_waf_prev_version))}}found latest onboard_waf_prev_version')
            else:
                sys.exit(logger.error(f'{config_name}{space:>{column_width - len(config_name)}}invalid waf_config_name, not found'))
            return onboard_waf_config_id, onboard_waf_prev_version, pd.DataFrame()
        else:
            onboard_waf_config_id = 0
            onboard_waf_prev_version = 0
            response = wrapper_object.getWafConfigurations()
            df = pd.DataFrame(response.json()['configurations'])
            df.fillna('', inplace=True)
            return onboard_waf_config_id, onboard_waf_prev_version, df

    def list_waf_policy(self, wrapper_object, config_id, version, policy_name: str | None = None) -> str:
        _, policies = wrapper_object.get_waf_policy_from_config(config_id, version)
        if not policies:
            sys.exit(logger.error('This configuration does not have any policy'))
        else:
            df = pd.DataFrame.from_dict(policies, orient='index')
            df.index.name = 'Policy ID'
            df.columns = ['Policy Name']
            df.sort_values(by='Policy Name', inplace=True)
            if not policy_name:
                policy_str_id = ''
                # logger.warning('Security Policy')
                # print(tabulate(df, headers='keys', tablefmt='psql', showindex=True))
            else:
                try:
                    policy_str_id = list(filter(lambda x: policies[x] == [policy_name], policies))[0]
                    logger.info(f'{policy_name}{space:>{column_width - len(policy_name)}}valid policy name')
                    logger.info(f'{policy_str_id}{space:>{column_width - len(policy_str_id)}}found policy id')
                except:
                    # show all policies instead
                    print(tabulate(df, headers='keys', tablefmt='psql', showindex=True))
                    logger.warning(f'policy name "{policy_name}" not found.  Name must be exact match.')
                    return None, policies
        return policy_str_id, policies

    def populate_waf_data(self, by: str, input: dict) -> dict:
        waf = []

        for i in input['waf_config_name'].unique():
            config = {}
            waf_policy_name = sorted(list({input['waf_policy_name'][j] for j in input[input['waf_config_name'] == i].index}))
            config['waf_config_name'] = i
            for policy in waf_policy_name:
                new_df = input[(input['waf_config_name'] == i) & (input['waf_policy_name'] == policy)]
                if by == 'propertyname':
                    combined_hostnames = new_df['hostname'].values
                    hostnames = [item for sublist in combined_hostnames for item in sublist]
                    combined_waf_target_hostnames = new_df['waf_target_hostname'].values
                    waf_target_hostnames = [item for sublist in combined_waf_target_hostnames for item in sublist]
                if by == 'hostname':
                    hostnames = new_df['hostname'].unique().tolist()
                    waf_target_hostnames = []
                config[policy] = (hostnames, waf_target_hostnames)
            waf.append(config)
        return waf

    def stringToList(self, input):
        try:
            if isinstance(input, list):
                newList = input
            elif isinstance(input, str) and len(input) != 0:
                tempList = input.split(', ')
                newList = list(map(lambda x: x, tempList))
            else:
                newList = []
        except:
            newList = None
        return (newList)

    def validate_email(self, emails: list) -> bool:
        if len(emails) > 0:
            for email in emails:
                if not is_email(email):
                    logger.error(f'{email}{space:>{column_width - len(email)}}invalid email address')
                    return False
        return True

    def validate_appsec_pre_create(self, main_object, wrap_api, util_waf, selectable_df):
        """
        Function to validate inputs for appsec-create
        """
        count = 0
        by = main_object.template
        csv = main_object.csv
        activate = main_object.activate
        network = main_object.network
        contract_id = main_object.contract_id
        group_id = main_object.group_id

        if main_object.template == 'propertyname':
            valid_csv, data = self.csv_2_appsec_create_by_propertyname(csv)
        else:
            valid_csv, data = self.csv_2_appsec_create_by_hostname(csv)
        if valid_csv is False:
            logger.error('CSV input needs to be corrected first')
            count += 1
            sys.exit()

        logger.warning('Validating inputs. Please wait, may take a few moments')
        df = pd.DataFrame(data)
        logger.debug(f'\nIncoming data\n{df}')

        if by == 'hostname':
            waf = self.populate_waf_data(by, df)
        else:
            df.insert(0, 'property_version', '')
            df.insert(0, 'property_id', '')
            all_property = df.property_name.unique()
            logger.debug(all_property)

            # validate property
            invalid_property = []
            for property in all_property:
                if wrap_api.property_exists(property) is False:
                    invalid_property.append(property)
                else:
                    property_df = pd.DataFrame(wrap_api.get_property_id(property))
                    if not activate:
                        new_df = property_df[property_df['stagingStatus'] == 'ACTIVE']
                    else:
                        if network == 'staging':
                            new_df = property_df[property_df['stagingStatus'] == 'ACTIVE']
                        else:
                            new_df = property_df[property_df['productionStatus'] == 'ACTIVE']

                    if new_df.empty:
                        sys.exit(logger.error(f'property {property} must be activated on the {network.upper()} network first'))
                    property_id = new_df['propertyId'].values[0]
                    df.loc[df['property_name'] == property, 'property_id'] = property_id
                    df.loc[df['property_name'] == property, 'property_version'] = new_df['propertyVersion'].values[0]

            # only process valid properties
            if len(invalid_property) == 0:
                valid_property = all_property
            else:
                logger.error(f'invalid property name {invalid_property}')
                valid_property = list(set(all_property) - set(invalid_property))
                logger.debug(f'{valid_property=}')
                if len(valid_property) == 0:
                    sys.exit(logger.info('Nothing to process'))
            df = df[df['property_name'].isin(valid_property)]
            columns = ['property_name', 'waf_config_name', 'waf_policy_name', 'hostname', 'property_id', 'property_version']
            df.sort_values(by=['waf_config_name', 'property_name'], inplace=True)
            df.reset_index(drop=True, inplace=True)
            logger.debug(f'\nCleanup Round 1\n{df[columns]}')

            # populate remaining empty hostname
            if 'hostname' in df.columns:
                if not activate:
                    network = 'staging'
                df['waf_target_hostname'] = df[['property_id', 'hostname']].apply(lambda x: [] if x.hostname is None else x.hostname, axis=1)
                if 'waf_target_hostname' in df.columns:
                    columns.append('waf_target_hostname')
                    df['waf_target_hostname'] = df['waf_target_hostname'].apply(lambda x: self.stringToList(x))
                df['hostname'] = df[['property_id', 'hostname']].apply(
                    lambda x: wrap_api.get_property_hostnames(x.property_id, contract_id, group_id, network) if x.hostname is None
                    else x.hostname, axis=1)
                df['hostname'] = df['hostname'].apply(lambda x: self.stringToList(x))
                logger.debug(f'\nCleanup Round 2\n{df[columns]}')
            else:
                df.insert(0, 'hostname', '')
                hostnames = wrap_api.get_property_hostnames(property_id, contract_id, group_id, network)
                df.loc[df['property_name'] == property, 'hostname'] = df['hostname'].apply(lambda x: hostnames)

        # processing by name of WAF Security Configuration
        # logger.info('Main data')
        # print(tabulate(df[['property_id', 'waf_config_name', 'waf_policy_name', 'waf_target_hostname']], headers='keys', tablefmt='psql', showindex=True))
        waf = self.populate_waf_data(by, df)
        df = pd.DataFrame(waf)
        waf_df = df.set_index('waf_config_name')
        waf_df.fillna('', inplace=True)
        logger.debug(f'\nPivot\n{waf_df}')

        # display data on terminal
        indexes = waf_df.index.to_list()
        columns = waf_df.columns.to_list()
        df = pd.DataFrame(waf, index=indexes, columns=columns)
        show_df = df.stack()
        show_df = pd.DataFrame(df.stack()).reset_index()
        logger.debug(f'\n{show_df}')
        show_df.columns = ['waf_config_name', 'policy', 'hostname']
        show_df[['hostname', 'waf_target_hostname']] = pd.DataFrame(show_df['hostname'].tolist(), index=show_df.index)
        logger.debug(f'\n{show_df}')
        if by == 'propertyname':
            columns = ['waf_config_name', 'policy', 'waf_target_hostname']
        else:
            columns = ['waf_config_name', 'policy', 'hostname']
        logger.info(f'\n{show_df[columns].to_markdown(headers=columns, tablefmt="psql")}')

        # check duplicate waf config name
        all_waf = show_df['waf_config_name'].unique().tolist()
        for waf in all_waf:
            config_detail = self.getWafConfigIdByName(wrap_api, waf)
            if config_detail['Found']:
                count += 1
                logger.error(f'{waf}{space:>{column_width - len(waf)}}duplicate waf_config_name already exists')

        # check if hostnames are activated in another config
        # TODO: is this possible on staging?

        _, selectable_hostnames, _ = wrap_api.get_selectable_hostnames(contract_id[4:], group_id[4:], network)
        all_hostnames = sorted(list({host for hosts in show_df['hostname'].tolist() for host in hosts}))
        logger.debug(all_hostnames)
        for hostname in all_hostnames:
            if hostname not in selectable_hostnames:
                count += 1
                logger.error(f'{hostname}{space:>{column_width - len(hostname)}}invalid hostname for contract/group')

        if main_object.network:
            if not self.validate_email(main_object.notification_emails):
                count += 1

        if count == 0:
            self.valid is True
        else:
            self.valid is False
            sys.exit(logger.error(f'Total {count} errors, please review'))

        return show_df

    def write_to_csv_input(self, headers: list, rows: list, output_filepath: str, directory: str):
        dt_string = datetime.now().strftime('%Y%m%d_%H%M_')
        output_filepath = f'{directory}/{dt_string}{output_filepath}'

        try:
            with open(output_filepath, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
        except FileNotFoundError as e:
            print()
            sys.exit(logger.error(e, exc_info=False))

        return output_filepath

    def write_to_csv_output(self, headers: list, rows: list, output_filepath: str, directory: str):
        dt_string = datetime.now().strftime('%Y%m%d_%H%M_')
        output_filepath = f'{directory}/{dt_string}{output_filepath}'

        try:
            with open(output_filepath, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
        except FileNotFoundError as e:
            print()
            sys.exit(logger.error(e, exc_info=False))

        return output_filepath

    def make_xlsx_hyperlink_to_external_link(self, url: str, alias: str) -> str:
        """
        create hyperlink using excel formula
        """
        if alias:
            return f'=HYPERLINK("{url}", "{alias}")'
        else:
            return f'{url}'

    def remove_behaviors(self, json_data, target_key, target_value):
        if isinstance(json_data, dict):
            if target_key in json_data and json_data[target_key] == target_value:
                return None  # Signaling to delete this dictionary
            else:
                keys_to_delete = []
                for key, value in list(json_data.items()):
                    new_value = self.remove_behaviors(value, target_key, target_value)
                    if new_value is None:
                        keys_to_delete.append(key)
                    else:
                        json_data[key] = new_value
                for key in keys_to_delete:
                    del json_data[key]

        elif isinstance(json_data, list):
            json_data = [self.remove_behaviors(item, target_key, target_value) for item in json_data]
            json_data = [item for item in json_data if item is not None]  # Remove the items that are marked for deletion

        return json_data

    def convert_property_amd(self, propertyJson, onboard_object):
        amd_supported_behaviors = ['adScalerCircuitBreaker', 'advanced',
                                   'akamaizer', 'akamaizerTag',
                                   'allHttpInCacheHierarchy',
                                   'allowCloudletsOrigins',
                                   'allowHTTPSCacheKeySharing',
                                   'allowHTTPSDowngrade', 'allowOptions',
                                   'allowTransferEncoding', 'altSvcHeader',
                                   'apiPrioritization',
                                   'applicationLoadBalancer',
                                   'audienceSegmentation',
                                   'autoDomainValidation',
                                   'baseDirectory',
                                   'bossBeaconing',
                                   'breadcrumbs',
                                   'breakConnection',
                                   'cacheError',
                                   'cacheKeyIgnoreCase', 'cacheKeyQueryParams', 'cacheRedirect',
                                   'cacheTag', 'cacheTagVisible',
                                   'caching',
                                   'centralAuthorization',
                                   'chaseRedirects',
                                   'clientCertificateAuth', 'clientCharacteristics', 'cloudWrapper', 'cloudWrapperAdvanced',
                                   'commonMediaClientData', 'constructResponse', 'contentCharacteristicsAMD',
                                   'contentPrePosition', 'contentTargetingProtection', 'cpCode', 'customBehavior',
                                   'datastream', 'denyAccess', 'dnsAsyncRefresh',
                                   'downgradeProtocol', 'downstreamCache', 'dynamicAdInsertion'
                                   'dynamicThroughtputOptimization',
                                   'dynamicThroughtputOptimizationOverride', 'edgeConnect', 'edgeImageConversion',
                                   'edgeOriginAuthorization', 'edgeRedirector', 'edgeScape', 'edgeWorker',
                                   'enforceMtlsSettings',
                                   'enhancedProxyDetection', 'epdForwardHeaderEnrichment', 'failAction', 'fastInvalidate',
                                   'fips', 'forwardRewrite', 'g2oheader', 'globalRequestNumber',
                                   'hdDataAdvanced', 'healthDetection', 'hsafEipBinding',
                                   'http2', 'http3', 'httpStrictTransportSecurity', 'httpToHttpsUpgrade',
                                   'imOverride', 'imageAndVideoManager', 'imageManager', 'imageManagerVideo',
                                   'inputValidation', 'instantConfig', 'largeFileOptimizationAdvanced',
                                   'limitBitRate', 'logCustom', 'mPulse', 'manifestPersonalization',
                                   'manifestRerouting', 'mediaAcceleration',
                                   'mediaAccelerationQuicOptout', 'mediaClient'
                                   'mediaOriginFailover',
                                   'modifyIncomingRequestHeader', 'modifyIncomingResponseHeader', 'modifyOutgoingRequestHeader', 'modifyOutgoingResponseHeader',
                                   'origin', 'originCharacteristics', 'originFailureRecoveryMethod', 'originFailureRecoveryPolicy', 'originIpAcl',
                                   'permissionsPolicy', 'persistentClientConnection', 'persistentConnection', 'personallyIdentifiableInformation', 'phasedRelease',
                                   'predictiveContentDelivery', 'prefreshCache', 'quality', 'readTimeout', 'redirect', 'redirectplus', 'refererChecking',
                                   'removeQueryParaeter', 'removeVary', 'report', 'requestClientHints', 'requestControl', 'responseCode', 'returnCacheStatus', 'rewriteUrl', 'salesForceCommerceCloudClient', 'salesForceCommerceCloudProvider', 'salesForceCommerceCloudProviderHostHeader', 'savePostDcaProcessing', 'scheduleInvalidation', 'segmentedContentProtection', 'segmentedMediaOptimization', 'segmentedMediaStreamingPrefetch', 'setVariable', 'simulateErrorCode', 'standardTLSMigration', 'standardTLSMigrationOverride', 'strictHeaderParsing', 'subCustomer', 'sureRoute', 'tieredDistribution', 'tieredDistributionAdvanced', 'tieredDistributionCustomization', 'timeout', 'validateEntityTag', 'verifyTokenAuthorization', 'virtualWaitingRoom', 'virtualWaitingRoomWithEdgeWorkers', 'visitorPrioritization', 'visitorPrioritizationFifo', 'visitorPrioritizationFifoStandalone', 'watermarkUrl', 'watermarking', 'akamaizertag', 'enableallmethodscacheh', 'allowoptions', 'basedir', 'breakconnect', 'negativettl', 'cachekeyignorecase', 'cachekeyqueryparams', 'cache302', 'cachetag', 'cachetagvisible', 'centralauth', 'chaseredirects', 'construct_response', 'cpcode', 'denyaccess', 'dnsasyncrefresh', 'downstreamcaching', 'edgeconnect', 'edgeoriginauth', 'failaction', 'healthdetect', 'mdc', 'bitratelimiting', 'modincomingreqheader', 'modincomingrespheader', 'modoutgoingreqheader', 'modoutgoingrespheader', 'clientpconns', 'pconns', 'pii', 'cacheprefresh', 'readtimeout', 'refererchecking', 'removeqsbyname', 'removevary', 'reporting', 'setresponsecode', 'urlrewrite', 'save_post_dca_processing', 'scheduledinvalidation', 'segmentedcontentprotection', 'segmentedmediaoptimization', 'sim_error_codes', 'strictheaderparsing', 'sureroute', 'tiereddistribution', 'connecttimeout', 'validateetag', 'token_auth_verify', 'manifestrerouting', 'mediaoriginfailover', 'hddata_advanced', 'asset_prioritization', 'conditionalOriginBehavior', 'audience_segmentation', 'edgescape', 'continuousDeployment', 'subcustomerenable', 'edge_redirector', 'forward_rewrite', 'edge_image_converter', 'watermark_tokens', 'imagemanagement', 'mediaclient', 'predictivecontentdelivery', 'protocoldowngrade', 'ip_geo_access', 'virtual_waiting_room', 'virtual_waiting_room_with_edge_workers', 'visitor_prioritization', 'visitor_prioritization_fifo', 'visitor_prioritization_fifo_standalone']

        if onboard_object.ehn_option == 'LIVE':
            segmentedMediaOptimization = json.dumps({'name': 'segmentedMediaOptimization',
                                                     'options': {'behavior': 'LIVE'}})
        else:
            segmentedMediaOptimization = json.dumps({'name': 'segmentedMediaOptimization',
                                                     'options': {'behavior': 'ON_DEMAND'}})
        contentCharacteristicsAMD = json.dumps({'name': 'contentCharacteristicsAMD',
                                                'options': {
                                                    'catalogSize': 'UNKNOWN',
                                                    'contentType': 'HD',
                                                    'popularityDistribution': 'UNKNOWN',
                                                    'hls': True,
                                                    'segmentDurationHLS': 'SEGMENT_DURATION_10S',
                                                    'segmentSizeHLS': 'UNKNOWN',
                                                    'hds': True,
                                                    'segmentDurationHDS': 'SEGMENT_DURATION_6S',
                                                    'segmentSizeHDS': 'UNKNOWN',
                                                    'dash': True,
                                                    'segmentDurationDASH': 'SEGMENT_DURATION_6S',
                                                    'segmentSizeDASH': 'UNKNOWN',
                                                    'smooth': True,
                                                    'segmentDurationSmooth': 'SEGMENT_DURATION_2S',
                                                    'segmentSizeSmooth': 'UNKNOWN'}})

        behaviors_to_add = [segmentedMediaOptimization, contentCharacteristicsAMD]
        for behavior in behaviors_to_add:
            propertyJson['rules']['behaviors'].append(json.loads(behavior))
        all_behaviors = self.get_all_behaviors(propertyJson, 'behaviors')
        behavior_names = list(set(list(map(lambda x: x['name'], all_behaviors))))
        behaviors_to_remove = [x for x in behavior_names if x not in amd_supported_behaviors]
        # behaviors_to_remove = [('name', 'originCharacteristics'), ('name', 'contentCharacteristicsDD')]
        for behavior in behaviors_to_remove:
            logger.debug(f'removing unsupported amd behavior {behavior}')
            propertyJson = self.remove_behaviors(propertyJson, 'name', behavior)
        propertyJson = self.remove_rule(propertyJson, 'name', 'Large Objects')
        return propertyJson

    def convert_property_dsa(self, propertyJson):

        dsa_supported_behaviors = ['enhancedDebug',
                                   'adaptiveImageCompression', 'advanced', 'akamaizer', 'akamaizerTag', 'allHttpInCacheHierarchy',
                                   'allowCloudletsOrigins', 'allowDelete', 'allowOptions', 'allowPatch', 'allowPost', 'allowPut',
                                   'allowTransferEncoding', 'altSvcHeader', 'apiPrioritization', 'applicationLoadBalancer',
                                   'audienceSegmentation', 'autoDomainValidation', 'baseDirectory', 'breadcrumbs', 'breakConnection',
                                   'brotli', 'cacheError', 'cacheId', 'cacheKeyIgnoreCase', 'cacheKeyQueryParams', 'cacheKeyRewrite',
                                   'cachePost', 'cacheRedirect', 'cacheTag', 'cacheTagVisible', 'caching', 'centralAuthorization',
                                   'chaseRedirects', 'clientCertificateAuth', 'cloudInterconnects', 'cloudWrapper', 'cloudWrapperAdvanced',
                                   'conditionalOrigin', 'constructResponse', 'corsSupport', 'cpCode', 'customBehavior', 'datastream', 'denyAccess',
                                   'deviceCharacteristicCacheId', 'deviceCharacteristicHeader', 'dnsAsyncRefresh', 'dnsPrefresh',
                                   'downstreamCache', 'edgeConnect', 'edgeImageConversion', 'edgeOriginAuthorization', 'edgeRedirector',
                                   'edgeScape', 'edgeSideIncludes', 'edgeWorker', 'enforceMtlsSettings', 'enhancedAkamaiProtocol', 'enhancedProxyDetection',
                                   'epdForwardHeaderEnrichment', 'failAction', 'failoverBotManagerFeatureCompatibility', 'fastInvalidate', 'fips', 'firstPartyMarketing',
                                   'firstPartyMarketingPlus', 'forwardRewrite', 'frontEndOptimization', 'globalRequestNumber', 'graphqlCaching', 'gzipResponse',
                                   'healthDetection', 'http2', 'http3', 'httpStrictTransportSecurity', 'imOverride', 'imageAndVideoManager', 'imageManager',
                                   'imageManagerVideo', 'include', 'inputValidation', 'instant', 'instantConfig', 'largeFileOptimization', 'logCustom', 'mPulse',
                                   'modifyIncomingRequestHeader', 'modifyIncomingResponseHeader', 'modifyOutgoingRequestHeader', 'modifyOutgoingResponseHeader',
                                   'networkConditionsHeader', 'origin', 'originCharacteristics', 'originIpAcl', 'permissionsPolicy', 'persistentClientConnection',
                                   'persistentConnection', 'personallyIdentifiableInformation', 'phasedRelease', 'prefetch', 'prefetchable', 'prefreshCache',
                                   'quicBeta', 'rapid', 'readTimeout', 'realUserMonitoring', 'redirect', 'redirectplus', 'refererChecking', 'removeQueryParameter',
                                   'removeVary', 'report', 'requestClientHints', 'requestControl', 'responseCode', 'responseCookie', 'returnCacheStatus',
                                   'rewriteUrl', 'rumCustom', 'salesForceCommerceCloudClient', 'salesForceCommerceCloudProvider', 'salesForceCommerceCloudProviderHostHeader',
                                   'savePostDcaProcessing', 'scheduleInvalidation', 'setVariable', 'shutr', 'simulateErrorCode', 'siteShield', 'strictHeaderParsing',
                                   'sureRoute', 'tcpOptimization', 'teaLeaf', 'tieredDistribution', 'tieredDistributionCustomization', 'timeout', 'validateEntityTag',
                                   'verifyTokenAuthorization', 'virtualWaitingRoom', 'virtualWaitingRoomWithEdgeWorkers', 'visitorPrioritization', 'visitorPrioritizationFifo',
                                   'visitorPrioritizationFifoStandalone', 'watermarkUrl', 'webApplicationFirewall', 'webSockets', 'webdav', 'akamaizertag',
                                   'enableallmethodscacheh', 'allowdelete', 'allowoptions', 'allowpatch', 'allowpost', 'allowput', 'basedir', 'negativettl',
                                   'cachekeyignorecase', 'cachekeyqueryparams', 'cachekeyrewrite', 'postcaching', 'cache302', 'cachetag', 'cachetagvisible',
                                   'chaseredirects', 'construct_response', 'cpcode', 'denyaccess', 'dnsasyncrefresh', 'dnsprefresh', 'downstreamcaching',
                                   'edgeconnect', 'edgeoriginauth', 'gzipresponse', 'largefileoptimizations', 'modincomingreqheader', 'modincomingrespheader',
                                   'modoutgoingreqheader', 'modoutgoingrespheader', 'clientpconns', 'pconns', 'pii', 'prefetching', 'prefetchableobject', 'cacheprefresh',
                                   'readtimeout', 'refererchecking', 'removeqsbyname', 'removevary', 'reporting', 'setresponsecode', 'setresponsecookie', 'urlrewrite',
                                   'save_post_dca_processing', 'scheduledinvalidation', 'sim_error_codes', 'strictheaderparsing', 'sureroute', 'tcpoptimizations',
                                   'tiereddistribution', 'connecttimeout', 'validateetag', 'centralauth', 'token_auth_verify', 'aic', 'cacheid', 'esi', 'asset_prioritization',
                                   'conditionalOriginBehavior', 'audience_segmentation', 'conditionalorigin', 'edgescape', 'continuousDeployment', 'edge_redirector',
                                   'edccacheid', 'edcheader', 'enhancedakamaiprotocol', 'forward_rewrite', 'feo', 'edge_image_converter', 'watermark_tokens', 'imagemanagement',
                                   'mdc', 'networkconditionsheader', 'cloudinterconnects', 'quicbeta', 'rum', 'rumcustom', 'ip_geo_access', 'breakconnect', 'failaction', 'healthdetect',
                                   'siteshield', 'virtual_waiting_room', 'virtual_waiting_room_with_edge_workers', 'visitor_prioritization',
                                   'visitor_prioritization_fifo', 'visitor_prioritization_fifo_standalone', 'waf']

        json2ui_dict = json2ui_behaviorNames()
        all_behaviors = self.get_all_behaviors(propertyJson, 'behaviors')

        behavior_names = list(set(list(map(lambda x: x['name'], all_behaviors))))
        behaviors_to_remove = [x for x in behavior_names if x not in dsa_supported_behaviors]
        comment_override = 'Removed the following behaviors when converting to DSA:'
        for behavior in behaviors_to_remove:
            logger.info(f'removing unsupported dsa behavior {behavior}')
            comment_override = f'{comment_override} {json2ui_dict[behavior.lower()]}, '
            propertyJson = self.remove_behaviors(propertyJson, 'name', behavior)
        comment_override = f"{comment_override}\n {propertyJson['comments']}"
        propertyJson['comments'] = comment_override
        return propertyJson

    def remove_rule(self, json_data, key, value):
        """
        Recursively removes an object from a nested JSON structure based on a key-value pair.

        Parameters:
        json_data (dict/list): The JSON data, represented as a nested dictionary or list.
        key (str): The key to be matched.
        value: The value to be matched with the key.

        Returns:
        dict/list: The modified JSON data with the specified object removed.
        """

        if isinstance(json_data, dict):
            if json_data.get(key) == value:
                return None  # Remove the object
            else:
                return {k: self.remove_rule(v, key, value) for k, v in json_data.items()}
        elif isinstance(json_data, list):
            return [self.remove_rule(item, key, value) for item in json_data if self.remove_rule(item, key, value) is not None]
        else:
            return json_data

    def get_all_behaviors(self, json_data, target_key):
        """
        Recursively searches for all occurrences of a key in a nested JSON and returns their values.

        :param json_data: The JSON object to search through.
        :param target_key: The key to search for.
        :return: A list of values for the occurrences of the key.
        """
        values_found = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if key == target_key:
                    values_found.extend(value)
                if isinstance(value, (dict, list)):
                    values_found.extend(self.get_all_behaviors(value, target_key))

        elif isinstance(json_data, list):
            for item in json_data:
                if isinstance(item, (dict, list)):
                    values_found.extend(self.get_all_behaviors(item, target_key))
        return values_found

    def console_hyperlink(self, uri, label=None):
        if label is None:
            label = uri
        parameters = ''
        escape_mask = '\033]8;{};{}\033\\{}\033]8;;\033\\'
        return escape_mask.format(parameters, uri, label)


def write_xlsx(filepath: str, dict_value: dict,
            freeze_row: int | None = 1,
            freeze_column: int | None = 2,
            show_url: bool | None = True,
            show_index: bool | None = False,
            adjust_column_width: bool | None = True) -> None:
    with pd.ExcelWriter(path=filepath, engine='xlsxwriter',
                    engine_kwargs={'options': {'strings_to_urls': show_url}}) as writer:
        writer.book.use_zip64()  # to allow excel to store files larger than 4GB
        MAX_XLXS_ROW = 1000000   # 1 million rows per sheet
        MAX_SHEETS = 89          # 89 sheets per excel
        for sheetname, df in dict_value.items():
            if df is not None:
                if len(df.index) <= MAX_XLXS_ROW:
                    df.to_excel(writer, sheet_name=sheetname,
                                freeze_panes=(freeze_row, freeze_column),
                                index=show_index)
                    if adjust_column_width is True:
                        auto_adjust_xlsx_column_width(df, writer, sheet_name=sheetname, margin=0,
                                                    index=show_index)
                    workbook = writer.book
                    cell_format = workbook.add_format({'bold': True,
                                                    'text_wrap': True,
                                                    'valign': 'top',
                                                    'align': 'left',
                                                    'fg_color': 'blue',
                                                    'border': 1,
                                                    })
                    header_format = workbook.add_format({'bold': True,
                                                        'text_wrap': True,
                                                        'valign': 'top',
                                                        'align': 'middle',
                                                        'fg_color': '#FFC588',  # orange
                                                        'border': 1,
                                                        })

                    # Write the column headers with the defined format.
                    ws = writer.sheets[sheetname]
                    ws.hide_gridlines()
                    for col_num, value in enumerate(df.columns.values):
                        if show_index:
                            ws.write(0, col_num + 1, value, header_format)
                        else:
                            ws.write(0, col_num, value, header_format)
                    format1 = workbook.add_format({'num_format': '#,##0'})
                    ws.set_column(2, 2, None, format1)
                    ws.autofit()
                else:
                    total, last_sheet = divmod(len(df.index), MAX_XLXS_ROW)
                    logger.debug(f'{total=} {last_sheet=} dataset={len(df.index)}')
                    if last_sheet <= MAX_XLXS_ROW:
                        for sheet in (n + 1 for n in range(total + 1)):
                            logger.debug(f'Sheet{sheet}')

                            sheet_no = sheet
                            logger.info(f'{sheetname}_{sheet_no}')
                            if sheet == 1:
                                first_row = 0
                                last_row = (sheet * MAX_XLXS_ROW) + 1
                            else:
                                first_row = last_row + 1
                                last_row = len(df.index)

                            if sheet == total + 1 and last_sheet > 0:
                                logger.debug(f'{total=} {sheet_no=} {sheet=}')
                                sheet_no = total + 1
                            logger.warning(f'Sheet{sheet}: from {first_row} to {last_row}')
                            df.iloc[first_row:last_row].to_excel(writer, sheet_name=f'{sheetname}_{sheet_no}')

                            '''
                            df.to_excel(writer, sheet_name=f'{sheetname}_{sheet_no}',
                                        freeze_panes=(freeze_row, freeze_column),
                                        index=show_index)
                            '''
                            if adjust_column_width is True:
                                auto_adjust_xlsx_column_width(df, writer, sheet_name=f'{sheetname}_{sheet_no}',
                                                        index=show_index)

                            workbook = writer.book
                            cell_format = workbook.add_format()
                            cell_format.set_bold()
                            cell_format.set_font_color('blue')
                            cell_format.set_text_wrap()

                            header_format = workbook.add_format({'bold': True,
                                                                'text_wrap': True,
                                                                'valign': 'top',
                                                                'align': 'middle',
                                                                'fg_color': '#FFC588',  # orange
                                                                'border': 1,
                                                                })

                            # Write the column headers with the defined format.
                            ws = writer.sheets[f'{sheetname}_{sheet_no}']
                            for col_num, value in enumerate(df.columns.values):
                                if show_index:
                                    ws.write(0, col_num + 1, value, header_format)
                                else:
                                    ws.write(0, col_num, value, header_format)

                            format1 = workbook.add_format({'num_format': '#,##0'})
                            ws.set_column(2, 2, None, format1)
                            ws.autofit()


def open_excel_application(filepath: str, df: pd.DataFrame | None = None) -> None:
    if platform.system() == 'Darwin':
        if len(df.index) > 0:
            subprocess.check_call(['open', '-a', 'Microsoft Excel', filepath])


def split_elements_newline(elements):
    if isinstance(elements, (list, tuple, dict)):
        return '\n'.join(map(str, elements))
    else:
        return ''


def split_elements_newline_withcomma(elements):
    logger.debug(elements)
    modified_elements = []

    for i, element in enumerate(elements, start=1):
        if isinstance(element, dict):
            modified_elements.append(f'{i}. {json.dumps(element)}')
        else:
            if len(elements) == 1:
                modified_elements.append(f'{str(element)}')
            else:
                modified_elements.append(f'{i}. {str(element)}')

    return ',\n'.join(modified_elements)


def json2ui_behaviorNames():
    return (
        {
            'enhanceddebug': 'Enhanced Debug',
            'mediaclient': 'Media Client',
            'denyaccess': 'Control Access',
            'advanced': 'Advanced',
            'adaptiveimagecompression': 'Adaptive Image Compression',
            'akamaizer': 'Akamaizer',
            'mediaacceleration': 'Media Acceleration',
            'mediaaccelerationquicoptout': 'Media Acceleration (QUIC Protocol) Opt-Out\n',
            'akamaizertag': 'Akamaize Tag',
            'allowdelete': 'Allow DELETE',
            'allowpatch': 'Allow PATCH',
            'allowput': 'Allow PUT',
            'allowpost': 'Allow POST',
            'allowoptions': 'Allow OPTIONS',
            'allowtransferencoding': 'Chunked Transfer Encoding',
            'watermarkurl': 'Watermark Token',
            'edgeimageconversion': 'Image Converter Settings',
            'allhttpincachehierarchy': 'Allow All Methods on Parent Servers',
            'cachekeyignorecase': 'Ignore Case In Cache Key',
            'cachekeyqueryparams': 'Cache Key Query Parameters',
            'cachekeyrewrite': 'Cache Key Path Rewrite (Beta)',
            'caching': 'Caching',
            'prefreshcache': 'Cache Prefreshing',
            'cacheid': 'Cache ID Modification',
            'cachetagvisible': 'Cache Tag Visibility',
            'cachetag': 'Cache Tag',
            'chaseredirects': 'Chase Redirects',
            'devicecharacteristiccacheid': ' Device Characterization - Define Cached Content',
            'devicecharacteristicheader': ' Device Characterization - Forward in Header',
            'centralauthorization': 'Centralized Authorization',
            'edgeredirector': 'Edge Redirector Cloudlet',
            'visitorprioritization': 'Visitor Prioritization Cloudlet',
            'requestcontrol': 'Request Control Cloudlet',
            'forwardrewrite': 'Forward Rewrite Cloudlet',
            'apiprioritization': 'API Prioritization Cloudlet',
            'audiencesegmentation': 'Audience Segmentation Cloudlet',
            'phasedrelease': 'Phased Release Cloudlet',
            'applicationloadbalancer': 'Application Load Balancer Cloudlet',
            'visitorprioritizationfifo': 'Virtual Waiting Room (Beta)',
            'virtualwaitingroom': 'Virtual Waiting Room',
            'visitorprioritizationfifostandalone': 'Virtual Waiting Room with EdgeWorkers (Beta)',
            'virtualwaitingroomwithedgeworkers': 'Virtual Waiting Room with EdgeWorkers',
            'cpcode': 'Content Provider Code',
            'downstreamcache': 'Downstream Cacheability',
            'dnsasyncrefresh': 'DNS Asynchronous Refresh',
            'dnsprefresh': 'DNS Prefresh',
            'edgeoriginauthorization': 'Edge Server Identification',
            'edgeoriginsignatureauth': '',
            'edgescape': 'Content Targeting (EdgeScape)',
            'edgesideincludes': 'ESI (Edge Side Includes)',
            'failaction': 'Site Failover',
            'instantconfig': 'InstantConfig',
            'mediafileretrievaloptimization': ' Media File Retrieval Optimization',
            'mobilesdkperformance': 'Mobile App Performance SDK',
            'rapid': 'Akamai API Gateway',
            'modifyincomingrequestheader': 'Modify Incoming Request Header',
            'modifyincomingresponseheader': 'Modify Incoming Response Header',
            'modifyoutgoingrequestheader': 'Modify Outgoing Request Header',
            'modifyoutgoingresponseheader': 'Modify Outgoing Response Header',
            'gzipresponse': 'Last Mile Acceleration (Gzip Compression)',
            'healthdetection': 'Origin Health Detection',
            'instant': 'Akamai Instant (Prefetching)',
            'netsession': 'NetSession',
            'networkconditionsheader': 'Network Conditions Header',
            'predictivecontentdelivery': 'Predictive Content Delivery',
            'originfailurerecoverymethod': ' Origin Failure Recovery Method',
            'originfailurerecoverypolicy': ' Origin Failure Recovery Policy',
            'mediaoriginfailover': 'Media Origin Failover',
            'conditionalorigin': 'Conditional Origin',
            'origin': 'Origin Server',
            'dummy-this-warning-should-appear-whenever-the-if-clause-is-satisfied': '',
            'cloudwrapper': 'Cloud Wrapper',
            'cloudwrapperadvanced': 'Cloud Wrapper Advanced',
            'origincharacteristics': 'Origin Characteristics',
            'clientcharacteristics': 'Client Characteristics',
            'contentcharacteristics': 'Content Characteristics',
            'contentcharacteristicsdd': 'Content Characteristics',
            'contentcharacteristicsamd': 'Content Characteristics',
            'origincharacteristicswsd': 'Origin Characteristics',
            'dynamicwebcontent': 'Content Characteristics - Dynamic Web Content',
            'contentcharacteristicswsdlargefile': 'Content Characteristics - Large File',
            'contentcharacteristicswsdvod': 'Content Characteristics - Streaming Video On-demand',
            'contentcharacteristicswsdlive': 'Content Characteristics - Streaming Video Live',
            'persistentconnection': 'Persistent Connections: Edge to Origin',
            'cachepost': 'Cache POST Responses',
            'enhancedproxydetection': 'Enhanced Proxy Detection with GeoGuard',
            'watermarking': 'Watermarking',
            'hsafeipbinding': 'HSAF for Edge IP Binding',
            'breadcrumbs': 'Breadcrumbs',
            'dynamicadinsertion': 'Dynamic Ad Insertion',
            'dynamicthroughtputoptimization': 'Quick Retry',
            'dynamicthroughtputoptimizationoverride': 'Quick Retry Override',
            'contenttargetingprotection': 'Content Targeting - Protection',
            'manifestpersonalization': 'Manifest Personalization',
            'autodomainvalidation': 'Auto Domain Validation',
            'httptohttpsupgrade': 'HTTP to HTTPS Upgrade',
            'standardtlsmigration': 'Standard TLS Migration',
            'standardtlsmigrationoverride': 'Standard TLS Migration Override',
            'allowhttpscachekeysharing': 'HTTPS Cache Key Sharing',
            'allowhttpsdowngrade': 'Protocol Downgrade (HTTPS Downgrade to Origin)',
            'downgradeprotocol': 'Protocol Downgrade',
            'persistentclientconnection': 'Persistent Connections: Client to Edge',
            'largefileoptimization': 'Large File Optimization',
            'largefileoptimizationadvanced': 'Large File Optimization (Advanced)',
            'logcustom': 'Log Custom Details',
            'predictiveprefetching': 'Predictive Prefetching',
            'prefetchable': 'Prefetchable Objects',
            'prefetch': 'Prefetch Objects',
            'quality': 'Delivery Optimizations',
            'randomseek': 'Random Seek',
            'readtimeout': 'Read Timeout',
            'timeout': 'Connect Timeout',
            'redirect': 'Redirect',
            'redirectplus': 'Redirect Plus',
            'removequeryparameter': 'Remove Outgoing Request Parameters',
            'removevary': 'Remove Vary Header',
            'report': 'Log Request Details',
            'savepostdcaprocessing': 'Save POST DCA processing result',
            'scheduleinvalidation': 'Scheduled Invalidation',
            'responsecode': 'Set Response Code',
            'responsecookie': 'Set Response Cookie',
            'shutr': 'SHUTR',
            'subcustomer': 'Subcustomer Enablement',
            'sureroute': 'SureRoute',
            'spdy': 'SPDY',
            'http2': 'HTTP/2',
            'tcpoptimization': 'TCP Optimizations',
            'fips': 'FIPS mode - origin',
            'http3': 'HTTP/3',
            'requestclienthints': 'Request Client Hints',
            'permissionspolicy': 'Permissions-Policy',
            'altsvcheader': 'Alt-Svc Header',
            'rmaoptimization': 'RMA Optimizations (RMA)',
            'tiereddistribution': 'Tiered Distribution',
            'tiereddistributionadvanced': 'Tiered Distribution (Advanced)',
            'modifyviaheader': 'Modify Via Header',
            'rewriteurl': 'Modify Outgoing Request Path',
            'validateentitytag': 'Validate Entity Tag (ETag)',
            'webapplicationfirewall': 'Web Application Firewall (WAF)',
            'cacheerror': 'Cache HTTP Error Responses',
            'cacheredirect': 'Cache HTTP Temporary Redirects',
            'restrictobjectcaching': 'Object Caching',
            'basedirectory': 'Origin Base Path',
            'breakconnection': 'Break Forward Connection',
            'personallyidentifiableinformation': 'Personally Identifiable Information (PII)',
            'siteshield': 'SiteShield',
            'frontendoptimization': 'Front-End Optimization (FEO)',
            'brotli': 'Brotli Support',
            'quicbeta': 'QUIC Support (Beta)',
            'imagemanagervideo': 'Image and Video Manager (Videos)',
            'resourceoptimizer': 'Resource Optimizer',
            'resourceoptimizerextendedcompatibility': 'Resource Optimizer Extended Compatibility',
            'brotlicompression': 'Brotli Compression',
            'scriptmanagement': 'Script Management',
            'websockets': 'WebSockets',
            'enhancedakamaiprotocol': 'Enhanced Akamai Protocol',
            'realusermonitoring': 'Real User Monitoring (RUM)',
            'rumcustom': 'RUM SampleRate',
            'edgeloadbalancingorigin': 'Edge Load Balancing: Origin Definition',
            'edgeloadbalancingadvanced': 'Edge Load Balancing: Advanced Metadata',
            'edgeloadbalancingdatacenter': 'Edge Load Balancing: Data Center',
            'edgeconnect': 'Cloud Monitor Instrumentation',
            'deliveryreceipt': 'Cloud Monitor Data Delivery',
            'verifytokenauthorization': 'Auth Token 2.0 Verification',
            'limitbitrate': '',
            'refererchecking': 'Legacy Referrer Checking',
            'webdav': 'WebDAV',
            'simulateerrorcode': 'Simulate Error Response Code',
            'g2oheader': 'Signature Header Authentication',
            'segmentedmediaoptimization': 'Segmented Media Delivery Mode',
            'segmentedcontentprotection': 'Segmented Media Protection',
            'hddataadvanced': 'HD Data Override: Advanced Metadata',
            'constructresponse': 'Construct Response',
            'fastinvalidate': 'Fast Invalidate (Safe to remove)',
            'saasdefinitions': 'SaaS Definitions',
            'salesforcecommercecloudprovider': 'Akamai Provider for Salesforce Commerce Cloud',
            'salesforcecommercecloudproviderhostheader': 'Akamai Provider for Salesforce Commerce Cloud Host Header Control',
            'salesforcecommercecloudclient': 'Akamai Connector for Salesforce Commerce Cloud',
            'manifestrerouting': 'Manifest Rerouting',
            'adscalercircuitbreaker': 'Ad Scaler Circuit Breaker',
            'imagemanager': 'Image and Video Manager (Images)',
            'imoverride': 'Image and Video Manager: Set Parameter',
            'setvariable': 'Set Variable',
            'allowcloudletsorigins': 'Allow Conditional Origins',
            'inputvalidation': 'Input Validation Cloudlet',
            'firstpartymarketing': 'Cloud Marketing Cloudlet (Beta)',
            'firstpartymarketingplus': 'Cloud Marketing Plus Cloudlet (Beta)',
            'injectreferenceid': 'Inject Reference ID',
            'denydirectfailoveraccess': 'Security Failover Protection',
            'adaptiveacceleration': 'Adaptive Acceleration',
            'preconnect': 'Manual Preconnect',
            'manualserverpush': 'Manual Server Push',
            'tealeaf': 'IBM Tealeaf Connector',
            'dcp': 'IoT Edge Connect',
            'dcpdevrelations': 'IoT Edge Connect Dev Relations',
            'dcpdefaultauthzgroups': 'Default Authorization Groups',
            'dcpauthhmactransformation': 'Variable Hash Transformation',
            'dcpauthregextransformation': 'Variable Regex Transformation',
            'dcpauthsubstringtransformation': 'Variable Substring Transformation',
            'dcpauthvariableextractor': 'Mutual Authentication',
            'uidconfiguration': 'UID Configuration',
            'aggregatedreporting': 'Aggregated Reporting',
            'requesttypemarker': 'Request Type Marker',
            'downloadcompletemarker': 'Download Complete Marker',
            'downloadnotification': 'Download Notification',
            'custombehavior': 'Custom Behavior',
            'bossbeaconing': 'Diagnostic data beacons (Ex. BOSS)',
            'mpulse': 'mPulse',
            'graphqlcaching': 'GraphQL Caching',
            'httpstricttransportsecurity': 'HTTP Strict Transport Security (HSTS)',
            'datastream': 'DataStream',
            'verifyjsonwebtoken': 'JWT verification',
            'verifyjsonwebtokenfordcp': 'JWT',
            'ecmsdatabase': 'Message Store database selection',
            'ecmsdataset': 'Message Store data set selection',
            'ecmsobjectkey': 'Message Store object key selection',
            'ecmsbulkupload': 'Message Store bulk upload',
            'edgeworker': 'EdgeWorkers',
            'segmentedmediastreamingprefetch': 'Segmented Media Streaming - Prefetch',
            'commonmediaclientdata': 'Common Media Client Data support',
            'enforcemtlssettings': 'Enforce mTLS settings',
            'clientcertificateauth': 'Client Certificate Authentication',
            'realtimereporting': 'Real-time Reporting',
            'failoverbotmanagerfeaturecompatibility': 'Security Failover Feature Compatibility',
            'globalrequestnumber': 'Global Request Number',
            'returncachestatus': 'Return Cache Status',
            'tiereddistributioncustomization': 'Tiered Distribution Customization',
            'metadatacaching': 'Metadata Caching',
            'dcprealtimeauth': 'Real time authentication',
            'cloudinterconnects': 'Cloud Interconnects for Google Cloud (GCP)',
            'originipacl': 'Origin IP Access Control List',
            'epdforwardheaderenrichment': 'Enhanced Proxy Detection with GeoGuard - Forward Header Enrichment',
            'include': 'Include',
            'strictheaderparsing': 'Strict Header Parsing'
        }
    )
