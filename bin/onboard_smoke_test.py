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

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class smoketest:
    # Initialize the object
    def __init__(self, config, click_args):
        # Read values from setup.json or --file
        # Certain values (onboard_) are updated in main processing later
        try:
            self.hostname_dict = {}
            self.csv_loc = click_args['csv']
            # self.csv_loc = self.get_actual_location(self.csv_loc)
            self.valid_csv = True
            self.acme_challenges = []
            self.csv_dict = []
            self.all_account_hostnames = []
            self.unique_hostnames = []

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
                    self.section = 'default'
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
