from __future__ import annotations

import sys
import time
from time import gmtime
from time import strftime

from exceptions import setup_logger

logger = setup_logger()


def _elapse_time(start_time: time, msg: str) -> None:
    end_time = time.perf_counter()
    elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
    logger.info(f'{msg}: {elapse_time}')


def _log_error(msg: str) -> None:
    if msg is not None:
        logger.error(msg)
        sys.exit()


# https://medium.com/@rahulkumar_33287/logger-error-versus-logger-exception-4113b39beb4b
def _log_exception(msg: str) -> None:
    logger.exception(msg)
    sys.exit()
