<a id="top"></a>

# cli-onboard

`cli-onboard` is an Akamai CLI plugin for onboarding Akamai Property Manager and application security configurations. It supports guided onboarding for new properties, updates to existing Web Application Firewall (WAF) / AppSec configurations, Default DV certificate workflows, and bulk conversion from competitor CDN migration artifacts.

## Quick navigation:

- [Start with the tutorial](#tutorial-onboard-your-first-property-)
- [Jump to task guides](#how-to-guides-)
- [Look up commands](#reference-)
- [Understand the workflow model](#explanation-)

## Requirements

- [Akamai CLI installed](https://github.com/akamai/cli)
- Minimum Python 3.12
- An `.edgerc` entry with credentials that can access the APIs you plan to use

#### Minimum API grants:

- Property Manager (`/papi`)
- Edge Hostnames API (`/hapi`)
- Certificate Provisioning System (`/cps`) — manages TLS certificate enrollments
- Application Security (`/appsec`) — WAF and bot-management configurations

Example `.edgerc` section:

```ini
[default]
client_secret = [CLIENT_SECRET]
host = [HOST]
access_token = [ACCESS_TOKEN]
client_token = [CLIENT_TOKEN]
```

## Installation

```bash
akamai install property-manager onboard
```

## 🚀 Tutorial: onboard your first property

This tutorial walks through the safest first run: create a new property from a JSON template without activating production.

If you already know what you need, skip to [How-to guides](#how-to-guides-) or [Reference](#reference-).

### 1. Fetch the sample templates

```bash
akamai onboard fetch-sample-templates
```

This creates a local `sample_templates/` directory with starter JSON and CSV files.

### 2. Edit the create template

Open `sample_templates/create.json` and set at least these values:

- `property_info.property_name`
- `property_info.contract_id`
- `property_info.group_id`
- `property_info.product_id`
- `public_hostnames`
- `edge_hostname.mode`

For a first run, keep activations disabled until validation succeeds:

```json
{
  "activate_property_staging": false,
  "activate_waf_policy_staging": false,
  "activate_property_production": false,
  "activate_waf_policy_production": false
}
```

### 3. Run the create command

```bash
akamai onboard create --file sample_templates/create.json
```

If your credentials live in a different `.edgerc` file or section:

```bash
akamai onboard --edgerc ~/.edgerc --section onboard create --file sample_templates/create.json
```

### 4. Review the result

Successful runs create or update Akamai configuration objects and write intermediate files under `logs/`.

After the command succeeds, you can enable staging activation in the JSON file and rerun.

[↑ Back to top](#top)

## 🧭 How-to guides

These are task-oriented entry points. If you are learning the tool for the first time, start with the [tutorial](#tutorial-onboard-your-first-property-).

1. [Create one hostname quickly](#1-create-one-hostname-quickly)
2. [Create one property with multiple hostnames](#2-create-one-property-with-multiple-hostnames)
3. [Create many properties from a template and CSV](#3-create-many-properties-from-a-template-and-csv)
4. [Work with Default DV certificates (Secure by Default / SBD)](#4-work-with-default-dv-certificates-secure-by-defaultsbd)
5. [Create new AppSec configurations in bulk](#5-create-new-appsec-configurations-in-bulk)
6. [Add hostnames to an existing AppSec configuration](#6-add-hostnames-to-an-existing-appsec-configuration)
7. [Remove hostnames from an existing AppSec configuration](#7-remove-hostnames-from-an-existing-appsec-configuration)
8. [Inspect existing AppSec policies before updating them](#8-inspect-existing-appsec-policies-before-updating-them)
9. [Convert competitor CDN artifacts into Akamai properties](#9-convert-competitor-cdn-artifacts-into-akamai-properties)


### 1. Create one hostname quickly

Use `single-host` when you want one property, one hostname, and optional security creation.

```bash
akamai onboard single-host --file sample_templates/single-host.json
```

**Best fit:**

- fast onboarding for one hostname
- simple property creation
- optional secure-by-default edge hostname handling
- see also: [Reference](#reference-) for the command catalog

### 2. Create one property with multiple hostnames

Use `multi-hosts` when several hostnames belong on one property.

```bash
akamai onboard multi-hosts \
  --file sample_templates/multiple-hosts.json \
  --csv sample_templates/multi-hosts-input.csv
```

**Best fit:**

- one delivery config with many hostnames
- optional shared or individual CP codes (billing and reporting identifiers)
- optional initial security configuration
- compare with [Create many properties from a template and CSV](#3-create-many-properties-from-a-template-and-csv)

### 3. Create many properties from a template and CSV

Use `batch-create` when you want to stamp out multiple properties from a common rule tree (a JSON file containing the delivery configuration rules).

```bash
akamai onboard batch-create \
  --template ~/path/to/ruletree.json \
  --csv ~/path/to/input.csv \
  --product prd_SPM \
  --group grp_1234 \
  --contract ctr_1234
```

Add `--secure-by-default` if you want Secure by Default certificate workflows.

If you are migrating from another CDN rather than stamping out a common template, use [Convert competitor CDN artifacts into Akamai properties](#convert-competitor-cdn-artifacts-into-akamai-properties).


### 4. Work with Default DV certificates (Secure by Default / SBD)

Use **`sbd-precheck`** to generate DNS token data before onboarding hostnames with default DV certificates.

```bash
akamai onboard sbd-precheck --csv sample_templates/SBD.csv
```

Use **`sbd-status`**  to identify stalled or dangling default DV certificates.

```bash
akamai onboard sbd-status
```

### 5. Create new AppSec configurations in bulk

Use `appsec-create` to create WAF security configurations, policies, and match targets (rules that map hostnames to a security policy) from CSV input.

```bash
akamai onboard appsec-create \
  --contract-id ctr_1111 \
  --group-id grp_1111 \
  --csv sample_templates/appsec-create-by-hostname.csv
```

Use `--by propertyname` when the CSV groups work by property name instead of hostname.

### 6. Add hostnames to an existing AppSec configuration

Use `appsec-update` to add selected hosts and optionally update match targets.

```bash
akamai onboard appsec-update \
  --config-id 9999 \
  --csv sample_templates/appsec-update.csv
```

### 7. Remove hostnames from an existing AppSec configuration

Use `appsec-remove` to remove selected hosts and clean up match targets.

```bash
akamai onboard appsec-remove \
  --config-id 9999 \
  --csv sample_templates/appsec-remove.csv
```

### 8. Inspect existing AppSec policies before updating them

Use `appsec-policy` to list security configurations, policies, and website match targets.

```bash
akamai onboard appsec-policy
akamai onboard appsec-policy --name-contains test
akamai onboard appsec-policy --waf-config-name sample_sec
akamai onboard appsec-policy --waf-config-name sample_sec --policy-name Default
```

### 9. Convert competitor CDN artifacts into Akamai properties

Use `convert` to create delivery configurations from migration CSV files and per-property rule-tree JSON files (one JSON file per property, containing delivery configuration rules).

```bash
akamai onboard convert \
  --csv migration-hostnames.csv \
  --directory /path/to/ruletree-jsons \
  --contract ctr_XXXXX \
  --group grp_XXXXX \
  --network ENHANCED_TLS
```

Use `--cert-mode CPS` if the properties require CPS-managed certificates.

For the full option list, see [Convert command options](#convert-command-options).

[↑ Back to top](#top)

## 📚 Reference

Use this section when you need facts rather than guidance. If you need a recommended path, go back to [🧭 How-to guides](#how-to-guides-).

### Global options

These options apply before the subcommand:

| Option | Description |
| --- | --- |
| `--edgerc` | Path to the credentials file. Defaults to `~/.edgerc`. |
| `--section`, `-s` | Section name in `.edgerc`. Defaults to `onboard`. |
| `--account-key` | Account switch key for Akamai internal workflows. |
| `--help`, `-h` | Show command help. |

### Command catalog

| Command | Purpose |
| --- | --- |
| `create` | Create a property and optionally update WAF from a JSON definition |
| `single-host` | Create one property for one hostname |
| `multi-hosts` | Create one property for many hostnames |
| `batch-create` | Create multiple properties from a common template |
| `fetch-sample-templates` | Copy example setup files locally |
| `appsec-policy` | List security configurations, policies, and match targets |
| `appsec-create` | Create AppSec configurations in bulk |
| `appsec-update` | Add hostnames to existing AppSec config |
| `appsec-remove` | Remove hostnames from existing AppSec config |
| `sbd-precheck` | Generate token data for Secure by Default validation |
| `sbd-status` | Report Secure by Default certificate status |
| `convert` | Convert competitor CDN artifacts into Akamai delivery configs |

### Common input types

> For `batch-create` and `convert`, the JSON input is a rule-tree JSON template (delivery configuration rules) rather than a setup JSON file.

| Command | CSV | JSON |
| --- | --- | --- |
| `create` |  | :heavy_check_mark: |
| `single-host` |  | :heavy_check_mark: |
| `multi-hosts` | :heavy_check_mark: | :heavy_check_mark: |
| `batch-create` | :heavy_check_mark: | :heavy_check_mark: |
| `appsec-create` | :heavy_check_mark: |  |
| `appsec-update` | :heavy_check_mark: |  |
| `appsec-remove` | :heavy_check_mark: |  |
| `sbd-precheck` | :heavy_check_mark: |  |
| `convert` | :heavy_check_mark: | :heavy_check_mark: |



### Convert command options

| Option | Required | Description |
| --- | --- | --- |
| `--csv` | Yes | CSV file with `hostname` and `propertyName` at minimum |
| `--directory` | Yes | Directory containing per-property rule-tree JSON files |
| `--contract` | Yes | Contract ID |
| `--group` | Yes | Group ID |
| `--network` | No | `ENHANCED_TLS` or `STANDARD_TLS` |
| `--product` | No | Product override when not supplied in CSV |
| `--cert-mode` | No | `SBD` or `CPS` |
| `--enrollment-id` | No | CPS enrollment ID used with `--cert-mode CPS` |
| `--use-existing-edgehostname` | No | Reuse a provided edge hostname or CSV column values |
| `--rule-format` | No | Rule format version, default `latest` |
| `--use-cpcode` | No | Reuse one CP code property manager config |
| `--gtm-domain` | No | Global Traffic Management (GTM) domain replacement target |
| `--media-ehn` | No | Adaptive Media Delivery (AMD) edge hostname mode: `VOD` or `LIVE` |
| `--activate` | No | Activation target: `staging` or `production` |
| `--email` | No | Notification emails for activation |
| `--force` | No | Skip confirmation prompt |
| `--launch/--no-launch` | No | Automatically open the Excel report |

[↑ Back to top](#top)

## 💡 Explanation

### Why there are multiple onboarding commands ?

The command set is organized around different operational entry points rather than one universal input format.

- `single-host` is the simplest onboarding case.
- `multi-hosts` is for one property with multiple hostnames.
- `batch-create` is for many properties built from a custom rule-tree template (a JSON file containing the delivery configuration rules).
- `create` is the most flexible JSON-driven workflow when you need explicit control over delivery, edge hostname, WAF, and activation settings.
- `convert` is a migration workflow for importing artifacts produced by Internal CDN conversion tooling.

### Delivery, certificates, and security are coupled

Several workflows combine property creation, edge hostname assignment, and WAF updates because Akamai onboarding typically spans all three layers. The CLI keeps those steps together so the data needed for one layer can be reused by the others.

### Why staging-first is safer

Many commands support activation, but a staging-first rollout is the lower-risk operating model:

- validate configuration shape before production traffic uses it
- verify DNS, edge hostname, and certificate behavior
- confirm AppSec match targets and selected hosts are correct

### Default DV (Secure By Default/SBD) versus [CPS](https://techdocs.akamai.com/cps/docs/cps-workflow)

- Default DV certificate is designed to make HTTPS onboarding and ongoing certificate management effortless.  Certificate provisioning, deployment, and renewal are fully automated and tightly integrated with hostname activation.
- CPS mode exists for workflows that require managed certificate enrollments or pre-existing edge hostnames.
- The `convert` command exposes these certificate choices explicitly because migration projects often need a mix of temporary and final certificate strategies.

[↑ Back to top](#top)

## Contribution guidelines

### Local development

The plugin metadata requires Python 3.12.

```bash
git clone https://github.com/akamai/cli-onboard.git
cd cli-onboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

To test a different branch:

1. Check out the branch: `git checkout -b new-branch`
2. Uninstall the existing version: `akamai uninstall onboard`
3. Get the repo's absolute path: `pwd` (e.g. `/Users/Documents/cli-onboard`)
4. Install from the local repo:
   - **macOS / Linux** (three slashes): `akamai install file:///Users/Documents/cli-onboard`
   - **Windows** (two slashes): `akamai install file://C:/Users/sample/cli-onboard`

Local artifacts are written to folders such as `logs/`, and `convert` writes an Excel workbook under `output/{account_name}/`.

By submitting a contribution to this project, you assign the contribution and associated copyright rights to the repository owner.

## Notice

Copyright 2020 Akamai Technologies, Inc.

All works contained in this repository, except those explicitly labeled otherwise, are the property of Akamai Technologies, Inc.

[↑ Back to top](#top)
