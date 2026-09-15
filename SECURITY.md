# Security Policy

## Supported Versions

Job Finder is self-hosted and maintained by one person. Security fixes land on `main`
and go out in a new release; older releases are not patched separately.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

If you're running an older release, upgrade to the latest before reporting. The issue
may already be fixed.

## Reporting a Vulnerability

**Please don't open a public issue, discussion or pull request for security problems.**

Report privately in either of these ways:

1. **GitHub (preferred):**
   [Report a vulnerability](https://github.com/lukebrewerton/job-finder/security/advisories/new)
   (Security tab → "Report a vulnerability").
2. **Email:** [vulnerabilities@job-finder.dev](mailto:vulnerabilities@job-finder.dev),
   if you'd rather not use GitHub.

Helpful things to include:

- The affected version or commit
- A description of the issue and its impact
- Steps to reproduce, or a minimal proof of concept
- Any relevant configuration (redact secrets)

### What to expect

This is a personal project maintained in spare time, so the timelines below are
best-effort rather than guarantees:

- **Acknowledgement:** within 7 days.
- **Initial assessment:** within 14 days, confirming whether the report is accepted
  and roughly how severe it is.
- **Updates:** at least every 14 days until it's resolved.

**If accepted:** I'll work on a fix privately in a GitHub security advisory, and may
invite you to collaborate on it. Once a patched release is out, the advisory is
published (with a CVE requested through GitHub where appropriate) and you're credited
unless you'd rather not be. Please keep the details private until then. I aim to
disclose within 90 days of the report.

**If declined:** I'll explain why, for example that it's out of scope, can't be
reproduced, or is intended behaviour. You're welcome to come back with more detail.

### Scope

In scope: the code in this repository (API, worker, web UI) and the Docker images and
Compose files it ships.

Out of scope:

- Vulnerabilities in third-party dependencies with no project-specific impact. Report
  those upstream; Dependabot tracks them here.
- Problems caused by how a particular instance is deployed or configured (exposed
  ports, weak secrets, a misconfigured reverse proxy or OIDC provider).
- Denial of service through volumetric traffic, social engineering, and findings from
  automated scanners with no demonstrated impact.
