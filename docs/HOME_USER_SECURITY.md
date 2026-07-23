# Home User Security Profiles

This document describes the Home User Security profiles bundled with firefox-policy-generator. These profiles provide balanced security and privacy configurations for individuals, families, and small offices that prioritize protection without sacrificing usability.

## Overview

Home users face unique security challenges:
- **Tracking & Profiling**: Advertisers, data brokers, and websites track browsing behavior across the internet
- **Malware & Exploit Kits**: Drive-by downloads and malicious ads can compromise systems
- **Privacy Erosion**: ISPs, governments, and platforms collect extensive surveillance data
- **Social Engineering**: Phishing, scams, and credential theft target individuals

The Home User Security profiles implement Mozilla's security recommendations and NIST cybersecurity best practices to mitigate these threats while maintaining the flexibility home users need for legitimate browsing, shopping, and entertainment.

## Profile Levels

The Home User Security preset includes three profiles:

### Strict

**Recommended For**:
- Users handling financial or medical information
- Activist, journalist, or high-value attack targets
- Users on public/shared networks
- Those willing to sacrifice some convenience for maximum privacy

**Key Controls**:
- Blocks all browser extension installation (administrator whitelist only)
- Disables password manager (requires manual credential entry)
- Blocks search suggestions
- Maximum tracking/fingerprinting protection
- Blocks all risky permissions by default
- Clears all data on shutdown

**Command Line Usage**:

```bash
python -m ffpolicy generate --preset home_user_security__strict -o policies.json
python -m ffpolicy export --preset home_user_security__strict --target system_linux
```

**Trade-offs**:
- No password generator/storage convenience
- Manual extension management required
- Search suggestions (helpful feature) disabled
- More restrictive user experience

### Balanced (Recommended)

**Recommended For**:
- Most home users and small office environments
- Families wanting to balance security with ease of use
- Users with typical browsing habits (social media, email, news, shopping)
- Default recommendation

**Key Controls**:
- Allows user-selected browser extensions (users responsible for vetting)
- Enables password manager for strong password generation/storage
- Disables search suggestions by default
- Strong tracking protection (fingerprinting, cryptomining blocking)
- Blocks risky permissions by default
- Clears history/cache on exit, keeps cookies for login persistence

**Command Line Usage**:

```bash
python -m ffpolicy generate --preset home_user_security__balanced -o policies.json
python -m ffpolicy export --preset home_user_security__balanced --target system_linux
```

**Trade-offs**:
- Trusts users to choose extensions wisely (education recommended)
- Stores passwords locally (require system password/PIN)
- Still blocks most convenience features (suggestions, data collection)

**Recommended Extensions** (Users should vet these):
- **uBlock Origin** - Ad and tracker blocking
- **HTTPS Everywhere** - Forces HTTPS connections
- **Bitwarden** - Cross-device password manager
- **Privacy Badger** - Tracker and fingerprinting protection

### Relaxed

**Recommended For**:
- Users who prioritize convenience over maximum privacy
- Low-risk browsing (not handling sensitive information)
- Casual internet users and entertainment
- Those who accept some data collection trade-offs

**Key Controls**:
- Allows extension installation with user choice
- Enables password manager
- Enables search suggestions for convenience
- Strong tracking protection still active
- Blocks most risky permissions
- Clears sensitive data on shutdown

**Command Line Usage**:

```bash
python -m ffpolicy generate --preset home_user_security__relaxed -o policies.json
python -m ffpolicy export --preset home_user_security__relaxed --target system_linux
```

**Trade-offs**:
- Receives more targeted ads through suggestions/recommendations
- Stores more data locally
- Still blocks telemetry but allows feature recommendations
- Easiest to use for casual browsing

## Profile Comparison

| Feature | Strict | Balanced | Relaxed |
|---------|--------|----------|---------|
| Extensions | Blocked | User choice | User choice |
| Password Manager | Disabled | Enabled | Enabled |
| Search Suggestions | Disabled | Disabled | Enabled |
| Tracking Protection | Maximum | Strong | Strong |
| Telemetry | Disabled | Disabled | Disabled |
| Feature Recommendations | Blocked | Blocked | Enabled |
| Private Browsing | Available | Available | Available |
| DNS-over-HTTPS | Enabled | Enabled | Enabled |
| TLS Minimum | 1.2 | 1.2 | 1.2 |
| Data on Shutdown | Clear All | Clear Sensitive | Clear Sensitive |
| **Typical User** | Security-focused | Most users | Convenience-focused |
| **Setup Time** | Low | Low | Low |
| **Training Needed** | No | Extension vetting | No |

## Privacy Features Explained

### Tracking Protection (Strict)

Firefox's Tracking Protection blocks known trackers while you browse. The "Strict" mode blocks:

- **Cookies from third-party sites** (prevent cross-site tracking)
- **Tracking content** (ads/analytics scripts that follow you across sites)
- **Cryptomining scripts** (malicious code that uses your CPU to mine cryptocurrency)
- **Fingerprinting scripts** (techniques that identify you uniquely without cookies)

**Impact**: Websites may load slightly slower; some sites may require exceptions.

### DNS-over-HTTPS (DoH)

Standard DNS queries are unencrypted, allowing your ISP to see every website you visit:

```
You → [unencrypted DNS query] → ISP → [sees: "example.com"] → ISP's DNS Server
```

DNS-over-HTTPS encrypts the query:

```
You → [HTTPS encrypted] → DoH Provider → [decrypted] → DNS Server
```

This prevents ISP surveillance but means your DoH provider sees your queries instead. Firefox defaults to Cloudflare's DoH (which publishes privacy policies) but can be configured for other providers.

### Data Sanitization on Shutdown

When enabled, Firefox automatically clears:
- **Cache** (temporary website files)
- **Cookies** (site login sessions, tracking cookies)
- **History** (list of visited websites)
- **Site data** (local storage, service worker data)
- **Sessions** (open tabs, forms)

This prevents:
- Other computer users from seeing browsing history
- Websites from re-identifying you on next visit
- Malicious scripts from persistent tracking

**Trade-off**: You'll need to re-login to sites on each session (unless you whitelist important sites).

### Disabled Telemetry

Firefox collects telemetry including:
- Crash reports
- Hardware information
- Add-on and extension data
- Search engine queries
- Performance metrics
- Usage patterns

All profiles disable this telemetry to prevent Mozilla from building usage profiles.

## Deployment Scenarios

### Single User, Personal Computer

```bash
python -m ffpolicy generate --preset home_user_security__balanced -o policies.json

# For GUI configuration
python -m ffpolicy
# In GUI: Import the policies.json to review settings
# Adjust any settings you want to customize
```

### Family Computer (Shared Multi-User)

Use **Strict** profile with parent account oversight:

```bash
python -m ffpolicy generate --preset home_user_security__strict -o policies.json

# Deploy to system Firefox on shared family computer
python -m ffpolicy export --preset home_user_security__strict \
  --target system_linux
```

Add administrative controls:
- Parent account controls `about:config` access
- Children can't install extensions without approval
- All browsing data cleared on logout

### Small Office (Multiple Staff)

Use **Balanced** profile as organizational baseline:

```bash
# Start with balanced baseline
python -m ffpolicy generate --preset home_user_security__balanced -o baseline.json

# Customize for your organization
python -m ffpolicy import baseline.json -o office_config.yaml

# Edit office_config.yaml to add:
# - Organization proxy
# - Approved extensions (security tools, communication apps)
# - Company homepage/intranet
# - SSL certificate pinning for internal sites
```

Then distribute to all office computers:

```bash
python -m ffpolicy generate office_config.yaml -o office_policies.json
python -m ffpolicy export office_policies.json \
  --target system_linux --elevate
```

## Customization Examples

### Add Extensions to Strict Profile

Start with strict, whitelist approved extensions:

```yaml
# Extract strict profile
python -m ffpolicy generate --preset home_user_security__strict -o base.json

# Edit base.json to add extensions (e.g., password manager + ad blocker)
{
  "policies": {
    "ExtensionSettings": {
      "*": {
        "installation_mode": "blocked"
      },
      "ublock0@raymondhill.net": {
        "installation_mode": "allowed"
      },
      "{d50a5053-bc23-4b38-84a1-7cb1b4446340}": {
        "installation_mode": "force_installed",
        "install_url": "https://addons.mozilla.org/firefox/downloads/file/..."
      }
    }
  }
}
```

### Add Organization Proxy to Balanced Profile

```bash
python -m ffpolicy generate --preset home_user_security__balanced -o base.json

# Edit to add proxy
python -m ffpolicy import base.json -o config.yaml
```

Then edit `config.yaml`:

```yaml
Proxy:
  Mode: manual
  HTTPProxy: proxy.company.com:8080
  SSLProxy: proxy.company.com:8080
  NoProxy: 'localhost, *.company.local'
  Locked: true

Preferences:
  'network.proxy.http': 'proxy.company.com'
  'network.proxy.http_port': 8080
```

### Set Custom Homepage

```bash
python -m ffpolicy import base.json -o custom.yaml
```

Edit `custom.yaml`:

```yaml
Homepage:
  URL: 'https://mysite.example.com'
  Locked: false  # Allow users to change if desired

Preferences:
  'browser.startup.homepage': 'https://mysite.example.com'
```

## Installation & Deployment

### Windows Computers

```bash
# Generate for Windows (policies.json location varies by Firefox installation)
python -m ffpolicy generate --preset home_user_security__balanced -o policies.json

# Deploy to Program Files
copy policies.json "C:\Program Files\Mozilla Firefox\distribution\"

# Or via Group Policy (convert to ADMX template first - requires additional tools)
```

### macOS

```bash
python -m ffpolicy generate --preset home_user_security__balanced -o policies.json

# Deploy to system-wide Firefox
sudo mkdir -p /Library/Application\ Support/Firefox/policies
sudo cp policies.json /Library/Application\ Support/Firefox/policies/
```

### Linux (Debian/Ubuntu)

```bash
python -m ffpolicy export --preset home_user_security__balanced \
  --target linux_lib_distribution
# Requires sudo - will prompt for password
```

Or manual deployment:

```bash
python -m ffpolicy generate --preset home_user_security__balanced -o policies.json

sudo mkdir -p /usr/lib/firefox/distribution
sudo cp policies.json /usr/lib/firefox/distribution/
sudo chown root:root /usr/lib/firefox/distribution/policies.json
```

## Troubleshooting

### "Website doesn't work with tracking protection enabled"

Some websites break with strict tracking protection. Disable it for that site:

1. Click shield icon in address bar
2. Click "Blocking is ON for this site"
3. Select "Disable for this site"

Or whitelist in policies:

```yaml
EnableTrackingProtection:
  Cryptomining: true
  Fingerprinting: true
  Locked: false  # Allow user overrides

Preferences:
  'browser.contentblocking.category':
    Value: 'standard'  # Less strict than 'strict'
    Status: 'unlocked'  # Allow users to change
```

### "I forgot my password and password manager is disabled"

In **Strict** profile, passwords aren't stored. Options:

1. Use site's "Forgot Password" feature
2. Switch to **Balanced** profile which allows password manager
3. Use external password manager (Bitwarden, 1Password)

### "DNS-over-HTTPS breaks my corporate proxy"

In corporate environments, DoH may need to be disabled:

```yaml
DNSOverHTTPS:
  Enabled: false
```

Contact your IT department to configure proxy-compatible DNS resolution.

## Extension Recommendations

For users on **Balanced** or **Relaxed** profiles:

### Essential for Privacy

- **uBlock Origin** - Blocks ads and trackers (most effective ad blocker)
- **Privacy Badger** - Electronic Frontier Foundation's tracker blocker
- **HTTPS Everywhere** - Forces encrypted connections

### Optional for Convenience

- **Bitwarden** - Cross-device password manager alternative to Firefox's built-in
- **Dark Reader** - Adds dark mode to websites
- **Tab Session Manager** - Saves and restores browser sessions

### Avoid

- "Cleaner" extensions (claim to speed up browser but often ship adware)
- Obscure ad blockers (may contain malware or spy on you)
- VPN extensions (use system VPN instead for better security)

## Related Documents

- **DISA STIG Firefox Profile**: See `DISA_STIG.md` for government endpoint standards
- **NIST SP 800-171**: See `NIST_SP_800_171.md` for Controlled Unclassified Information protection
- **Mozilla Security Recommendations**: https://www.mozilla.org/en-US/firefox/security/
- **EFF's Privacy Badger**: https://privacybadger.org/

## FAQ

**Q: Why disable password manager in Strict profile?**
A: High-security users typically use centralized credential management (Bitwarden, corporate password vault) instead of browser storage. Disabling it encourages using external tools that can be monitored and audited.

**Q: Is Balanced profile actually private?**
A: Balanced profile provides good privacy for typical users without being overly restrictive. It blocks most tracking, but accepts some convenience trade-offs (suggestions, password storage). For absolute privacy, use Strict.

**Q: Can I mix settings from different profiles?**
A: Yes! Start with Balanced, import to YAML, customize, then re-generate. The tool supports incremental configuration.

**Q: Do I need this if I use a VPN?**
A: VPNs hide your IP from websites but don't prevent tracking via cookies, fingerprinting, or behavioral patterns. Use both: VPN for network privacy + this profile for website privacy.

**Q: How do I know if tracking protection is working?**
A: Visit https://coveryourtracks.eff.org - it reports how resistant you are to fingerprinting. Look for shield icon in address bar showing blocked trackers.

**Q: Can I update the profile later?**
A: Yes. Generate a new policies.json anytime, then re-export. Firefox will apply updated settings on next restart.

## Version History

- **v1.0** (2026-07-23): Initial Home User Security profiles (Strict, Balanced, Relaxed)
