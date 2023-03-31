# RELEASE NOTES

## 2.2.0

#### FEATURES/ENHANCEMENTS:

- Support multi-hosts command to add multiple hostnames and respective origin to the delivery/property configuration and include all of those hostnames into the new security configuration
  - The command requires a new input file in a CSV format
  - Support three standard akamai product: prd_SPM, prd_Fresca, prd_API_Accel

#### MISC:

- Allow short arguments i.e. both --file and -f will work
- Rename sample setup files that are easier to identify for each command
- Display proper version for --version and -h command
