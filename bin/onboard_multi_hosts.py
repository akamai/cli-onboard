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

import json
import sys
from pathlib import Path

from exceptions import get_cli_root_directory
from exceptions import setup_logger

logger = setup_logger()
root = get_cli_root_directory()


class onboard:
    def __init__(self, json_input: dict):
        try:
            self.contract_id = json_input['property_info']['contract_id']
            self.product_id = json_input['property_info']['product_id']
            self.property_name = json_input['property_info']['property_name']
            self.individual_cpcode = json_input['property_info']['individual_cpcode']

            self.edge_hostname = json_input['edge_hostname']['use_existing_edge_hostname']
            self.existing_enrollment_id = json_input['edge_hostname']['create_from_existing_enrollment_id']

            try:
                self.secure_by_default = json_input['edge_hostname']['secure_by_default']
            except KeyError as k:
                logger.warning('You are not using the latest template. Please use new setup.json template if you want to use secure by default')
                self.secure_by_default = False

            # The cpcode name contains one or more of these special characters ^ _ , # % ' \" ",
            self.new_cpcode_name = self.property_name.replace('_', ' ')

            # Security
            self.create_new_security_config = json_input['update_waf_info']['create_new_security_config']
            self.waf_config_name = ''
            if len(json_input['update_waf_info']['waf_config_name']) > 0:
                self.waf_config_name = json_input['update_waf_info']['waf_config_name']
            self.activate_production = json_input['activate_production']
            self.notification_emails = json_input['notification_emails']
        except KeyError as k:
            sys.exit(logger.error(f'Input file is missing {k}'))

        if isinstance(self.existing_enrollment_id, str):
            if self.existing_enrollment_id == '':
                self.existing_enrollment_id = 0
            else:
                self.existing_enrollment_id = int(self.existing_enrollment_id)

        try:
            self.version_notes = json_input['property_info']['version_notes']
        except:
            self.version_notes = ''

    def write_variable_json(self, default_origin: str, cp_code: int) -> None:
        """
        Override origin server inside templates/variables.json which is hidden from user
        """
        var = {}
        var['origin_default'] = default_origin
        var['cp_code'] = cp_code

        # override when run via CLI
        variable_file = Path(root, 'templates/akamai_product_templates/multi-hosts/variables.json')
        with variable_file.open('w') as file:
            json.dump(var, file, indent=4)

        # override when run via python script
        with Path('logs/variables.json').absolute().open('w') as file:
            json.dump(var, file, indent=4)

    def get_product_template(self, src_file: str) -> dict:
        with open(src_file) as f:
            rules = json.load(f)
        logger.debug(json.dumps(rules, indent=4))
        return rules

    def override_product_template(self, onboard, rules: dict) -> None:
        # override when run via CLI
        template_file = Path(root, 'templates/akamai_product_templates/multi-hosts/multiple_hosts.json')
        with template_file.open('w') as file:
            json.dump(rules, file, indent=4)
            onboard.source_template_file = f'{template_file}'

        # override when run via python script
        with Path('logs/multiple_hosts.json').absolute().open('w') as file:
            json.dump(rules, file, indent=2)
        return None
