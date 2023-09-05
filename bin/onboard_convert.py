"""
Copyright 2023 Akamai Technologies, Inc. All Rights Reserved.

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

import os
from pathlib import Path

from exceptions import setup_logger
logger = setup_logger()


class onboard:
    # Initialize the object
    def __init__(self, config, click_args):
        # Read values from setup.json or --file
        # Certain values (onboard_) are updated in main processing later
        try:
            self.property_name = []
            self.csv_loc = click_args['csv']
            self.property_list = []
            self.valid_csv = True
            self.csv_dict = []
            self.secure_network = click_args['network']
            self.ehn_suffix = '.edgekey.net'
            if self.secure_network == 'STANDARD_TLS':
                self.ehn_suffix = 'edgesuite.net'
            self.contract_id = click_args['contract']
            self.group_id = click_args['group']
            self.product_id = click_args['product']
            self.rule_format = click_args['rule_format']
            self.create_new_cpcode = True
            self.source_template_file = click_args['template']
            self.source_template_file = self.get_actual_location(self.source_template_file)
            self.level_0_rules = []

            self.public_hostnames = []

            self.onboard_property_id = None
            self.onboard_default_cpcode = 0
            self.edge_hostname_id = 0
            self.edge_hostname_list = []
            # Edge hostname values
            if click_args['secure_by_default']:
                self.edge_hostname_mode = 'secure_by_default'
            else:
                self.edge_hostname_mode = 'use_existing_edgehostname'

            # WAF values
            if click_args['waf_config']:
                self.add_selected_host = True
            else:
                self.add_selected_host = False

            self.waf_config_name = click_args['waf_config']

            if click_args['waf_match_target']:
                self.update_match_target = True
            else:
                self.update_match_target = False
            self.waf_match_target_id = click_args['waf_match_target']
            if isinstance(self.waf_match_target_id, str):
                if self.waf_match_target_id == '':
                    self.waf_match_target_id = 0
                else:
                    self.waf_match_target_id = int(self.waf_match_target_id)

            self.onboard_waf_config_id = None
            self.onboard_waf_config_version = None
            self.onboard_waf_prev_version = None

            self.activate_property_staging = False
            self.activate_waf_policy_staging = False
            self.activate_property_production = False
            self.activate_waf_policy_production = False

            # Activation values
            if 'delivery-staging' in click_args['activate']:
                self.activate_property_staging = True
            if 'waf-staging' in click_args['activate']:
                self.activate_waf_policy_staging = True
            if 'delivery-production' in click_args['activate']:
                self.activate_property_production = True
            if 'waf-production' in click_args['activate']:
                self.activate_waf_policy_production = True

            if click_args['email']:
                self.notification_emails = click_args['email']
            else:
                self.notification_emails = ['noreply@akamai.com']
            self.version_notes = 'Created using Onboard CLI'

            # Read config object that contains the command line parameters
            if not config.edgerc:
                if not os.getenv('AKAMAI_EDGERC'):
                    self.edgerc = os.path.join(os.path.expanduser('~'), '.edgerc')
                else:
                    self.edgerc = os.getenv('AKAMAI_EDGERC')
            else:
                self.edgerc = config.edgerc

            if not config.section:
                if not os.getenv('AKAMAI_EDGERC_SECTION'):
                    self.section = 'onboard'
                else:
                    self.section = os.getenv('AKAMAI_EDGERC_SECTION')
            else:
                self.section = config.section

        except KeyError as k:
            print('\nInput file is missing ' + str(k))
            exit(-1)

    def get_actual_location(self, file_location: str) -> str:
        abs_file_location = file_location
        home = str(Path.home())
        if '~' in file_location:
            file_location = file_location.replace('~', '')
            abs_file_location = f'{home}/{file_location}'

        return abs_file_location
