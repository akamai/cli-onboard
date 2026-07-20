"""
Keep README.md's Command catalog in sync with the CLI's actual registered
commands. `cli.json` isn't the right source for this - it only describes the
single top-level `onboard` plugin (see sync_cli_manifest.py), not its 12
subcommands. The real source of truth is the `click`/`rich_click` group
defined in bin/akamai-onboard.py, so this script captures its real `--help`
"Commands" panel (the same rich_click-rendered box a user sees running the
CLI) and rewrites it between the `<!-- command-catalog:start/end -->` markers
in README.md whenever it drifts - mirroring sync_cli_manifest.py's
fail-and-rewrite pattern.

Loading bin/akamai-onboard.py executes the whole module (it has a hyphen in
its filename, so it can't be `import`-ed normally - see tests/conftest.py's
`akamai_onboard_module` fixture for the same pattern), which pulls in the
project's full dependency set. Run this via `uv run`, not bare `python`.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / 'README.md'
BIN_DIR = ROOT / 'bin'

START_MARKER = '<!-- command-catalog:start -->'
END_MARKER = '<!-- command-catalog:end -->'

# Fixed so the generated output doesn't vary by the machine's terminal width -
# matches the COLUMNS this repo's CI already pins for CLI output (build.yml).
HELP_COLUMNS = '120'

# Meta-commands that aren't part of the onboarding command catalog.
EXCLUDED_COMMANDS = {'help'}


def load_cli():
    spec = importlib.util.spec_from_file_location('akamai_onboard_cli', BIN_DIR / 'akamai-onboard.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.cli


def get_commands(cli) -> dict[str, str]:
    """name -> one-line purpose, for every command except EXCLUDED_COMMANDS."""
    return {
        name: command.get_short_help_str(limit=1000)
        for name, command in sorted(cli.commands.items())
        if name not in EXCLUDED_COMMANDS
    }


def render_catalog(cli) -> str:
    """Capture the real `--help` "Commands" panel, with EXCLUDED_COMMANDS
    removed before rendering so the box border is recalculated cleanly rather
    than leaving a gap. Restores `cli.commands` afterwards - callers (like the
    test suite's session-scoped `cli` fixture) may reuse the same Group
    instance elsewhere and shouldn't see this as a permanent mutation."""
    removed = {name: cli.commands.pop(name) for name in EXCLUDED_COMMANDS if name in cli.commands}
    try:
        output = CliRunner().invoke(cli, ['--help'], env={'COLUMNS': HELP_COLUMNS}).output
        start = output.index('╭─ Commands')
        end = output.index('╯', start) + 1
        commands_panel = output[start:end]
    finally:
        cli.commands.update(removed)

    return f'```console\n$ akamai onboard --help\n\n{commands_panel}\n```'


def splice_catalog(readme_text: str, catalog: str) -> str:
    pattern = re.compile(re.escape(START_MARKER) + r'.*?' + re.escape(END_MARKER), re.DOTALL)
    if not pattern.search(readme_text):
        raise ValueError(f'Could not find {START_MARKER} / {END_MARKER} markers in README.md')
    return pattern.sub(f'{START_MARKER}\n{catalog}\n{END_MARKER}', readme_text)


def find_unknown_common_input_type_commands(readme_text: str, known_commands: set[str]) -> list[str]:
    """The "Common input types" table's CSV/JSON metadata isn't derivable from
    `click` introspection, so it stays hand-maintained - but its command-name
    column must still be a subset of the canonical command set, so an
    added/removed command surfaces a required edit here too."""
    section = readme_text.split('### Common input types', 1)
    if len(section) != 2:
        return []
    table_text = section[1].split('###', 1)[0]

    referenced = set(re.findall(r'^\|\s*`([a-z0-9-]+)`', table_text, re.MULTILINE))
    return sorted(referenced - known_commands)


def main() -> int:
    cli = load_cli()
    known_commands = set(get_commands(cli))
    catalog = render_catalog(cli)

    readme_text = README_PATH.read_text()
    new_readme_text = splice_catalog(readme_text, catalog)

    unknown = find_unknown_common_input_type_commands(new_readme_text, known_commands)
    if unknown:
        print(
            f"README.md's Common input types table references command(s) not in the CLI: {', '.join(unknown)}",
            file=sys.stderr,
        )
        return 1

    if new_readme_text != readme_text:
        README_PATH.write_text(new_readme_text)
        print("Updated README.md's Command catalog to match the CLI's registered commands")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
