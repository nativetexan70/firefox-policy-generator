# DISA STIG support (Mozilla Firefox)

ffpolicy bundles a **preset** for the DISA Security Technical Implementation Guide
for Mozilla Firefox (Release 8, Benchmark Date: 01 Jul 2026, `MOZ_Firefox_STIG`
version 6). It covers all 33 rules in the benchmark: 30 are applied automatically
as `policies.json` values, and 3 require manual/procedural action outside of
`policies.json` (browser version, certificate installation, and an
organization-specific MIME allowlist - see the table below).

Applying the preset gives you a compliant baseline; you then layer your own
**manual settings** on top for anything organization-specific (e.g. a
pop-up allowlist, a custom homepage) - the preset and manual configuration
are meant to be combined, not either/or.

## Profiles

The STIG defines nine profiles - one per Mission Assurance Category (I/II/III)
times confidentiality level (Classified/Public/Sensitive) - and all nine select
the exact same 33 rules for this benchmark, so every profile below applies an
identical set of values. Pick whichever matches your system's official
designation for audit purposes:

| Preset id | Profile |
|---|---|
| `disa_stig__mac_1_classified` | I - Mission Critical Classified |
| `disa_stig__mac_1_public` | I - Mission Critical Public |
| `disa_stig__mac_1_sensitive` | I - Mission Critical Sensitive |
| `disa_stig__mac_2_classified` | II - Mission Support Classified |
| `disa_stig__mac_2_public` | II - Mission Support Public |
| `disa_stig__mac_2_sensitive` | II - Mission Support Sensitive |
| `disa_stig__mac_3_classified` | III - Administrative Classified |
| `disa_stig__mac_3_public` | III - Administrative Public |
| `disa_stig__mac_3_sensitive` | III - Administrative Sensitive |

## Apply via CLI

```bash
# See all profiles, including the items that need manual follow-up
python -m ffpolicy presets

# Full rule-by-rule description + recommendation for one profile
python -m ffpolicy preset-info disa_stig__mac_1_classified

# Preset only
python -m ffpolicy generate --preset disa_stig__mac_1_classified -o policies.json --offline

# Preset as a baseline, with your own input file layered on top (input wins
# on any key both define) - this is the "preset + manual settings" workflow
python -m ffpolicy generate my-overrides.yaml \
  --preset disa_stig__mac_1_classified -o policies.json --offline
```

`my-overrides.yaml` only needs to contain the keys you want to add or change,
for example an organization-specific pop-up allowlist:

```yaml
policies:
  PopupBlocking:
    Allow:
      - "https://intranet.example.mil/"
    Default: true
    Locked: true
```

`validate`, `export`, and `preview` all accept the same `--preset` option, and
`input_file` is optional whenever `--preset` is given.

## Apply via GUI

Menu bar → **Presets** → **DISA STIG - Mozilla Firefox** submenu:

- **View rule details...** opens a scrollable list of every rule with its
  severity, the policy it sets, a description of what the setting does, and
  the recommendation (identical across all nine profiles, since they share
  one ruleset).
- **Apply \<profile\>...** (one action per profile) asks for confirmation
  (it overwrites any existing values for the policies it sets), applies the
  values, then shows the 3 manual/procedural items that still need
  attention. Any policy form you have open at the time refreshes to show the
  newly-applied value, so you can immediately hand-tune something like
  `PopupBlocking.Allow`.

## Example: description and recommendation

Every rule carries both a **description** (why the setting matters, from the
STIG's vulnerability discussion) and a **recommendation** (what to actually
set), shown by `preset-info` and the GUI's rule-details view:

> **[V-251546, high] Firefox must be configured to allow only TLS 1.2 or above.**
> Policy: `SSLVersionMin`
> Description: Use of versions prior to TLS 1.2 are not permitted. SSL 2.0 and
> SSL 3.0 contain a number of security flaws. These versions must be disabled
> in compliance with the Network Infrastructure and Secure Remote Computing
> STIGs.
> Recommendation: Set SSLVersionMin to "tls1.2" (or "tls1.3").

## Rule -> policy mapping

| Vuln ID | STIG Rule | Severity | Policy | Title |
|---|---|---|---|---|
| V-251545 | FFOX-00-000001 | high | _manual/procedural_ | The installed version of Firefox must be supported. |
| V-251546 | FFOX-00-000002 | high | `SSLVersionMin` | Firefox must be configured to allow only TLS 1.2 or above. |
| V-251547 | FFOX-00-000003 | medium | `Preferences` | Firefox must be configured to ask which certificate to present to a website when a certificate is required. |
| V-251548 | FFOX-00-000004 | medium | `Preferences` | Firefox must be configured to not automatically check for updated versions of installed search plugins. |
| V-251549 | FFOX-00-000005 | medium | `ExtensionUpdate` | Firefox must be configured to not automatically update installed add-ons and plugins. |
| V-251550 | FFOX-00-000006 | medium | _manual/procedural_ | Firefox must be configured to not automatically execute or download MIME types that are not authorized for auto-download. |
| V-251551 | FFOX-00-000007 | medium | `DisableFormHistory` | Firefox must be configured to disable form fill assistance. |
| V-251552 | FFOX-00-000008 | medium | `PasswordManagerEnabled` | Firefox must be configured to not use a password store with or without a master password. |
| V-251553 | FFOX-00-000009 | medium | `PopupBlocking` | Firefox must be configured to block pop-up windows. |
| V-251554 | FFOX-00-000010 | medium | `Preferences` | Firefox must be configured to prevent JavaScript from moving or resizing windows. |
| V-251555 | FFOX-00-000011 | medium | `Preferences` | Firefox must be configured to prevent JavaScript from raising or lowering windows. |
| V-251557 | FFOX-00-000013 | medium | `InstallAddonsPermission` | Firefox must be configured to disable the installation of extensions. |
| V-251558 | FFOX-00-000014 | medium | `DisableTelemetry` | Background submission of information to Mozilla must be disabled. |
| V-251559 | FFOX-00-000015 | low | `DisableDeveloperTools` | Firefox development tools must be disabled. |
| V-251560 | FFOX-00-000016 | medium | _manual/procedural_ | Firefox must have the DOD root certificates installed. |
| V-251562 | FFOX-00-000018 | medium | `DisableForgetButton` | Firefox must prevent the user from quickly deleting data. |
| V-251563 | FFOX-00-000019 | medium | `DisablePrivateBrowsing` | Firefox private browsing must be disabled. |
| V-251564 | FFOX-00-000020 | medium | `SearchSuggestEnabled` | Firefox search suggestions must be disabled. |
| V-251565 | FFOX-00-000021 | low | `Permissions` | Firefox autoplay must be disabled. |
| V-251566 | FFOX-00-000022 | medium | `NetworkPrediction` | Firefox network prediction must be disabled. |
| V-251567 | FFOX-00-000023 | medium | `EnableTrackingProtection` | Firefox fingerprinting protection must be enabled. |
| V-251568 | FFOX-00-000024 | medium | `EnableTrackingProtection` | Firefox cryptomining protection must be enabled. |
| V-251569 | FFOX-00-000025 | medium | `Preferences` | Firefox Enhanced Tracking Protection must be enabled. |
| V-251570 | FFOX-00-000026 | medium | `Preferences` | Firefox extension recommendations must be disabled. |
| V-251571 | FFOX-00-000027 | medium | `DisabledCiphers` | Firefox deprecated ciphers must be disabled. |
| V-251572 | FFOX-00-000028 | medium | `UserMessaging` | Firefox must not recommend extensions as the user is using the browser. |
| V-251573 | FFOX-00-000029 | medium | `FirefoxHome` | The Firefox New Tab page must not show Top Sites, Sponsored Top Sites, Pocket Recommendations, Sponsored Pocket Stories, Searches, Highlights, or Snippets. |
| V-251577 | FFOX-00-000033 | medium | `DNSOverHTTPS` | Firefox must be configured so that DNS over HTTPS is disabled. |
| V-251578 | FFOX-00-000034 | medium | `DisableFirefoxAccounts` | Firefox accounts must be disabled. |
| V-251580 | FFOX-00-000036 | medium | `DisableFeedbackCommands` | Firefox feedback reporting must be disabled. |
| V-251581 | FFOX-00-000037 | medium | `EncryptedMediaExtensions` | Firefox encrypted media extensions must be disabled. |
| V-252881 | FFOX-00-000017 | medium | `SanitizeOnShutdown` | Firefox must be configured to not delete data upon shutdown. |
| V-252909 | FFOX-00-000039 | medium | `DisableFirefoxStudies` | Firefox Studies must be disabled. |

For the full description and recommendation behind every row, run
`ffpolicy preset-info <preset id>` or open **View rule details...** in the GUI.

## The 3 manual/procedural items

These can't be expressed as `policies.json` values at all, so no preset can
cover them - they're operator/deployment actions, tracked here for auditability:

- **V-251545** (high) - Upgrade Firefox to a vendor-supported release; verify
  via Help → About Firefox. Not a policy.
- **V-251550** (medium) - Remove any unauthorized extensions from the
  auto-download MIME type list. Organization-specific; no default is safe to
  assume.
- **V-251560** (medium) - Install the DOD root certificates (via OS
  certificate store / GPO "Import Enterprise Roots", or the `Certificates`
  policy's `ImportEnterpriseRoots`/`Install` fields for CA files you manage
  directly).

## Data provenance and a note on accuracy

Preset values come from each rule's official "Linux `policies.json` file" fix
text in the STIG benchmark, cross-checked against each policy's current
documented shape at `firefox-admin-docs.mozilla.org` (via its GitHub source,
`mozilla/enterprise-admin-reference` - the docs site itself isn't reachable
from every environment). One correction was made during that cross-check:
`FirefoxHome.Locked` is capitalized (`Locked`, not `locked`) to match what
Firefox's schema and DISA's own `about:policies` compliance check actually
require - the STIG's fix-text example itself uses the lowercase form, which
would silently fail to lock the policy in a real deployment.

Where a single policy is set by multiple rules (`Preferences` by 6 rules;
`EnableTrackingProtection` by 2), the preset stores one merged value combining
all of them - applying the preset sets that whole merged object, not each
rule's fragment independently.

## Implementation notes

Since all nine profiles share an identical ruleset for this benchmark, the
bundled resource (`resources/presets/disa_stig.yaml`) stores the values/rules
once and a `profiles` list of `{id, title}` pairs; `core/presets.py`'s
`load_bundled_presets()` expands that into nine distinct `Preset` objects
(sharing a `family` name for GUI/CLI grouping) rather than duplicating ~260
lines of YAML nine times. A resource with no `profiles` key still loads as a
single preset, so this is additive, not a requirement for future presets.
