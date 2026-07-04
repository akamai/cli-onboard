## Plan: Build cli-onboard Test Generator

Build a two-layer test generator for `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard`: first a local generator that emits hermetic pytest files from structured convert scenarios, then an integration generator that reuses the same scenario vocabulary for live Akamai API cases with manifests and cleanup. The recommended approach is stdlib-only Python scenario definitions plus code generation to readable individual test functions, matching the current repo style and avoiding new dependencies while you learn the design.

**Steps**

Phase 1 — Learn the Existing Test Contract
1. Read the existing local convert suite and treat it as the golden style guide. Key patterns to reuse:
   - `tests/conftest.py`: `csv_factory`, `template_dir_factory`, `FakeConvertUtility`, `StubWrapper`, `build_onboard_object`, `fake_edgerc`, `runner`, `cli`.
   - `tests/test_convert_csv_validation.py`: direct utility validation tests.
   - `tests/test_convert_directory_validation.py`: tiny fake object for focused validator tests.
   - `tests/test_convert_flag_constructor.py`, `tests/test_convert_flag_edgehostname.py`, `tests/test_convert_flag_setup_validation.py`, `tests/test_convert_flag_cli_guards.py`: four distinct execution harnesses for four kinds of scenarios.
2. Write a short developer note, likely `docs/test-generator.md`, explaining the four local harness types:
   - `utility_csv`: calls `utility.utility().csv_validator_convert()`.
   - `utility_directory`: calls `json_input_file_validator()` with minimal fake object.
   - `constructor`: builds `onboard_convert.onboard()` and asserts derived state.
   - `cli`: uses `CliRunner.invoke()` with `Config(utility_cls=FakeConvertUtility)`.
   - `setup_validation`: uses `build_onboard_object` plus `StubWrapper` and `confirm_input`.

Phase 2 — Define Scenario Model
3. Create generator package structure:
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tools/test_generator/__init__.py`
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tools/test_generator/scenarios.py`
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tools/test_generator/render.py`
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tools/generate_convert_tests.py`
4. Use Python scenario objects instead of YAML/JSON initially. Rationale: no new dependency, supports comments, and keeps learning focused on mapping behavior to tests rather than parser choices.
5. Model each scenario with fields such as:
   - `id`, `name`, `description`, `kind`, `type` (`positive`, `negative`, `gap`, `skip`), `layer` (`local`, `integration`).
   - `csv_rows`, `template_names`, `click_overrides`, `expected_exit_code`, `expected_output`, `expected_logs`, `expected_state`, `skip_reason`.
   - `integration_assets`, `teardown_policy`, `requires_env` for live cases.
6. Add validation inside the generator before rendering:
   - Every local scenario must choose one supported `kind`.
   - Business-logic negative CLI cases should prefer message assertions over nonzero exit code, because many code paths exit with code 0.
   - `gap` scenarios must include explanatory text so generated tests clearly mark characterization behavior.
   - Integration scenarios must declare asset manifest fields and teardown behavior.

Phase 3 — Generate Local Pytest Tests
7. Start by generating one narrow file, not the whole suite:
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tests/generated/test_convert_generated_local.py`
8. Renderer should emit normal pytest functions, not parameterized tests, because current tests are readable individual functions and `CONVERT_TEST_PLAN.md` maps IDs to specific function names.
9. Implement renderers per scenario kind:
   - `utility_csv`: create CSV via `csv_factory` or `headers_only_csv_factory`, call `util.csv_validator_convert()`, assert validity and row count/output.
   - `utility_directory`: create template dir via `template_dir_factory`, construct a minimal fake object, call `util.json_input_file_validator()`.
   - `constructor`: build `onboard_convert.onboard(config_stub, click_args_factory(...))`, assert fields like `edge_hostname_mode`.
   - `edgehostname_pipeline`: populate `onboard_object.csv_dict`, call `util.csv_2_property_dict_convert()`, assert `edge_hostname_list` or captured error log.
   - `setup_validation`: use `build_onboard_object`, `stub_wrapper_factory`, `caplog`, and optional `confirm_input` callable.
   - `cli`: use `runner.invoke(cli, args, obj=Config(utility_cls=...))`, `fake_edgerc`, generated CSV/templates, and assert output text.
10. Seed the generator with a small subset first, for example TC-B1, TC-B3, TC-C1, TC-D5, TC-D14, and TC-D1. This gives one case from each major harness before scaling.
11. Add a `--check` mode to fail if generated output is stale. It should render to memory and compare against the checked-in generated file without writing.

Phase 4 — Integrate With Test Commands
12. Update pytest configuration only if needed. Current `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/pyproject.toml` has `pythonpath = ["bin"]`; if generated tests import `tools.test_generator`, either add project root to pytest pythonpath or keep generated tests free of generator imports.
13. Add commands to documentation:
   - Generate local tests: `uv run python tools/generate_convert_tests.py --layer local`
   - Check generated tests are current: `uv run python tools/generate_convert_tests.py --layer local --check`
   - Run generated local tests: `uv run pytest tests/generated/test_convert_generated_local.py`
   - Run full local suite: `uv run pytest tests/`
14. Do not replace current handcrafted tests during the first pass. Generated tests should live alongside them until the team trusts the generator.

Phase 5 — Extend to Integration Scenario Generation
15. Create opt-in integration generated tests under:
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tests/integration/generated/test_convert_generated_integration.py`
16. Add integration support helpers:
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tests/integration/conftest.py`
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tests/integration/asset_manifest.py`
   - `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tests/integration/cleanup_convert_assets.py`
17. Gate integration tests with environment variables and pytest markers:
   - `CLI_ONBOARD_RUN_INTEGRATION=1`
   - `AKAMAI_EDGERC`, `AKAMAI_EDGERC_SECTION`
   - `CLI_ONBOARD_CONTRACT`, `CLI_ONBOARD_GROUP`, optional `CLI_ONBOARD_ACCOUNT_KEY`
   - `CLI_ONBOARD_TEST_CPCODE` for all cases except the one that intentionally creates a cpcode.
18. Generated integration tests should always create run-scoped names directly in generated CSV rows, not rely on `--dryrun --prefix`, because current dryrun prefix behavior is characterized as broken/dead code.
19. Each integration test writes asset IDs as soon as they are known:
   - property ID/name/version
   - edge hostname ID/name
   - activation IDs/statuses
   - cpcode ID if created or reused
20. Teardown helper order:
   - Check activation state.
   - Deactivate staging, then production if active.
   - Poll until deactivation completes.
   - Delete property.
   - Delete edge hostname if no active property references it.
   - Leave cpcode in place, since cpcode deletion is not exposed.
21. Add integration commands:
   - Generate integration tests: `uv run python tools/generate_convert_tests.py --layer integration`
   - Run explicit integration suite: `CLI_ONBOARD_RUN_INTEGRATION=1 uv run pytest tests/integration/ -m integration`

Phase 6 — Documentation and Learning Loop
22. Update `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/CONVERT_TEST_PLAN.md` with a “Generated tests” section that states which TC IDs are generator-backed and which remain handcrafted.
23. Add `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/docs/test-generator.md` as the learning guide:
   - How a scenario becomes a test.
   - How to choose the correct harness kind.
   - Why local and integration layers are separate.
   - How characterization/gap tests should be written and later flipped.
24. Once the first generated local subset is stable, add more TC-A through TC-D scenarios incrementally. Only then consider replacing duplicated handcrafted tests.

**Relevant files**
- `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/tests/conftest.py` — reuse fixtures and import-side-effect mitigation; especially `FakeConvertUtility`, `StubWrapper`, `build_onboard_object`, `fake_edgerc`.
- `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/CONVERT_TEST_PLAN.md` — source scenario taxonomy, TC IDs, local/API split, gap semantics, exit-code warning.
- `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/bin/akamai-onboard.py` — `convert()` CLI options, early guards, `Config(utility_cls=...)` injection seam.
- `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/bin/onboard_convert.py` — constructor behavior and `edge_hostname_mode` derivation.
- `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/bin/utility.py` — local functions to target: `csv_validator_convert`, `json_input_file_validator`, `csv_2_property_dict_convert`, `csv_2_property_array_convert`, `validateSetupStepsConvert`.
- `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/bin/utility_papi.py` — integration workflow helpers for cpcode creation/search and activation polling.
- `/Users/pwongcha/Documents/akamai-bitbucket/cloudflare/cli-onboard/pyproject.toml` — pytest config and dependency policy.

**Verification**
1. After creating the first scenario subset, run `uv run python tools/generate_convert_tests.py --layer local --check` and confirm it fails before generated output exists or is stale.
2. Run `uv run python tools/generate_convert_tests.py --layer local` and inspect the generated pytest file for readable names and comments.
3. Run `uv run pytest tests/generated/test_convert_generated_local.py`.
4. Run `uv run pytest tests/` to ensure generated tests do not disturb the existing 42 passing / 1 skipped local suite.
5. For integration helpers, first run a dry structural check without live API: `uv run pytest tests/integration/ -m integration` should skip cleanly when `CLI_ONBOARD_RUN_INTEGRATION` is not set.
6. With credentials and sandbox variables set, run one generated integration scenario only, then verify the manifest is written and cleanup removes/deactivates the property and edge hostname.
7. Only after single-case cleanup is proven, run the full generated integration suite.

**Decisions**
- Generate individual pytest functions instead of parameterized tests to match the current test style and keep TC IDs easy to map back to the plan.
- Use Python scenario definitions first to avoid adding dependencies such as PyYAML or Jinja2.
- Keep generated tests alongside handcrafted tests initially; do not delete or rewrite the current suite in the first iteration.
- Local generation is the foundation; integration generation is opt-in and environment-gated.
- Business-logic failures assert on output/log text, not exit code, because many failure paths exit with code 0.
- Integration naming must be done in generated CSV data, not via `--dryrun --prefix`, because that flag path is currently dead/buggy.

**Further Considerations**
1. Consider adding `pytest.mark.generated` and `pytest.mark.integration` markers to make generated tests easy to run or exclude. This may require adding marker declarations to `pyproject.toml`.
2. Decide later whether generated files are committed. Recommendation: commit local generated tests for reviewability, but treat integration generated tests as optionally regenerated if sandbox details change.
3. If the scenario model grows beyond convert, split by command: `convert_scenarios.py`, `appsec_scenarios.py`, `batch_create_scenarios.py`, while keeping one renderer library.
