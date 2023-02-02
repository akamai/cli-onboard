# RELEASE NOTES

## 2.0.0 (February 3, 2023)

#### FEATURES/ENHANCEMENTS:

* Support single-host command for autommatic new single hostname property and security onboarding
  * Ex: akamai onboard single-host --file <setup_file.json>
  * uses simpler setup_single_host.json format
  * supports standard Akamai product ids: prd_SPM, prd_Fresca, prd_API_Accel
  * activates property manager and default security to Akamai staging and/or production automatically
* Allow for custom version_notes in setup.json files
* Enhanced logging and setup file validation improvements

#### MISC:

* Remove support for new_enhanced_tls_edgehostname and create_new_ssl_cert: true
  * use new_enhanced_tls_edgehostname and use_existing_enrollment_id: true instead

#### BUG FIXES:

* Fix sample provided templates with no cpcode behavior in default rule ([#19](https://github.com/akamai/cli-onboard/issues/19))
