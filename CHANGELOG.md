# RELEASE NOTES

<!-- Format: new entries use separate "#### ENHANCEMENTS:" and "#### BUG FIXES:"
     headings (omit whichever has no items). Historical entries below that use
     a different heading are left as originally written. -->

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Each release is grouped into two sections:

- **ENHANCEMENTS** — new features or improvements to existing behavior
- **BUG FIXES** — bug fixes

---

## [v2.5.5] - 2026-08-17

#### ENHANCEMENTS:

- `convert`'s Excel report labels rows submitted under `--no-wait`
- `convert`'s Excel report now shows which CP Code was used per hostname and flags any hostnames that were skipped
- Add `--no-wait` to `single-host`, `multi-hosts`, `convert`, `batch-create`, and the AppSec commands: submit production activation and return immediately instead of waiting for it to finish
- Add `--preview` to `convert`: see exactly what a run would create before anything touches Akamai for real
- Add `--prune-hostname-rules` to `convert`: drops rules for hostnames not in this run's CSV so each property only keeps its own rules
- Add `--unique-cpcode` to `convert`: each hostname can get its own CP Code instead of sharing one for the whole property
- Add security vulnerability checks — `uv audit` (dependency vulnerabilities), `bandit` (static analysis, medium+ severity), and `gitleaks` (secret scanning) — enforced locally via pre-commit and in CI (`.github/workflows/security.yml`)
- New `check-activation` command checks on activation(s) submitted earlier with `--no-wait`; add `--wait` to keep polling until every activation finishes

#### BUG FIXES:

- `appsec-create --activate production` now actually activates to the production network — it was silently activating to staging twice instead
- `batch-create`'s WAF production activation now fires correctly instead of silently never running, even when delivery activation to production succeeded
- `check-activation` now works with minimal, hand-built CSVs, not just ones produced by a prior `--no-wait` run
- Bump vulnerable `setuptools`/`urllib3`/`aiohttp`/`cryptography`/`idna`/`pyasn1` versions flagged by `uv audit`
- Fall back to the package's own install location instead of the current working directory when locating the CLI's root directory
- Fix command injection risk in `akamai pm ...` shell-outs (`akamai-onboard.py`, `utility.py`, `wrapper_api.py`) — run with argument list and `shell=False` instead of a shell string

## [v2.5.4] - 2026-08-04

#### ENHANCEMENTS:

- `convert` precheck now prints the account's actual valid groups/contracts as a colorful `rich` table
- Add `--log-level`/`--debug`/`--verbose` flags to the `cli` group and every subcommand
- Drop `config/logging.json` and the path-hunting logic that located and copied it
- Logging config is now a plain Python dict in `exceptions.py`, applied once at the real entry point instead of once per module
- Table shows when `--group`/`--contract`/a csv `GroupID` doesn't validate, mirroring `akamai pm list-groups`/`list-contracts`
- Verbosity can be set globally (`cli-onboard --debug convert ...`) or per-subcommand; most-verbose-wins if both are set

#### BUG FIXES:

- `--contract` was never actually checked against the account's real contracts; now validated directly
- `--group`/`--contract` are commonly passed unprefixed, so the literal comparison rejected valid ones and left listings empty
- `convert` precheck never validated `--group` or a csv `GroupID` against the account's real groups
- `convert` precheck's `--contract` line was echoed as "valid" whenever the product lookup happened to succeed
- An invalid group only surfaced later as a raw API failure mid-run; it's now checked up front, same as `--product`
- Fixed a prefix mismatch: PAPI returns group/contract IDs with their `grp_`/`ctr_` prefix
- Replace deprecated `os.system()` calls with `subprocess.run()` in `akamai-onboard.py`, `utility.py`, `wrapper_api.py`

## [v2.5.3] - 2026-07-31

#### ENHANCEMENTS:

- Default `--section` to `default` (matching a stock `.edgerc`) instead of `onboard`
- Drop the `uliplot` dependency (vendored the one function used, `auto_adjust_xlsx_column_width`, into `xlsx_util.py`) - `uliplot` pulled in `matplotlib`/`Pillow` for unrelated plotting helpers this CLI never used, which noticeably slowed the first run after a fresh install
- Extract shared CP code result-logging helper
- New command: `sbd-precheck`, `sbd-status`, `convert`
- Rename `ASK` to `account_switch_key` for clarity
- Rename `iteractive_mode` to `force_mode` for clarity
- Simplify internal logic for handling edge hostname modes (no behavior change)
- Update Ion Premier and Ion Standard Template

- Logging improvements
  - log file now appends (mode: "a") instead of overwriting each run
  - detailed API response bodies now captured in logs/onboard.log only, not shown in CLI output
  - API response dumps (edge hostname creation, cpcode operations, hostname updates) moved from ERROR to DEBUG level
  - Switch console logging from `coloredlogs` to `rich` (`RichHandler`)
  - drops the `WARNING:`/`INFO:` level prefix
  - adds a right-aligned source `file.py:line` tag; file log (`logs/onboard.log`) format is unchanged

#### BUG FIXES:

- Fix `appsec-remove` crash (`ValueError: too many values to unpack`) from `init_config()` return value mismatch
- Fix `cli-onboard` so it's installable via `pip install -e .` / `uv tool install -e .` (adds a `cli_entry` console-script shim and setuptools packaging config so flat-layout auto-discovery doesn't break)
- Fix crash (`cannot access local variable 'session'`) that masked the real "Edgerc section ... not found" error
- Fix pandas `FutureWarning` on `fillna` to use `fillna('').infer_objects(copy=False)` per pandas' own guidance)
- Fix the `sync-readme-commands` pre-commit hook to sanitize ANSI escape codes and handle the square-cornered box style Rich falls back to on non-VT Windows consoles (e.g. GitHub Actions' `windows-latest` runners), which was failing CI
- Fix UTF-8 encoding on Windows to prevent Unicode errors and CI build failures
- utility_papi.py - better error handling
- utility.py - better error handling
- wrapper_api.py - better error handling

## [v2.4.0] - 2025-02-06

#### ENHANCEMENTS/BUG FIXES:

- New command: `appsec-remove`
- `appsec-update` improve logging messages
- Bump minimum python version to 3.12

## [v2.3.7] - 2024-08-19

#### ENHANCEMENTS:

- Replaced `cerberus` with `jsonschema`
- Upgraded `pandas` to version `2.2.2`

## [v2.3.6] - 2024-07-25

#### BUG FIXES:

- appsec-create fail on brand new group without any config
- appsec-create version/activation note is empty

## [v2.3.5] - 2024-07-25

#### BUG FIXES:

- Update origin behavior template to [match Jun 12 2024 release](https://techdocs.akamai.com/property-mgr/changelog)
- Display API creation error but not visible on the UI
- Fix script error when create property using fixed ruleformat (ie. vYYYY-MM-DD)
