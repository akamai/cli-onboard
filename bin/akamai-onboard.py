"""
Copyright 2019 Akamai Technologies, Inc. All Rights Reserved.

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""
from __future__ import annotations

import configparser
import json
import logging.config
import os
import sys
import time
from pathlib import Path
from shutil import copytree
from time import gmtime
from time import strftime

import _logging as lg
import click
import onboard
import onboard_batch_create
import onboard_multi_hosts
import onboard_single_host
import requests
import steps
import utility
import utility_papi
import utility_waf
import wrapper_api
from akamai.edgegrid import EdgeGridAuth
from akamai.edgegrid import EdgeRc
from exceptions import get_cli_root_directory
from exceptions import setup_logger
from model.multi_hosts import MultiHosts
from model.single_host import SingleHost


PACKAGE_VERSION = '2.2.0'
logger = setup_logger()
root = get_cli_root_directory()


class Config:
    def __init__(self):
        pass


pass_config = click.make_pass_decorator(Config, ensure=True)


def init_config(config):
    if not config.edgerc:
        if not os.getenv('AKAMAI_EDGERC'):
            edgerc_file = os.path.join(os.path.expanduser('~'), '.edgerc')
        else:
            edgerc_file = os.getenv('AKAMAI_EDGERC')
    else:
        edgerc_file = config.edgerc

    if not os.access(edgerc_file, os.R_OK):
        lg._log_error(f'Unable to read edgerc file {edgerc_file}')

    if not config.section:
        if not os.getenv('AKAMAI_EDGERC_SECTION'):
            section = 'onboard'
        else:
            section = os.getenv('AKAMAI_EDGERC_SECTION')
    else:
        section = config.section
    try:
        edgerc = EdgeRc(config.edgerc)
        base_url = edgerc.get(section, 'host')
        session = requests.Session()
        session.auth = EdgeGridAuth.from_edgerc(edgerc, section)

    except configparser.NoSectionError:
        lg._log_error(f'Edgerc section {section} not found')
    except Exception:
        lg._log_error(f'Unknown error occurred trying to read edgerc file {edgerc_file}')
    finally:
        wrap_api = wrapper_api.apiCallsWrapper(session, base_url, config.account_key)
        if config.account_key:
            account_name = wrap_api.get_account_name(config.account_key)
            logger.warning(f'Account Name: {account_name} {config.account_key}')

    return session, wrap_api


@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--edgerc', metavar='', default=os.path.join(os.path.expanduser('~'), '.edgerc'),
              help='Location of the credentials file [$AKAMAI_EDGERC]', required=False)
@click.option('-s', '--section', metavar='', default='onboard',
              help='Section of the credentials file [$AKAMAI_EDGERC_SECTION]', required=False)
@click.option('-a', '--account-key', '--accountkey', '--accountSwitchKey', '--accountswitchkey',
              metavar='',
              help='Account Switch Key (Akamai Internal Only)', required=False)
@click.version_option(version=PACKAGE_VERSION)
@pass_config
def cli(config, edgerc, section, account_key):
    '''
    Akamai CLI for onboarding properties v2.2.0
    '''
    config.edgerc = edgerc
    config.section = section
    config.account_key = account_key


@cli.command()
@click.pass_context
def help(ctx):
    '''
    Show help information
    '''
    print(ctx.parent.get_help())


@cli.command(short_help='Pull sample templates')
@pass_config
def fetch_sample_templates(config):
    source_folder = Path(root, 'templates', 'sample_setup_files')
    Path('sample_templates').mkdir(parents=True, exist_ok=True)
    target_folder = Path().resolve()
    target_folder = Path(target_folder, 'sample_templates')

    copytree(source_folder, target_folder, dirs_exist_ok=True)
    logger.info(f'Sample templates can be found in directory {target_folder}')


@cli.command(short_help='Create a delivery configuration with mutltiple hostnames and security configuration with one WAF policy')
@click.option('--csv', metavar='', required=True,
              help='File containing hostname and origin servername i.e. testwebsite.com,origin-testwebsite.com')
@click.option('-f', '--file', metavar='', required=True,
              help='File containing setup/onboard config key-value pairs in JSON')
@pass_config
def multi_hosts(config, csv, file):
    logger.info('Start Akamai CLI onboard')
    _, wrap_api = init_config(config)
    util = utility.utility()
    origin_parent_rules, public_hostnames, origin_hostnames = util.csv_2_origin_rules(csv)
    setup = onboard_multi_hosts.onboard(load_json(file))
    onboard = MultiHosts(setup.property_name, setup.contract_id, setup.product_id,
                         public_hostnames,
                         setup.secure_by_default, setup.edge_hostname,
                         setup.notification_emails,
                         setup.individual_cpcode)

    # Override default
    util.onboard_override_default(onboard, setup, cli_mode='multi-hosts')
    util.validate_group_id(onboard, wrap_api.get_groups_without_parent())
    util.validateSetupSteps(onboard, wrap_api, cli_mode='multi-hosts')

    if util.valid:
        rules = setup.get_product_template(onboard.source_template_file)
        logger.info(f'Rule Template Location: {onboard.source_template_file}')
        rules_after_default_rules = rules['rules']['children']
        rules_after_default_rules.insert(0, origin_parent_rules)
        rules['rules'].update({'children': rules_after_default_rules})
        logger.debug(json.dumps(rules, indent=4))
        with open(f'logs/{onboard.property_name}_v1.json', 'w') as outfile:
            json.dump(rules, outfile, ensure_ascii=True, indent=2)

        # Load business rule for delivery and security
        util_papi = utility_papi.papiFunctions()
        util_waf = utility_waf.wafFunctions()
        cp_code_id = []
        logger.debug(f'{public_hostnames=}')

        # Use first hostname in csv file as default cpcode name
        if onboard.create_new_cpcode:
            if not onboard.individual_cpcode:
                # use property name as main cp code
                onboard.add(onboard.property_name)
                cp_code_id.append(util_papi.create_new_cpcode(onboard, wrap_api, onboard.property_name,
                                                onboard.contract_id,
                                                onboard.group_id,
                                                onboard.product_id))

            else:
                onboard.add(public_hostnames[0])
                cp_code_id.append(util_papi.create_new_cpcode(onboard, wrap_api, onboard.new_cpcode_name[0],
                                                onboard.contract_id,
                                                onboard.group_id,
                                                onboard.product_id))

            logger.debug(f'{public_hostnames=} {cp_code_id=}')

        # If individual_cpcode=True, create new CpCode for each hostname
        if onboard.individual_cpcode:
            onboard.new_cpcode_name += public_hostnames[1:]
            # start from second hostname
            for name in onboard.new_cpcode_name[1:]:
                cp_code_id.append(util_papi.create_new_cpcode(onboard, wrap_api, name,
                                        onboard.contract_id,
                                        onboard.group_id,
                                        onboard.product_id))

            # update parent rule named 'Origin Rules', the first children after the Default Rule
            if rules['rules']['children'][0]['name'] == 'Origin Rules':
                logger.debug('Found Origin Rules')
                children_of_origin_rules = rules['rules']['children'][0]['children']

                for i, cpcode in enumerate(cp_code_id):
                    cp_code_rule = {}
                    cp_code_rule['name'] = 'cpCode'
                    cp_code_rule['options'] = {}
                    cp_code_rule['options']['value'] = {}
                    cp_code_rule['options']['value']['id'] = cpcode
                    children_of_origin_rules[i]['behaviors'].insert(0, cp_code_rule)

            rules['rules']['children'][0].update({'children': []})
            origin_rule_parent = rules['rules']['children'][0]
            origin_rule_parent.update({'children': children_of_origin_rules})
            logger.debug(f'{onboard.new_cpcode_name=}')
            logger.debug(json.dumps(children_of_origin_rules, indent=4))
            logger.debug(json.dumps(origin_rule_parent, indent=4))

        # Override default
        onboard.onboard_default_cpcode = cp_code_id[0]
        onboard.update_origin_default(origin_hostnames[0])
        setup.write_variable_json(onboard.origin_default, onboard.onboard_default_cpcode)
        setup.override_product_template(onboard, rules)
        logger.debug(f'{onboard.origin_default=} {onboard.onboard_default_cpcode=}')
        logger.debug(f'{cp_code_id=} {onboard.new_cpcode_name=} {onboard.secure_network=}')

        # Create the property, merge & update the property rules, figure out edgehostname logic
        util_papi.create_update_pm(config, onboard, wrap_api, util, cli_mode='multi-hosts')

        logger.debug(f'{onboard.secure_network=}')
        if onboard.activate_property_staging is False:
            logger.info('Activate Property Staging: SKIPPING')
        else:
            logger.debug(f'{onboard.contract_id=} {onboard.group_id=} {onboard.onboard_property_id=}')
            status = util_papi.activate_and_poll(wrap_api,
                                                onboard.property_name,
                                                onboard.contract_id,
                                                onboard.group_id,
                                                onboard.onboard_property_id, version=1,
                                                network='STAGING',
                                                emailList=onboard.notification_emails,
                                                notes='Onboard CLI Activation')
            if not status:
                lg._log_exception(msg='Unable to activate property to staging network')
            else:
                if not onboard.create_new_security_config:
                    print()
                    logger.warning('Create Security configuration on Staging: SKIPPING')
                else:
                    if onboard.onboard_waf_config_id == 0:
                        waf_ver = util_waf.create_waf_config(wrap_api, onboard)
                        if not waf_ver:
                            sys.exit()
                        waf_policy = util_waf.create_waf_policy(wrap_api, onboard)
                        if not waf_policy:
                            sys.exit()
                        waf_match_tgt = util_waf.create_waf_match_target(wrap_api, onboard)
                        if not waf_match_tgt:
                            sys.exit()
                    if onboard.activate_waf_policy_staging:
                        status = util_waf.activateAndPoll(wrap_api, onboard, network='STAGING')
                        if not status:
                            sys.exit()
                    else:
                        logger.warning('Activate Security configuration on Staging: SKIPPING')

        if not onboard.activate_property_production:
            print()
            logger.warning('Activate Property Production: SKIPPING')
        else:
            status = util_papi.activate_and_poll(wrap_api,
                                            onboard.property_name,
                                            onboard.contract_id,
                                            onboard.group_id,
                                            onboard.onboard_property_id, version=1,
                                            network='PRODUCTION',
                                            emailList=onboard.notification_emails,
                                            notes='Onboard CLI Activation')
            if not status:
                logger.error('Unable to activate property to staging network')
            else:
                if onboard.create_new_security_config and onboard.activate_waf_policy_production:
                    status = util_waf.activateAndPoll(wrap_api, onboard, network='PRODUCTION')
                    if not status:
                        sys.exit()
                else:
                    logger.info('Activate Security configuration on Staging: PRODUCTION')

    util.log_cli_timing()
    return 0


@cli.command(short_help='Create a simple delivery and security configuration with one hostname and one WAF policy')
@click.option('-f', '--file', metavar='', required=True,
              help='File containing setup/onboard config key-value pairs in JSON')
@pass_config
def single_host(config, file):
    logger.info('Start Akamai CLI onboard')
    _, wrap_api = init_config(config)
    util = utility.utility()

    # Populate onboarding data from user input and default values
    setup = onboard_single_host.onboard(load_json(file))
    onboard = SingleHost(setup.property_name, setup.contract_id, setup.product_id,
                         setup.public_hostnames,
                         setup.secure_by_default, setup.edge_hostname,
                         setup.notification_emails)

    # Override default
    util.onboard_override_default(onboard, setup, cli_mode='single-host')
    util.validate_group_id(onboard, wrap_api.get_groups_without_parent())
    util.validateSetupSteps(onboard, wrap_api, cli_mode='single_host')
    if util.valid:
        # Load business rule for delivery and security
        util_papi = utility_papi.papiFunctions()
        util_waf = utility_waf.wafFunctions()
        if onboard.create_new_cpcode:
            onboard.onboard_default_cpcode = util_papi.create_new_cpcode(onboard, wrap_api,
                                                                         onboard.new_cpcode_name,
                                                                         onboard.contract_id,
                                                                         onboard.group_id,
                                                                         onboard.product_id)

        # Create the property, merge & update the property rules, figure out edgehostname logic
        util_papi.create_update_pm(config, onboard, wrap_api, util)

        if onboard.activate_property_staging is False:
            logger.info('Activate Property Staging: SKIPPING')
        else:
            status = util_papi.activate_and_poll(wrap_api,
                                               onboard.property_name,
                                               onboard.contract_id,
                                               onboard.group_id,
                                               onboard.onboard_property_id, version=1,
                                               network='STAGING',
                                               emailList=onboard.notification_emails,
                                               notes='Onboard CLI Activation')
            if not status:
                lg._log_exception(msg='Unable to activate property to staging network')
            else:
                if not onboard.create_new_security_config:
                    print()
                    logger.warning('Create Security configuration on Staging: SKIPPING')
                else:
                    if onboard.onboard_waf_config_id == 0:
                        waf_ver = util_waf.create_waf_config(wrap_api, onboard)
                        if not waf_ver:
                            sys.exit()
                        waf_policy = util_waf.create_waf_policy(wrap_api, onboard)
                        if not waf_policy:
                            sys.exit()
                        waf_match_tgt = util_waf.create_waf_match_target(wrap_api, onboard)
                        if not waf_match_tgt:
                            sys.exit()
                    if onboard.activate_waf_policy_staging:
                        status = util_waf.activateAndPoll(wrap_api, onboard, network='STAGING')
                        if not status:
                            sys.exit()
                    else:
                        logger.warning('Activate Security configuration on Staging: SKIPPING')

        if not onboard.activate_property_production:
            print()
            logger.warning('Activate Property Production: SKIPPING')
        else:
            status = util_papi.activate_and_poll(wrap_api,
                                            onboard.property_name,
                                            onboard.contract_id,
                                            onboard.group_id,
                                            onboard.onboard_property_id, version=1,
                                            network='PRODUCTION',
                                            emailList=onboard.notification_emails,
                                            notes='Onboard CLI Activation')
            if not status:
                logger.error('Unable to activate property to production network')
            else:
                if onboard.create_new_security_config and onboard.activate_waf_policy_production:
                    status = util_waf.activateAndPoll(wrap_api, onboard, network='PRODUCTION')
                    if not status:
                        sys.exit()
                else:
                    logger.info('Activate Security configuration on Staging: PRODUCTION')

    util.log_cli_timing()
    return 0


@cli.command(short_help='Create a delivery configuration and update existing WAF policy')
@click.option('-f', '--file', metavar='', help='File containing setup/onboard config key-value pairs in JSON', required=True)
@pass_config
def create(config, file):

    logger.info('Start Akamai CLI onboard')
    _, wrapper_object = init_config(config)
    setup_json_content = load_json(file)
    onboard_object = onboard.onboard(setup_json_content, config)

    # Validate setup and akamai cli and cli pipeline are installed
    utility_object = utility.utility()
    cli_installed = utility_object.installedCommandCheck('akamai')
    pipeline_installed = utility_object.executeCommand(['akamai', 'pipeline'])

    if not (pipeline_installed and (cli_installed or pipeline_installed)):
        sys.exit()

    # Validate akamai cli and cli pipeline are installed
    utility_papi_object = utility_papi.papiFunctions()
    utility_waf_object = utility_waf.wafFunctions()

    # Determine necessary execution steps
    steps_object = steps.executionSteps()
    utility_object.validateSetupSteps(onboard_object, wrapper_object, cli_mode='create')

    # Got this far, we are ready to try and execute the actual steps
    if utility_object.valid is True:
        # Create new cpcode
        if steps_object.doCreateNewCpCode(setup_json_content):
            utility_papi_object.create_new_cpcode(onboard_object, wrapper_object,
                                                onboard_object.new_cpcode_name,
                                                onboard_object.contract_id,
                                                onboard_object.group_id,
                                                onboard_object.product_id)

        # Create the property, merge & update the property rules, figure out edgehostname logic
        utility_papi_object.create_update_pm(config, onboard_object, wrapper_object, utility_object)

        # Activate property to staging
        if steps_object.doPropertyActivateStaging(setup_json_content):
            activation_status = utility_papi_object.activate_and_poll(wrapper_object,
                                                    onboard_object.property_name,
                                                    onboard_object.contract_id,
                                                    onboard_object.group_id,
                                                    onboard_object.onboard_property_id, version=1,
                                                    network='STAGING',
                                                    emailList=onboard_object.notification_emails,
                                                    notes='Onboard CLI Activation')
            if activation_status is False:
                logger.error('Unable to activate property to staging network')
                exit(-1)
        else:
            logger.info('Activate Property Staging: SKIPPING')

        # Add WAF selected hosts
        if steps_object.doWafAddSelectedHosts(setup_json_content):
            # First have to create a new WAF config version
            print()
            logger.warning('Onboarding Security Config')
            logger.debug(f'Trying to create new version for WAF configuration: {onboard_object.waf_config_name}')
            create_waf_version = utility_waf_object.createWafVersion(wrapper_object, onboard_object, notes=onboard_object.version_notes)
            wrapper_object.update_waf_config_version_note(onboard_object, notes=onboard_object.version_notes)
            if create_waf_version is False:
                sys.exit()

            # Created WAF config version, now can add selected hosts to it
            logger.debug(f'Trying to add property public_hostnames as selected hosts to WAF configuration: {onboard_object.waf_config_name}')
            add_hostnames = utility_waf_object.addHostnames(wrapper_object,
                                        onboard_object.public_hostnames,
                                        onboard_object.onboard_waf_config_id,
                                        onboard_object.onboard_waf_config_version)
            if add_hostnames is True:
                logger.info(f'Successfully added {onboard_object.public_hostnames} as selected hosts')
            else:
                logger.error('Unable to add selected hosts to WAF Configuration')
                exit(-1)
        else:
            logger.info('WAF Add Selected Hosts: SKIPPING')

        # Update WAF match target
        if onboard_object.update_match_target:
            modify_matchtarget = utility_waf_object.updateMatchTarget(wrapper_object,
                                        onboard_object.public_hostnames,
                                        onboard_object.onboard_waf_config_id,
                                        onboard_object.onboard_waf_config_version,
                                        onboard_object.waf_match_target_id)
            if modify_matchtarget:
                logger.info(f'Successfully added {onboard_object.public_hostnames} to WAF Configuration Match Target')
            else:
                sys.exit(logger.error('Unable to update match target in WAF Configuration'))

        else:
            logger.info('WAF Update Match Target: SKIPPING')

        # Activate WAF configuration to staging
        if steps_object.doWafActivateStaging(setup_json_content):
            waf_activation_status = utility_waf_object.activateAndPoll(wrapper_object, onboard_object, network='STAGING')
            if waf_activation_status is False:
                sys.exit(logger.error('Unable to activate WAF configuration to staging network'))
        else:
            logger.info('Activate WAF Configuration Staging: SKIPPING')

        # Activate property to production
        if steps_object.doPropertyActivateProduction(setup_json_content):
            activation_status = utility_papi_object.activate_and_poll(wrapper_object,
                        onboard_object.property_name,
                        onboard_object.contract_id, onboard_object.group_id,
                        onboard_object.onboard_property_id, version=1,
                        network='PRODUCTION',
                        emailList=onboard_object.notification_emails, notes='Onboard CLI Activation')
            if activation_status is False:
                sys.exit(logger.error('Unable to activate property to production network'))

        else:
            logger.info('Activate Property Production: SKIPPING')

        # Activate WAF configuration to production
        if steps_object.doWafActivateProduction(setup_json_content):
            waf_activation_status = utility_waf_object.activateAndPoll(wrapper_object, onboard_object, network='PRODUCTION')
            if waf_activation_status is False:
                sys.exit(logger.error('Unable to activate WAF configuration to production network'))
        else:
            logger.info('Activate WAF Configuration Production: SKIPPING')

        print()
        utility_object.log_cli_timing()

    else:
        logger.error('Please correct the setup json file settings and try again.')
        return 0

    return 0


@cli.command(short_help='Create a 1 or more delivery configurations using a csv input and optionally update WAF policy')
@click.option('-t', '--template', metavar='', help='file path to single file json template.', required=True)
@click.option('-n', '--network', metavar='', type=click.Choice(['ENHANCED_TLS', 'STANDARD_TLS']), help='use either ENHANCED_TLS or STANDARD_TLS', show_default=True, default='ENHANCED_TLS', required=False)
@click.option('-c', '--contract', metavar='', help='Contract ID (starts with ctr)', required=False)
@click.option('-g', '--group', metavar='', help='Group ID (starts with grp)', required=False)
@click.option('-p', '--product', metavar='', help='one of prd_SPM, prd_Fresca, prd_API_Accel (case sensitive)', required=False)
@click.option('-f', '--rule-format', metavar='', help='rule format (typically latest, but can use frozen rule format if desired)', default='latest', show_default=True)
@click.option('--use-cpcode', metavar='', help='override creating new cpcode for each hostname', required=False)
@click.option('--secure-by-default', metavar='', is_flag=True, default=False, help='use secure by default certificates', required=False)
@click.option('--waf-config', metavar='', help='name of security configuration to update', required=False)
@click.option('--waf-match-target', metavar='', help='waf match target id to add hostnames to (use numeric waf match target id)', required=False)
@click.option('--activate', metavar='', type=click.Choice(['delivery-staging', 'waf-staging', 'delivery-production', 'waf-production']), multiple=True, help='Options: delivery-staging, delivery-production, waf-staging, waf-production', required=False)
@click.option('--email', metavar='', multiple=True, help='email(s) for activation notifications', required=False)
@click.option('--csv', metavar='', required=True, help='csv file with headers hostname,origin,edgeHostname,forwardHostHeader,propertyName,')
@pass_config
def batch_create(config, **kwargs):
    logger.info('Start Akamai CLI onboard')
    _, wrapper_object = init_config(config)
    click_args = kwargs
    start_time = time.perf_counter()

    onboard_object = onboard_batch_create.onboard(config, click_args)

    # Validate setup and akamai cli and cli pipeline are installed
    csv = click_args['csv']
    utility_object = utility.utility()

    # Validate akamai cli and cli pipeline are installed
    cli_installed = utility_object.installedCommandCheck('akamai')
    pipeline_installed = utility_object.executeCommand(['akamai', 'pipeline'])

    if not (pipeline_installed and (cli_installed or pipeline_installed)):
        sys.exit()

    # If groupId, contractId or productId is missing, list them
    if click_args['group'] is None:
        command = (f'akamai pm lg -a {config.account_key}') if config.account_key is not None else ('akamai pm lg')
        logger.warning(f'Group ID is required.  Running akamai property manager cli command: {command}')
        sys.exit(os.system(command))

    if click_args['contract'] is None:
        command = (f'akamai pm lc -a {config.account_key}') if config.account_key is not None else ('akamai pm lc')
        logger.warning(f'Contract ID is required.  Running akamai property manager cli command: {command}')
        sys.exit(os.system(command))

    if click_args['product'] is None:
        command = (f"akamai pm lp -c {click_args['contract']} -a {config.account_key}") if config.account_key is not None else (f"akamai pm lc -c {click_args['contract']}")
        logger.warning(f'Product ID is required.  Running akamai property manager cli command: {command}')
        sys.exit(os.system(command))

    utility_papi_object = utility_papi.papiFunctions()
    utility_waf_object = utility_waf.wafFunctions()

    # Determine necessary execution steps
    steps_object = steps.executionSteps()

    # validate setup steps when csv input provided
    utility_object.csv_validator(onboard_object, csv)
    utility_object.csv_2_property_dict(onboard_object)
    utility_object.validateSetupStepsCSV(onboard_object, wrapper_object, cli_mode='batch-create')

    # Got this far, we are ready to try and execute the actual steps
    if utility_object.valid is True:

        # create new cpcode for each hostname
        cpcodeList = {}
        for hostname in onboard_object.public_hostnames:
            if not click_args['use_cpcode']:
                cpcode = utility_papi_object.create_new_cpcode(onboard_object,
                                                            wrapper_object,
                                                            hostname,
                                                            onboard_object.contract_id,
                                                            onboard_object.group_id,
                                                            onboard_object.product_id)
            else:
                cpcode = int(click_args['use_cpcode'])
            cpcodeList[hostname] = cpcode
        # build dictonary of json rule trees based on hostnames/property names from csv input
        propertyJson, hostnameList = utility_object.csv_2_property_array(config, onboard_object, cpcodeList)
        onboard_object.public_hostnames = hostnameList

        # create new properties based on json rule tree dictionary
        propertyIdDict = utility_papi_object.batch_create_update_pm(config, onboard_object, wrapper_object, utility_object, propertyJson, cpcodeList)

        # activate to staging if required
        if onboard_object.activate_property_staging:
            activation_status, success_hostnames, failed_activations, activationDict = utility_papi_object.batch_activate_and_poll(wrapper_object,
                                                    propertyIdDict,
                                                    onboard_object.contract_id,
                                                    onboard_object.group_id,
                                                    version=1,
                                                    network='STAGING',
                                                    emailList=onboard_object.notification_emails,
                                                    notes='Onboard CLI Activation')
            # check to see if any activations failed
            if (len(failed_activations) > 0) or (activation_status is False):
                logger.error('Unable to activate property to staging network')
                for failedActivation in failed_activations:
                    logger.error(f'Unable to activate {failedActivation["propertyName"]} to staging network')
                    # get list of successfully activated properties
                if len(success_hostnames) == 0:
                    exit(-1)
                else:
                    logger.info('Proceeding with hostnames that were successfully activated')
            # remove hostnames from failed activations from WAF eligible hostnames
            onboard_object.public_hostnames = success_hostnames
        else:
            logger.info('Activate Property Staging: SKIPPING')

        # Add WAF selected hosts
        if onboard_object.add_selected_host:

            # First have to create a new WAF config version
            print()
            logger.warning('Onboarding Security Config')
            logger.debug(f'Trying to create new version for WAF configuration: {onboard_object.waf_config_name}')
            create_waf_version = utility_waf_object.createWafVersion(wrapper_object, onboard_object, notes=onboard_object.version_notes)
            wrapper_object.update_waf_config_version_note(onboard_object, notes=onboard_object.version_notes)
            if create_waf_version is False:
                sys.exit()

            # Created WAF config version, now can add selected hosts to it
            logger.debug(f'Trying to add property public_hostnames as selected hosts to WAF configuration: {onboard_object.waf_config_name}')
            add_hostnames = utility_waf_object.addHostnames(wrapper_object,
                                        onboard_object.public_hostnames,
                                        onboard_object.onboard_waf_config_id,
                                        onboard_object.onboard_waf_config_version)
            if add_hostnames is True:
                logger.info(f'Successfully added {onboard_object.public_hostnames} as selected hosts')
            else:
                logger.error('Unable to add selected hosts to WAF Configuration')
                exit(-1)
        else:
            logger.info('WAF Add Selected Hosts: SKIPPING')

        # Update WAF match target
        if onboard_object.update_match_target:
            modify_matchtarget = utility_waf_object.updateMatchTarget(wrapper_object,
                                        onboard_object.public_hostnames,
                                        onboard_object.onboard_waf_config_id,
                                        onboard_object.onboard_waf_config_version,
                                        onboard_object.waf_match_target_id)
            if modify_matchtarget:
                logger.info(f'Successfully added {onboard_object.public_hostnames} to WAF Configuration Match Target')
            else:
                sys.exit(logger.error('Unable to update match target in WAF Configuration'))

        else:
            logger.info('WAF Update Match Target: SKIPPING')

        # Activate WAF configuration to staging
        if onboard_object.activate_waf_policy_staging:
            waf_activation_status = utility_waf_object.activateAndPoll(wrapper_object, onboard_object, network='STAGING')
            if waf_activation_status is False:
                sys.exit(logger.error('Unable to activate WAF configuration to staging network'))
        else:
            logger.info('Activate WAF Configuration Staging: SKIPPING')

        # Activate property to production
        if onboard_object.activate_property_production:
            # get list of successful staging activations for production activation
            success_staging_activations = (list(filter(lambda x: x['activationStatus']['STAGING'] in ['ACTIVE'], activationDict)))

            activation_status, success_hostnames, failed_activations, activationDict = utility_papi_object.batch_activate_and_poll(wrapper_object,
                                                        success_staging_activations,
                                                        onboard_object.contract_id,
                                                        onboard_object.group_id,
                                                        version=1,
                                                        network='PRODUCTION',
                                                        emailList=onboard_object.notification_emails,
                                                        notes='Onboard CLI Activation')
        else:
            logger.info('Activate Property Production: SKIPPING')

        # Activate WAF configuration to production only after success delivery config in production
        if onboard_object.activate_waf_policy_production and activation_status == 'ACTIVE':
            waf_activation_status = utility_waf_object.activateAndPoll(wrapper_object, onboard_object, network='PRODUCTION')
            if waf_activation_status is False:
                sys.exit(logger.error('Unable to activate WAF configuration to production network'))
        else:
            logger.info('Activate WAF Configuration Production: SKIPPING')

        print()
        end_time = time.perf_counter()
        elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
        logger.info(f'TOTAL DURATION: {elapse_time}, End Akamai CLI onboard')

    else:
        logger.error('Please correct the setup json file settings and try again.')
        return 0

    return 0
    
def get_prog_name():
    prog = os.path.basename(sys.argv[0])
    if os.getenv('AKAMAI_CLI'):
        prog = 'akamai onboard'
    return prog


def get_cache_dir():
    if os.getenv('AKAMAI_CLI_CACHE_DIR'):
        return os.getenv('AKAMAI_CLI_CACHE_DIR')

    return os.curdir


def load_json(file):
    try:
        with open(file) as f:
            data = json.load(f)
        logger.info(f'Successfully read {file}')
    except (ValueError, FileNotFoundError) as e:
        lg._log_error(e)
    return data


if __name__ == '__main__':
    try:
        print()
        status = cli(prog_name='akamai onboard')
    except KeyboardInterrupt:
        exit(1)
