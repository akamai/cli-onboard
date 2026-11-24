<a id="top"></a>

# cli-onboard

`cli-onboard` is an Akamai CLI plugin for onboarding Akamai Property Manager and application security configurations. It supports guided onboarding for new properties, updates to existing Web Application Firewall (WAF) / AppSec configurations, Default DV certificate workflows, and bulk conversion from competitor CDN migration artifacts.

## 🚀 New here? Start here

1. Check the [Requirements](#requirements) — install the Akamai CLI, and add an `.edgerc` entry with API access.
2. Install the plugin (see [Installation](#installation) below).
3. Follow the [📘 Tutorial](#-tutorial-onboard-your-first-property) to onboard your first property safely (no production activation).

Already familiar with the tool? Jump to [🎯 How-to guides](#-how-to-guides) or [📖 Commands Reference](#-commands-reference).

[↑ Back to top](#top)

---

## Requirements

- [Akamai CLI installed](https://github.com/akamai/cli)
- Minimum Python 3.12
- An `.edgerc` entry with credentials that can access the APIs you plan to use

## Minimum API grants

Your `.edgerc` credentials need access to all four of these APIs:

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

Install failing? See [💡 Troubleshooting `akamai install`](CONTRIBUTING.md#troubleshooting-akamai-install) in CONTRIBUTING.md — most failures there also apply to a normal install, not just a local dev one.

[↑ Back to top](#top)

---

## 📚 Documentation

### Documentation System

This project follows the [Divio documentation system](https://documentation.divio.com/):

| Pillar      | Purpose                | When to use                            |
| ----------- | ----------------------- | ---------------------------------------- |
| [📘 Tutorial](#-tutorial-onboard-your-first-property) | Learning-oriented       | "I want to learn by doing"              |
| [🎯 How-to](#-how-to-guides)   | Problem-oriented        | "I want to accomplish a specific task"  |
| [💡 Explanation](#-explanation) | Understanding-oriented  | "I want to understand how this works"   |
| [📖 Reference](#-commands-reference) | Information-oriented    | "I need to look up technical details"   |

### Project Documentation

| Document                                 | Tutorial                                                               | How-to                                                          | Explanation                                                              | Reference                                                              |
| ------------------------------------------ | --------------------------------------------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **[README](README.md)** (this file)      | [Onboard your first property](#-tutorial-onboard-your-first-property) | [Task-oriented command guides](#-how-to-guides)                 | [Rule-trees, command design, staging-first, DV vs CPS](#-explanation)      | [Global options, command catalog, input types](#-commands-reference)      |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** — for developers changing this plugin's code | -                                                                      | [Dev environment setup](CONTRIBUTING.md#dev-environment-setup)  | [Troubleshooting `akamai install`](CONTRIBUTING.md#troubleshooting-akamai-install) | [Running the tests](CONTRIBUTING.md#running-the-tests)                    |
| **[CHANGELOG.md](CHANGELOG.md)** — for checking what changed between versions | -                                                                      | -                                                                | -                                                                            | [Release history](CHANGELOG.md)                                           |

[↑ Back to top](#top)

---

## 📘 Tutorial: onboard your first property

This tutorial walks through the safest first run: create a new property from a JSON template without activating production.

> 🚀 **Start here:** before running any command below, complete [Requirements](#requirements) and [Installation](#installation). The `onboard` command isn't recognized by the Akamai CLI until the plugin is installed with `akamai install property-manager onboard`.

### 1. Fetch the sample templates

```bash
akamai onboard fetch-sample-templates
```

This creates a local `sample_templates/` directory with starter JSON and CSV files.

### 2. Edit the create template

Open `sample_templates/create.json` and set at least these values:

| Field                              | What it is                                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `property_info.property_name`      | The name for your new Property Manager configuration (shown in Akamai Control Center).             |
| `property_info.contract_id`        | Your Akamai contract ID, e.g. `ctr_1-ABC123` — billing/entitlement scope for the property.          |
| `property_info.group_id`           | The Akamai group ID, e.g. `grp_12345` — controls access permissions for the property.               |
| `property_info.product_id`         | The Akamai product ID, e.g. `prd_SPM` — determines which delivery product features are available.  |
| `public_hostnames`                 | The list of hostnames (e.g. `["www.example.com"]`) this property will serve.                       |
| `edge_hostname.mode`               | How the edge hostname is created — e.g. `new_enhanced_tls_edgehostname` for a new Enhanced TLS edge hostname, or use an existing one instead. |

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

If your credentials live in a different `.edgerc` file or section (the CLI uses the `default` section unless you override it):

```bash
akamai onboard --edgerc ~/.edgerc --section mysection create --file sample_templates/create.json
```

### 4. Review the result

Successful runs create or update Akamai configuration objects and write intermediate files under `logs/`.

After the command succeeds, you can enable staging activation in the JSON file and rerun.

Next step: try one of the [🎯 How-to guides](#-how-to-guides) for a task closer to your real onboarding scenario.

[↑ Back to top](#top)

---

## 🎯 How-to guides

These are task-oriented entry points. If you are learning the tool for the first time, start with the [📘 Tutorial](#-tutorial-onboard-your-first-property). For the full command list, see the [📖 Command catalog](#-commands-reference).

1. [Create one hostname quickly](#1-create-one-hostname-quickly)
2. [Create one property with multiple hostnames](#2-create-one-property-with-multiple-hostnames)
3. [Create many properties from a template and CSV](#3-create-many-properties-from-a-template-and-csv)
4. [Work with Default DV certificates (Secure by Default / SBD)](#4-work-with-default-dv-certificates-secure-by-default--sbd)
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
- see also: [📖 Commands Reference](#-commands-reference) for the command catalog

[↑ Back to How-to list](#-how-to-guides)

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

[↑ Back to How-to list](#-how-to-guides)

### 3. Create many properties from a template and CSV

Use `batch-create` when you want to stamp out multiple properties from a common [rule-tree JSON](#what-is-a-rule-tree-json).

```bash
akamai onboard batch-create \
  --template ~/path/to/ruletree.json \
  --csv ~/path/to/input.csv \
  --product prd_SPM \
  --group grp_1234 \
  --contract ctr_1234
```

Add `--secure-by-default` if you want Secure by Default certificate workflows.

If you are migrating from another CDN rather than stamping out a common template, use [Convert competitor CDN artifacts into Akamai properties](#9-convert-competitor-cdn-artifacts-into-akamai-properties).

[↑ Back to How-to list](#-how-to-guides)

### 4. Work with Default DV certificates (Secure by Default / SBD)

Use **`sbd-precheck`** to generate DNS token data before onboarding hostnames with default DV certificates.

```bash
akamai onboard sbd-precheck --csv sample_templates/SBD.csv
```

Use **`sbd-status`** to identify stalled or dangling default DV certificates.

```bash
akamai onboard sbd-status
```

See also: [💡 Default DV (Secure By Default/SBD) versus CPS](#default-dv-secure-by-defaultsbd-versus-cps) for when to choose which.

[↑ Back to How-to list](#-how-to-guides)

### 5. Create new AppSec configurations in bulk

Use `appsec-create` to create WAF security configurations, policies, and match targets (rules that map hostnames to a security policy) from CSV input.

```bash
akamai onboard appsec-create \
  --contract-id ctr_1111 \
  --group-id grp_1111 \
  --csv sample_templates/appsec-create-by-hostname.csv
```

Use `--by propertyname` when the CSV groups work by property name instead of hostname.

[↑ Back to How-to list](#-how-to-guides)

### 6. Add hostnames to an existing AppSec configuration

Use `appsec-update` to add selected hosts and optionally update match targets.

```bash
akamai onboard appsec-update \
  --config-id 9999 \
  --csv sample_templates/appsec-update.csv
```

[↑ Back to How-to list](#-how-to-guides)

### 7. Remove hostnames from an existing AppSec configuration

Use `appsec-remove` to remove selected hosts and clean up match targets.

```bash
akamai onboard appsec-remove \
  --config-id 9999 \
  --csv sample_templates/appsec-remove.csv
```

[↑ Back to How-to list](#-how-to-guides)

### 8. Inspect existing AppSec policies before updating them

Use `appsec-policy` to list security configurations, policies, and website match targets.

```bash
akamai onboard appsec-policy
akamai onboard appsec-policy --name-contains test
akamai onboard appsec-policy --waf-config-name sample_sec
akamai onboard appsec-policy --waf-config-name sample_sec --policy-name Default
```

[↑ Back to How-to list](#-how-to-guides)

### 9. Convert competitor CDN artifacts into Akamai properties

Use `convert` to create delivery configurations from migration CSV files and per-property [rule-tree JSON](#what-is-a-rule-tree-json) files (one per property).

```bash
akamai onboard convert \
  --csv migration-hostnames.csv \
  --directory /path/to/ruletree-jsons \
  --contract ctr_XXXXX \
  --group grp_XXXXX \
  --network ENHANCED_TLS
```

Use `--cert-mode CPS` if the properties require CPS-managed certificates — see [💡 Default DV versus CPS](#default-dv-secure-by-defaultsbd-versus-cps) for when to choose which.

For the full option list, see [📖 Convert command options](#convert-command-options).

[↑ Back to top](#top)

---

## 📖 Commands Reference

Use this section when you need facts rather than guidance. If you need a recommended path, go back to [🎯 How-to guides](#-how-to-guides).

**In this section:**

1. [Global options](#global-options)
2. [Command catalog](#command-catalog)
3. [Common input types](#common-input-types)
4. [Convert command options](#convert-command-options)

### Global options

These options apply before the subcommand:

```shell
 --edgerc                                                     Path to the credentials file [$AKAMAI_EDGERC]
 --section                                                -s  Section name in the credentials file
                                                              [$AKAMAI_EDGERC_SECTION]
 --account-key,--accountkey,--accountSwitchKey,--account  -a  Account Switch Key (Akamai Internal Only)
 switchkey
 --version                                                    Show akamai onboard CLI version
 --help                                                   -h  Show command help
```

[↑ Back to Commands Reference](#-commands-reference)

### Command catalog

This is the real `--help` output for the CLI's registered commands, kept in sync automatically — see [`bin/sync_readme_commands.py`](bin/sync_readme_commands.py).

<!-- command-catalog:start -->
```console
$ akamai onboard --help

╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ appsec-create           Create new security configuration, security policy, and policy match target                  │
│ appsec-policy           List available security configuration policy                                                 │
│ appsec-remove           Remove hostnames from selected hosts and any policy match targets                            │
│ appsec-update           Add hostnames as selected hosts to existing security configuration and optionally add to     │
│                         policy match target                                                                          │
│ batch-create            Create a 1 or more delivery configurations using a csv input and optionally update WAF       │
│                         policy                                                                                       │
│ convert                 🌈 Bring over delivery configs from Competitors 🌈                                           │
│ create                  Create a delivery configuration and update existing WAF policy                               │
│ fetch-sample-templates  Pull sample templates                                                                        │
│ multi-hosts             Create a delivery configuration with mutltiple hostnames and security configuration with one │
│                         WAF policy                                                                                   │
│ sbd-precheck            ✔️ Precheck Default DV (SBD) hostnames for token placement                                    │
│ sbd-status              ✔️ View Default DV (SBD) certificate deployment status                                        │
│ single-host             Create a simple delivery and security configuration with one hostname and one WAF policy     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
<!-- command-catalog:end -->

[↑ Back to Commands Reference](#-commands-reference)

### Common input types

> For `batch-create` and `convert`, the JSON input is a [💡 rule-tree JSON](#what-is-a-rule-tree-json) template rather than a setup JSON file.

| Command         | CSV                | JSON               |
| --------------- | ------------------ | ------------------ |
| `create`        |                    | :heavy_check_mark: |
| `single-host`   |                    | :heavy_check_mark: |
| `multi-hosts`   | :heavy_check_mark: | :heavy_check_mark: |
| `batch-create`  | :heavy_check_mark: | :heavy_check_mark: |
| `appsec-create` | :heavy_check_mark: |                    |
| `appsec-update` | :heavy_check_mark: |                    |
| `appsec-remove` | :heavy_check_mark: |                    |
| `sbd-precheck`  | :heavy_check_mark: |                    |
| `convert`       | :heavy_check_mark: | :heavy_check_mark: |

[↑ Back to Commands Reference](#-commands-reference)

### Convert command options

```console
$ akamai onboard convert --help

 Usage: akamai onboard convert [OPTIONS]

 Bring over Cloudflare/Cloudfront/Imperva/Fastly configs to Akamai platform

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --contract                   -c  contract ID                                                                      │
│    --group                      -g  group ID                                                                         │
│    --product                    -p  one of prd_SPM, prd_Fresca, prd_Site_Accel, prd_Download_Delivery (case          │
│                                     sensitive)                                                                       │
│    --network                    -n  network to use for edge hostnames (ENHANCED_TLS or STANDARD_TLS)                 │
│                                     [default: STANDARD_TLS]                                                          │
│ *  --directory                  -d  directory where ruletree json files are [required]                               │
│ *  --csv                            csv file with headers hostname,propertyName [required]                           │
│    --rule-format                -f  rule format (typically latest, but can use frozen rule format if desired)        │
│                                     [default: latest]                                                                │
│    --use-cpcode                     reuse existing numeric CP Code                                                   │
│    --cert-mode                      Certificate mode [default: SBD]                                                  │
│    --use-existing-edgehostname      Use existing edge hostnames. Pass an EHN name for a single EHN, or pass 'CSV' to │
│                                     use the edgeHostname column from the CSV.                                        │
│    --enrollment-id                  Existing CPS enrollment ID for creating CPS_MANAGED edge hostnames (one per      │
│                                     property)                                                                        │
│    --media-ehn                      AMD Edge Hostname option (VOD, LIVE) [default: VOD]                              │
│    --gtm-domain                     gtm domain to use in properties                                                  │
│    --activate                       Options: staging, production                                                     │
│    --email                          email(s) for activation notifications                                            │
│    --force                          skip user confirmation prompt                                                    │
│    --launch/--no-launch             automatically open excel application                                             │
│    --help                       -h  Show this message and exit.                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

`*` marks a required option.

[↑ Back to Commands Reference](#-commands-reference) · [↑ Back to top](#top)

---

## 💡 Explanation

### What is a rule-tree JSON?

A rule-tree JSON is a JSON file containing Property Manager delivery configuration rules — the same rule-tree shape PAPI accepts for a property. `batch-create` and `convert` take this as their template/per-property input, instead of the single-property setup JSON used by `create`, `single-host`, and `multi-hosts`.

### Why there are multiple onboarding commands?

The command set is organized around different operational entry points rather than one universal input format (see the [📖 Command catalog](#-commands-reference) for the full list):

- `single-host` is the simplest onboarding case.
- `multi-hosts` is for one property with multiple hostnames.
- `batch-create` is for many properties built from a custom [rule-tree JSON](#what-is-a-rule-tree-json) template.
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

- Default DV certificate is designed to make HTTPS onboarding and ongoing certificate management effortless. Certificate provisioning, deployment, and renewal are fully automated and tightly integrated with hostname activation.
- CPS mode exists for workflows that require managed certificate enrollments or pre-existing edge hostnames.
- The `convert` command exposes these certificate choices explicitly because migration projects often need a mix of temporary and final certificate strategies.

[↑ Back to top](#top)

---

## 🙌 Contribution guidelines

Want to contribute? See [CONTRIBUTING.md](CONTRIBUTING.md) for dev environment setup, running tests and lint, and how to submit a change.

Curious what's changed recently, or upgrading from an older version? See [📖 CHANGELOG.md](CHANGELOG.md) for the release history.

## Notice

Copyright 2020 Akamai Technologies, Inc.

All works contained in this repository, except those explicitly labeled otherwise, are the property of Akamai Technologies, Inc.

[↑ Back to top](#top)
