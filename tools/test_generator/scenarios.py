from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

VALID_KINDS = {
    'utility_csv',
    'utility_directory',
    'constructor',
    'edgehostname_pipeline',
    'setup_validation',
    'cli',
}


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    kind: str
    type: str
    layer: str
    csv_rows: list[dict] = field(default_factory=list)
    template_names: list[str] = field(default_factory=list)
    click_overrides: dict = field(default_factory=dict)
    expected_exit_code: int | None = None
    expected_output: str | None = None
    expected_logs: str | None = None
    expected_state: dict = field(default_factory=dict)
    skip_reason: str | None = None
    # integration-only fields (unused until Milestone 4, kept as stubs per the milestone design)
    integration_assets: list[str] = field(default_factory=list)
    teardown_policy: str | None = None
    requires_env: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.kind not in VALID_KINDS:
            raise ValueError(
                f'Unsupported scenario kind {self.kind!r} for {self.id!r}; '
                f'must be one of {sorted(VALID_KINDS)}'
            )
        if self.type == 'gap' and not self.description.strip():
            raise ValueError(
                f'Gap scenario {self.id!r} must include explanatory description text'
            )
