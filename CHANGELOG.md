# RELEASE NOTES

## 2.4.0

#### ENHANCEMENTS/BUG FIXES:

- New command: `appsec-remove`
- `appsec-update` improve logging messages
- Bump minimum python version to 3.12

## 2.3.5

#### BUG FIXES:

- Update origin behavior template to [match Jun 12 2024 release](https://techdocs.akamai.com/property-mgr/changelog)
- Display API creation error but not visible on the UI
- Fix script error when create property using fixed ruleformat (ie. vYYYY-MM-DD)

## 2.3.6

#### BUG FIXES:

- appsec-create fail on brand new group without any config
- appsec-create version/activation note is empty

## 2.3.7

#### ENHANCEMENTS:

- Replaced `cerberus` with `jsonschema`
- Upgraded `pandas` to version `2.2.2`
