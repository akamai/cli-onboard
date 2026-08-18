"""Checks that logging verbosity options work consistently across the main command and all its subcommands."""
from __future__ import annotations

import logging

import pytest

# Minimum required options per subcommand, just enough to get past click's own
# parsing and into the function body (where apply_log_level_from_flags() runs).
_REQUIRED_ARGS = {
    'convert': ['--csv', 'x.csv', '-d', 'x'],
    'batch-create': ['--template', 't.json', '--contract', 'ctr_1', '--group', 'grp_1',
                      '--product', 'prd_1', '--csv', 'x.csv'],
    'sbd-status': [],
    'sbd-precheck': ['--csv', 'x.csv'],
    'appsec-update': ['--config-id', '123', '--csv', 'x.csv'],
    'appsec-remove': ['--config-id', '123', '--csv', 'x.csv'],
    'multi-hosts': ['--csv', 'x.csv', '--file', 'f.json'],
    'single-host': ['--file', 'f.json'],
    'create': ['--file', 'f.json'],
    'appsec-policy': [],
    'appsec-create': ['--contract-id', 'ctr_1', '--group-id', 'grp_1', '--csv', 'x.csv'],
}

# Subcommands that accept open-ended options, so logging flags apply automatically.
_KWARGS_SUBCOMMANDS = ['batch-create', 'sbd-status', 'sbd-precheck', 'appsec-update', 'appsec-remove']

# Subcommands with a fixed set of options that also load credentials, tested the same way.
_FIXED_SIGNATURE_SUBCOMMANDS = ['multi-hosts', 'single-host', 'create', 'appsec-policy', 'appsec-create']

# Subcommands that don't need credentials, so they run to completion instead of
# failing early - verified separately below.
_NO_INIT_CONFIG_SUBCOMMANDS = ['fetch-sample-templates', 'help']


def _invoke(runner, cli, tmp_path, subcommand, extra_group_args=(), extra_subcommand_args=()):
    # Missing edgerc fails init_config() cleanly, after apply_log_level_from_flags() runs.
    missing_edgerc = tmp_path / 'does-not-exist.edgerc'
    args = ['--edgerc', str(missing_edgerc), *extra_group_args,
            subcommand, *_REQUIRED_ARGS[subcommand], *extra_subcommand_args]
    result = runner.invoke(cli, args)
    assert 'Unable to read edgerc file' in result.output
    return result


# --- convert -----------------------------------------------------------------

def test_no_logging_flags_leaves_root_at_info(runner, cli, tmp_path, restore_logging_state):
    # Matches the real bootstrap: setup_logger() always sets root to INFO before
    # any flag is parsed. With no flags at all, that default must be undisturbed.
    logging.getLogger().setLevel(logging.INFO)
    _invoke(runner, cli, tmp_path, 'convert')
    assert logging.getLogger().level == logging.INFO


def test_group_level_debug_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, 'convert', extra_group_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


def test_group_level_verbose_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, 'convert', extra_group_args=['--verbose'])
    assert logging.getLogger().level == logging.DEBUG


def test_group_level_log_level_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, 'convert', extra_group_args=['--log-level', 'ERROR'])
    assert logging.getLogger().level == logging.ERROR


def test_subcommand_level_debug_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, 'convert', extra_subcommand_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


def test_subcommand_level_verbose_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, 'convert', extra_subcommand_args=['--verbose'])
    assert logging.getLogger().level == logging.DEBUG


def test_subcommand_level_log_level_flag(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, 'convert', extra_subcommand_args=['--log-level', 'ERROR'])
    assert logging.getLogger().level == logging.ERROR


def test_most_verbose_wins_across_group_and_subcommand(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, 'convert',
            extra_group_args=['--debug'],
            extra_subcommand_args=['--log-level', 'ERROR'])
    assert logging.getLogger().level == logging.DEBUG


def test_most_verbose_wins_regardless_of_which_side_is_more_verbose(runner, cli, tmp_path, restore_logging_state):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, 'convert',
            extra_group_args=['--log-level', 'ERROR'],
            extra_subcommand_args=['--debug'])
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


# --- subcommands with flexible argument handling -----------------------------

@pytest.mark.parametrize('subcommand', _KWARGS_SUBCOMMANDS)
def test_kwargs_subcommand_no_flags_leaves_root_at_info(runner, cli, tmp_path, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.INFO)
    _invoke(runner, cli, tmp_path, subcommand)
    assert logging.getLogger().level == logging.INFO


@pytest.mark.parametrize('subcommand', _KWARGS_SUBCOMMANDS)
def test_kwargs_subcommand_group_level_debug_flag(runner, cli, tmp_path, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, subcommand, extra_group_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


@pytest.mark.parametrize('subcommand', _KWARGS_SUBCOMMANDS)
def test_kwargs_subcommand_level_debug_flag(runner, cli, tmp_path, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, subcommand, extra_subcommand_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


@pytest.mark.parametrize('subcommand', _KWARGS_SUBCOMMANDS)
def test_kwargs_subcommand_level_log_level_flag(runner, cli, tmp_path, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, subcommand, extra_subcommand_args=['--log-level', 'ERROR'])
    assert logging.getLogger().level == logging.ERROR


@pytest.mark.parametrize('subcommand', _KWARGS_SUBCOMMANDS)
def test_kwargs_subcommand_help_shows_logging_options(runner, cli, subcommand):
    result = runner.invoke(cli, [subcommand, '--help'])
    assert result.exit_code == 0
    for option in ('--log-level', '--debug', '--verbose'):
        assert option in result.output


# --- subcommands with a fixed set of options ----------------------------------

@pytest.mark.parametrize('subcommand', _FIXED_SIGNATURE_SUBCOMMANDS)
def test_fixed_signature_subcommand_no_flags_leaves_root_at_info(runner, cli, tmp_path, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.INFO)
    _invoke(runner, cli, tmp_path, subcommand)
    assert logging.getLogger().level == logging.INFO


@pytest.mark.parametrize('subcommand', _FIXED_SIGNATURE_SUBCOMMANDS)
def test_fixed_signature_subcommand_group_level_debug_flag(runner, cli, tmp_path, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, subcommand, extra_group_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


@pytest.mark.parametrize('subcommand', _FIXED_SIGNATURE_SUBCOMMANDS)
def test_fixed_signature_subcommand_level_debug_flag(runner, cli, tmp_path, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, subcommand, extra_subcommand_args=['--debug'])
    assert logging.getLogger().level == logging.DEBUG


@pytest.mark.parametrize('subcommand', _FIXED_SIGNATURE_SUBCOMMANDS)
def test_fixed_signature_subcommand_level_log_level_flag(runner, cli, tmp_path, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.WARNING)
    _invoke(runner, cli, tmp_path, subcommand, extra_subcommand_args=['--log-level', 'ERROR'])
    assert logging.getLogger().level == logging.ERROR


@pytest.mark.parametrize('subcommand', _FIXED_SIGNATURE_SUBCOMMANDS)
def test_fixed_signature_subcommand_help_shows_logging_options(runner, cli, subcommand):
    result = runner.invoke(cli, [subcommand, '--help'])
    assert result.exit_code == 0
    for option in ('--log-level', '--debug', '--verbose'):
        assert option in result.output


# --- fetch-sample-templates and help (no credential loading required) --------

@pytest.mark.parametrize('subcommand', _NO_INIT_CONFIG_SUBCOMMANDS)
def test_no_init_config_subcommand_no_flags_leaves_root_at_info(runner, cli, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.INFO)
    result = runner.invoke(cli, [subcommand])
    assert result.exit_code == 0
    assert logging.getLogger().level == logging.INFO


@pytest.mark.parametrize('subcommand', _NO_INIT_CONFIG_SUBCOMMANDS)
def test_no_init_config_subcommand_group_level_debug_flag(runner, cli, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.WARNING)
    result = runner.invoke(cli, ['--debug', subcommand])
    assert result.exit_code == 0
    assert logging.getLogger().level == logging.DEBUG


@pytest.mark.parametrize('subcommand', _NO_INIT_CONFIG_SUBCOMMANDS)
def test_no_init_config_subcommand_level_debug_flag(runner, cli, restore_logging_state, subcommand):
    logging.getLogger().setLevel(logging.WARNING)
    result = runner.invoke(cli, [subcommand, '--debug'])
    assert result.exit_code == 0
    assert logging.getLogger().level == logging.DEBUG


@pytest.mark.parametrize('subcommand', _NO_INIT_CONFIG_SUBCOMMANDS)
def test_no_init_config_subcommand_help_shows_logging_options(runner, cli, subcommand):
    result = runner.invoke(cli, [subcommand, '--help'])
    assert result.exit_code == 0
    for option in ('--log-level', '--debug', '--verbose'):
        assert option in result.output
