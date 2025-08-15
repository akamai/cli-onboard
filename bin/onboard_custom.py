from __future__ import annotations

import os
from pathlib import Path

from exceptions import setup_logger

logger = setup_logger()


class Onboard:
    def __init__(self, config, click_args: dict, util):

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

        try:
            self.version_notes = 'adding paths via cli'
            self.property_name = []
            self.csv_loc = self.get_actual_location(click_args['csv'])
            self.env_loc = self.get_actual_location(click_args['env'])

            self.env_details = util.env_validator(self.env_loc)
            self.build_env = click_args['build_env']
            self.valid_csv = True
            self.valid_env = True
            self.paths = util.csv_2_path_array(self.csv_loc)
            self.paths_update = []
            self.property_version = click_args['property_version']
            self.property_version_note = click_args['note']
            self.cloudlet_policy = self.env_details[self.build_env]['cloudlet_policy']

            self.activate_property_staging = self.env_details[self.build_env]['activate_property_staging']
            self.activate_waf_staging = self.env_details[self.build_env]['activate_waf_staging']
            self.activate_cloudlet_staging = self.env_details[self.build_env]['activate_cloudlet_staging']

            self.activate_property_production = self.env_details[self.build_env]['activate_property_production']
            self.activate_waf_production = self.env_details[self.build_env]['activate_waf_production']
            self.activate_cloudlet_production = self.env_details[self.build_env]['activate_cloudlet_production']

            if click_args['email']:
                self.notification_emails = click_args['email'][0].split(',')
            else:
                self.notification_emails = ['noreply@akamai.com']

            self.version_notes = click_args.get('note', 'Created using Onboard CLI')

        except KeyError as k:
            exit(logger.error('Invalid argument/value ' + str(k)))

    def get_actual_location(self, file_location: str) -> str:
        abs_file_location = file_location
        home = str(Path.home())
        if '~' in file_location:
            file_location = file_location.replace('~', '')
            abs_file_location = f'{home}/{file_location}'

        if Path(abs_file_location).is_file():
            return abs_file_location
        else:
            exit(logger.error(f'File not found {abs_file_location}'))

class OnboardCustomUpdate(Onboard):
    """Update flow: modify existing rules"""
    def __init__(self, config, click_args: dict, util):
        super().__init__(config, click_args, util)
        self.paths_update = util.csv_2_pathToUpdate_array(self.csv_loc)

    @property
    def input_paths(self):
        return self.paths_update
