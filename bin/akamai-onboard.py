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

import configparser
import json
import logging
import os
import requests
import sys
import time
from time import strftime
from time import gmtime
from akamai.edgegrid import EdgeGridAuth, EdgeRc
import click
import wrapper_api
import onboard
import utility
import steps
import utility_papi
import utility_waf

"""
This code leverages Akamai OPEN API.
In case you need quick explanation contact the initiators.
Initiators: vbhat@akamai.com and aetsai@akamai.com
"""

PACKAGE_VERSION = "1.0.5"

# Setup logging
#if not os.path.exists('logs'):
#    os.makedirs('logs')
#log_file = os.path.join('logs', 'onboard.log')

# Set the format of logging in console and file separately
#log_formatter = logging.Formatter(
#    "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
#console_formatter = logging.Formatter("%(message)s")
#root_logger = logging.getLogger()

#logfile_handler = logging.FileHandler(log_file, mode='w')
#logfile_handler.setFormatter(log_formatter)
#root_logger.addHandler(logfile_handler)

#console_handler = logging.StreamHandler()
#console_handler.setFormatter(console_formatter)
#root_logger.addHandler(console_handler)
# Set Log Level to DEBUG, INFO, WARNING, ERROR, CRITICAL
#root_logger.setLevel(logging.INFO)


def init_config(edgerc_file, section):
    if not edgerc_file:
        if not os.getenv("AKAMAI_EDGERC"):
            edgerc_file = os.path.join(os.path.expanduser("~"), '.edgerc')
        else:
            edgerc_file = os.getenv("AKAMAI_EDGERC")

    if not os.access(edgerc_file, os.R_OK):
        print("Unable to read edgerc file \"%s\"" % edgerc_file)
        exit(1)

    if not section:
        if not os.getenv("AKAMAI_EDGERC_SECTION"):
            section = "onboard"
        else:
            section = os.getenv("AKAMAI_EDGERC_SECTION")

    try:
        edgerc = EdgeRc(edgerc_file)
        base_url = edgerc.get(section, 'host')

        session = requests.Session()
        session.auth = EdgeGridAuth.from_edgerc(edgerc, section)

        return base_url, session
    except configparser.NoSectionError:
        print("Edgerc section \"%s\" not found" % section)
        exit(1)
    except Exception:
        print(
            "Unknown error occurred trying to read edgerc file (%s)" %
            edgerc_file)
        exit(1)

class Config(object):
    def __init__(self):
        pass
pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group(context_settings={'help_option_names':['-h','--help']})
@click.option('--edgerc', metavar='', default=os.path.join(os.path.expanduser("~"),'.edgerc'),help='Location of the credentials file [$AKAMAI_EDGERC]', required=False)
@click.option('--section', metavar='', help='Section of the credentials file [$AKAMAI_EDGERC_SECTION]', required=False)
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


@cli.command(short_help='Create a configuration')
@click.option('--file', metavar='', help='File containing setup/onboard config key-value pairs in JSON', required=True)
@pass_config
def create(config, file):
    start_time = round(time.time())
    base_url, session = init_config(config.edgerc, config.section)
    account_switch_key = config.account_key

    #open setup.json to validate in next step
    try:
        with open(file, mode='r') as setup_file_handler:
            setup_json_content = json.load(setup_file_handler)

        #in the future, could look at validating the json schema

    except:
        print('ERROR: Unable to open setup file')
        exit(-1)



    #Object Instantiaions
    onboard_object = onboard.onboard(setup_json_content, config)
    wrapper_object = wrapper_api.apiCallsWrapper(base_url, account_switch_key)

    #Validate setup file
    utility_object = utility.utility()
    utility_papi_object = utility_papi.papiFunctions()
    utility_waf_object = utility_waf.wafFunctions()

    #Validate akamai cli and cli pipeline are installed
    cli_installed = utility_object.installedCommandCheck('akamai')
    pipeline_installed = utility_object.executeCommand(['akamai', 'pipeline'])

    #Determine necessary execution steps
    steps_object = steps.executionSteps()

    #Validate if setup steps are specified in the right order
    print('\n*************************************')
    print('**Validating setup file information**')
    print('*************************************\n')
    setup_values_validation = utility_object.validateSetupSteps(session, onboard_object, wrapper_object)

    #Got this far, we are ready to try and execute the actual steps
    if utility_object.valid is True:
        print('\n*************************************')
        print('**Starting onboarding process********')
        print('*************************************\n')

        #Create new cpcode
        if steps_object.doCreateNewCpCode(setup_json_content):
            utility_papi_object.createNewCpCode(session, onboard_object, wrapper_object, onboard_object.new_cpcode_name, onboard_object.contract_id, \
                                                        onboard_object.group_id, onboard_object.product_id)
        
        #Create the property, merge & update the property rules, figure out edgehostname logic
        utility_papi_object.createAndUpdateProperty(session, setup_json_content, onboard_object, wrapper_object, utility_object)

        #Activate property to staging
        if steps_object.doPropertyActivateStaging(setup_json_content):
            activation_status = utility_papi_object.activateAndPoll(session, wrapper_object, onboard_object.property_name, \
                                                    onboard_object.contract_id, onboard_object.group_id, onboard_object.onboard_property_id, version=1, \
                                                    network='STAGING', emailList=onboard_object.notification_emails, notes='Onboard CLI Activation')
            if activation_status is False:
                print('ERROR: Unable to activate property to staging network')
                exit(-1)
        else:
            print('\nActivate Property Staging: SKIPPING')

        #Add WAF selected hosts
        if steps_object.doWafAddSelectedHosts(setup_json_content):
            #First have to create a new WAF config version
            print('\nTrying to create new version for WAF configuration: ' + str(onboard_object.waf_config_name))
            create_waf_version = utility_waf_object.createWafVersion(session, setup_json_content, utility_object, wrapper_object, onboard_object)
            if create_waf_version is True:
                print('Successfully created WAF configuruation version: ' + str(onboard_object.onboard_waf_config_version))
            else:
                print('ERROR: Unable create new version for WAF configuration')
                exit(-1)

            #Created WAF config version, now can add selected hosts to it
            print('\nTrying to add property public_hostnames as selected hosts to WAF configuration: ' + str(onboard_object.waf_config_name))
            add_hostnames = utility_waf_object.addHostnames(session, wrapper_object, \
                                        onboard_object.public_hostnames, onboard_object.onboard_waf_config_id, onboard_object.onboard_waf_config_version)
            if add_hostnames is True:
                print('Successfully added ' + str(onboard_object.public_hostnames) + ' as selected hosts')
            else:
                print('ERROR: Unable to add selected hosts to WAF Configuration')
                exit(-1)
        else:
            print('\nWAF Add Selected Hosts: SKIPPING')

        #Update WAF match target
        if steps_object.doWafUpdateMatchTarget(setup_json_content):
            print('\nTrying to add property public_hostnames to WAF Match Target Id: ' + str(onboard_object.waf_match_target_id))

            modify_matchtarget = utility_waf_object.updateMatchTarget(session, wrapper_object, \
                                        onboard_object.public_hostnames, onboard_object.onboard_waf_config_id, onboard_object.onboard_waf_config_version, \
                                        onboard_object.waf_match_target_id)
            if modify_matchtarget is True:
                print('Successfully added ' + str(onboard_object.public_hostnames) + ' to WAF Configuration Match Target')
            else:
                print('ERROR: Unable to update match target in WAF Configuration')
                exit(-1)
        else:
            print('\nWAF Update Match Target: SKIPPING')

        #Activate WAF configuration to staging
        if steps_object.doWafActivateStaging(setup_json_content):
            waf_activation_status = utility_waf_object.activateAndPoll(session, wrapper_object, onboard_object, network='STAGING')
            if waf_activation_status is False:
                print('ERROR: Unable to activate WAF configuration to staging network')
                exit(-1)
        else:
            print('\nActivate WAF Configuration Staging: SKIPPING')

        #Activate property to production
        if steps_object.doPropertyActivateProduction(setup_json_content):
            activation_status = utility_papi_object.activateAndPoll(session, wrapper_object, onboard_object.property_name, \
                        onboard_object.contract_id, onboard_object.group_id, onboard_object.onboard_property_id, version=1, \
                        network='PRODUCTION', emailList=onboard_object.notification_emails, notes='Onboard CLI Activation')
            if activation_status is False:
                print('ERROR: Error activating property to production network')
                exit(-1)
        else:
            print('\nActivate Property Production: SKIPPING')

        #Activate WAF configuration to production
        if steps_object.doWafActivateProduction(setup_json_content):
            waf_activation_status = utility_waf_object.activateAndPoll(session, wrapper_object, onboard_object, network='PRODUCTION')
            if waf_activation_status is False:
                print('ERROR: Unable to activate WAF configuration to production network')
                exit(-1)
        else:
            print('\nActivate WAF Configuration Production: SKIPPING')

    else:
        print('\nPlease correct the setup json file settings and try again.')
        return 0

    print('\nEND')
    end_time = round(time.time())
    command_time = end_time - start_time
    print('TOTAL DURATION: ' + str(strftime("%H:%M:%S", gmtime(command_time))) + '\n')

    return 0


def get_prog_name():
    prog = os.path.basename(sys.argv[0])
    if os.getenv("AKAMAI_CLI"):
        prog = "akamai onboard"
    return prog


def get_cache_dir():
    if os.getenv("AKAMAI_CLI_CACHE_DIR"):
        return os.getenv("AKAMAI_CLI_CACHE_DIR")

    return os.curdir


if __name__ == '__main__':
    try:
        status = cli(prog_name='akamai onboard')
        exit(status)
    except KeyboardInterrupt:
        exit(1)
