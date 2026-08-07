<a id="top"></a>

# cli-onboard

`cli-onboard` is an Akamai CLI plugin for onboarding Akamai Property Manager and application security configurations. It supports guided onboarding for new properties, updates to existing Web Application Firewall (WAF) / AppSec configurations, Default DV certificate workflows, and bulk conversion from competitor CDN migration artifacts.

## Quick navigation:

- [Start with the tutorial](#-tutorial-onboard-your-first-property)
- [How-to guides](#-how-to-guides)
- [Commands Reference](#-commands-reference)
- [Explanation](#-explanation)
- [Contributing](CONTRIBUTING.md)

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

If you already know what you need, skip to [How-to guides](#-how-to-guides) or [Commands Reference](#-commands-reference).

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

If your credentials live in a different `.edgerc` file or section (the CLI uses the `default` section unless you override it):

```bash
akamai onboard --edgerc ~/.edgerc --section mysection create --file sample_templates/create.json
```

### 4. Review the result

Successful runs create or update Akamai configuration objects and write intermediate files under `logs/`.

After the command succeeds, you can enable staging activation in the JSON file and rerun.

[↑ Back to top](#top)

## 🧭 How-to guides

These are task-oriented entry points. If you are learning the tool for the first time, start with the [tutorial](#-tutorial-onboard-your-first-property). For the full command list, see the [Command catalog](#-commands-reference).

[1. Create one hostname quickly](#1-create-one-hostname-quickly)
[2. Create one property with multiple hostnames](#2-create-one-property-with-multiple-hostnames)
[3. Create many properties from a template and CSV](#3-create-many-properties-from-a-template-and-csv)
[4. Work with Default DV certificates (Secure by Default / SBD)](#4-work-with-default-dv-certificates-secure-by-default--sbd)
[5. Create new AppSec configurations in bulk](#5-create-new-appsec-configurations-in-bulk)
[6. Add hostnames to an existing AppSec configuration](#6-add-hostnames-to-an-existing-appsec-configuration)
[7. Remove hostnames from an existing AppSec configuration](#7-remove-hostnames-from-an-existing-appsec-configuration)
[8. Inspect existing AppSec policies before updating them](#8-inspect-existing-appsec-policies-before-updating-them)
[9. Convert competitor CDN artifacts into Akamai properties](#9-convert-competitor-cdn-artifacts-into-akamai-properties)
[10. Skip waiting for activation and check status later](#10-skip-waiting-for-activation-and-check-status-later)

### 1. Create one hostname quickly

Use `single-host` when you want one property, one hostname, and optional security creation.

```bash
akamai onboard single-host --file sample_templates/single-host.json
```

**Best fit:**

- fast onboarding for one hostname
- simple property creation
- optional secure-by-default edge hostname handling
- see also: [Commands Reference](#-commands-reference) for the command catalog

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

Use `convert` to create delivery configurations from migration CSV files and per-property [rule-tree JSON](#what-is-a-rule-tree-json) files (one per property).

```bash
akamai onboard convert \
  --csv migration-hostnames.csv \
  --directory /path/to/ruletree-jsons \
  --contract ctr_XXXXX \
  --group grp_XXXXX \
  --network ENHANCED_TLS
```

Use `--cert-mode CPS` if the properties require CPS-managed certificates — see [Default DV versus CPS](#default-dv-secure-by-defaultsbd-versus-cps) for when to choose which.

For the full option list, see [Convert command options](#convert-command-options).

### 10. Skip waiting for activation and check status later

Add `--no-wait` to `single-host`, `multi-hosts`, `convert`, `batch-create`, `appsec-create`, `appsec-update`, or `appsec-remove` to submit production activation(s) and return immediately instead of polling for completion. Staging activation always waits, since production is gated on staging succeeding first.

```bash
akamai onboard batch-create \
  --template ~/path/to/ruletree.json \
  --csv ~/path/to/input.csv \
  --product prd_SPM \
  --group grp_1234 \
  --contract ctr_1234 \
  --activate delivery-production \
  --no-wait
```

Each submitted activation ID is recorded to a manifest CSV (printed at the end of the run). Check on it later with `check-activation`:

```bash
akamai onboard check-activation --file output/<account>/<timestamp>_activation-status.csv
```

Add `--wait` to poll until every activation in the file is active (or errored) instead of checking once and exiting. `check-activation` also accepts a minimal, hand-built CSV or a single `--activation-id` for an ad-hoc check — see `akamai onboard check-activation --help`.

[↑ Back to top](#top)

## 📚 Commands Reference

Use this section when you need facts rather than guidance. If you need a recommended path, go back to [🧭 How-to guides](#-how-to-guides).

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
│ check-activation        Check status of activation(s) submitted earlier with --no-wait                               │
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

### Common input types

> For `batch-create` and `convert`, the JSON input is a [rule-tree JSON](#what-is-a-rule-tree-json) template rather than a setup JSON file.

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
│    --dryrun                         admin - test config                                                              │
│    --prefix                         admin - required for dryrun.                                                     │
│    --launch/--no-launch             automatically open excel application                                             │
│    --no-wait                        Submit production activation(s) and return immediately instead of polling for    │
│                                     completion; check status later with check-activation. Staging activation always  │
│                                     waits.                                                                           │
│    --log-level                      Set logging verbosity                                                            │
│    --debug,--verbose                shortcut for --log-level DEBUG                                                   │
│    --help                       -h  Show this message and exit.                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

`*` marks a required option.

[↑ Back to top](#top)

## 💡 Explanation

### What is a rule-tree JSON?

A rule-tree JSON is a JSON file containing Property Manager delivery configuration rules — the same rule-tree shape PAPI accepts for a property. `batch-create` and `convert` take this as their template/per-property input, instead of the single-property setup JSON used by `create`, `single-host`, and `multi-hosts`.

### Why there are multiple onboarding commands ?

The command set is organized around different operational entry points rather than one universal input format (see the [Command catalog](#-commands-reference) for the full list):

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

- Default DV certificate is designed to make HTTPS onboarding and ongoing certificate management effortless.  Certificate provisioning, deployment, and renewal are fully automated and tightly integrated with hostname activation.
- CPS mode exists for workflows that require managed certificate enrollments or pre-existing edge hostnames.
- The `convert` command exposes these certificate choices explicitly because migration projects often need a mix of temporary and final certificate strategies.

[↑ Back to top](#top)

## Contribution guidelines

Want to contribute? See [CONTRIBUTING.md](CONTRIBUTING.md) for dev environment setup, running tests and lint, and how to submit a change.

## Notice

Copyright 2020 Akamai Technologies, Inc.

All works contained in this repository, except those explicitly labeled otherwise, are the property of Akamai Technologies, Inc.

[↑ Back to top](#top)
