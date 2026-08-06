"""Ticket 02: --log-level/--debug/--verbose wired into the `cli` group and `convert`.

These invoke `convert` with a deliberately-missing edgerc file, mirroring the
pattern in tests/test_convert_cli_parsing.py::test_missing_edgerc_file_exits -
apply_log_level() runs as the very first thing in convert()'s body, before
init_config() fails cleanly on the missing edgerc, so we can assert on the
resulting root logger level without any network access or real credentials.
"""
from __future__ import annotations

import logging


def _invoke_convert(runner, cli, tmp_path, extra_group_args=(), extra_convert_args=()):
    missing_edgerc = tmp_path / 'does-not-exist.edgerc'
    args = ['--edgerc', str(missing_edgerc), *extra_group_args,
            'convert', '--csv', 'x.csv', '-d', 'x', *extra_convert_args]
    result = runner.invoke(cli, args)
    assert 'Unable to read edgerc file' in result.output
    return result


def test_no_logging_flags_leaves_root_at_info(runner, cli, tmp_path, restore_logging_state):
    # Matches the real bootstrap: setup_logger() always sets root to INFO before
    # any flag is parsed. With no flags at all, that default must be undisturbed.
    logging.getLogger().setLevel(logging.INFO)
    _invoke_convert(runner, cli, tmp_path)
    assert logging.getLogger().level == logging.INFO


def test_group_level_debug_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke_convert(runner, cli, tmp_path, extra_group_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


def test_group_level_verbose_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke_convert(runner, cli, tmp_path, extra_group_args=['--verbose'])
    assert logging.getLogger().level == logging.DEBUG


def test_group_level_log_level_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke_convert(runner, cli, tmp_path, extra_group_args=['--log-level', 'ERROR'])
    assert logging.getLogger().level == logging.ERROR


def test_subcommand_level_debug_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke_convert(runner, cli, tmp_path, extra_convert_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


def test_subcommand_level_verbose_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke_convert(runner, cli, tmp_path, extra_convert_args=['--verbose'])
    assert logging.getLogger().level == logging.DEBUG


def test_subcommand_level_log_level_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke_convert(runner, cli, tmp_path, extra_convert_args=['--log-level', 'ERROR'])
    assert logging.getLogger().level == logging.ERROR


def test_most_verbose_wins_across_group_and_subcommand(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke_convert(runner, cli, tmp_path,
                     extra_group_args=['--debug'],
                     extra_convert_args=['--log-level', 'ERROR'])
    assert logging.getLogger().level == logging.DEBUG


def test_most_verbose_wins_regardless_of_which_side_is_more_verbose(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke_convert(runner, cli, tmp_path,
                     extra_group_args=['--log-level', 'ERROR'],
                     extra_convert_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


def test_help_shows_logging_options_on_group(runner, cli):
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    for option in ('--log-level', '--debug', '--verbose'):
        assert option in result.output


def test_help_shows_logging_options_on_convert(runner, cli):
    result = runner.invoke(cli, ['convert', '--help'])
    assert result.exit_code == 0
    for option in ('--log-level', '--debug', '--verbose'):
        assert option in result.output
