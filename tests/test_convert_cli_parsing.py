"""Checks that the convert command's options are parsed correctly and invalid input is rejected with a clear message."""
from __future__ import annotations


def test_help_shows_all_options(runner, cli):
    result = runner.invoke(cli, ['convert', '--help'])
    assert result.exit_code == 0
    for option in ('--contract', '--group', '--product', '--network', '--directory',
                   '--csv', '--rule-format', '--use-cpcode', '--unique-cpcode', '--prune-hostname-rules', '--cert-mode',
                   '--use-existing-edgehostname', '--enrollment-id', '--media-ehn',
                   '--gtm-domain', '--activate', '--email', '--force', '--dryrun',
                   '--prefix', '--preview', '--launch'):
        assert option in result.output


def test_missing_csv_option_errors(runner, cli):
    result = runner.invoke(cli, ['convert', '-d', '/tmp/whatever'])
    assert result.exit_code == 2
    assert '--csv' in result.output


def test_missing_directory_option_errors(runner, cli):
    result = runner.invoke(cli, ['convert', '--csv', '/tmp/whatever.csv'])
    assert result.exit_code == 2
    assert '--directory' in result.output


def test_invalid_network_choice_errors(runner, cli):
    result = runner.invoke(cli, ['convert', '--csv', 'x.csv', '-d', 'x', '-n', 'BOGUS'])
    assert result.exit_code == 2
    assert 'BOGUS' in result.output


def test_invalid_cert_mode_choice_errors(runner, cli):
    result = runner.invoke(cli, ['convert', '--csv', 'x.csv', '-d', 'x', '--cert-mode', 'bogus'])
    assert result.exit_code == 2
    assert 'bogus' in result.output


def test_invalid_activate_choice_errors(runner, cli):
    result = runner.invoke(cli, ['convert', '--csv', 'x.csv', '-d', 'x', '--activate', 'bogus'])
    assert result.exit_code == 2
    assert 'bogus' in result.output


def test_non_integer_enrollment_id_errors(runner, cli):
    result = runner.invoke(cli, ['convert', '--csv', 'x.csv', '-d', 'x', '--enrollment-id', 'abc'])
    assert result.exit_code == 2
    assert 'enrollment-id' in result.output


def test_missing_edgerc_file_exits(runner, cli, tmp_path):
    missing_edgerc = tmp_path / 'does-not-exist.edgerc'
    result = runner.invoke(cli, [
        '--edgerc', str(missing_edgerc),
        'convert', '--csv', 'x.csv', '-d', 'x',
    ])
    # Quirk worth knowing: every error path here calls `sys.exit(logger.error(...))` or
    # bare `sys.exit()`, which exits with code None/0 ("success") even on failure — so
    # exit_code can't distinguish pass/fail in this codebase. Message content can.
    assert result.exit_code == 0
    assert 'Unable to read edgerc file' in result.output


def test_edgerc_missing_section_surfaces_clean_error(runner, cli, tmp_path):
    """Checks that an unknown credentials section produces a clear error message instead of a confusing crash."""
    edgerc = tmp_path / 'good-file-bad-section.edgerc'
    edgerc.write_text('[default]\nhost = example.com\nclient_token = a\nclient_secret = b\naccess_token = c\n')
    result = runner.invoke(cli, [
        '--edgerc', str(edgerc),
        '-s', 'onboard',  # section not present in the file above
        'convert', '--csv', 'x.csv', '-d', 'x',
    ])
    assert result.exit_code == 0
    assert 'Edgerc section onboard not found' in result.output
    assert 'session' not in result.output
    assert 'NameError' not in result.output
