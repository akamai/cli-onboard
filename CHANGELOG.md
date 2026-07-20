# RELEASE NOTES

<!-- Format: new entries use separate "#### ENHANCEMENTS:" and "#### BUG FIXES:"
     headings (omit whichever has no items). Historical entries below that use
     a different heading are left as originally written. -->

## 2.5.2

#### ENHANCEMENTS:

- New command: `sbd-precheck`, `sbd-status`, `convert`
- Update Ion Premier and Ion Standard Template
- Rename `iteractive_mode` to `force_mode` for clarity
- Rename `ASK` to `account_switch_key` for clarity
- Simplify internal logic for handling edge hostname modes (no behavior change)
- Extract shared CP code result-logging helper
- Default `--section` to `default` (matching a stock `.edgerc`) instead of `onboard`
- Switch console logging from `coloredlogs` to `rich` (`RichHandler`): drops the `WARNING:`/`INFO:` level prefix, adds a right-aligned source `file.py:line` tag; file log (`logs/onboard.log`) format is unchanged

#### BUG FIXES:

- Fix UTF-8 encoding on Windows to prevent Unicode errors and CI build failures
- Fix crash (`cannot access local variable 'session'`) that masked the real "Edgerc section ... not found" error
- Fix `appsec-remove` crash (`ValueError: too many values to unpack`) from `init_config()` return value mismatch

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
