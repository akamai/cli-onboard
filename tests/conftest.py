from __future__ import annotations

import csv
import importlib.util
import json
import logging.config  # noqa: F401 - needed so exceptions.setup_logger() can find dictConfig
import os
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / 'bin'

# `bin/*.py` modules call setup_logger() at import time, which creates
# `logs/` and `config/` in the current working directory as a side effect.
# Move the whole test process into a scratch directory before any test file
# imports those modules, so that side effect doesn't litter the repo root.
_SCRATCH_DIR = tempfile.mkdtemp(prefix='cli-onboard-tests-')
os.chdir(_SCRATCH_DIR)

# setup_logger() falls back to a relative 'config/logging.json' when it can't
# find a copy under ~/.akamai-cli (i.e. on any machine without a prior real
# `akamai install`, such as a CI runner). Seed that fallback here so the
# import below doesn't depend on the machine's install history.
os.makedirs('config', exist_ok=True)
shutil.copy2(REPO_ROOT / 'config' / 'logging.json', 'config/logging.json')

# Must be imported after the chdir above - utility.py calls setup_logger() at
# import time, which creates `logs/`/`config/` as a side effect in the cwd.
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
        'launch': True,
    }
    args.update(overrides)
    return args


@pytest.fixture
def click_args_factory():
    return _default_click_args


@pytest.fixture
def config_stub():
    """Stand-in for the click `Config` object passed into onboard_convert.onboard()."""
    return SimpleNamespace(edgerc='/dev/null', section='onboard', account_key=None)


@pytest.fixture
def csv_factory(tmp_path):
    """Write a CSV fixture file under tmp_path from a list of row dicts, return its path."""
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
    """Write a CSV with only a header row (zero data rows), return its path."""
    def _make(fieldnames: list[str], filename: str = 'empty.csv') -> str:
        path = tmp_path / filename
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return str(path)

    return _make


@pytest.fixture
def template_dir_factory(tmp_path):
    """Write ruletree template JSON files (named after property/hostname) under a tmp dir."""
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
    """Minimal stand-in for the PAPI wrapper object used by validateSetupStepsConvert.

    Real validateSetupStepsConvert calls wrapper_object.property_exists(name) and
    (via utility.validateProductId) wrapper_object.getProductsByContract(contract_id) —
    both genuine network calls in production. This stub answers both locally so the
    surrounding flag/GTM/email/activation logic can be exercised without a live API.
    """

    def __init__(self, existing_properties: set[str] | None = None, valid_products: set[str] | None = None):
        self.existing_properties = existing_properties or set()
        self.valid_products = valid_products or {'prd_Site_Accel'}

    def property_exists(self, property_name: str) -> bool:
        return property_name in self.existing_properties

    def getProductsByContract(self, contract_id: str):
        return SimpleNamespace(
            status_code=200,
            json=lambda: {'products': {'items': [{'productId': p} for p in self.valid_products]}},
        )


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
    """Build a real onboard_convert.onboard() instance, then fill in the fields that,
    in a real `convert` run, would have been populated by CSV/directory processing
    upstream of validateSetupStepsConvert. Lets Group-C tests exercise the real
    validation function without replaying the whole CSV pipeline each time.
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
    """A real utility.utility(), with the `akamai` CLI/pipeline shell-out (irrelevant
    to the business logic under test, and not something a hermetic suite should
    depend on being on PATH) skipped via its check_prereqs constructor seam.
    """
    return utility.utility(check_prereqs=False)


@pytest.fixture
def papi():
    """A real utility_papi.papiFunctions() - no constructor seam needed, it has
    no state and no shell-out of its own; all PAPI calls go through the
    wrapper_object it's passed, which tests double out at the call site.
    """
    return utility_papi.papiFunctions()


class FakeConvertUtility(utility.utility):
    """Test double for the utility.utility() that convert() builds at
    bin/akamai-onboard.py:229, injected via Config(utility_cls=...) + `obj=` on
    CliRunner.invoke() rather than monkeypatching utility.utility.

    Subclasses real utility.utility so all the business logic under test
    (load_csv_input, csv_2_property_dict_convert, etc.) runs for real; only the two
    genuinely-networked/shelled-out gates convert() hits before that logic
    (check_cli_prereq, check_api_access) are replaced, plus the constructor's
    `akamai` CLI prereq shell-out (skipped via check_prereqs=False).
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
def fake_edgerc(tmp_path):
    """A syntactically valid .edgerc with a real [onboard] section.

    init_config() reads this synchronously (EdgeRc/EdgeGridAuth) with no network call —
    good enough to get a CLI invocation past credential loading in tests.
    """
    edgerc_path = tmp_path / 'valid.edgerc'
    edgerc_path.write_text(
        '[onboard]\n'
        'host = example.akamaiapis.net\n'
        'client_token = test_client_token\n'
        'client_secret = test_client_secret\n'
        'access_token = test_access_token\n'
    )
    return str(edgerc_path)
