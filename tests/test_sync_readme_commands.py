"""
Tests for bin/sync_readme_commands.py, which keeps README.md's Command catalog
in sync with the CLI's actual registered commands.

splice_catalog/find_unknown_common_input_type_commands are pure string
transformations, tested here with synthetic input - no need to touch the real
README.md or spin up the CLI for those. get_commands/render_catalog are
exercised against the real `cli` fixture (tests/conftest.py) instead, since
those depend on the actual click app.
"""
from __future__ import annotations

import pytest
import sync_readme_commands as sync


def test_render_catalog_captures_the_real_help_commands_panel(cli):
    catalog = sync.render_catalog(cli)

    assert catalog.startswith('```console\n$ akamai onboard --help\n')
    assert catalog.endswith('```')
    assert 'Commands' in catalog
    # rich-click renders panels with rounded corners (╭╰), but Rich substitutes
    # square corners (┌└) on Windows consoles that don't report VT/ANSI support
    # (e.g. GitHub Actions' windows-latest runners) - accept either box style.
    assert ('╭' in catalog and '╰' in catalog) or ('┌' in catalog and '└' in catalog)
    assert '`single-host`' not in catalog  # real --help output, not markdown
    assert 'single-host' in catalog
    assert 'Create a simple delivery and security configuration' in catalog


def test_render_catalog_excludes_the_help_meta_command(cli):
    catalog = sync.render_catalog(cli)

    for line in catalog.splitlines():
        assert not line.strip().startswith('│ help '), f'help command leaked into catalog: {line!r}'


def test_render_catalog_does_not_permanently_mutate_the_cli(cli):
    assert 'help' in cli.commands

    sync.render_catalog(cli)

    assert 'help' in cli.commands, 'render_catalog must restore cli.commands after rendering'


def test_splice_catalog_replaces_content_between_markers():
    readme = (
        '# Title\n\n'
        '<!-- command-catalog:start -->\n'
        'stale table\n'
        '<!-- command-catalog:end -->\n\n'
        'more content\n'
    )

    result = sync.splice_catalog(readme, 'fresh table')

    assert 'stale table' not in result
    assert '<!-- command-catalog:start -->\nfresh table\n<!-- command-catalog:end -->' in result
    assert result.startswith('# Title')
    assert result.endswith('more content\n')


def test_splice_catalog_is_idempotent():
    readme = '<!-- command-catalog:start -->\nold\n<!-- command-catalog:end -->\n'

    once = sync.splice_catalog(readme, 'new')
    twice = sync.splice_catalog(once, 'new')

    assert once == twice


def test_splice_catalog_raises_when_markers_missing():
    with pytest.raises(ValueError, match='command-catalog'):
        sync.splice_catalog('# No markers here\n', 'table')


def test_find_unknown_common_input_type_commands_flags_names_not_in_the_cli():
    readme = (
        '### Common input types\n\n'
        '| Command       | CSV | JSON |\n'
        '| ------------- | --- | ---- |\n'
        '| `single-host` |     | ✅    |\n'
        '| `retired-cmd` | ✅   |      |\n\n'
        '### Convert command options\n'
    )

    unknown = sync.find_unknown_common_input_type_commands(readme, {'single-host', 'convert'})

    assert unknown == ['retired-cmd']


def test_find_unknown_common_input_type_commands_passes_when_all_known():
    readme = (
        '### Common input types\n\n'
        '| Command       | CSV | JSON |\n'
        '| ------------- | --- | ---- |\n'
        '| `single-host` |     | ✅    |\n\n'
        '### Convert command options\n'
    )

    unknown = sync.find_unknown_common_input_type_commands(readme, {'single-host', 'convert'})

    assert unknown == []


def test_find_unknown_common_input_type_commands_ignores_readme_without_that_section():
    unknown = sync.find_unknown_common_input_type_commands('# No such section here\n', {'single-host'})

    assert unknown == []


def test_get_commands_matches_the_real_cli(cli):
    commands = sync.get_commands(cli)

    assert 'help' not in commands
    assert commands.keys() == {
        'appsec-create',
        'appsec-policy',
        'appsec-remove',
        'appsec-update',
        'batch-create',
        'check-activation',
        'convert',
        'create',
        'fetch-sample-templates',
        'multi-hosts',
        'sbd-precheck',
        'sbd-status',
        'single-host',
    }
    assert all(purpose for purpose in commands.values())
