"""
Copyright 2022 Akamai Technologies, Inc. All Rights Reserved.

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
import logging
import os
import shutil
import time
from pathlib import Path

import coloredlogs


def setup_logger():
    # Create folders and copy config json when running via Akamai CLI
    Path('logs').mkdir(parents=True, exist_ok=True)
    Path('config').mkdir(parents=True, exist_ok=True)

    docker_path = os.path.expanduser(Path('/cli'))
    local_home_path = os.path.expanduser(Path('~/.akamai-cli'))

    if Path(docker_path).exists():
        origin_config = f'{docker_path}/.akamai-cli/src/cli-onboard/config/logging.json'
    elif Path(local_home_path).exists():
        origin_config = f'{local_home_path}/src/cli-onboard/config/logging.json'
        origin_config = os.path.expanduser(origin_config)
    else:
        raise FileNotFoundError('Could not find logging.json')

    try:
        shutil.copy2(origin_config, 'config/logging.json')
    except FileNotFoundError as e:
        origin_config = 'config/logging.json'

    with open(origin_config) as f:
        log_cfg = json.load(f)
    logging.config.dictConfig(log_cfg)
    logging.Formatter.converter = time.gmtime
    logger = logging.getLogger(__name__)
    coloredlogs.install(logger=logger, fmt='%(levelname)-7s: %(message)s')
    return logger


def get_cli_root_directory():
    docker_path = os.path.expanduser(Path('/cli'))
    local_home_path = os.path.expanduser(Path('~/.akamai-cli/src/cli-onboard'))
    if Path(docker_path).exists():
        return Path(f'{docker_path}/.akamai-cli/src/cli-onboard')
    elif Path(local_home_path).exists():
        return Path(f'{local_home_path}')
    else:
        return os.getcwd()
