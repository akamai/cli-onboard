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
    def __init__(self, config, click_args):
        try:
            self.config_id = click_args['config_id']
            self.waf_config_name = ''
            self.config_version = click_args['version']
            self.csv = click_args['csv']
            self.valid_csv = True
            self.csv_dict = []
            self.hostname_list = []
            self.appsec_json = {}
            self.skip_selected_hosts = []
            self.onboard_waf_config_version = ''
            self.activate_staging = False
            self.activate_production = False
            if 'staging' in click_args['activate']:
                self.activate_staging = True
            if 'production' in click_args['activate']:
                self.activate_production = True
            if click_args['email']:
                self.notification_emails = click_args['email']
            else:
                self.notification_emails = ['noreply@akamai.com']
            self.version_notes = 'Created using Onboard CLI'
        except KeyError as k:
            print('\nMissing ' + str(k))
            exit(-1)

        try:
            self.version_notes = click_args['version_notes']
        except:
            self.version_notes = 'Created using Onboard CLI'
