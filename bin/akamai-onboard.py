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
import subprocess
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path
from shutil import copytree
from time import gmtime
from time import strftime

import _logging as lg
import activation_manifest
import activation_status
import no_wait_activation
import onboard
import onboard_appsec_update
import onboard_batch_create
import onboard_convert
import onboard_multi_hosts
import onboard_single_host
import onboard_smoke_test
import pandas as pd
import requests
import rich_click as click
import steps
import util_emojis as emoji
import utility
import utility_papi
import utility_sbd
import utility_smoketest
import utility_waf
import wrapper_api
from akamai.edgegrid import EdgeGridAuth
from akamai.edgegrid import EdgeRc
from exceptions import apply_log_level_from_flags
from exceptions import get_cli_execution_directory
from exceptions import get_cli_root_directory
from exceptions import setup_logger
from model.appsec import AppSec
from model.appsec import Generic
from model.appsec import Property
from model.multi_hosts import MultiHosts
from model.single_host import SingleHost
from rich import print
from rich.console import Console
from tabulate import tabulate

if sys.platform == 'win32':
    # Windows consoles default to a non-UTF-8 codepage (e.g. cp1252) when stdout/stderr
    # aren't attached to a real terminal, which breaks the emoji used throughout the CLI's
    # help text and output (UnicodeEncodeError).
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logger = setup_logger()
root = get_cli_root_directory()
dir = get_cli_execution_directory()


def _load_package_metadata():
    """pyproject.toml is the single source of truth for the CLI's version/description.

    Resolved from this file's own location (not get_cli_root_directory()), so it always
    reflects the code that's actually running - the dev checkout under `uv run`, or the
    installed copy under `~/.akamai-cli/src/cli-onboard` - rather than whichever install
    happens to exist on disk.
    """
    package_root = Path(__file__).resolve().parent.parent
    with open(Path(package_root, 'pyproject.toml'), 'rb') as f:
        project = tomllib.load(f)['project']
    return project['version'], project['description']


PACKAGE_VERSION, PACKAGE_DESCRIPTION = _load_package_metadata()

click.rich_click.MAX_WIDTH = 120
click.rich_click.STYLE_USAGE = 'bold white'
click.rich_click.STYLE_USAGE_COMMAND = 'bold dark_orange'
click.rich_click.STYLE_OPTION_DEFAULT = 'bold dark_orange'

click.rich_click.SHOW_REQUIRED_OPTIONS = True
click.rich_click.STYLE_REQUIRED_LONG = 'bold red'
click.rich_click.STYLE_REQUIRED_SHORT = 'bold red'

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_CLICK_SHORT_HELP = True
click.rich_click.SHOW_METAVARS_COLUMN = False
click.rich_click.STYLE_HELPTEXT_FIRST_LINE = 'light_goldenrod2'
click.rich_click.STYLE_HELPTEXT = 'light_goldenrod2'


class Config:
    def __init__(self, utility_cls=None):
        # Injection seam for tests: convert() builds `utility.utility()` off of this
        # instead of importing the class directly, so tests can substitute a
        # subclass (e.g. one that skips the `akamai` CLI prereq shell-out and stubs
        # network calls) by constructing Config(utility_cls=...) and passing it as
        # `obj=` to CliRunner.invoke(), rather than monkeypatching utility.utility.
        self.utility_cls = utility_cls


pass_config = click.make_pass_decorator(Config, ensure=True)


def log_level_options(f):
    """Shared --log-level/--debug/--verbose options for the cli group and each subcommand."""
    f = click.option('--debug', '--verbose', 'verbose', is_flag=True, default=False,
                      help='shortcut for --log-level DEBUG')(f)
    f = click.option('--log-level', metavar='',
                      type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False),
                      default=None, help='Set logging verbosity')(f)
    return f


def no_wait_option(f):
    """Shared --no-wait option for every command that can activate production."""
    return click.option('--no-wait', metavar='', is_flag=True, default=False,
                         help='Submit production activation(s) and return immediately instead of polling for '
                              'completion; check status later with check-activation. Staging activation always waits.')(f)


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
            section = 'default'
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

    wrap_api = wrapper_api.apiCallsWrapper(session, base_url, config.account_key)
    if config.account_key:
        account_name = wrap_api.get_account_name(config.account_key)
        logger.warning(f'Account Name: {account_name} {config.account_key}')
        account_name = account_name.replace(' ', '_')  # replace empty space with underscore
        Path(f'input/{account_name}').mkdir(parents=True, exist_ok=True)
        Path(f'output/{account_name}').mkdir(parents=True, exist_ok=True)
        account_input_folder = f'input/{account_name}'
        account_output_folder = f'output/{account_name}'
    else:
        account_input_folder = ''
        account_output_folder = ''

    print('_' * 120)
    print()
    return session, wrap_api, account_input_folder, account_output_folder


@click.group(context_settings={'help_option_names': ['-h', '--help']},
             help=f'{PACKAGE_DESCRIPTION} (v{PACKAGE_VERSION})',
             invoke_without_command=True, no_args_is_help=False)
@click.option('--edgerc', metavar='', default=os.path.join(os.path.expanduser('~'), '.edgerc'),
              help='Location of the credentials file [$AKAMAI_EDGERC]', required=False)
@click.option('-s', '--section', metavar='', default='default',
              help='Section of the credentials file [$AKAMAI_EDGERC_SECTION]', required=False)
@click.option('-a', '--account-key', '--accountkey', '--accountSwitchKey', '--accountswitchkey',
              metavar='',
              help='Account Switch Key (Akamai Internal Only)', required=False)
@log_level_options
@click.version_option(version=PACKAGE_VERSION)
@click.pass_context
@pass_config
def cli(config, ctx, edgerc, section, account_key, log_level, verbose):
    apply_log_level_from_flags(log_level, verbose)
    config.edgerc = edgerc
    config.section = section
    config.account_key = account_key
    if ctx.invoked_subcommand is None:
        # Click 8.2+ raises NoArgsIsHelpError (exit code 2) when a group with
        # no_args_is_help gets no subcommand, which the akamai-cli wrapper
        # reports as a command failure. Show help and exit cleanly instead.
        click.echo(ctx.get_help())
        ctx.exit(0)


@cli.command()
@log_level_options
@click.pass_context
def help(ctx, log_level, verbose):
    '''
    Show help information
    '''
    apply_log_level_from_flags(log_level, verbose)
    print(ctx.parent.get_help())


@cli.command(short_help=f'{emoji.rainbow} Bring over delivery configs from Competitors {emoji.rainbow}')
@click.option('-c', '--contract', metavar='', help='contract ID')
@click.option('-g', '--group', metavar='', help='group ID')
@click.option('-p', '--product', metavar='', help='one of prd_SPM, prd_Fresca, prd_Site_Accel, prd_Download_Delivery (case sensitive)')
@click.option('-n', '--network', type=click.Choice(['ENHANCED_TLS', 'STANDARD_TLS']),
              help='network to use for edge hostnames (ENHANCED_TLS or STANDARD_TLS)',
              show_default=True, default='STANDARD_TLS')
@click.option('-d', '--directory', metavar='', help='directory where ruletree json files are', required=True)
@click.option('--csv', metavar='', help='csv file with headers hostname,propertyName', required=True)
@click.option('-f', '--rule-format', metavar='', help='rule format (typically latest, but can use frozen rule format if desired)', default='latest', show_default=True)
@click.option('--use-cpcode', metavar='', help='reuse existing numeric CP Code')
@click.option('--cert-mode', type=click.Choice(['SBD', 'CPS'], case_sensitive=False),
              default='SBD', show_default=True, help='Certificate mode')
@click.option('--use-existing-edgehostname', metavar='', default=None, is_flag=False,
              flag_value='CSV', help="Use existing edge hostnames. Pass an EHN name for a single EHN, or pass 'CSV' to use the edgeHostname column from the CSV.")
@click.option('--enrollment-id', metavar='', type=int, default=None,
              help='Existing CPS enrollment ID for creating CPS_MANAGED edge hostnames (one per property)')
@click.option('--media-ehn', type=click.Choice(['VOD', 'LIVE']), default='VOD', multiple=False, help='AMD Edge Hostname option (VOD, LIVE)', show_default=True)
@click.option('--gtm-domain', metavar='', multiple=False, default=None, help='gtm domain to use in properties', show_default=True)
@click.option('--activate', metavar='', type=click.Choice(['staging', 'production']), multiple=True, help='Options: staging, production')
@click.option('--email', metavar='', multiple=True, help='email(s) for activation notifications')
@click.option('--force', metavar='', is_flag=True, default=False, help='skip user confirmation prompt')
@click.option('--dryrun', metavar='', is_flag=True, default=False, help='admin - test config')
@click.option('--prefix', metavar='', help='admin - required for dryrun.')
@click.option('--launch/--no-launch', default=True, metavar='', help='automatically open excel application')
@no_wait_option
@log_level_options
@pass_config
def convert(config, **kwargs):
    """
    Bring over Cloudflare/Cloudfront/Imperva/Fastly configs to Akamai platform
    """
    apply_log_level_from_flags(kwargs.pop('log_level'), kwargs.pop('verbose'))
    logger.info('Start Akamai CLI onboard')
    start_time = time.perf_counter()
    try:
        _, papi, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1
    click_args = kwargs

    onboard_object = onboard_convert.onboard(config, click_args)
    onboard_object.account_switch_key = config.account_key

    if click_args['enrollment_id'] and click_args['cert_mode'].upper() != 'CPS':
        sys.exit(logger.error('--enrollment-id requires --cert-mode CPS'))

    # Validate setup and akamai cli and cli pipeline are installed
    util_papi = utility_papi.papiFunctions()
    util = (config.utility_cls or utility.utility)()
    util.check_cli_prereq(click_args, config)

    if util.check_api_access(papi):
        sys.exit()

    # validate setup steps when csv input provided
    logger.warning(f'{emoji.checking} Validating setup information. Please wait, may take a few moments')
    print('_' * 120)
    print()

    onboard_object.csv_dict = util.load_csv_input(click_args['csv'], function='convert')
    loaded_properties = onboard_object.csv_dict

    if not click_args['dryrun']:
        if click_args['prefix']:
            sys.exit(logger.error('--prefix is require under --dryrun mode'))
    else:
        prefix = click_args['prefix']
        if not prefix:
            sys.exit(logger.error('--dryrun requires --prefix argument'))
        replace_properties = []
        for i, _prop in enumerate(loaded_properties, start=1):
            _properties = {}
            _properties['hostname'] = f'{prefix}{i}.com'
            _properties['propertyName'] = f"{prefix}{_prop['propertyName']}"
            _properties['product'] = click_args['product'] if click_args['product'] else _prop['product']
            _properties['group'] = _prop['GroupID']
            replace_properties.append(_properties)
        onboard_object.csv_dict = replace_properties

    replace_properties = []
    for i, _prop in enumerate(loaded_properties, start=1):
        _properties = {}
        _properties['hostname'] = _prop['hostname']
        _properties['propertyName'] = _prop['propertyName']
        _properties['product'] = click_args['product'] if click_args['product'] else _prop['product']
        if 'edgeHostname' in _prop and click_args['use_existing_edgehostname'] == 'CSV':
            _properties['edgeHostname'] = _prop['edgeHostname']
        replace_properties.append(_properties)
    onboard_object.csv_dict = replace_properties

    propertyList, hostnameList = util.csv_2_property_dict_convert(onboard_object)
    property_dict = util.csv_2_property_array_convert(onboard_object, click_args['prefix'])

    # validate if account has enough SBD to proceed
    if click_args['cert_mode'].upper() == 'SBD' and not click_args['use_existing_edgehostname']:
        valid_quota = util.check_sbd_quota(papi, click_args, len(onboard_object.property_list))
        if valid_quota is not None and not valid_quota:
            akam = []
            for key, value in property_dict.items():
                ehns = value['edgeHostnames']
                akam.extend([ehn for ehn in ehns if ehn.endswith('.akamaized.net')])

            if len(akam) == 0:
                return -1
            else:
                csv_file = click_args['csv']
                try:
                    csv_file = csv_file.split('/')[-1]
                except Exception as e:
                    logger.info(e)

    # Got this far, we are ready to try and execute the actual steps
    valid_steps = util.validateSetupStepsConvert(onboard_object, papi, click_args['prefix'])
    if not valid_steps:
        logger.error('Please correct the setup json file settings and try again.')
        return -1
    else:
        print()
        if click_args['use_cpcode']:
            logger.warning(f'Reusing existing cpCode {int(click_args['use_cpcode'])}')
        else:
            logger.warning('Finding cpCodes to use')

        all_smoketest = []
        sheet = {}
        for property in property_dict:
            custom_solution = False  # csv doesn't have GroupID header
            onboard_object.ok_to_activate = True
            original_ruletree = property_dict[property]['ruleTree']

            if not click_args['use_cpcode']:
                logger.critical(f'{emoji.dart}{property}')

            try:
                comments = original_ruletree['comments']
            except KeyError:
                comments = 'Created using CLI-Onboard'

            # convert ruletree to amd
            if property_dict[property]['product'] == 'prd_Adaptive_Media_Delivery':
                amd_rule_tree = util.convert_property_amd(original_ruletree, onboard_object)
                original_ruletree = amd_rule_tree
            if property_dict[property]['product'] in ['prd_Site_Accel' or 'Site_Accel']:
                dsa_rule_tree = util.convert_property_dsa(original_ruletree)
                original_ruletree = dsa_rule_tree

            level0 = original_ruletree['rules']
            host = property_dict[property]['hostnames'][0]
            cpcode_name = f'{host}'
            if not click_args['use_cpcode']:
                if onboard_object.group_id is None:
                    onboard_object.group_id = property_dict[property]['group']
                    custom_solution = True

                logger.debug(f'{onboard_object.group_id=}')
                cpcode = util_papi.search_for_cpcode(onboard, papi, cpcode_name,
                                                        onboard_object.contract_id,
                                                        onboard_object.group_id,
                                                        property_dict[property]['product'], 'default')
                if not cpcode:
                    cpcode = util_papi.create_new_cpcode(onboard, papi, cpcode_name,
                                                        onboard_object.contract_id,
                                                        onboard_object.group_id,
                                                        property_dict[property]['product'], 'default')
            else:
                cpcode = int(click_args['use_cpcode'])
            original_ruletree = util_papi.inject_cpcode_behavior(level0, cpcode)
            all_smoketest.append([host, '/', cpcode])

            property_dict[property]['ruleTree'] = {'rules': original_ruletree}
            property_dict[property]['comments'] = comments
            if custom_solution is True:
                onboard_object.group_id = None

            with open(f'logs/{property}_v1.json', 'w') as outfile:
                json.dump(original_ruletree, outfile, ensure_ascii=True, indent=2)

        logger.debug(all_smoketest)
        headers = ['hostname', 'scope', 'cpcode']
        dt_string = datetime.now().strftime('%Y%m%d_%H%M_')

        print()
        msg = 'smoke-test input'

        # create new properties based on json rule tree dictionary
        propertyIds_list, skip_property = util_papi.batch_create_update_pm_convert(config,
                                                                                   onboard_object,
                                                                                   papi,
                                                                                   property_dict,
                                                                                   click_args['dryrun'])
        logger.debug(f'{propertyIds_list=}')
        logger.debug(f'{skip_property=}')

        properties_to_activate = list(filter(lambda x: x['propertyId'] not in skip_property, propertyIds_list))
        logger.debug(properties_to_activate)
        # activate to staging if required
        success_hostnames = []
        stg_df = pd.DataFrame()
        if len(properties_to_activate) > 0 and onboard_object.activate_property_staging:
            activation_status, success_hostnames, failed_activations, stg_activation = util_papi.batch_activate_and_poll(papi,
                                                    properties_to_activate,
                                                    onboard_object.contract_id,
                                                    onboard_object.group_id,
                                                    version=1,
                                                    network='STAGING',
                                                    emailList=onboard_object.notification_emails,
                                                    notes='Onboard CLI Activation')

            # check to see if any activations failed
            if (len(failed_activations) > 0) or (activation_status is False):
                for failedActivation in failed_activations:
                    logger.error(f'{emoji.fail} Unable to activate {failedActivation['propertyName']} to staging network {emoji.attention}')
                    # get list of successfully activated properties
                if len(success_hostnames) > 0:
                    logger.info('Proceeding with hostnames that were successfully activated')

            # remove hostnames from failed activations from WAF eligible hostnames
            onboard_object.public_hostnames = success_hostnames

            stg_df = pd.DataFrame(stg_activation)
            end_time = time.perf_counter()
            elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
            if activation_status:
                logger.info(f'activation time total: {elapse_time}\n')
        else:
            print()
            logger.info('Activate Property Staging: SKIPPING')

        # Activate property to production
        prd_df = pd.DataFrame()
        if len(success_hostnames) > 0 and onboard_object.activate_property_production:
            # get list of successful staging activations
            success_staging_activations = (list(filter(lambda x: x['activationStatus']['STAGING'] in ['ACTIVE'], stg_activation)))
            if click_args['no_wait']:
                manifest_path = activation_manifest.new_manifest_path(account_output)
                _, prd_activation = util_papi.batch_activate_and_poll(papi,
                                                            success_staging_activations,
                                                            onboard_object.contract_id,
                                                            onboard_object.group_id,
                                                            version=1,
                                                            network='PRODUCTION',
                                                            emailList=onboard_object.notification_emails,
                                                            notes='Onboard CLI Activation',
                                                            no_wait=True)
                activation_manifest.append_batch(manifest_path, prd_activation, version=1)
                activation_manifest.stamp_batch_report_status(prd_activation)
                prd_df = pd.DataFrame(prd_activation)
            else:
                activation_status, success_hostnames, failed_activations, prd_activation = util_papi.batch_activate_and_poll(papi,
                                                            success_staging_activations,
                                                            onboard_object.contract_id,
                                                            onboard_object.group_id,
                                                            version=1,
                                                            network='PRODUCTION',
                                                            emailList=onboard_object.notification_emails,
                                                            notes='Onboard CLI Activation')
                prd_df = pd.DataFrame(prd_activation)
                end_time = time.perf_counter()
                elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
                if activation_status:
                    print()
                    logger.info(f'activation time total: {elapse_time}\n')
        else:
            logger.info('Activate Property Production: SKIPPING')

        activation_df = pd.DataFrame()
        if onboard_object.activate_property_staging:
            # provide activation result in excel
            activation_df = pd.concat([stg_df, prd_df], ignore_index=True)
            activation_df = activation_df.reset_index(drop=True)
            activation_df.index = activation_df.index + 1

        # Final logging to excel
        for property in property_dict:
            property_dict[property]['ruleTree'] = ''

        result_df = pd.DataFrame(property_dict).T
        result_df.index.name = 'propertyName'
        result_df = result_df.reset_index()

        cols = ['error_flags', 'hostnames', 'edgeHostnames']
        for col in cols:
            result_df[col] = result_df.apply(lambda row: utility.split_elements_newline_withcomma(row[col])
                                                        if row[col] else '', axis=1)
        cols.insert(0, 'propertyName')
        cols.insert(1, 'product')
        cols.insert(4, 'comments')
        result_df = result_df.rename(columns={'url': 'propertyName'})

        sheet['properties'] = result_df[cols]

        if not activation_df.empty:
            sheet['activation_status'] = activation_df

        activation_df = pd.DataFrame()

        conversion_filepath = f'{account_output}/{dt_string}conversion-result.xlsx'
        logger.info('conversion (activation) output')
        logger.info(f'{conversion_filepath} {emoji.bow}')
        utility.write_xlsx(conversion_filepath, sheet, show_index=False, freeze_column=1)
        open_excel_automatically = kwargs['launch'] if kwargs['launch'] else False
        if open_excel_automatically:
            utility.open_excel_application(conversion_filepath, result_df)

        print()
        util.log_cli_timing()
    return 0


@cli.command(short_help='Pull sample templates')
@log_level_options
def fetch_sample_templates(log_level, verbose):
    """
    Retrieve sample templates for available commands
    """
    apply_log_level_from_flags(log_level, verbose)
    source_folder = Path(root, 'templates', 'sample_setup_files')
    Path('sample_templates').mkdir(parents=True, exist_ok=True)
    target_folder = Path().resolve()
    target_folder = Path(target_folder, 'sample_templates')

    copytree(source_folder, target_folder, dirs_exist_ok=True)
    logger.info(f'Sample templates can be found in directory {target_folder}')


@cli.command(short_help='Create a delivery configuration with mutltiple hostnames and security configuration with one WAF policy')
@click.option('--csv', metavar='', required=True,
              help='CSV input file without headers.  Data in format hostname,origin-hostname')
@click.option('-f', '--file', metavar='', required=True,
              help='File containing setup/onboard config key-value pairs in JSON')
@no_wait_option
@log_level_options
@pass_config
def multi_hosts(config, csv, file, no_wait, log_level, verbose):
    """
    Simplify onboarding ONE property with multiple hostnames and optionally multiple CPCodes
    """
    apply_log_level_from_flags(log_level, verbose)
    logger.info('Start Akamai CLI onboard')
    try:
        _, wrap_api, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1
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
    if not onboard.group_id:
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
            activation_kwargs = dict(wrapper_object=wrap_api,
                                      property_name=onboard.property_name,
                                      contract_id=onboard.contract_id,
                                      group_id=onboard.group_id,
                                      property_id=onboard.onboard_property_id, version=1,
                                      network='PRODUCTION',
                                      emailList=onboard.notification_emails,
                                      notes='Onboard CLI Activation')
            if no_wait:
                manifest_path = activation_manifest.new_manifest_path(account_output)
                no_wait_activation.fire_single_property_production(util_papi, util_waf, wrap_api, onboard, manifest_path)
            else:
                status = util_papi.activate_and_poll(**activation_kwargs)
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
@no_wait_option
@log_level_options
@pass_config
def single_host(config, file, no_wait, log_level, verbose):
    """
    Simplify onboarding ONE property.  By default, delivery config will be activating on STAGING network.
    Security config will also be activating on STAGING network if create_new_security_config is True.
    """
    apply_log_level_from_flags(log_level, verbose)
    logger.info('Start Akamai CLI onboard')
    try:
        _, wrap_api, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1
    util = utility.utility()

    # Populate onboarding data from user input and default values
    setup = onboard_single_host.onboard(load_json(file))
    onboard = SingleHost(setup.property_name, setup.contract_id, setup.product_id,
                         setup.public_hostnames,
                         setup.secure_by_default, setup.edge_hostname,
                         setup.notification_emails)

    # Override default
    util.onboard_override_default(onboard, setup, cli_mode='single-host')
    if not onboard.group_id:
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
            activation_kwargs = dict(wrapper_object=wrap_api,
                                      property_name=onboard.property_name,
                                      contract_id=onboard.contract_id,
                                      group_id=onboard.group_id,
                                      property_id=onboard.onboard_property_id, version=1,
                                      network='PRODUCTION',
                                      emailList=onboard.notification_emails,
                                      notes='Onboard CLI Activation')
            if no_wait:
                manifest_path = activation_manifest.new_manifest_path(account_output)
                no_wait_activation.fire_single_property_production(util_papi, util_waf, wrap_api, onboard, manifest_path)
            else:
                status = util_papi.activate_and_poll(**activation_kwargs)
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


@cli.command(short_help='Check status of activation(s) submitted earlier with --no-wait')
@click.option('--file', metavar='', default=None, help='CSV of activations to check')
@click.option('--activation-id', metavar='', default=None,
              help='single activation id to check, for an ad-hoc check without --file')
@click.option('--property-id', metavar='', default=None,
              help='property id for the ad-hoc check (delivery activation); omit for a WAF activation')
@click.option('--version', metavar='', default=None, help='property/config version, display only, for the ad-hoc check')
@click.option('-c', '--contract', metavar='', default=None,
              help='Contract ID; required to check any delivery activation')
@click.option('-g', '--group', metavar='', default=None,
              help='Group ID; required to check any delivery activation')
@click.option('--wait', metavar='', is_flag=True, default=False,
              help='Poll until every activation is active (or errored) instead of checking once and exiting')
@log_level_options
@pass_config
def check_activation(config, file, activation_id, property_id, version, contract, group, wait, log_level, verbose):
    """
    Check current status of activation(s) submitted earlier with --no-wait,
    or of a minimal hand-built CSV of activation IDs collected from
    elsewhere (see --file).

    By default queries each activation exactly once and exits -- does not
    poll or block. With --wait, polls until every activation is active or
    errored instead. Exit code is 0 if everything checked is active, non-zero
    otherwise.
    """
    apply_log_level_from_flags(log_level, verbose)
    logger.info('Start Akamai CLI onboard check-activation')
    try:
        _, wrap_api, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        sys.exit(1)

    if file:
        try:
            rows = activation_status.load_manifest_rows(file)
        except ValueError as err:
            # not lg._log_error(err) -- it calls a bare sys.exit() internally,
            # which exits 0, defeating check-activation's exit-code contract.
            logger.error(str(err))
            sys.exit(1)
    elif activation_id:
        rows = [{'property_name': property_id or activation_id, 'property_id': property_id or '',
                 'version': version or '', 'activation_id': activation_id}]
    else:
        logger.error('Must provide either --file or --activation-id')
        sys.exit(1)

    if not rows:
        logger.error(f'No activation rows found in {file}')
        sys.exit(1)

    if wait:
        results = activation_status.wait_until_done(wrap_api, rows, contract, group)
    else:
        results = activation_status.check_all(wrap_api, rows, contract, group)
        console = Console()
        console.print(activation_status.build_status_table(results))

    all_active = all(r['is_active'] for r in results)
    sys.exit(0 if all_active else 1)


@cli.command(short_help='Create a delivery configuration and update existing WAF policy')
@click.option('-f', '--file', metavar='', help='File containing setup/onboard config key-value pairs in JSON', required=True)
@log_level_options
@pass_config
def create(config, file, log_level, verbose):
    apply_log_level_from_flags(log_level, verbose)
    logger.info('Start Akamai CLI onboard')
    try:
        _, wrapper_object, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1
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
@click.option('-c', '--contract', metavar='', help='Contract ID (starts with ctr)', required=True)
@click.option('-g', '--group', metavar='', help='Group ID (starts with grp)', required=True)
@click.option('-p', '--product', metavar='', help='one of prd_SPM, prd_Fresca, prd_API_Accel (case sensitive)', required=True)
@click.option('-f', '--rule-format', metavar='', help='rule format (typically latest, but can use frozen rule format if desired)', default='latest', show_default=True)
@click.option('--use-cpcode', metavar='', help='override creating new cpcode for each hostname', required=False)
@click.option('--secure-by-default', metavar='', is_flag=True, default=False, help='use secure by default certificates', required=False)
@click.option('--waf-config', metavar='', help='name of security configuration to update', required=False)
@click.option('--waf-match-target', metavar='', help='waf match target id to add hostnames to (use numeric waf match target id)', required=False)
@click.option('--activate', metavar='', type=click.Choice(['delivery-staging', 'waf-staging', 'delivery-production', 'waf-production']), multiple=True, help='Options: delivery-staging, delivery-production, waf-staging, waf-production', required=False)
@click.option('--email', metavar='', multiple=True, help='email(s) for activation notifications', required=False)
@click.option('--csv', metavar='', required=True, help='csv file with headers hostname,origin,propertyName,forwardHostHeader,edgeHostname')
@no_wait_option
@log_level_options
@pass_config
def batch_create(config, **kwargs):
    """
    Create a 1 or more delivery configurations using a csv input and optionally update WAF policy
    """
    apply_log_level_from_flags(kwargs.pop('log_level'), kwargs.pop('verbose'))
    logger.info('Start Akamai CLI onboard')
    try:
        _, wrapper_object, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1
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
        command = (f'akamai pm lg -s default -a {config.account_key}') if config.account_key is not None else ('akamai pm lg')
        logger.warning(f'Group ID is required.  Running akamai property manager cli command: {command}')
        sys.exit(subprocess.run(command, shell=True).returncode)

    if click_args['contract'] is None:
        command = (f'akamai pm lc -s default -a {config.account_key}') if config.account_key is not None else ('akamai pm lc')
        logger.warning(f'Contract ID is required.  Running akamai property manager cli command: {command}')
        sys.exit(subprocess.run(command, shell=True).returncode)

    if click_args['product'] is None:
        command = (f"akamai pm lp -s default -c {click_args['contract']} -a {config.account_key}") if config.account_key is not None else (f"akamai pm lc -c {click_args['contract']}")
        logger.warning(f'Product ID is required.  Running akamai property manager cli command: {command}')
        sys.exit(subprocess.run(command, shell=True).returncode)

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
                    logger.error(f'Unable to activate {failedActivation['propertyName']} to staging network')
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
        if click_args['no_wait']:
            manifest_path = activation_manifest.new_manifest_path(account_output)

            if onboard_object.activate_property_production:
                # get list of successful staging activations for production activation
                success_staging_activations = (list(filter(lambda x: x['activationStatus']['STAGING'] in ['ACTIVE'], activationDict)))

                _, activationDict = utility_papi_object.batch_activate_and_poll(wrapper_object,
                                                            success_staging_activations,
                                                            onboard_object.contract_id,
                                                            onboard_object.group_id,
                                                            version=1,
                                                            network='PRODUCTION',
                                                            emailList=onboard_object.notification_emails,
                                                            notes='Onboard CLI Activation',
                                                            no_wait=True)
                activation_manifest.append_batch(manifest_path, activationDict, version=1)
            else:
                logger.info('Activate Property Production: SKIPPING')

            # WAF production activation fires regardless of delivery's outcome under --no-wait -- see issue 01
            if onboard_object.activate_waf_policy_production:
                waf_submitted, waf_activation_id = utility_waf_object.activateAndPoll(wrapper_object, onboard_object,
                                                                                       network='PRODUCTION', no_wait=True)
                if waf_submitted:
                    logger.info(f'WAF configuration production activation submitted, activation id: {waf_activation_id}')
                    activation_manifest.append_activation(manifest_path, onboard_object.waf_config_name, '',
                                                           onboard_object.onboard_waf_config_version, waf_activation_id)
                else:
                    logger.error('Unable to submit WAF configuration activation to production network')
            else:
                logger.info('Activate WAF Configuration Production: SKIPPING')
        else:
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


@cli.command(short_help=f'{emoji.heavy_check_mark} View Default DV (SBD) certificate deployment status')
@log_level_options
@pass_config
def sbd_status(config, **kwargs):
    """
    Check status of all secure by default hostnames on an account
    """
    apply_log_level_from_flags(kwargs.pop('log_level'), kwargs.pop('verbose'))
    logger.info('Start Akamai CLI onboard Secure by Default Status')

    # Validate akamai cli and cli pipeline are installed
    try:
        _, wrapper_object, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1

    util = utility.utility()
    cli_installed = util.installedCommandCheck('akamai')
    pipeline_installed = util.executeCommand(['akamai', 'pipeline'])

    if not (pipeline_installed and (cli_installed or pipeline_installed)):
        sys.exit()

    # utility_papi_object = utility_papi.papiFunctions()
    utility_sbd_object = utility_sbd.sbdFunctions(wrapper_object.session)

    sbd_hostnames = utility_sbd_object.get_sbd_hostnames(wrapper_object)
    if sbd_hostnames:
        logger.info(f'Found {len(sbd_hostnames)} DEFAULT hostnames, checking status. {emoji.magnify_glass}')
    else:
        logger.info(f'Found no DEFAULT hostnames... {emoji.shrug}')
        util.log_cli_timing()
        exit(0)

    unique_properties = utility_sbd_object.get_unique_properties(sbd_hostnames)

    logger.info(f'Pulling down {len(unique_properties)} unique properties to fetch status. {emoji.looking}')

    hostname_status = utility_sbd_object.get_papi_hostname_status(wrapper_object, unique_properties, sbd_hostnames)
    stalled_status = ['PENDING', 'STALLED', 'DEPLOYING']
    #  stalled_hostnames = list(filter(lambda x: (x['productionStatus'] in stalled_status and x['production'] != '') or x['stagingStatus'] in stalled_status, hostname_status))
    stalled_hostnames = list(filter(lambda x: (x.get('productionStatus', '') in stalled_status and x.get('production', '') != '') or x.get('stagingStatus', '') in stalled_status, hostname_status))

    keys_to_remove = ['groupId', 'contractId', 'staging', 'production']
    for d in stalled_hostnames:
        if d['production'] == '':
            d['productionStatus'] = 'AWAITING_PRODUCTION_ACTIVATION'
        for key in keys_to_remove:
            d.pop(key, None)

    if stalled_hostnames:
        table = utility_sbd_object.create_output_table(stalled_hostnames, stalled_status)
        logger.info(f'{len(stalled_hostnames)} stalled hostnames found. {emoji.attention}')
        print('_' * 120)
        console = Console()
        print()
        console.print(table)
    else:
        logger.info(f'No stalled hostnames found {emoji.tada}')

    print()
    if stalled_hostnames:
        sbd_output_filename = 'sbd_output.csv'
        _DataFrame = pd.DataFrame(stalled_hostnames)
        _DataFrame.to_csv(sbd_output_filename, encoding='utf-8', index=False)
        logger.info(f'CSV output contains all hostnames checked with the PAPI status, please review {emoji.attention}')
        logger.info(f'{sbd_output_filename} {emoji.bow}')
    util.log_cli_timing()


@cli.command(short_help=f'{emoji.heavy_check_mark} Precheck Default DV (SBD) hostnames for token placement')
@click.option('--csv', metavar='', required=True, help='csv file with a list of hostnames')
@click.option('--launch/--no-launch', default=True, metavar='', help='automatically open excel application')
@click.option('--tokens-only', default=False, is_flag=True, metavar='', help='skip dns check to see if acme record is valid (only generate tokens)')
@log_level_options
@pass_config
def sbd_precheck(config, **kwargs):
    """
    Precheck Default DV (SBD) hostnames for token placement
    """
    apply_log_level_from_flags(kwargs.pop('log_level'), kwargs.pop('verbose'))
    logger.info('Start Akamai CLI onboard Secure by Default Precheck')

    # Validate akamai cli and cli pipeline are installed
    try:
        _, wrapper_object, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1

    precheck_object = onboard_smoke_test.smoketest(config, kwargs)
    csv = kwargs['csv']
    util = utility.utility()
    cli_installed = util.installedCommandCheck('akamai')
    pipeline_installed = util.executeCommand(['akamai', 'pipeline'])

    if not (pipeline_installed and (cli_installed or pipeline_installed)):
        sys.exit()

    utility_papi_object = utility_papi.papiFunctions()
    utility_precheck_object = utility_smoketest.smoketestFunctions(wrapper_object.session)
    utility_precheck_object.getHostnamesFromCsv(precheck_object)  # import hostnames to list

    utility_papi_object.get_acme_challenges(config, precheck_object, wrapper_object)  # get acme tokens
    if kwargs['tokens_only']:
        token_output = []
        precheck_file = 'sbd-tokens.csv'
        for hostname in precheck_object.acme_challenges:
            token_output.append({
                'hostname': hostname['cnameFrom'],
                'acme_hostname': hostname['validationCname']['hostname'],
                'acme_target': hostname['validationCname']['target']})
        filename = utility_precheck_object.buildOutputcsv_sbd_tokens_only(token_output, precheck_file, account_output)
    else:
        logger.info('Validating acme tokens...')

        utility_precheck_object.check_acme_dns_sbd_precheck(precheck_object)

        precheck_file = 'certificate-sbd-precheck.xlsx'
        open_excel_automatically = kwargs['launch'] if kwargs['launch'] else False
        filename = utility_precheck_object.buildOutputXLS_sbd_precheck(precheck_object,
                                                                    precheck_file,
                                                                    directory=account_output,
                                                                    launch=open_excel_automatically)

    print()
    logger.info(f'Review this output before running convert command {emoji.attention}')
    logger.info(f'{filename} {emoji.bow}')
    util.log_cli_timing()


@cli.command(short_help='Add hostnames as selected hosts to existing security configuration and optionally add to policy match target')
@click.option('--config-id', metavar='', help='security configuration id (numeric), or run appsec-policy to get all available config', required=True)
@click.option('--csv', metavar='', required=True, help='csv file with headers hostname,matchTargetId')
@click.option('--version-notes', metavar='', help='notes for the new version', required=False)
@click.option('--activate', metavar='', type=click.Choice(['staging', 'production']), multiple=True, help='Options: staging, production', required=False, default=[])
@click.option('--version', metavar='', help='version to add hostname(s) to', default='latest', required=False)
@click.option('--email', metavar='', required=False, help='email for activation notifications')
@no_wait_option
@log_level_options
@pass_config
def appsec_update(config, **kwargs):
    """
    Update existing security configuration

    \b
    Add additional hostnames and optionally add to policy match target
    """
    apply_log_level_from_flags(kwargs.pop('log_level'), kwargs.pop('verbose'))
    logger.info('Start Akamai CLI onboard')
    try:
        _, wrapper_object, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1
    util = utility.utility()
    click_args = kwargs

    onboard_object = onboard_appsec_update.onboard(click_args)

    # Validate setup and akamai cli and cli pipeline are installed
    csv = click_args['csv']

    # Validate akamai cli and cli pipeline are installed
    cli_installed = util.installedCommandCheck('akamai')
    pipeline_installed = util.executeCommand(['akamai', 'pipeline'])

    if not (pipeline_installed and (cli_installed or pipeline_installed)):
        sys.exit()

    # validate setup steps when csv input provided
    util.csv_validator_appsec(onboard_object, csv)
    util.csv_2_appsec_array(onboard_object)
    util.validateAppsecSteps(onboard_object, wrapper_object, cli_mode='appsec-update')

    if util.valid is True:
        utility_waf_object = utility_waf.wafFunctions()
        # First create new WAF configuration version
        logger.debug(f'Trying to create new version for WAF configuration: {onboard_object.waf_config_name}')
        create_waf_version = utility_waf_object.createWafVersion(wrapper_object, onboard_object, notes=onboard_object.version_notes)
        wrapper_object.update_waf_config_version_note(onboard_object, notes=onboard_object.version_notes)
        if create_waf_version is False:
            sys.exit()

        # Created WAF config version, now can add selected hosts to it
        logger.debug(f'Trying to add property public_hostnames as selected hosts to WAF configuration: {onboard_object.waf_config_name}')
        hostnames_to_add = list(filter(lambda x: x not in onboard_object.skip_selected_hosts, onboard_object.hostname_list))
        add_hostnames = utility_waf_object.addHostnames(wrapper_object,
                                                        hostnames_to_add,
                                                        onboard_object.config_id,
                                                        onboard_object.onboard_waf_config_version)
        if add_hostnames is True:
            logger.info(f'Selected hosts: Successfully added {hostnames_to_add}')
        else:
            logger.error('Unable to add selected hosts to WAF Configuration')
            exit(-1)

        # Update WAF match target
        policy_id = ''
        for policy in onboard_object.appsec_json:
            policy_hostnames_to_add = list(filter(lambda x: x not in onboard_object.skip_selected_hosts, onboard_object.appsec_json[policy]['hostnames']))
            modify_matchtarget, policy_id = utility_waf_object.updateMatchTarget(wrapper_object,
                                                                                 policy_hostnames_to_add,
                                                                                 onboard_object.config_id,
                                                                                 onboard_object.onboard_waf_config_version,
                                                                                 policy)
            if modify_matchtarget:
                resp = utility_waf_object.get_security_policy(wrapper_object, onboard_object.config_id, onboard_object.onboard_waf_config_version, policy_id)
                policy_name = resp['policyName']
                logger.info(f"WAF Configuration Match Target '{policy_name}/{policy_id}': Successfully added {policy_hostnames_to_add}")
            else:
                logger.error(f"Failed to add {policy_hostnames_to_add} to match target '{policy_name}/{policy_id}'")

        # Activate WAF configuration to staging
        if click_args['activate']:
            no_wait_activation.fire_appsec_update_activations(
                utility_waf_object, wrapper_object, onboard_object, click_args['activate'], click_args['no_wait'],
                activation_manifest.new_manifest_path(account_output))
        else:
            print()
            logger.warning('Activate WAF Configuration Production: SKIPPING')

        util.log_cli_timing()


@cli.command(short_help='List available security configuration policy')
@click.option('--waf-config-name', metavar='', help='Security config name', required=False)
@click.option('--policy-name', metavar='', help='Security policy name, exact match', required=False)
@click.option('--name-contains', metavar='', help='Keyword search security config by name', required=False)
@log_level_options
@pass_config
def appsec_policy(config, waf_config_name, policy_name, name_contains, log_level, verbose):
    """
    List available security configuration policy
    """
    apply_log_level_from_flags(log_level, verbose)
    logger.info('Start Akamai CLI onboard')
    try:
        _, wrap_api, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1
    util = utility.utility()
    config_id, version, df = util.validate_waf_config_name(wrap_api, waf_config_name)
    if not waf_config_name:
        logger.warning('WAF Security Configuration')
        if name_contains:
            df = df[df['name'].str.contains(name_contains)]
        if not df.empty:
            print(tabulate(df[['name', 'id']], headers='keys', tablefmt='psql', showindex=False))
            logger.warning('Add --waf-config-name to list Policy and Website Match Target')
        else:
            logger.info('No result found')
    else:
        policy_str_id, policies = util.list_waf_policy(wrap_api, config_id, version, policy_name)
        if policy_str_id:
            wrap_api.list_policy_match_targets(config_id, version, policy_str_id, policy_name)
        else:
            wrap_api.list_match_targets(config_id, version, policies)
    util.log_cli_timing()


@cli.command(short_help='Remove hostnames from selected hosts and any policy match targets')
@click.option('--config-id', metavar='', help='name of security configuration to update', required=True)
@click.option('--csv', metavar='', required=True, help='csv file with headers hostname,matchTargetId')
@click.option('--version-notes', metavar='', help='notes for the new version')
@click.option('--activate', metavar='', type=click.Choice(['staging', 'production']), multiple=True, help='Options: staging, production')
@click.option('--version', metavar='', help='version to add hostname(s) to', default='latest')
@click.option('--email', metavar='', help='email for activation notifications')
@no_wait_option
@log_level_options
@pass_config
def appsec_remove(config, **kwargs):
    """
    Remove hostnames from selected hosts and any policy match targets
    """
    apply_log_level_from_flags(kwargs.pop('log_level'), kwargs.pop('verbose'))
    logger.info('Start Akamai CLI onboard')
    _, wrapper_object, account_input, account_output = init_config(config)
    util = utility.utility()
    click_args = kwargs

    onboard_object = onboard_appsec_update.onboard(click_args)

    # Validate setup and akamai cli and cli pipeline are installed
    csv = click_args['csv']

    # Validate akamai cli and cli pipeline are installed
    cli_installed = util.installedCommandCheck('akamai')
    pipeline_installed = util.executeCommand(['akamai', 'pipeline'])

    if not (pipeline_installed and (cli_installed or pipeline_installed)):
        sys.exit()

    # validate setup steps when csv input provided
    util.csv_validator_appsec(onboard_object, csv)
    util.csv_2_appsec_array(onboard_object, delete=True)
    util.validateAppsecSteps(onboard_object, wrapper_object, cli_mode='appsec-remove')

    if util.valid is True:
        utility_waf_object = utility_waf.wafFunctions()
        # First create new WAF configuration version
        logger.debug(f'Trying to create new version for WAF configuration: {onboard_object.waf_config_name}')
        create_waf_version = utility_waf_object.createWafVersion(wrapper_object, onboard_object, notes=onboard_object.version_notes)
        wrapper_object.update_waf_config_version_note(onboard_object, notes=onboard_object.version_notes)
        if create_waf_version is False:
            sys.exit()

        # Created WAF config version, now can remove selected hosts from it
        logger.debug(f'Trying to remove property public_hostnames as selected hosts from WAF configuration: {onboard_object.waf_config_name}')
        success, removed_hostnames = utility_waf_object.removeHostnames(wrapper_object,
                                                        onboard_object.hostname_list,
                                                        onboard_object.config_id,
                                                        onboard_object.onboard_waf_config_version)
        if success is True:
            if removed_hostnames > 0:
                logger.info(f'Selected hosts: Successfully Removed {removed_hostnames} hostnames from selected hosts')
        else:
            logger.error('Unable to remove selected hosts to WAF Configuration')
            exit(-1)

        all_match_targets = wrapper_object.getAllWebMatchTargets(onboard_object.config_id, onboard_object.onboard_waf_config_version)
        # Update WAF match target
        for match_target in all_match_targets:
            policy_id = match_target['securityPolicy']['policyId']
            resp = utility_waf_object.get_security_policy(wrapper_object, onboard_object.config_id, onboard_object.onboard_waf_config_version, policy_id)
            policy_name = resp['policyName']
            policy_name = f"'{policy_name}/{match_target['securityPolicy']['policyId']}'"

            if match_target.get('hostnames', False):
                policy_hostnames_remaining = list(filter(lambda x: x not in onboard_object.hostname_list, match_target['hostnames']))
                policy_hostnames_to_remove = list(filter(lambda x: x in onboard_object.hostname_list, match_target['hostnames']))
                logger.debug(f"Removing {len(policy_hostnames_to_remove)} hostnames from {match_target['securityPolicy']['policyId']}")
                logger.debug(policy_hostnames_to_remove)
                removed_hostnames = len(match_target['hostnames']) - len(policy_hostnames_remaining)
                if removed_hostnames == 0:
                    logger.debug(f"Website Match Targets {match_target['securityPolicy']['policyId']}: No hostnames found to removed")
                else:
                    modify_matchtarget = utility_waf_object.updateMatchTargetRemoveHosts(wrapper_object,
                                                                                         policy_hostnames_remaining,
                                                                                         onboard_object.config_id,
                                                                                         onboard_object.onboard_waf_config_version,
                                                                                         match_target['targetId'])
                    if modify_matchtarget:
                        logger.info(f'WAF Configuration Match Target {policy_name}: Successfully removed {removed_hostnames} hostnames')
                    else:
                        logger.error(f'Failed to remove {removed_hostnames} hostnames from match target {policy_name}')
            else:
                logger.info(f'WAF Configuration Match Target {policy_name}: No hostnames found')
        # Activate WAF configuration to staging
        if click_args['activate']:
            no_wait_activation.fire_appsec_update_activations(
                utility_waf_object, wrapper_object, onboard_object, click_args['activate'], click_args['no_wait'],
                activation_manifest.new_manifest_path(account_output))
        else:
            print()
            logger.warning('Activate WAF Configuration Production: SKIPPING')

        util.log_cli_timing()


class Fake:
    def __init__(self, li_obj):
        self.obj = li_obj


@cli.command(short_help='Create new security configuration, security policy, and policy match target')
@click.option('-c', '--contract-id', metavar='', help='Contract ID (starts with ctr_)', required=True)
@click.option('-g', '--group-id', metavar='', help='Group ID (starts with grp_)', required=True)
@click.option('--activate', metavar='', type=click.Choice(['staging', 'production']), multiple=False, required=False,
              help='Akamai network to activate security configuration Options: staging, production')
@click.option('--csv', metavar='', required=True, help='CSV input file')
@click.option('--by', metavar='', type=click.Choice(['hostname', 'propertyname']), default='hostname', required=False,
              help='by command depends on data in CSV input file.     Options: hostname, propertyname')
@click.option('--email', metavar='', required=False, help='email for activation notifications')
@click.option('--version-notes', 'note', metavar='', default='Onboard CLI Activation', help='config version notes')
@no_wait_option
@log_level_options
@pass_config
def appsec_create(config, contract_id, group_id, by, activate, csv, email, note, no_wait, log_level, verbose):
    """
    Batch create new security configuration, security policy, and policy match target

    \b
    Security config will not be activated, unless --activate is specified.

    \b
    CSV input file options

      \b
      Option 1 by hostname <default>: Headers contain waf_config_name,waf_policy_name,hostname

      \b
      Option 2 by propertyname: Headers contain propertyname,waf_config_name,waf_policy_name,hostname
    """
    apply_log_level_from_flags(log_level, verbose)
    logger.info('Start Akamai CLI onboard')
    try:
        _, wrap_api, account_input, account_output = init_config(config)
    except Exception as err:
        lg._log_error(err)
        return 1
    util = utility.utility()
    util_waf = utility_waf.wafFunctions()

    appsec_main = Generic(contract_id, group_id, csv, by)
    # override default
    if email:
        appsec_main.notification_emails = [email]
    appsec_main.activate = activate
    appsec_main.version_notes = note
    _, selectable_hostnames, selectable_df = wrap_api.get_selectable_hostnames(contract_id[4:], group_id[4:], appsec_main.network)
    show_df = util.validate_appsec_pre_create(appsec_main, wrap_api, util_waf, selectable_df)

    # start onboarding security config
    if util.valid:

        prev_waf_config = 0
        appsec_onboard = []
        for i in show_df.index:
            # populate property onboard data
            waf_config = show_df['waf_config_name'][i]
            policy = show_df['policy'][i]
            public_hostnames = show_df['hostname'][i]
            logger.debug(f'{waf_config} {policy} {public_hostnames}')
            onboard = Property(contract_id, group_id, waf_config, policy)
            onboard.version_notes = note
            if len(public_hostnames) > 0:
                onboard.public_hostnames = public_hostnames
                if by == 'propertyname':
                    onboard.waf_target_hostnames = show_df['waf_target_hostname'][i]

            # validate hostnames and remove invalid hostnames
            invalid_hostnames = list({x for x in onboard.public_hostnames if x not in selectable_hostnames})
            if len(invalid_hostnames) > 1:
                onboard.public_hostnames = list(filter(lambda x: x not in invalid_hostnames, onboard.public_hostnames))
                if len(onboard.public_hostnames) == 0:
                    logger.warning(f'Web security configuration {waf_config} - SKIPPING')
                    logger.info(f'{invalid_hostnames} are not selectable hostnames')
                    break
                if invalid_hostnames and len(onboard.public_hostnames) > 0:
                    logger.warning(f'{invalid_hostnames} are not selectable hostnames for {waf_config}')

            # start onboarding security config
            if waf_config != prev_waf_config:
                if util_waf.create_waf_config(wrap_api, onboard):
                    prev_waf_config_id = onboard.onboard_waf_config_id
                    prev_waf_config_version = onboard.onboard_waf_config_version
                    prev_waf_config = waf_config
                    if activate:
                        # popolate AppSec data
                        appsec = AppSec(waf_config, onboard.onboard_waf_config_id, onboard.onboard_waf_config_version, [email])
                        appsec.version_notes = note
                        appsec_onboard.append(appsec)
                else:
                    sys.exit(logger.error('Fail to create waf config'))
            else:
                # add hostnames to new policy
                onboard.onboard_waf_config_id = prev_waf_config_id
                onboard.onboard_waf_config_version = prev_waf_config_version
                output = []
                for hostname in onboard.public_hostnames:
                    member = {}
                    member['hostname'] = hostname
                    output.append(member)
                payload = {}
                payload['hostnameList'] = output
                payload['mode'] = 'append'
                logger.debug(output)
                resp = wrap_api.modifyWafHosts(onboard.onboard_waf_config_id, onboard.onboard_waf_config_version, json.dumps(payload))
                if not resp.ok:
                    logger.error(resp.json())

            if util_waf.create_waf_policy(wrap_api, onboard):
                if by == 'propertyname':
                    if util_waf.create_waf_match_target(wrap_api, onboard, onboard.waf_target_hostnames):
                        pass
                else:
                    if util_waf.create_waf_match_target(wrap_api, onboard):
                        pass
            else:
                sys.exit(logger.error('Fail to create waf policy'))

        # activating
        if activate:
            time.sleep(5)
            no_wait_activation.fire_appsec_create_activations(
                util_waf, wrap_api, appsec_onboard, activate, no_wait,
                activation_manifest.new_manifest_path(account_output))
        util.log_cli_timing()


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
