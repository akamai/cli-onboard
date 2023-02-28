# cli-onboard

Provides a way to onboard a new Akamai Property Manager configuration using any flexible user-defined setup. You can include any desired settings (subject to authorization and entitlements) such as:

- Any property mangager configuration json rule template
- Standard TLS or Enhanced TLS Network
- Use new or existing SSL Certificates and Edge Hostnames
- Include in existing WAF configurations (Add Selected Hosts and/or Match Targets)
- Flexible activation to staging or production network

## Akamai CLI Install

```bash
%  akamai install onboard
%  akamai install property-manager (if not already installed)
```

## Local Install

- Python 3+
- pip install edgegrid-python
- User should also have [cli-property-manager](https://github.com/akamai/cli-property-manager) installed

## Credentials

In order to use this module, you need to:

- Set up your credentials in your .edgerc file
- The default section used in your configuration file should be called 'onboard'. If you wish to override, you may also use the --section <name> to use the specific section credentials from your .edgerc file
- Your API credential should include at least the following grants:
  - Property Manager (/papi)
  - Edge Hostnames API (/hapi)
  - Certificate Provisioning System (/cps)
  - Application Security (/appsec)

```
[onboard]
client_secret = [CLIENT_SECRET]
host = [HOST]
access_token = [ACCESS_TOKEN_HERE]
client_token = [CLIENT_TOKEN_HERE]
```

# Onboard Types

This CLI has 2 command types for onboarding new properties:

- [create](#create)
- [single-host](#single-host)

# create

## Example Usage

```bash
akamai onboard create --file /templates/sample_setup_files/setup.json
akamai onboard create --file ~/path/to/setup.json
```

## Setup JSON File Documentation

Sample **templates/sample_setup_files/setup.json** for an initial empty setup file.

<details>
    <summary>Click me</summary>

```JSON
{
"property_info": {
    "property_name": "",
    "secure_network": "STANDARD_TLS",
    "contract_id": "ctr_",
    "group_id": "grp_",
    "product_id": "prd_",
    "version_notes": "",
    "rule_format": "latest",
    "default_cpcode": {
        "create_new_cpcode": false,
        "new_cpcode_name": ""

    },
    "file_info": {
        "use_file": false,
        "source_template_file": "",
        "source_values_file": ""
    },
    "folder_info": {
        "use_folder": false,
        "folder_path": "",
        "env_name": ""
    }
},
"public_hostnames": [
    ""
],
"edge_hostname": {
    "mode": "new_standard_tls_edgehostname",
    "use_existing_edgehostname": {
        "edge_hostname": ""
    },
    "new_standard_tls_edgehostname": {},
    "new_enhanced_tls_edgehostname": {
        "ssl_cert_info": {
            "use_existing_enrollment_id": false,
            "existing_enrollment_id": 0,
            "create_new_ssl_cert": false,
            "ssl_cert_template_file": "",
            "ssl_cert_template_values": "",
            "temp_existing_edge_hostname": ""

        }
    },
    "secure_by_default": {
        "create_new_edge_hostnames": false,
        "use_existing_edge_hostname": ""
    }
},
"activate_property_staging": false,
"update_waf_info": {
    "add_selected_host": false,
    "waf_config_name": "",
    "update_match_target": false,
    "waf_match_target_id": 0
},
"activate_waf_policy_staging": false,
"activate_property_production": false,
"activate_waf_policy_production": false,
"notification_emails": [
    ""
]
}

```

</details>

## Field Descriptions

<details>
    <summary>Show me</summary>

- property_name: Name of the property manager configuration to be created
- secure_network: Use either ENHANCED_TLS or STANDARD_TLS
- contract*id: Contract ID (starts with ctr*)
- group*id: Group ID (starts with grp*)
- product*id: Product ID (usually starts with prd* and should be one of available products from specified contract_id)
- rule_format: Rule format (typically latest, but can you frozen rule format if desired)

**default_cpcode**

- create_new_cpcode: Specify true if you want a brand new cp code created as part of the new property manager configuration
- new_cpcode_name: If create_new_cpcode is true, specify name of new cp code

**file_info**

- use_file: Specify true if you want to use a single file json template
- source_template_file: File path to single file json template. This file can have ${env.variable} references to serve place holders that will be substitued from values in source_values_file
- source_values_file: File path to the single file variable values. This source values file can look like this:

```bash
{
	"origin_default": "origin-www.dummy.com",
	"cpcode_default": 12345
}
```

**folder_info**

- use_folder: Specify true if you want to use an existing Akamai pipeline folder structure. This folder should contain the projectInfo.json and environments folder
- folder_path: File path to the Akamai pipeline folder
- env_name: Environment name to build. This name should be defined in projectInfo.json and have corrent setting and variable values in environments folder

**public_hostnames**

- Array of property hostnames in this new configuration

**edge_hostname**

- For a new property manager configuration, we can use an existing edge hostname, create a new standard_tls edge hostname, or create a new enhanced_tls edge hostname
- mode: Should be one of: use_existing_edgehostname, new_standard_tls_edgehostname, new_enhanced_tls_edgehostname

**use_existing_edgehostname**

- edge_hostname: Specify the existing edge hostname to use. If using ENHANCED_TLS, this should end with edgekey.net ; otherwise if using STANDARD_TLS, this should end with edgesuite.net

**new_enhanced_tls_edgehostname -- use existing enrollment**

- use_existing_enrollment_id: Set to true if you want to create a new edge hostname from an existing certificate enrollment. If true, you must also put in values for the existing_enrollment_id.
- existing_enrollment_id: Enrollment ID of the existing certificate

**new_enhanced_tls_edgehostname -- create new enrollment**

- create_new_ssl_cert: Set to true if you want to brand new certificate enrollment. If true, you must also put in values for the ssl_cert_template_file, ssl_cert_template_values, and use_temp_existing_edge_hostname_id (NOT USED ANYMORE)
- ssl_cert_template_file: File path to ssl certificate template json file. This can be for any certificate type (NOT USED ANYMORE)
- ssl_cert_template_values: Values for the ssl certificate template to be used (NOT USED ANYMORE)
- temp_existing_edge_hostname: Due to backend api limitations, a new edge hostname cannot be immediately made that references a newly created certificate enrollment for a brief period of time. Rather than be blocked by this process, specify a temporary edge hostname to use as a placeholder. This value is not really used and just a place holder to proceed with the property manager configuration creation. If using ENHANCED_TLS, use an existing edge hostname ends with edgekey.net ; otherwise if using STANDARD_TLS, use an existing edge hostname that ends with edgesuite.net (NOT USED ANYMORE)

**secure_by_default -- provision secure by default certificates**
- create_new_edge_hostnames: set to true if you want a new unique edge hostname created for each onboarded hostname. The edge hostnames created will be in the form {hostname}.edgekey.net
- use_existing_edge_hostname: add an existing edge hostname to use - it must be SNI. All Secure by Default certificates are SNI.

**update_waf_info**

- add_selected_host: Set to true if you want to add specified public_hostnames to WAF selected hosts
- waf_config-name: Name of security configuration
- update_match_target: Set to true if you wwant to add specified public_hostnames to specifed waf_match_target_id
- waf_match_target_id: waf match target id to add hostnames to (use numeric waf match target id)
- NOTE: If you do not know the match target id, leave the value as 0 and execute the onboarding. The validation steps will print out the existing match target IDs for the WAF config selected.
- NOTE: These settings can only happen if property manager configuration is activated to Akamai staging

**activate settings**

- activate_property_staging: Activate property manager configuration to staging network
- activate_property_production: Activate property manager configuration to production network (must go through staging first)
- activate_waf_policy_staging: Activate security configuration to staging network
- activate_waf_policy_production: Activate security configuration to production network (must go through staging first)
- notification_emails: Array of emails to be notified after activations
</details>

<br/><br/>

# single-host

### Example Usage

```bash
akamai onboard single-host --file /templates/sample_setup_files/setup_single_host.json
akamai onboard single-host --file ~/path/to/setup_single_host.json
```

```bash
{
    "property_info": {
        "contract_id": "ctr_",
        "product_id": "prd_",
        "property_hostname": "",
        "property_origin": ""
    },
    "edge_hostname": {
        "secure_by_default": true,
        "use_existing_edge_hostname": "",
        "create_from_existing_enrollment_id": 0
    },
    "update_waf_info": {
        "create_new_security_config": true,
        "waf_config_name": ""
    },
    "activate_production": false,
    "notification_emails": [
        ""
    ]
}
```

### Field Descriptions

<details>
    <summary>Show me</summary>

- contract*id: Contract ID (starts with ctr*)
- product_id: Product ID: one of prd_SPM, prd_Fresca, prd_API_Accel (case sensitive)
- property_hostname: Public facing hostname
- property_origin: Origin hostname for property_hostname
- activate_production: Activate to Akamai production network (will always update to Akamai staging already)
- notification_emails: Array of emails to be notified after activations

---

**edge_hostname**

- secure_by_default: set to true if you want to provision a default certificate for the hostname. This will automatically create a new edge hostname.
- use_existing_edge_hostname: specify existing edge hostname to use (must already exist). Will not be used if 'secure_by_default' is set to true.
- create_from_existing_enrollment_id: create new edge hostname from existing certificate enrollment id (must already exist)

---

**update_waf_info**

- create_new_security_config: true = will create default security configuration in alert mode
- waf_config_name: name of new security config to be created (if blank, will use default "WAF Security File" as name
</details>

<br></br>

# Contribution

By submitting a contribution (the “Contribution”) to this project, and for good and valuable consideration, the receipt and sufficiency of which are hereby acknowledged, you (the “Assignor”) irrevocably convey, transfer, and assign the Contribution to the owner of the repository (the “Assignee”), and the Assignee hereby accepts, all of your right, title, and interest in and to the Contribution along with all associated copyrights, copyright registrations, and/or applications for registration and all issuances, extensions and renewals thereof (collectively, the “Assigned Copyrights”). You also assign all of your rights of any kind whatsoever accruing under the Assigned Copyrights provided by applicable law of any jurisdiction, by international treaties and conventions and otherwise throughout the world.

# Notice

Copyright 2020 – Akamai Technologies, Inc.

All works contained in this repository, excepting those explicitly otherwise labeled, are the property of Akamai Technologies, Inc.
