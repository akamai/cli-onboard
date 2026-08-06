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
import logging.config
import os
import shutil
import time
from pathlib import Path

from rich.logging import RichHandler


def setup_logger():
    """Create folders and copy config json when running via Akamai CLI"""
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
        origin_config = 'cli-onboard/config/logging.json'

    try:
        shutil.copy2(origin_config, 'config/logging.json')
    except FileNotFoundError as e:
        origin_config = 'config/logging.json'

    with open(origin_config) as f:
        log_cfg = json.load(f)
    logging.config.dictConfig(log_cfg)
    logging.Formatter.converter = time.gmtime
    logger = logging.getLogger(__name__)
    # Leave this logger's own level at NOTSET so it inherits its effective level
    # from the root logger (see apply_log_level()) instead of being pinned here -
    # root starts at INFO so today's default behavior is unchanged.
    logging.getLogger().setLevel(logging.INFO)
    for handler in logger.handlers[:]:
        if isinstance(handler, RichHandler):
            logger.removeHandler(handler)
    logger.addHandler(RichHandler(show_level=False, show_time=False, rich_tracebacks=True))
    return logger


def resolve_log_level(log_level: str | None, debug: bool, verbose: bool) -> int:
    """Compute the effective log level from --log-level/--debug/--verbose, most
    verbose wins. Defaults to INFO when none of the three are set.
    """
    levels = []
    if log_level:
        levels.append(getattr(logging, log_level.upper()))
    if debug or verbose:
        levels.append(logging.DEBUG)
    if not levels:
        return logging.INFO
    return min(levels)


def apply_log_level(level: int) -> None:
    """Apply an effective log level process-wide.

    Sets the root logger to the more verbose of its current level and `level`,
    so calling this more than once (e.g. once from the CLI group, once from a
    subcommand) always keeps the most verbose level ever requested, regardless
    of call order. Third-party HTTP libraries are pinned to WARNING regardless
    of `level`, since urllib3/requests DEBUG logging dumps raw request headers -
    including the EdgeGrid Authorization signature.
    """
    root = logging.getLogger()
    root.setLevel(min(root.level, level))
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def get_cli_root_directory():
    docker_path = os.path.expanduser(Path('/cli'))
    local_home_path = os.path.expanduser(Path('~/.akamai-cli/src/cli-onboard'))
    if Path(docker_path).exists():
        return Path(f'{docker_path}/.akamai-cli/src/cli-onboard')
    elif Path(local_home_path).exists():
        return Path(f'{local_home_path}')
    else:
        return os.getcwd()


def get_cli_execution_directory():
    return os.getcwd()
