# cli-onboard

Provides a way to onboard a new Akamai Property Manager configuration using any flexible user-defined setup. You can include any desired settings (subject to authorization and entitlements) such as:

- Any property manager configuration json rule template
- Standard TLS or Enhanced TLS Network
- Use new or existing SSL Certificates and Edge Hostnames
- Include in existing WAF configurations (Add Selected Hosts and/or Match Targets)
- Flexible activation to staging or production network

## Prerequisites - Setup API Credentials

In order to use this module, you need to:

- Set up your credentials in your `.edgerc` file
- The default section used in your configuration file should be called `onboard`. If you wish to override, you may also use the `--section <section_name>` to use the specific section credentials from your `.edgerc` file
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

## Akamai Onboard CLI Install

```bash
%  akamai install onboard
%  akamai install property-manager (if not already installed)
```

# Onboard Types

This CLI has 4 command types for onboarding new properties:

- [create](#create)
- [single-host](#single-host)
- [multi-hosts](#multi-hosts)
- [batch-create](#batch-create)
- [fetch-sample-templates ](#fetch-sample-templates)

# create

## Example Usage

```bash
akamai onboard create --file /templates/sample_setup_files/create.json
akamai onboard create --file ~/path/to/create.json
```

## Setup JSON File Documentation

Sample **templates/sample_setup_files/create.json** for an initial empty setup file.

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

- **property_name**: Name of the property manager configuration to be created
- **secure_network**: Use either ENHANCED_TLS or STANDARD_TLS
- **contract_id**: Contract ID (starts with ctr\_)
- **group_id**: Group ID (starts with grp\_)
- **product_id**: Product ID (usually starts with prd\* and should be one of available products from specified contract_id)
- **rule_format**: Rule format (typically latest, but can you frozen rule format if desired)

**default_cpcode**

- **create_new_cpcode**: Specify true if you want a brand new cp code created as part of the new property manager configuration
- **new_cpcode_name**: If create_new_cpcode is true, specify name of new cp code

**file_info**

- **use_file**: Specify true if you want to use a single file json template
- **source_template_file**: File path to single file json template. This file can have `${env.variable}` references to serve place holders that will be substituted from values in source_values_file
- **source_values_file**: File path to the single file variable values. This source values file can look like this:

```bash
{
	"origin_default": "origin-www.dummy.com",
	"cpcode_default": 12345
}
```

**folder_info**

- **use_folder**: Specify true if you want to use an existing Akamai pipeline folder structure. This folder should contain the projectInfo.json and environments folder
- **folder_path**: File path to the Akamai pipeline folder
- **env_name**: Environment name to build. This name should be defined in `projectInfo.json` and have correct setting and variable values in environments folder

**public_hostnames**

- Array of property hostnames in this new configuration

**edge_hostname**

- For a new property manager configuration, we can use an existing edge hostname, create a new standard_tls edge hostname, or create a new enhanced_tls edge hostname
- **mode**: Should be one of: `use_existing_edgehostname, new_standard_tls_edgehostname, new_enhanced_tls_edgehostname, secure_by_default`

**use_existing_edgehostname**

- **edge_hostname**: Specify the existing edge hostname to use.
  - If using `ENHANCED_TLS`, this should end with `edgekey.net`
  - If using `STANDARD_TLS`, this should end with `edgesuite.net`

**new_enhanced_tls_edgehostname -- use existing enrollment**

- **use_existing_enrollment_id**: Set to `true` if you want to create a new edge hostname from an existing certificate enrollment. If true, you must also put in value for the existing_enrollment_id.
- **existing_enrollment_id**: Enrollment ID of the existing certificate

**new_enhanced_tls_edgehostname -- create new enrollment**

- **create_new_ssl_cert**: Set to `true` if you want to brand new certificate enrollment. If true, you must also put in values for the ssl_cert_template_file, ssl_cert_template_values, and use_temp_existing_edge_hostname_id **(NOT USED ANYMORE)**
- **ssl_cert_template_file**: File path to ssl certificate template json file. This can be for any certificate type (NOT USED ANYMORE)
- **ssl_cert_template_values**: Values for the ssl certificate template to be used **(NOT USED ANYMORE)**
- **temp_existing_edge_hostname**: Due to backend api limitations, a new edge hostname cannot be immediately made that references a newly created certificate enrollment for a brief period of time. Rather than be blocked by this process, specify a temporary edge hostname to use as a placeholder. This value is not really used and just a place holder to proceed with the property manager configuration creation. If using `ENHANCED_TLS`, use an existing edge hostname ends with `edgekey.net` ; otherwise if using `STANDARD_TLS`, use an existing edge hostname that ends with `edgesuite.net` **(NOT USED ANYMORE)**

**secure_by_default -- provision secure by default certificates**

- **create_new_edge_hostnames**: set to **true** if you want a new unique edge hostname created for each onboarded hostname. The edge hostnames created will be in the form `{hostname}.edgekey.net`
- **use_existing_edge_hostname**: add an existing edge hostname to use - it must be **SNI**. All Secure by Default certificates are `SNI`.

**update_waf_info**

- **add_selected_host**: Set to `true` if you want to add specified public_hostnames to WAF selected hosts
- **waf_config-name**: Name of security configuration
- **update_match_target**: Set to `true` if you want to add specified public_hostnames to specified waf_match_target_id
- **waf_match_target_id**: waf match target id to add hostnames to (use numeric waf match target id)
- NOTE: If you do not know the match target id, leave the value as `0` and execute the onboarding. The validation steps will print out the existing match target IDs for the WAF config selected.
- NOTE: These settings can only happen if property manager configuration is activated on the Akamai Staging network

**activate settings**

- **activate_property_staging**: Activate property manager configuration to `staging` network
- **activate_property_production**: Activate property manager configuration to `production` network (must go through staging first)
- **activate_waf_policy_staging**: Activate security configuration to `staging` network
- **activate_waf_policy_production**: Activate security configuration to `production` network (must go through staging first)
- **notification_emails**: Array of emails to be notified after activations
</details>

<br/><br/>

# single-host

### Description

single-host creates a property with one public hostname at the top level of the contract unless group_id is specified in the JSON file.

### Example Usage

```bash
akamai onboard single-host --file /templates/sample_setup_files/single.json
akamai onboard single-host --file ~/path/to/single.json
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
        "noreply@akamai.com"
    ]
}
```

### Field Descriptions

<details>
    <summary>Show me</summary>

- **contract_id**: Contract ID (starts with ctr\_)
- **product_id**: Product ID: one of `prd_SPM`, `prd_Fresca`,`prd_API_Accel` (case sensitive)
- **property_hostname**: Public facing hostname. This will be used as the name of the property.
- **property_origin**: Origin hostname for property_hostname
- **activate_production**: Activate to Akamai `production` network (single-mode will always activate property on the Akamai staging)
- **notification_emails**: Array of emails to be notified after activations

**Optional Values:**

- **group_id**: Group ID (starts with grp\_) If you do not have security at the contract/top level or you would like to put the property on a specify property group.
- **version_notes**: Allow you to override the default value `Initial Version`

**edge_hostname**

- **secure_by_default**: set to **true** if you want to provision a default certificate for the hostname. This will automatically create a new edge hostname.
- **use_existing_edge_hostname**: specify existing edge hostname to use (must already exist). Value will not be used if `secure_by_default` is set to `true`.
- **create_from_existing_enrollment_id**: create new edge hostname from existing certificate enrollment id (must already exist)

**update_waf_info**

- **create_new_security_config**:
  - set to `true` will create default security configuration in `alert` mode
  - set to `false` will not create a security configuration
- **waf_config_name**: name of new security config to be created. If `blank`, the default policy will be `WAF Security File`
</details>

<br></br>

# multi-hosts

### Example Usage

```bash
akamai onboard multi-hosts -f path-to/multiple.json --csv path-to/multi-hosts-input.csv
```

```bash
{
  "property_info": {
    "contract_id": "ctr_",
    "product_id": "prd_",
    "property_name": "",
    "individual_cpcode": false
  },
  "edge_hostname": {
    "secure_by_default": false,
    "use_existing_edge_hostname": "",
    "create_from_existing_enrollment_id": 0
  },
  "update_waf_info": {
    "create_new_security_config": true,
    "waf_config_name": ""
  },
  "activate_production": true,
  "notification_emails": ["noreply@akamai.com"]
}
```

### Field Descriptions

- **contract_id**: Contract ID (starts with **ctr\_**) You can get this information from Akamai Technical Project Manager
- **product_id**: Supported Product ID are **prd_SPM, prd_Fresca, prd_API_Accel** (case sensitive)
- **property_name**: Name of the property aka delivery configuration
- **individual_cpcode**: Set to **true** if you want to create cp code for each hostname
- The rest is the same as **single-host** mode

# batch-create

## Description

batch-create creates and optionally activates multi properties based on a custom json template and csv input file. It can add multiple hostnames and origin behaviors to a single property, or create multiple porperties.

## Example Usage

```bash
akamai onboard batch-create --template ~/path/to/ruletree.json --csv ~/path/to/csv.csv --product prd_SPM --group grp_1234 --contract ctr_1-2345

akamai onboard batch-create --template ~/path/to/ruletree.json --csv ~/path/to/csv.csv --product prd_SPM --group grp_1234 --contract ctr_1-2345 --secure-by-default

```

## CSV Input File Documentation

Sample **templates/sample_setup_files/batch-activation.csv** for an initial empty setup file.

<details>
    <summary>Click me</summary>

```CSV
hostname,origin,propertyName,forwardHostHeader,edgeHostname
www.example.com,origin.example.com,new_property_1,ORIGIN_HOSTNAME,www.example.com.edgekey.net
```

- **hostname**: [required] Hostname that you want to onboard
- **origin**: [required] Origin hostname
- **propertyName**: Name of property. If empty or column is missing, defaults to hostname.
- - If 2 rows have the same propertyName, the hostnames will be added to the same property and an origin behavior ruleset will be injected into the input template
- **forwardHostHeader**: Host header used on forward request to origin. Can be either `INCOMING_HOST_HEADER` or `ORIGIN_HOSTNAME`. If empty or column is missing, defaults to `INCOMING_HOST_HEADER`. This setting will override whatever is in the input template default origin behavior.
- **edgeHostname**: [required unless using secure_by_default] The edge hostname to map the hostname to. The edge hostname must already exist. batch-create mode `does NOT` create new edge hostnames unless secure-by-default mode is being used.

</details>

## Input Descriptions

<details>
    <summary>Show me</summary>

- **--template** **-t**: file path to single file json template. [required]
- **--csv**: csv file with headers hostname,origin,edgeHostname,forwardHostHeader,propertyName [required]
- **--network** **-n**: use either ENHANCED_TLS or STANDARD_TLS [default:ENHANCED_TLS]
- **--contract** **-c**: Contract ID (starts with ctr\_) [required]
- **--group** **-g**: Group ID (starts with grp\_) [required]
- **--product** **-p**: Product ID (usually starts with prd\* and should be one of available products from specified contract_id) [required]
- **--rule-format** **-f**: Rule format (typically latest, but can you frozen rule format if desired) [default:latest]
- **--use-cpcode**: Override creation of new cpcodes and use single cpcode for all properties
- **--secure-by-default**: Use secure by default certificates
- **--waf-config**: name of security configuration to update
- **--waf-match-target**: waf match target id to add hostnames to (use numeric waf match target id)
- **--activate**: Activation networks. If activating waf on a network, delivery must also be activated. Options: `delivery-staging`, `delivery-production`, `waf-staging`, `waf-production`
- **--email**: email(s) for activation notifications

</details>

<br/><br/>

# fetch-sample-templates

This will create a folder called `sample_setup_files` locally so you will have sample setups in both JSON and CSV format depending on the command you choose the onboard.

# Contribution

By submitting a contribution (the “Contribution”) to this project, and for good and valuable consideration, the receipt and sufficiency of which are hereby acknowledged, you (the “Assignor”) irrevocably convey, transfer, and assign the Contribution to the owner of the repository (the “Assignee”), and the Assignee hereby accepts, all of your right, title, and interest in and to the Contribution along with all associated copyrights, copyright registrations, and/or applications for registration and all issuances, extensions and renewals thereof (collectively, the “Assigned Copyrights”). You also assign all of your rights of any kind whatsoever accruing under the Assigned Copyrights provided by applicable law of any jurisdiction, by international treaties and conventions and otherwise throughout the world.

## Local Install

- Minimum python 3.6 `git clone https://github.com/akamai/cli-onboard.git  `
- Create python virtual environment `python3 -m venv .venv`
- Install required packages `pip3 install -r requirements.txt`

# Notice

Copyright 2020 – Akamai Technologies, Inc.

All works contained in this repository, excepting those explicitly otherwise labeled, are the property of Akamai Technologies, Inc.
