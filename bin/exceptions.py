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

import logging.config
import os
import time
from pathlib import Path

from rich.logging import RichHandler

# Inlined equivalent of the old config/logging.json - avoids disk I/O.
_LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'long': {
            'format': '%(asctime)s %(process)d %(filename)-17s %(lineno)-5d %(levelname)-8s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'file_handler': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'filename': 'logs/onboard.log',
            'formatter': 'long',
            'delay': True,
            'mode': 'a',
            'encoding': 'utf8',
        },
    },
    'root': {
        'handlers': ['file_handler'],
    },
}


def setup_logger():
    """Configure process-wide logging once, at the real entry point."""
    Path('logs').mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(_LOG_CONFIG)
    logging.Formatter.converter = time.gmtime
    root = logging.getLogger()
    # NOTSET here so it inherits from root (see apply_log_level()), not pinned.
    root.setLevel(logging.INFO)
    for handler in root.handlers[:]:
        if isinstance(handler, RichHandler):
            root.removeHandler(handler)
    root.addHandler(RichHandler(show_level=False, show_time=False, rich_tracebacks=True))
    return logging.getLogger(__name__)


def resolve_log_level(log_level: str | None, verbose: bool) -> int:
    """Resolve --log-level/--debug/--verbose to a level; most verbose wins, default INFO."""
    levels = []
    if log_level:
        levels.append(getattr(logging, log_level.upper()))
    if verbose:
        levels.append(logging.DEBUG)
    if not levels:
        return logging.INFO
    return min(levels)


# Most verbose level requested so far, tracked separately from root.level so a
# lone --log-level WARNING/ERROR/CRITICAL isn't blocked by the INFO bootstrap.
_most_verbose_level_requested: int | None = None


def apply_log_level(level: int) -> None:
    """Set the process-wide log level to the most verbose of `level` and any prior call."""
    global _most_verbose_level_requested
    if _most_verbose_level_requested is None or level < _most_verbose_level_requested:
        _most_verbose_level_requested = level
    logging.getLogger().setLevel(_most_verbose_level_requested)
    # Pinned regardless of level: DEBUG here would dump raw HTTP headers,
    # including the EdgeGrid Authorization signature.
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def apply_log_level_from_flags(log_level: str | None, verbose: bool) -> None:
    """Apply only if a flag was given, so an unset layer can't override another's level."""
    if log_level or verbose:
        apply_log_level(resolve_log_level(log_level, verbose))


def get_cli_root_directory():
    docker_path = os.path.expanduser(Path('/cli'))
    local_home_path = os.path.expanduser(Path('~/.akamai-cli/src/cli-onboard'))
    if Path(docker_path).exists():
        return Path(f'{docker_path}/.akamai-cli/src/cli-onboard')
    elif Path(local_home_path).exists():
        return Path(f'{local_home_path}')
    else:
        # fallback to use package location instead of cwd
        # Same reasoning as _load_package_metadata() in akamai-onboard.py.
        return Path(__file__).resolve().parent.parent


def get_cli_execution_directory():
    return os.getcwd()
