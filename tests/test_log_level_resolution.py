from __future__ import annotations

import logging

import exceptions
import pytest


@pytest.fixture
def restore_logging_state():
    """Snapshot/restore global logging state that resolve_log_level()/apply_log_level()
    mutate, so tests in this file can't leak level changes into each other or into
    other test files that share the same process-wide logging registry.
    """
    root = logging.getLogger()
    shared = logging.getLogger('exceptions')
    urllib3_logger = logging.getLogger('urllib3')
    requests_logger = logging.getLogger('requests')
    snapshot = (root.level, shared.level, urllib3_logger.level, requests_logger.level)
    yield
    root.level, shared.level, urllib3_logger.level, requests_logger.level = snapshot


class TestResolveLogLevel:
    def test_defaults_to_info_when_nothing_set(self):
        assert exceptions.resolve_log_level(None, False, False) == logging.INFO

    def test_log_level_alone_is_honored(self):
        assert exceptions.resolve_log_level('ERROR', False, False) == logging.ERROR

    def test_log_level_is_case_insensitive(self):
        assert exceptions.resolve_log_level('debug', False, False) == logging.DEBUG
        assert exceptions.resolve_log_level('DEBUG', False, False) == logging.DEBUG

    def test_debug_flag_wins_over_less_verbose_log_level(self):
        assert exceptions.resolve_log_level('WARNING', True, False) == logging.DEBUG

    def test_verbose_flag_wins_over_less_verbose_log_level(self):
        assert exceptions.resolve_log_level('WARNING', False, True) == logging.DEBUG

    def test_debug_and_verbose_both_set_is_still_debug(self):
        assert exceptions.resolve_log_level(None, True, True) == logging.DEBUG

    def test_more_verbose_explicit_log_level_beats_no_flags(self):
        # DEBUG is more verbose than the INFO default, so it should win even
        # though --debug/--verbose weren't passed.
        assert exceptions.resolve_log_level('DEBUG', False, False) == logging.DEBUG


class TestApplyLogLevel:
    def test_lowers_root_level_when_more_verbose(self, restore_logging_state):
        logging.getLogger().setLevel(logging.INFO)
        exceptions.apply_log_level(logging.DEBUG)
        assert logging.getLogger().level == logging.DEBUG

    def test_never_regresses_to_a_less_verbose_level(self, restore_logging_state):
        logging.getLogger().setLevel(logging.INFO)
        exceptions.apply_log_level(logging.WARNING)
        assert logging.getLogger().level == logging.INFO

    def test_most_verbose_wins_regardless_of_call_order(self, restore_logging_state):
        logging.getLogger().setLevel(logging.INFO)
        exceptions.apply_log_level(logging.DEBUG)
        exceptions.apply_log_level(logging.ERROR)
        assert logging.getLogger().level == logging.DEBUG

    def test_pins_urllib3_and_requests_to_warning_even_under_debug(self, restore_logging_state):
        exceptions.apply_log_level(logging.DEBUG)
        assert logging.getLogger('urllib3').level == logging.WARNING
        assert logging.getLogger('requests').level == logging.WARNING

    def test_pins_urllib3_and_requests_to_warning_at_any_level(self, restore_logging_state):
        exceptions.apply_log_level(logging.CRITICAL)
        assert logging.getLogger('urllib3').level == logging.WARNING
        assert logging.getLogger('requests').level == logging.WARNING


class TestSetupLoggerLevelWiring:
    def test_shared_logger_has_no_explicit_level(self):
        logger = exceptions.setup_logger()
        assert logger.level == logging.NOTSET

    def test_root_is_initialized_to_info(self, restore_logging_state):
        logging.getLogger().setLevel(logging.WARNING)
        exceptions.setup_logger()
        assert logging.getLogger().level == logging.INFO

    def test_shared_logger_reflects_root_level_changes(self, restore_logging_state):
        logger = exceptions.setup_logger()
        logging.getLogger().setLevel(logging.INFO)
        assert logger.isEnabledFor(logging.DEBUG) is False

        exceptions.apply_log_level(logging.DEBUG)
        assert logger.isEnabledFor(logging.DEBUG) is True
