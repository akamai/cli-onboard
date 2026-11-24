"""
Keep cli.json's version/description in sync with pyproject.toml, which is the
single source of truth. akamai-cli reads cli.json without running any Python,
so the two can't be unified at runtime - this script is run by pre-commit to
catch drift instead.
"""
from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    version, description = project['version'], project['description']

    manifest_path = ROOT / 'cli.json'
    manifest = json.loads(manifest_path.read_text())

    changed = False
    for command in manifest['commands']:
        if command.get('version') != version:
            command['version'] = version
            changed = True
        if command.get('description') != description:
            command['description'] = description
            changed = True

    if changed:
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(f'Updated cli.json to match pyproject.toml (version={version})')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
