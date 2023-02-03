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
from time import gmtime
from time import strftime

import _logging as lg
import click
import onboard
import onboard_single_host
import requests
import steps
import utility
import utility_papi
import utility_waf
import wrapper_api
from akamai.edgegrid import EdgeGridAuth
from akamai.edgegrid import EdgeRc
from exceptions import setup_logger
from model.single_host import SingleHost

"""
This code leverages Akamai OPEN API.
In case you need quick explanation contact the initiators.
Initiators: vbhat@akamai.com and aetsai@akamai.com
"""

PACKAGE_VERSION = '2.0.0'
logger = setup_logger()


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

    return session, wrap_api


@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--edgerc', metavar='', default=os.path.join(os.path.expanduser('~'), '.edgerc'),
              help='Location of the credentials file [$AKAMAI_EDGERC]', required=False)
@click.option('--section', metavar='', default='onboard',
              help='Section of the credentials file [$AKAMAI_EDGERC_SECTION]', required=False)
@click.option('--account-key', metavar='', help='Account Key', required=False)
@click.version_option(version=PACKAGE_VERSION)
@pass_config
def cli(config, edgerc, section, account_key):
    '''
    Akamai CLI for onboarding properties
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


@cli.command(short_help='Create a simple delivery and security configuration with one hostname and one WAF policy')
@click.option('--file', metavar='', required=True,
              help='File containing setup/onboard config key-value pairs in JSON')
@pass_config
def single_host(config, file):
    start_time = time.perf_counter()

    # Populate onboarding data from user input and default values
    json_data = load_json(file)
    setup = onboard_single_host.onboard(json_data)
    onboard = SingleHost(setup.property_name,
                         setup.contract_id,
                         setup.product_id,
                         setup.public_hostnames,
                         setup.edge_hostname,
                         setup.notification_emails
    )

    # Override default
    onboard.new_cpcode_name = setup.new_cpcode_name
    onboard.create_new_security_config = setup.create_new_security_config
    if len(setup.waf_config_name) > 0:
        onboard.waf_config_name = setup.waf_config_name
    home = str(Path.home())
    template_path = f'{home}/.akamai-cli/src/cli-onboard/templates/akamai_product_templates'
    onboard.source_template_file = f'{template_path}/{setup.product_id}.json'
    onboard.source_values_file = f'{template_path}/template_variables.json'
    logger.info(f'Rule Template Location: {onboard.source_template_file}')
    if setup.existing_enrollment_id > 0:
        onboard.use_existing_enrollment_id = True
        onboard.edge_hostname_mode = 'new_enhanced_tls_edgehostname'
        onboard.existing_enrollment_id = setup.existing_enrollment_id
    if setup.version_notes is not None:
        onboard.version_notes = setup.version_notes
    if not setup.activate_production:
        onboard.activate_property_production = False
        onboard.activate_waf_policy_production = False

    # Validate setup and akamai cli and cli pipeline are installed
    util = utility.utility()
    util.installedCommandCheck('akamai')
    util.executeCommand(['akamai', 'pipeline'])

    # Load business rule for delivery and security
    util_papi = utility_papi.papiFunctions()
    util_waf = utility_waf.wafFunctions()

    _, wrap_api = init_config(config)
    groups = wrap_api.get_groups_without_parent()
    for grp in groups:
        if grp['contractIds'][0] == onboard.contract_id:
            onboard.group_id = grp['groupId']
            exit
    if onboard.group_id is None:
        sys.exit(logger.error('Unknown Error: Cannot find top level group_id'))

    util.validateSetupSteps(onboard, wrap_api, cli_mode='single_host')
    if util.valid:
        if onboard.create_new_cpcode:
            util_papi.createNewCpCode(onboard, wrap_api,
                                      onboard.new_cpcode_name,
                                      onboard.contract_id,
                                      onboard.group_id,
                                      onboard.product_id)

        # Create the property, merge & update the property rules, figure out edgehostname logic
        util_papi.createAndUpdateProperty(config, onboard, wrap_api, util)

        if onboard.activate_property_staging is False:
            logger.info('Activate Property Staging: SKIPPING')
        else:
            status = util_papi.activateAndPoll(wrap_api,
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
            status = util_papi.activateAndPoll(wrap_api,
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
    print()
    end_time = time.perf_counter()
    elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
    logger.info(f'TOTAL DURATION: {elapse_time}, End Akamai CLI onboard')
    return 0


@cli.command(short_help='Create a configuration')
@click.option('--file', metavar='', help='File containing setup/onboard config key-value pairs in JSON', required=True)
@pass_config
def create(config, file):
    start_time = time.perf_counter()

    setup_json_content = load_json(file)
    onboard_object = onboard.onboard(setup_json_content, config)

    # Validate setup and akamai cli and cli pipeline are installed
    utility_object = utility.utility()
    utility_object.installedCommandCheck('akamai')
    utility_object.executeCommand(['akamai', 'pipeline'])

    # Validate akamai cli and cli pipeline are installed
    utility_papi_object = utility_papi.papiFunctions()
    utility_waf_object = utility_waf.wafFunctions()

    # Determine necessary execution steps
    steps_object = steps.executionSteps()
    _, wrapper_object = init_config(config)
    utility_object.validateSetupSteps(onboard_object, wrapper_object, cli_mode='create')

    # Got this far, we are ready to try and execute the actual steps
    if utility_object.valid is True:
        # Create new cpcode
        if steps_object.doCreateNewCpCode(setup_json_content):
            utility_papi_object.createNewCpCode(onboard_object, wrapper_object,
                                                onboard_object.new_cpcode_name,
                                                onboard_object.contract_id,
                                                onboard_object.group_id,
                                                onboard_object.product_id)

        # Create the property, merge & update the property rules, figure out edgehostname logic
        utility_papi_object.createAndUpdateProperty(config, onboard_object, wrapper_object, utility_object)

        # Activate property to staging
        if steps_object.doPropertyActivateStaging(setup_json_content):
            activation_status = utility_papi_object.activateAndPoll(wrapper_object,
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
            activation_status = utility_papi_object.activateAndPoll(wrapper_object,
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
        logger.info('Start Akamai CLI onboard')
        status = cli(prog_name='akamai onboard')
    except KeyboardInterrupt:
        exit(1)
