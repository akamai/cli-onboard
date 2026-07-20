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
from model.edge_hostname_mode import EdgeHostnameMode
logger = setup_logger()


class onboard:
    # Initialize the object
    def __init__(self, config, click_args):
        # Read values from setup.json or --file
        # Certain values (onboard_) are updated in main processing later
        try:
            self.property_name = []
            self.account_switch_key = ''
            self.csv_loc = click_args['csv']
            self.csv_loc = self.get_actual_location(self.csv_loc)
            self.force_mode = click_args['force']
            self.ehn_option = click_args['media_ehn']
            self.property_list = []
            self.product_list = []
            self.valid_csv = True
            self.csv_dict = []
            self.all_template_json_exists = True
            self.ok_to_activate = []
            self.secure_network = click_args['network']
            self.ehn_suffix = '.edgekey.net'
            if self.secure_network == 'STANDARD_TLS':
                self.ehn_suffix = 'edgesuite.net'
            self.contract_id = click_args['contract']
            self.group_id = click_args['group']
            self.product_id = click_args['product']
            self.rule_format = click_args['rule_format']
            self.create_new_cpcode = True
            self.source_directory = click_args['directory']
            self.source_directory = self.get_actual_location(self.source_directory)
            self.level_0_rules = []
            self.gtm_domain = click_args['gtm_domain']
            self.gtm_replacement_count = 0

            self.public_hostnames = []

            self.onboard_property_id = None
            self.onboard_default_cpcode = 0
            self.edge_hostname_id = 0
            self.edge_hostname_list = []
            self.cert_mode = click_args.get('cert_mode', 'SBD').upper()
            self.enrollment_id = click_args.get('enrollment_id')
            self.use_existing_ehn = click_args.get('use_existing_edgehostname')

            if self.use_existing_ehn:
                self.edge_hostname_mode = EdgeHostnameMode.USE_EXISTING_EDGEHOSTNAME
            elif self.cert_mode == 'CPS' and self.enrollment_id:
                self.edge_hostname_mode = EdgeHostnameMode.CREATE_CPS_EDGEHOSTNAME
            elif self.cert_mode == 'CPS':
                self.edge_hostname_mode = EdgeHostnameMode.CPS_PLACEHOLDER
            else:
                self.edge_hostname_mode = EdgeHostnameMode.SECURE_BY_DEFAULT

            self.activate_property_production = False
            self.activate_property_staging = False
            # Activation values
            if 'staging' in click_args['activate']:
                self.activate_property_staging = True
            if 'production' in click_args['activate']:
                self.activate_property_production = True

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
