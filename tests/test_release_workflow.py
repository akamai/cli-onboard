"""The release workflow must find the CHANGELOG section for the current version.

It once searched for a heading of exactly '## 2.5.5' while CHANGELOG.md uses
'## [v2.5.5] - date', so every release run failed with "No CHANGELOG.md
section found".
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / '.github' / 'workflows' / 'release.yml').read_text(encoding='utf-8')
CHANGELOG = ROOT / 'CHANGELOG.md'


def _awk_program() -> str:
    match = re.search(r"awk -v ver=\"[^\"]*\" '(.*?)' CHANGELOG\.md", WORKFLOW, re.S)
    assert match, 'awk step not found in release.yml'
    return match.group(1)


def _extract(version: str, changelog: Path = CHANGELOG) -> str:
    result = subprocess.run(
        ['awk', '-v', f'ver={version}', _awk_program(), str(changelog)],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def _current_version() -> str:
    text = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    return re.search(r'^version = "(.*)"', text, re.M).group(1)


def test_extracts_notes_for_current_version():
    notes = _extract(_current_version())
    assert notes.strip(), 'no notes found for the version in pyproject.toml'
    assert '## [' not in notes, 'notes leaked into the next version section'


def test_stops_at_next_version(tmp_path):
    log = tmp_path / 'CHANGELOG.md'
    log.write_text(
        '## [v2.0.1] - 2026-01-02\n- new\n\n## [v2.0.0] - 2026-01-01\n- old\n',
        encoding='utf-8',
    )
    assert _extract('2.0.1', log).strip() == '- new'


def test_unknown_version_gives_empty_notes():
    assert _extract('99.99.99').strip() == ''


def test_dots_in_version_are_literal(tmp_path):
    log = tmp_path / 'CHANGELOG.md'
    log.write_text('## [v2x0x1] - 2026-01-02\n- wrong\n', encoding='utf-8')
    assert _extract('2.0.1', log).strip() == ''


def test_plain_heading_still_supported(tmp_path):
    log = tmp_path / 'CHANGELOG.md'
    log.write_text('## 2.0.1\n- plain\n', encoding='utf-8')
    assert _extract('2.0.1', log).strip() == '- plain'
