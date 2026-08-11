from __future__ import annotations

import csv
import importlib.util
import json
import logging
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / 'bin'

# Avoids cli fixture's setup_logger() littering logs/ in the repo root during tests.
_SCRATCH_DIR = tempfile.mkdtemp(prefix='cli-onboard-tests-')
os.chdir(_SCRATCH_DIR)

import exceptions  # noqa: E402
import utility  # noqa: E402
import utility_papi  # noqa: E402


# ---------------------------------------------------------------------------
# click_args factory — mirrors the defaults on `convert` in bin/akamai-onboard.py
# so tests only need to override the option(s) they're exercising.
# ---------------------------------------------------------------------------
def _default_click_args(**overrides) -> dict:
    args = {
        'contract': 'ctr_TEST123',
        'group': 'grp_456',
        'product': None,
        'network': 'STANDARD_TLS',
        'directory': 'templates',
        'csv': 'input.csv',
        'rule_format': 'latest',
        'use_cpcode': None,
        'unique_cpcode': False,
        'prune_hostname_rules': False,
        'cert_mode': 'SBD',
        'use_existing_edgehostname': None,
        'enrollment_id': None,
        'media_ehn': 'VOD',
        'gtm_domain': None,
        'activate': (),
        'email': (),
        'force': False,
        'dryrun': False,
        'prefix': None,
        'preview': False,
        'launch': True,
    }
    args.update(overrides)
    return args


@pytest.fixture
def click_args_factory():
    return _default_click_args


@pytest.fixture
def config_stub():
    """A stand-in configuration object used when setting up a test run."""
    return SimpleNamespace(edgerc='/dev/null', section='onboard', account_key=None)


@pytest.fixture
def csv_factory(tmp_path):
    """Creates a temporary CSV file from sample data rows, for use in a test."""
    def _make(rows: list[dict], filename: str = 'input.csv') -> str:
        path = tmp_path / filename
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return str(path)

    return _make


@pytest.fixture
def headers_only_csv_factory(tmp_path):
    """Creates a temporary CSV file that has column headers but no data rows."""
    def _make(fieldnames: list[str], filename: str = 'empty.csv') -> str:
        path = tmp_path / filename
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return str(path)

    return _make


@pytest.fixture
def template_dir_factory(tmp_path):
    """Creates sample configuration template files, one per property name, in a temporary folder."""
    def _make(names: list[str], directory: str = 'templates') -> str:
        template_dir = tmp_path / directory
        template_dir.mkdir(exist_ok=True)
        minimal_ruletree = {
            'rules': {
                'name': 'default',
                'children': [],
                'behaviors': [
                    {'name': 'origin', 'options': {}},
                    {'name': 'cpCode', 'options': {}},
                ],
            }
        }
        for name in names:
            with open(template_dir / f'{name}.json', 'w') as f:
                json.dump(minimal_ruletree, f)
        return str(template_dir)

    return _make


class StubWrapper:
    """A fake connection that answers questions about existing properties, products,
    groups, and contracts locally instead of calling a real service.
    """

    def __init__(self, existing_properties: set[str] | None = None, valid_products: set[str] | None = None,
                 valid_groups: dict[str, list[str]] | None = None, valid_contracts: set[str] | None = None):
        self.existing_properties = existing_properties or set()
        self.valid_products = valid_products or {'prd_Site_Accel'}
        # groupId -> contractIds it belongs to; defaults match click_args_factory's
        # 'group': 'grp_456' / 'contract': 'ctr_TEST123' so unrelated tests pass by default.
        self.valid_groups = valid_groups or {'grp_456': ['ctr_TEST123']}
        self.valid_contracts = valid_contracts or {'ctr_TEST123'}

    def property_exists(self, property_name: str) -> bool:
        return property_name in self.existing_properties

    def getProductsByContract(self, contract_id: str):
        return SimpleNamespace(
            status_code=200,
            json=lambda: {'products': {'items': [{'productId': p} for p in self.valid_products]}},
        )

    def get_groups(self):
        return [{'groupId': gid, 'groupName': f'{gid}-name', 'contractIds': contracts}
                for gid, contracts in self.valid_groups.items()]

    def get_contracts(self):
        return [{'contractId': cid, 'contractTypeName': 'DIRECT_CUSTOMER'} for cid in self.valid_contracts]


@pytest.fixture
def stub_wrapper_factory():
    return StubWrapper


@pytest.fixture(scope='session')
def akamai_onboard_module():
    # bin/akamai-onboard.py has a hyphen in its filename, so it can't be `import`-ed
    # normally — load it directly from its file path instead.
    spec = importlib.util.spec_from_file_location('akamai_onboard_cli', BIN_DIR / 'akamai-onboard.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli(akamai_onboard_module):
    return akamai_onboard_module.cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def build_onboard_object(click_args_factory, config_stub):
    """Builds a ready-to-validate onboarding request with realistic setup values
    already filled in, without re-running the full CSV import each time.
    """
    import onboard_convert

    def _build(click_overrides=None, gtm_replacement_count=0, property_list=None,
               public_hostnames=None, product_list=None, edge_hostname_list=None,
               all_template_json_exists=True, valid_csv=True):
        click_args = click_args_factory(**(click_overrides or {}))
        onboard_object = onboard_convert.onboard(config_stub, click_args)
        onboard_object.csv_loc = 'input.csv'
        onboard_object.valid_csv = valid_csv
        onboard_object.all_template_json_exists = all_template_json_exists
        onboard_object.gtm_replacement_count = gtm_replacement_count
        onboard_object.public_hostnames = public_hostnames or ['www.example.com']
        onboard_object.property_list = property_list or ['example-prop']
        onboard_object.product_list = product_list or ['prd_Site_Accel']
        suffix = '.edgesuite.net' if onboard_object.secure_network == 'STANDARD_TLS' else '.edgekey.net'
        onboard_object.edge_hostname_list = edge_hostname_list or [f'www.example.com{suffix}']
        return onboard_object

    return _build


@pytest.fixture
def util():
    """A real onboarding helper for tests, with the external command-line check turned off."""
    return utility.utility(check_prereqs=False)


@pytest.fixture
def papi():
    """A real helper for CP code and property operations, paired with a fake connection in tests."""
    return utility_papi.papiFunctions()


class FakeConvertUtility(utility.utility):
    """A test version of the conversion helper that skips real network and
    command-line checks so the rest of its logic still runs normally.
    """

    def __init__(self, api_access: bool = False):
        super().__init__(check_prereqs=False)
        self._api_access = api_access

    def check_cli_prereq(self, click_args, config) -> None:
        return None

    def check_api_access(self, papi) -> bool:
        return self._api_access


@pytest.fixture
def fake_convert_utility_cls():
    return FakeConvertUtility


@pytest.fixture
def restore_logging_state():
    """Reset logging level state to a fresh-process baseline, then restore it after."""
    root = logging.getLogger()
    shared = logging.getLogger('exceptions')
    urllib3_logger = logging.getLogger('urllib3')
    requests_logger = logging.getLogger('requests')
    snapshot = (root.level, shared.level, urllib3_logger.level, requests_logger.level,
                exceptions._most_verbose_level_requested)
    exceptions._most_verbose_level_requested = None
    yield
    (root.level, shared.level, urllib3_logger.level, requests_logger.level,
     exceptions._most_verbose_level_requested) = snapshot


@pytest.fixture
def fake_edgerc(tmp_path):
    """A valid sample credentials file, just enough to let a test run past the login step."""
    edgerc_path = tmp_path / 'valid.edgerc'
    edgerc_path.write_text(
        '[default]\n'
        'host = example.akamaiapis.net\n'
        'client_token = test_client_token\n'
        'client_secret = test_client_secret\n'
        'access_token = test_access_token\n'
    )
    return str(edgerc_path)
