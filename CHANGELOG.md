# RELEASE NOTES

<!-- Format: new entries use separate "#### ENHANCEMENTS:" and "#### BUG FIXES:"
     headings (omit whichever has no items). Historical entries below that use
     a different heading are left as originally written. -->

## 2.5.3

#### ENHANCEMENTS:

- New command: `sbd-precheck`, `sbd-status`, `convert`
- Update Ion Premier and Ion Standard Template
- Rename `iteractive_mode` to `force_mode` for clarity
- Rename `ASK` to `account_switch_key` for clarity
- Simplify internal logic for handling edge hostname modes (no behavior change)
- Extract shared CP code result-logging helper
- Default `--section` to `default` (matching a stock `.edgerc`) instead of `onboard`
- Drop the `uliplot` dependency (vendored the one function used, `auto_adjust_xlsx_column_width`, into `xlsx_util.py`) - `uliplot` pulled in `matplotlib`/`Pillow` for unrelated plotting helpers this CLI never used, which noticeably slowed the first run after a fresh install

- Logging improvements
  - log file now appends (mode: "a") instead of overwriting each run
  - detailed API response bodies now captured in logs/onboard.log only, not shown in CLI output
  - API response dumps (edge hostname creation, cpcode operations, hostname updates) moved from ERROR to DEBUG level
  - Switch console logging from `coloredlogs` to `rich` (`RichHandler`)
  - drops the `WARNING:`/`INFO:` level prefix
  - adds a right-aligned source `file.py:line` tag; file log (`logs/onboard.log`) format is unchanged

#### BUG FIXES:

- wrapper_api.py - better error handling
- utility_papi.py - better error handling
- utility.py - better error handling
- Fix UTF-8 encoding on Windows to prevent Unicode errors and CI build failures
- Fix crash (`cannot access local variable 'session'`) that masked the real "Edgerc section ... not found" error
- Fix `appsec-remove` crash (`ValueError: too many values to unpack`) from `init_config()` return value mismatch
- Fix pandas `FutureWarning` on `fillna` to use `fillna('').infer_objects(copy=False)` per pandas' own guidance)
- Fix `cli-onboard` so it's installable via `pip install -e .` / `uv tool install -e .` (adds a `cli_entry` console-script shim and setuptools packaging config so flat-layout auto-discovery doesn't break)
- Fix the `sync-readme-commands` pre-commit hook to sanitize ANSI escape codes and handle the square-cornered box style Rich falls back to on non-VT Windows consoles (e.g. GitHub Actions' `windows-latest` runners), which was failing CI

## 2.4.0

#### ENHANCEMENTS/BUG FIXES:

- New command: `appsec-remove`
- `appsec-update` improve logging messages
- Bump minimum python version to 3.12

## 2.3.7

#### ENHANCEMENTS:

- Replaced `cerberus` with `jsonschema`
- Upgraded `pandas` to version `2.2.2`

## 2.3.6

#### BUG FIXES:

- appsec-create fail on brand new group without any config
- appsec-create version/activation note is empty

## 2.3.5

#### BUG FIXES:

- Update origin behavior template to [match Jun 12 2024 release](https://techdocs.akamai.com/property-mgr/changelog)
- Display API creation error but not visible on the UI
- Fix script error when create property using fixed ruleformat (ie. vYYYY-MM-DD)
