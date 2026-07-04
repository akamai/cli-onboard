# `onboard convert` Test Plan (v4 — Local suite built: 42 passed, 1 skipped, split into 7 files)

Source: `bin/akamai-onboard.py:convert` (options), `bin/onboard_convert.py` (arg → state mapping),
`bin/utility.py` (`csv_validator_convert`, `validateSetupStepsConvert`, `check_sbd_quota`).

Test suite: `tests/` (pytest, added as a dev dependency via `uv add --group dev pytest`,
configured in `pyproject.toml`). Run with:

```
uv run pytest tests/
```

## How to read this doc

- **Type**: `Positive` = should succeed · `Negative` = should fail with a clear error · `Gap` = the doc's assumption or the confirmed spec doesn't match what the code actually does today — either never implemented, or implemented but dead/broken. Each Gap test pins down *today's actual behavior* (a characterization test, see below) so a future fix flips the assertion instead of the bug going unnoticed.
- **Layer**: `Local` = fails/succeeds before any Akamai API call, no credentials or live contract needed → unit-style tests, safe for CI. `API` = drives real Akamai PAPI/CPS/Edge Hostname calls against a live contract+group → integration tests, not yet built (see §8).
- **ID prefix**: each letter is just this doc's section number spelled out — no meaning beyond "which section this row lives in":

  | Prefix | Section | Layer |
  |---|---|---|
  | TC-A | §2 CLI parsing / global sanity | Local |
  | TC-B | §3 CSV validation | Local |
  | TC-C | §4 Directory / template validation | Local |
  | TC-D | §5 Flag interaction / logical validation | Local |
  | TC-E | §6 API-required — functional / happy-path | **API (integration)** |
  | TC-F | §7 API-required — error / edge scenarios | **API (integration)** |

## Characterization tests vs. spec tests

Not all 43 tests in the built suite are the same *kind* of test:

- **Spec tests** (36 of them) assert behavior you confirmed as intended, verified against the actual code. These fail if a future change breaks intended behavior — ordinary regression tests.
- **Characterization tests** (7, all marked `Gap` below) assert *whatever the code currently does*, which is known/suspected to be wrong. Their purpose is to make the current behavior visible and change-detectable, not to declare it correct. They are: TC-B6, TC-B7, TC-D3, TC-D15 (×2 functions), TC-D19-adjacent nuance, TC-A8b.
- **TC-D6** is neither — it's `skip`ped outright, since the intended behavior isn't implemented at all and there's nothing meaningful to characterize or assert yet.

## Test count summary

| Section | Positive | Negative | Gap (characterizes a bug) | Total |
|---|---|---|---|---|
| §2 TC-A | 1 | 7 | 1 | 9 |
| §3 TC-B | 2 | 3 | 2 | 7 |
| §4 TC-C | 2 | 2 | 0 | 4 |
| §5 TC-D | 7 | 11 | 3 | 21 |
| §6 TC-E | 15 | 0 | 0 | 15 (not yet built — API/integration) |
| §7 TC-F | 1 | 9 | 0 | 10 (not yet built — API/integration) |
| **Total** | **28** | **32** | **6** | **66** |

Every TC-E and TC-F case is an integration test — they call real PAPI/CPS/Edge Hostname/CP Code endpoints and need a live contract, group, and valid `.edgerc` credentials; not built yet (§8 setup/teardown still applies before starting them). TC-A through TC-D are all built and passing/skipped in `tests/`.

## Cross-cutting finding: exit codes don't distinguish success from failure

Nearly every "negative" path in this codebase calls `sys.exit(logger.error(...))` or a bare `sys.exit()`. `logger.error(...)` returns `None`, and `sys.exit(None)` — like bare `sys.exit()` — exits with **code 0**, the same as success. Only genuine click-level parsing errors (missing required option, bad `Choice`, bad type) produce a real nonzero exit code (2), because those come from click itself before `convert()`'s body runs. Every test in the suite that exercises a business-logic failure therefore asserts on **log/output message content**, not exit code — asserting `exit_code != 0` would be silently wrong everywhere in this app.

## 1. Option reference

| Option | Values | Default | Notes |
|---|---|---|---|
| `-c/--contract` | string | none | |
| `-g/--group` | string | none | |
| `-p/--product` | `prd_SPM`, `prd_Fresca`, `prd_Site_Accel`, `prd_Download_Delivery`, ... | none (falls back to CSV `product` col) | overrides CSV per-row |
| `-n/--network` | `ENHANCED_TLS`, `STANDARD_TLS` | `STANDARD_TLS` | sets edge hostname suffix |
| `-d/--directory` | path | **required** | ruletree json templates |
| `--csv` | path | **required** | see §3 schema |
| `-f/--rule-format` | string | `latest` | |
| `--use-cpcode` | numeric string | none | reuse existing cpcode, skips create/search |
| `--cert-mode` | `SBD`, `CPS` | `SBD` | |
| `--use-existing-edgehostname` | none / `CSV` / `<ehn-name>` | `None` | optional-value flag |
| `--enrollment-id` | int | none | requires `--cert-mode CPS` |
| `--media-ehn` | `VOD`, `LIVE` | `VOD` | only affects `prd_Adaptive_Media_Delivery` |
| `--gtm-domain` | string ending `.akadns.net` | none | only required if templates reference gtm |
| `--activate` | `staging`, `production` (multiple) | none | production requires staging in same run |
| `--email` | string (multiple) | `['noreply@akamai.com']` | required valid if activating |
| `--force` | flag | `False` | skips y/n confirmation prompt |
| `--dryrun` | flag | `False` | requires `--prefix` — **see TC-D3: currently has no other effect (dead code)** |
| `--prefix` | string | none | only valid with `--dryrun` |
| `--launch/--no-launch` | flag | `True` | auto-opens Excel |

All options above are confirmed in-scope — none are being dropped (including CPS/`--enrollment-id`).

Derived `edge_hostname_mode` (precedence, first match wins):
1. `--use-existing-edgehostname` set → `use_existing_edgehostname` (wins even if `--cert-mode CPS` also set — see TC-D6, currently silent, no warning). **Only the literal value `CSV` actually works end-to-end — see TC-D15: an explicit `<ehn-name>` sets this mode but the name is never applied anywhere, so the run always fails.**
2. `--cert-mode CPS` + `--enrollment-id` → `create_cps_edgehostname`
3. `--cert-mode CPS` (no enrollment) → `cps_placeholder`
4. else → `secure_by_default`

---

## 2. CLI parsing / global sanity (Local) — TC-A · 1 Positive / 7 Negative / 1 Gap

`tests/test_convert_cli_parsing.py`

| ID | Scenario | Type | Test function |
|---|---|---|---|
| TC-A1 | `convert --help` renders all options | Positive | `test_help_shows_all_options` |
| TC-A2 | Omit `--csv` | Negative (click "missing required option") | `test_missing_csv_option_errors` |
| TC-A3 | Omit `--directory` | Negative | `test_missing_directory_option_errors` |
| TC-A4 | `--network BOGUS` | Negative (click.Choice rejects) | `test_invalid_network_choice_errors` |
| TC-A5 | `--cert-mode bogus` | Negative (click.Choice rejects) | `test_invalid_cert_mode_choice_errors` |
| TC-A6 | `--activate bogus` | Negative (click.Choice rejects) | `test_invalid_activate_choice_errors` |
| TC-A7 | `--enrollment-id abc` (non-int) | Negative (click type error) | `test_non_integer_enrollment_id_errors` |
| TC-A8a | `.edgerc` file missing entirely | Negative ("Unable to read edgerc file") | `test_missing_edgerc_file_exits` |
| TC-A8b | `.edgerc` file exists but `-s` section is absent | **Gap** — split out from the original single TC-A8. `init_config()`'s except/finally in `bin/akamai-onboard.py` raises a bare `UnboundLocalError`/`NameError` (`session`/`base_url` are never assigned before the `finally` block runs) instead of the intended "Edgerc section ... not found" message. `convert()`'s `except Exception` catches it and exits 0, so the CLI doesn't crash — it just prints a confusing, wrong-looking error. | `test_edgerc_missing_section_surfaces_nameerror_bug` |

## 3. CSV validation — `csv_validator_convert` (Local) — TC-B · 2 Positive / 3 Negative / 2 Gap

`tests/test_convert_csv_validation.py`

Schema: `hostname` required/non-empty; `propertyName`, `product`, `secureNetwork`, `AN`, `GroupID`, `orgId` optional; `edgeHostname` optional but if present must end in `.edgekey.net`/`.edgesuite.net`/`.akamaized.net`.

| ID | Scenario | Type | Test function |
|---|---|---|---|
| TC-B1 | Valid CSV, all optional columns present | Positive | `test_valid_csv_all_optional_columns_passes` |
| TC-B2 | Valid CSV, only `hostname` column | Positive | `test_valid_csv_hostname_only_passes` |
| TC-B3 | Row missing `hostname` value | Negative | `test_missing_hostname_value_errors` |
| TC-B4 | Row with `edgeHostname` not ending in valid suffix | Negative | `test_invalid_edgehostname_suffix_errors` |
| TC-B5 | CSV file path doesn't exist | Negative | `test_csv_path_not_found_errors` |
| TC-B6 | Empty CSV (headers only, no rows) | **Gap** — confirmed spec says clear error + exit; `cerberus_validator`'s row loop just never executes on zero rows, so `csv_validator_convert` returns `(True, [])` — no error at all. | `test_empty_csv_headers_only_is_a_gap_not_an_error` |
| TC-B7 | Duplicate `hostname` rows | **Gap** — confirmed spec says warn the user to fix the CSV; the cerberus schema has no uniqueness constraint, so duplicates validate cleanly with zero warning. | `test_duplicate_hostname_rows_currently_pass_silently` |

## 4. Directory / template validation — `json_input_file_validator` (Local) — TC-C · 2 Positive / 2 Negative

`tests/test_convert_directory_validation.py`

**Correction vs. the original plan draft:** template files are matched by *propertyName* (falling back to hostname when no propertyName is given), one JSON file per CSV row — **not** one JSON file per product as originally assumed. `csv_2_property_dict_convert` sets each row's `templateName` from `propertyName`; `json_input_file_validator` looks for `<templateName>.json` in `--directory`. A missing file for one row is also *not* fatal by itself inside `csv_2_property_array_convert` (it logs and `continue`s) — the actual hard-fail gate is `json_input_file_validator`, called from `validateSetupStepsConvert`.

| ID | Scenario | Type | Test function |
|---|---|---|---|
| TC-C1 | Directory has a `<propertyName>.json` for every CSV row | Positive | `test_directory_has_all_required_templates_passes` |
| TC-C2 | Directory missing a required row's template json | Negative | `test_directory_missing_a_template_errors` |
| TC-C3 | Directory path doesn't exist | Negative | `test_directory_path_not_found_errors` |
| TC-C4 | *(not in original plan)* Row has no `propertyName` at all → falls back to matching `<hostname>.json` | Positive | `test_falls_back_to_hostname_when_no_template_name` |

## 5. Flag interaction / logical validation (Local) — TC-D · 7 Positive / 11 Negative / 3 Gap

Split into four files by which real function owns the check (originally one file, `test_convert_flag_logic.py`, split for readability):

- **Group A** — `tests/test_convert_flag_constructor.py`: `onboard_convert.onboard()` constructor (pure, no I/O), edge_hostname_mode derivation.
- **Group B** — `tests/test_convert_flag_edgehostname.py`: `utility.csv_2_property_dict_convert()`, per-row edge hostname resolution.
- **Group C** — `tests/test_convert_flag_setup_validation.py`: `utility.validateSetupStepsConvert()` — GTM domain, activation ordering, email, confirm prompt. Composed with a real `onboard_convert.onboard()` + a small `StubWrapper` (answers `property_exists`/`getProductsByContract` locally) rather than a live PAPI wrapper.
- **Group D** — `tests/test_convert_flag_cli_guards.py`: the real `convert` CLI command, with the two network/shell seams (`check_cli_prereq`, `check_api_access`) monkeypatched out, so the early flag guards run exactly as a user would trigger them.

| ID | Scenario | Type | Test function(s) |
|---|---|---|---|
| TC-D1 | `--dryrun` without `--prefix` | Negative ("--dryrun requires --prefix") | `test_dryrun_without_prefix_errors` (Group D) |
| TC-D2 | `--prefix` without `--dryrun` | Negative ("--prefix is require under --dryrun mode") | `test_prefix_without_dryrun_errors` (Group D) |
| TC-D3 | `--dryrun --prefix foo` | **Gap** — the original plan assumed this generates synthetic hostnames/property names. It doesn't: `akamai-onboard.py:249-257` builds them, but the very next block (`:259-268`) unconditionally rebuilds `csv_dict` from the *original* CSV rows again, regardless of dryrun, overwriting the synthetic values before anything downstream sees them. `--dryrun` currently only skips the "must supply --prefix" guard — nothing else. Also found in passing: that dead block still indexes `product`/`GroupID` unconditionally, so a CSV with just a `hostname` column (valid per TC-B2) would crash it with an uncaught `KeyError` under `--dryrun`. | `test_dryrun_prefix_synthetic_names_are_dead_code` (Group D, via a spy that captures `csv_dict` and stops the run before deeper network calls) |
| TC-D4 | `--enrollment-id 12345` without `--cert-mode CPS` | Negative (explicit sys.exit) | `test_enrollment_id_without_cps_errors` (Group D, real check); `test_enrollment_id_without_cps_is_checked_in_convert_not_constructor` (Group A, pins down that the constructor alone doesn't gate it) |
| TC-D5 | `--cert-mode CPS --enrollment-id 12345` | Positive → mode `create_cps_edgehostname` | `test_cps_with_enrollment_id_selects_create_cps_mode` (Group A) |
| TC-D6 | `--cert-mode CPS --enrollment-id 12345 --use-existing-edgehostname CSV` | **Gap, skipped** — confirmed spec: warn about the redundant flags, state it's proceeding with `use_existing_edgehostname` mode, prompt to confirm (or skip prompt under `--force`). Code does none of this (`bin/onboard_convert.py:64-67`, silent). Not implemented, so nothing to characterize yet — see "Open questions." | `test_use_existing_ehn_with_cps_enrollment_warns_and_confirms` (Group A, `@pytest.mark.skip`) |
| TC-D7 | `--activate production` (no `staging`) | Negative | `test_activate_production_without_staging_errors` (Group C) |
| TC-D8 | `--activate staging --activate production` | Positive | `test_activate_staging_then_production_passes` (Group C) |
| TC-D9 | `--activate staging` with no `--email` (default `noreply@akamai.com`) | Positive | `test_activate_staging_default_email_passes` (Group C) |
| TC-D10 | `--activate staging --email not-an-email` | Negative | `test_activate_staging_invalid_email_errors` (Group C) |
| TC-D11 | `--activate staging --email ''` | Negative | `test_activate_staging_empty_email_errors` (Group C) |
| TC-D12 | `--use-cpcode abc` (non-numeric) | Negative (`int()` conversion error) | *(not yet built — straightforward, deferred; not exercised by any current group)* |
| TC-D13 | `--use-existing-edgehostname` (bare flag, no value) → `CSV`, CSV has `edgeHostname` column | Positive | `test_bare_use_existing_ehn_flag_selects_csv_mode` (Group A, mode selection); `test_csv_mode_with_edgehostname_column_uses_csv_values` (Group B, pipeline effect) |
| TC-D14 | `--use-existing-edgehostname CSV` but CSV has no `edgeHostname` column | Negative | `test_csv_mode_missing_edgehostname_column_errors` (Group B) |
| TC-D15 | `--use-existing-edgehostname my.edgekey.net` (explicit single EHN) | **Gap** — the original plan assumed Positive. It isn't: `akamai-onboard.py:265` only copies a row's `edgeHostname` into the working dict when the flag's value is literally the string `'CSV'`. For any other explicit name, that condition is always False, so the name is stored on the onboard object but never applied anywhere. Since `edge_hostname_mode` is still `use_existing_edgehostname`, every such run hits the same "edgeHostname column must exist" exit as TC-D14. **This means passing an explicit single edge hostname name currently never works.** | `test_explicit_ehn_name_also_selects_use_existing_mode` (Group A, mode selection); `test_explicit_ehn_name_is_never_actually_applied` (Group B, characterizes the bug) |
| TC-D16 | `--gtm-domain foo` (missing `.akadns.net` suffix) | Negative | `test_gtm_domain_missing_suffix_errors` (Group C) |
| TC-D17 | `--gtm-domain -foo.akadns.net` (leading hyphen) | Negative | `test_gtm_domain_leading_hyphen_errors` (Group C) |
| TC-D18 | `--gtm-domain foo.akadns.net`, templates contain gtm refs | Positive | `test_gtm_domain_with_gtm_refs_passes` (Group C) |
| TC-D19 | Templates contain gtm refs, no `--gtm-domain` given | **Reclassified from Negative to Positive (non-fatal, with a nuance).** The fallback-domain branch (`utility.py:489-492`) is the only branch in the whole GTM section that never does `count += 1` — so this logs an ERROR-level message ("No --gtm-domain input...") yet auto-recovers with a generated fallback domain and the run succeeds. The log level is arguably misleading (reads like a failure, isn't one); confirm whether that's intentional or worth a follow-up. | `test_missing_gtm_domain_with_refs_is_non_fatal` (Group C) |
| TC-D20 | `--force` suppresses the y/n confirmation prompt | Positive | `test_force_skips_confirmation_prompt` (Group C, asserts `input()` is never called) |
| TC-D21 | No `--force`, answer `no` at confirmation prompt | Negative (clean exit) | `test_declining_confirmation_without_force_exits_cleanly` (Group C) |

---

## 6. API-required — functional / end-to-end (integration tests, need real contract+group+creds) — TC-E · 15 Positive

Not built yet — needs §8's sandbox/teardown first. Every row creates real assets on the target contract/group.

| ID | Scenario | Type | Assets created |
|---|---|---|---|
| TC-E1 | Minimal happy path: SBD, STANDARD_TLS, no activation | Positive | property, cpcode, edge hostname, SBD cert |
| TC-E2 | `--network ENHANCED_TLS` → edgekey.net hostnames | Positive | + edgekey edge hostname |
| TC-E3 | `-p prd_SPM` overrides CSV `product` column for all rows | Positive | property, cpcode, edge hostname |
| TC-E4 | No `-p`, product taken per-row from CSV | Positive | property, cpcode, edge hostname (per product) |
| TC-E5 | `--use-cpcode <existing numeric id>` reused for all properties | Positive | property, edge hostname (no new cpcode) |
| TC-E6 | No `--use-cpcode`: cpcode searched by hostname, created if missing | Positive | property, **new cpcode (permanent, see §8)**, edge hostname |
| TC-E7 | Product `prd_Adaptive_Media_Delivery` + `--media-ehn VOD` | Positive | property, cpcode, VOD edge hostname |
| TC-E8 | Product `prd_Adaptive_Media_Delivery` + `--media-ehn LIVE` | Positive | property, cpcode, LIVE edge hostname |
| TC-E9 | Product `prd_Site_Accel` (DSA ruletree conversion path) | Positive | property, cpcode, edge hostname |
| TC-E10 | `--activate staging` → property activates, xlsx shows staging status | Positive | + **staging activation** |
| TC-E11 | `--activate staging --activate production` → both activate in sequence | Positive | + **staging & production activation** |
| TC-E12 | `--rule-format` pinned to a frozen version vs `latest` | Positive | property |
| TC-E13 | `--no-launch` suppresses auto-open of Excel (useful for CI) | Positive | property, cpcode, edge hostname |
| TC-E14 | Multiple `--email a@x.com --email b@x.com` | Positive | property (activation notification only, no extra asset) |
| TC-E15 | Multi-row CSV, mixed products, mixed hostnames, one combined run | Positive | multiple properties/cpcodes/edge hostnames |

## 7. API-required — error/edge scenarios (integration tests) — TC-F · 1 Positive / 9 Negative

Not built yet.

| ID | Scenario | Type |
|---|---|---|
| TC-F1 | Property name in CSV already exists on account | Negative ("invalid property name; already in use") |
| TC-F2 | Invalid `--product` for the given `--contract` (not entitled) | Negative |
| TC-F3 | SBD quota exhausted (`x-limit-default-certs-per-contract-remaining` < needed) | Negative |
| TC-F4 | SBD cert provisioning returns 403 (still provisioning) | Negative |
| TC-F5 | SBD returns 429 (rate limited) | Negative |
| TC-F6 | Invalid `--enrollment-id` (doesn't exist in CPS) | Negative |
| TC-F7 | Hostname with invalid characters (CSV) | Negative |
| TC-F8 | Hostname starts/ends with hyphen (CSV) | Negative |
| TC-F9 | One property activation fails to staging, others succeed → partial success handling | Positive (partial success) — confirmed acceptable, but the run must clearly log which properties succeeded vs. failed |
| TC-F10 | Staging activation fails → production activation must be skipped entirely | Negative — confirmed |

Note: TC-F1, F9, F10 leave behind a real (possibly partially activated) property even though the test itself is "negative" — they still need teardown per §8.

---

## 8. Test environment: setup & teardown for §6/§7 (integration tests, not started)

This repo has no built-in "delete property/cpcode/edge hostname" command today (`appsec-remove` only removes hostnames from a WAF config, it doesn't touch PAPI assets), so teardown for TC-E/TC-F has to be handled by a new helper outside `onboard convert` itself. Akamai's own constraints on what's actually deletable:

- **Properties**: deletable via PAPI (`DELETE /papi/v1/properties/{propertyId}`) only while never activated, or after being **deactivated** from every network first.
- **CP Codes**: Akamai does not expose a delete API for cpcodes — once created they're permanent.
- **Edge hostnames**: deletable via PAPI only if not referenced by any active property — must be deleted *after* the owning property is deactivated/deleted, not before.
- **SBD certs**: provisioned automatically alongside the edge hostname; nothing to clean up separately.
- **CPS enrollments**: reference a pre-existing test enrollment for TC-D5/E-equivalent CPS cases rather than creating new ones.

### Confirmed setup

- **Sandbox contract + group** will be provided as part of test environment setup — no action needed from us to source one.
- **Cpcode leakage from TC-E6 is acceptable** (one permanent cpcode per full suite run) — no need to mock/simulate that case to avoid it.
- **A run-scoped naming prefix** (reuse the existing `--prefix` convention) so every hostname/property created by a run is identifiable for cleanup, e.g. `tc-e1-<timestamp>-www.example.com`. Note: this is unrelated to `--dryrun`'s broken `--prefix` handling (TC-D3) — TC-E/F runs are real, non-dryrun runs that would need their *own* naming discipline applied via the CSV/property names directly, since `--dryrun --prefix` doesn't actually do anything today.
- A **fixed, reusable test cpcode** via `--use-cpcode` for every TC-E/F case except TC-E6 (which must exercise cpcode creation) — keeps the suite from creating cpcodes it doesn't need to.
- **A manifest of created asset IDs** (property ID, edge hostname ID, cpcode ID, activation IDs) written per test run to a JSON file, so cleanup doesn't depend on parsing the xlsx output.

### Confirmed teardown behavior

- **Teardown always runs** if any assets were created during a test, regardless of whether that test was expected to pass or fail (so TC-F1/F9/F10 get cleaned up too).
- **Teardown logic, in order**:
  1. Check whether the property is active on any network.
  2. If active: deactivate staging first, then production (if applicable), polling until each deactivation completes.
  3. Delete the property.
  4. Delete the edge hostname (only possible once the property is gone).
  5. Leave the cpcode alone (not deletable via API — expected and accepted, per above).
- This will be implemented as a Python script reusing the existing `wrapper_object`/PAPI calls already in `bin/utility_papi.py`. Not built yet.

---

## 9. Local test suite — what was built

```
pyproject.toml            # pytest added under [dependency-groups] dev; [tool.pytest.ini_options]
                           # sets pythonpath=["bin"], testpaths=["tests"]
tests/
  conftest.py                            # shared fixtures (see below)
  test_convert_cli_parsing.py            # TC-A (9 tests)
  test_convert_csv_validation.py         # TC-B (7 tests)
  test_convert_directory_validation.py   # TC-C (4 tests)
  test_convert_flag_constructor.py       # TC-D Group A (5 tests + 1 skip)
  test_convert_flag_edgehostname.py      # TC-D Group B (3 tests)
  test_convert_flag_setup_validation.py  # TC-D Group C (11 tests)
  test_convert_flag_cli_guards.py        # TC-D Group D (4 tests)
```

`test_convert_flag_logic.py` was the original single file for all of TC-D; split into the
four Group files above for readability once it grew past ~340 lines covering four
unrelated real functions.

42 passed, 1 skipped (`TC-D6`), 0 failed. All pre-commit hooks (reorder-python-imports,
pyupgrade, flake8) pass on all files. Function names across the whole suite dropped
their `test_tc_<id>_...` / `test_<id>_...` prefixes (e.g. `test_help_shows_all_options`,
not `test_a1_help_shows_all_options`) — the ID-to-function mapping now lives only in
this doc's tables, not in the name itself.

**Key fixtures in `conftest.py`:**
- `runner` / `cli` — `CliRunner` + the `convert` command, loaded via `importlib` since `bin/akamai-onboard.py`'s hyphenated filename can't be `import`-ed normally.
- `click_args_factory` — full default kwargs dict mirroring `convert`'s click options, override only what a test cares about.
- `config_stub` — stand-in for click's `Config` object.
- `csv_factory` / `headers_only_csv_factory` — write CSV fixtures under `tmp_path`.
- `template_dir_factory` — write ruletree template JSON files named after property/hostname.
- `fake_edgerc` — a syntactically valid `.edgerc` with a real `[onboard]` section (no network call happens just from reading it).
- `build_onboard_object` — builds a real `onboard_convert.onboard()` and fills in the fields that CSV/directory processing would normally have populated upstream, so Group-C tests can call `validateSetupStepsConvert` directly.
- `stub_wrapper_factory` (`StubWrapper`) — answers `property_exists()`/`getProductsByContract()` locally instead of hitting PAPI, so `validateSetupStepsConvert` can run hermetically.
- `util` / `_disable_akamai_cli_prereq_check` (autouse) — shared across every file that needs a real `utility.utility()` instance; promoted to `conftest.py` during the 4-way flag-logic split since three of the four new files needed both (previously duplicated per-file).

**Two other things the harness had to work around, not because of test design but because of how the app itself is built:**
- `utility.utility()`'s constructor shells out to check the real `akamai` CLI is installed (`validate_prerequisite_cli`) and `sys.exit()`s if not — patched to a no-op, autouse, in `conftest.py`, otherwise the suite would silently depend on the `akamai` binary being on PATH.
- `exceptions.py`'s `setup_logger()` calls `logging.config.dictConfig` without importing the `logging.config` submodule itself; it only works in the real app because `bin/akamai-onboard.py` happens to import it first. `conftest.py` imports it explicitly so `utility.py`/`onboard_convert.py` can be imported standalone in tests. Also: `setup_logger()` creates `logs/`/`config/` directories as a side effect of being imported at all — `conftest.py` `chdir`s the whole test process into a scratch tmp dir at collection time so this doesn't litter the repo.

**Deliberately not built:** TC-D12 (`--use-cpcode abc` non-numeric) — straightforward, low-risk, deferred for time; nothing discovered about it worth flagging.

---

## Open questions

1. **TC-D6** (warn+confirm for the CPS/enrollment + `--use-existing-edgehostname` combo) is a confirmed spec but not implemented. Want this filed as a separate implementation task before the test is written for real, or should it stay `skip`ped for now?
2. **Five discovered gaps/bugs now have characterization tests** (TC-A8b, TC-B6, TC-B7, TC-D3, TC-D15) plus one reclassified nuance (TC-D19). None of these were flagged in the original plan — they only surfaced from tracing the actual code while writing tests. Do you want these filed as bug tickets, or is this doc sufficient tracking for now? The most consequential one is probably **TC-D15**: `--use-existing-edgehostname <name>` (an explicit single edge hostname, as opposed to bare-flag/`CSV` mode) appears to never work at all as coded.
3. TC-D12 wasn't built — want it added before moving to §6/§7, or is the current coverage enough to call the Local suite done?
4. Ready to start on §8 (sandbox/teardown) and the TC-E/F integration suite whenever the sandbox contract/group is available — nothing else is blocking that.
