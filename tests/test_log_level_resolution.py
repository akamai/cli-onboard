from __future__ import annotations

import logging

import exceptions

# `restore_logging_state` fixture lives in tests/conftest.py, shared with
# tests/test_log_level_cli.py.


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
    def test_first_call_is_always_honored_even_if_quieter_than_the_info_bootstrap(self, restore_logging_state):
        # setup_logger() always bootstraps root to INFO before any flag is parsed.
        # A lone `--log-level ERROR` (quieter than INFO) must still take effect -
        # it must not be treated as "regressing" against that incidental bootstrap.
        logging.getLogger().setLevel(logging.INFO)
        exceptions.apply_log_level(logging.ERROR)
        assert logging.getLogger().level == logging.ERROR

    def test_second_call_lowers_root_level_when_more_verbose(self, restore_logging_state):
        exceptions.apply_log_level(logging.INFO)
        exceptions.apply_log_level(logging.DEBUG)
        assert logging.getLogger().level == logging.DEBUG

    def test_never_regresses_to_a_less_verbose_level_than_already_requested(self, restore_logging_state):
        exceptions.apply_log_level(logging.INFO)
        exceptions.apply_log_level(logging.WARNING)
        assert logging.getLogger().level == logging.INFO

    def test_most_verbose_wins_regardless_of_call_order(self, restore_logging_state):
        exceptions.apply_log_level(logging.DEBUG)
        exceptions.apply_log_level(logging.ERROR)
        assert logging.getLogger().level == logging.DEBUG

        exceptions._most_verbose_level_requested = None
        exceptions.apply_log_level(logging.ERROR)
        exceptions.apply_log_level(logging.DEBUG)
        assert logging.getLogger().level == logging.DEBUG

    def test_pins_urllib3_and_requests_to_warning_even_under_debug(self, restore_logging_state):
        exceptions.apply_log_level(logging.DEBUG)
        assert logging.getLogger('urllib3').level == logging.WARNING
        assert logging.getLogger('requests').level == logging.WARNING

    def test_pins_urllib3_and_requests_to_warning_at_any_level(self, restore_logging_state):
        exceptions.apply_log_level(logging.CRITICAL)
        assert logging.getLogger('urllib3').level == logging.WARNING
        assert logging.getLogger('requests').level == logging.WARNING


class TestApplyLogLevelFromFlags:
    def test_no_flags_given_does_not_touch_the_current_level(self, restore_logging_state):
        exceptions.apply_log_level(logging.ERROR)
        exceptions.apply_log_level_from_flags(None, False, False)
        assert logging.getLogger().level == logging.ERROR

    def test_log_level_alone_is_applied(self, restore_logging_state):
        exceptions.apply_log_level_from_flags('ERROR', False, False)
        assert logging.getLogger().level == logging.ERROR

    def test_unset_layer_cannot_clobber_a_quieter_explicit_level_set_elsewhere(self, restore_logging_state):
        # Simulates: group passes --log-level ERROR, subcommand passes nothing.
        # The subcommand's absence of flags must not be treated as an implicit
        # "INFO" request that overrides the group's explicit, quieter choice.
        exceptions.apply_log_level_from_flags('ERROR', False, False)
        exceptions.apply_log_level_from_flags(None, False, False)
        assert logging.getLogger().level == logging.ERROR

    def test_debug_from_either_layer_still_wins(self, restore_logging_state):
        exceptions.apply_log_level_from_flags('ERROR', False, False)
        exceptions.apply_log_level_from_flags(None, True, False)
        assert logging.getLogger().level == logging.DEBUG


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
