from __future__ import annotations

import pytest

from .scenarios import Scenario

ALL_SIX_KINDS = (
    'utility_csv',
    'utility_directory',
    'constructor',
    'edgehostname_pipeline',
    'setup_validation',
    'cli',
)


def test_valid_scenario_passes():
    scenario = Scenario(
        id='TC-B1',
        name='csv utility happy path',
        description='Exercises the csv utility with a valid input file.',
        kind='utility_csv',
        type='positive',
        layer='local',
    )

    scenario.validate()


def test_unsupported_kind_raises():
    scenario = Scenario(
        id='TC-B2',
        name='unsupported kind',
        description='Should be rejected.',
        kind='bogus',
        type='positive',
        layer='local',
    )

    with pytest.raises(ValueError, match='bogus'):
        scenario.validate()


def test_gap_without_description_raises():
    scenario = Scenario(
        id='TC-B3',
        name='undocumented gap',
        description='',
        kind='utility_csv',
        type='gap',
        layer='local',
    )

    with pytest.raises(ValueError, match='explanatory'):
        scenario.validate()


def test_all_six_kinds_construct_and_validate():
    for kind in ALL_SIX_KINDS:
        scenario = Scenario(
            id=f'TC-{kind}',
            name=f'{kind} scenario',
            description=f'Covers the {kind} harness kind.',
            kind=kind,
            type='positive',
            layer='local',
        )

        scenario.validate()
