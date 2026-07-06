from __future__ import annotations

import argparse

from test_generator.scenarios import Scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Generate pytest tests from Scenario objects.'
    )
    parser.add_argument(
        '--layer',
        required=True,
        choices=['local', 'integration'],
        help='Which scenario layer to generate tests for.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Verify generated output is up to date without writing.',
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    print(
        f'Placeholder: --layer {args.layer} test generation not yet implemented '
        f'(rendering lands in Milestone 2). Package wiring confirmed: '
        f'{Scenario.__name__} import succeeded.'
    )


if __name__ == '__main__':
    main()
