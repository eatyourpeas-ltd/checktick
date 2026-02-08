---
title: "Network Security & Configuration Standard"
category: dspt-9-it-protection
---

# Network Security & Configuration Standard (Section 9)

## 1. Password Management for Network Devices

{{ platform_name }} enforces a "Zero-Default" policy for all networking hardware and software.

* **Immediate Change:** Vendor-supplied default passwords (e.g., 'admin', 'password') must be changed during the initial setup of any networking device (routers, modems, switches).
* **Strength Requirements:** New passwords must meet our "High-Strength" criteria (minimum 12 characters, complex mix) and be stored in the corporate password manager.
* **Unique Identities:** Wherever the hardware supports it, default 'admin' accounts are disabled in favor of individual named accounts for the CTO and SIRO.
* **Cloud Boundary Controls** Our primary network boundary is managed via Northflank's Infrastructure-as-Code (IaC) settings. Access to change these "firewall-equivalent" settings is protected by the same MFA and unique-identity standards as our code repository.

## 2. Remote Access & Management

* **Management Interfaces:** Local management interfaces for networking hardware must not be accessible from the public internet (WAN side).
* **MFA:** Any cloud-based networking console (e.g., Northflank, Domain Registrars) must have Multi-Factor Authentication (MFA) enabled.
* **Just-In-Time (JIT) Management** We do not leave administrative ports (e.g., database ports) open for management. Any direct database access for maintenance is conducted via temporary, authenticated proxy connections that bypass the public internet boundary.

## 3. Annual Review

The CTO performs an annual audit of all registered hardware assets to ensure that firmware is updated and administrative passwords remain unique and secure.

## 4. Device and Network Firewall Policy

{{ platform_name }} enforces a "Defence in Depth" approach to network security across all layers of our architecture.

### 4.1 Network Boundary Controls (Router/Gateway Level)

All administrative staff working with {{ platform_name }} systems must ensure their local network boundary (home/office routers) adheres to the following security requirements:

* **No VPN Services:** We do not utilize corporate VPN services. All access to production infrastructure is via cloud-managed authentication (MFA-protected HTTPS consoles). Unauthorized third-party VPN software on business devices is prohibited.
* **DMZ Disabled:** Demilitarized Zone (DMZ) functionality must be disabled on all routers. No devices should be placed outside the protection of the router's firewall.
* **UPnP Disabled:** Universal Plug and Play (UPnP) must be switched off to prevent automatic port forwarding and unauthorized device discovery.
* **Port Forwarding Disabled:** No inbound port forwarding rules are permitted except where explicitly documented and approved in the Infrastructure Technical Change Log. Default configuration must be "Deny All Inbound."
* **Remote Management Disabled:** Router administrative interfaces must not be accessible from the public internet (WAN side).

**Current Network Equipment:**

* BT Smart Hub 2 (boundary router/firewall)
* Administrative access: Local network only (192.168.1.254)
* Admin password: Changed from default, stored in Bitwarden (CTO access only)

* **Verification Schedule:** Router firewall configurations are verified bi-annually (June and December) as documented in the Annual Compliance Checklist. The CTO logs into the router administrative interface to confirm:
  * Zero port forwarding rules enabled
  * DMZ disabled
  * UPnP disabled
  * Remote management disabled

### 4.2 Endpoint Device Firewalls (Workstations/Laptops)

All devices used to access {{ platform_name }} administrative systems must have their native operating system firewalls activated:

* **macOS Devices:** 
  - Application Firewall must be enabled
  - **Stealth Mode** must be activated to prevent device discovery on public networks
  - Block all incoming connections except those explicitly required for approved business applications
* **Windows Devices:**
  - Windows Defender Firewall must be enabled for all network profiles (Domain, Private, Public)
  - Block all incoming connections that are not approved
  - Stealth mode equivalent settings enabled
* **Linux Devices:**
  - UFW (Uncomplicated Firewall) or iptables must be configured to deny all inbound by default
  - Only allow specific outbound connections required for business operations

### 4.3 Compliance Verification & Review Schedule

The above firewall requirements are verified during:

* **Annual Infrastructure & Firewall Review:** Performed in February each year as documented in [Infrastructure Technical Change Log](infrastructure-technical-change-log.md)
* **Bi-annual Security Review & Firewall Audit:** Conducted in June and December each year as documented in [Security Review Log](security-review-log.md)
* **Quarterly Device Compliance Spot Checks:** During Q1-Q4 access reviews as per [Annual Compliance Checklist](annual-compliance-checklist-2026.md)

Any device found to be non-compliant with these firewall requirements must be immediately disconnected from administrative access until remediated.

**Last Policy Review:** 08/02/2026
**Next Policy Review:** 08/02/2027
**Policy Owner:** {{ cto_name }} (CTO/SIRO)

## 5. Protection of Administrative Interfaces

As {{ platform_name }} utilizes cloud-managed boundaries, the following controls are mandatory for the Northflank and Domain Management consoles:

* **MFA Enforcement:** Every administrative account must utilize TOTP or FIDO2 hardware keys.
* **Audit Logging:** We rely on the provider's immutable audit logs to monitor for configuration changes. These logs are reviewed by the SIRO quarterly.
* **Infrastructure as Code (IaC):** To ensure 'Roll-back' capability, network ingress rules are documented in our repository. Any manual change in the console must be reconciled with the repository within 24 hours to ensure the 'Source of Truth' remains valid.
* **Session Security:** Management sessions must be conducted over encrypted TLS 1.2+ connections and are configured to auto-terminate after 60 minutes of inactivity.

## 6. Inbound Connection Verification (Default Deny)

**Last Verified:** 08/02/2026
**Verified By:** {{ siro_name }} (CTO)

The following inbound protocol checks have been performed on the production boundary:

| Protocol / Port | Status | Justification |
| :--- | :--- | :--- |
| **HTTP (80)** | **Blocked** | Redirected to 443 at Load Balancer |
| **HTTPS (443)** | **Open** | Required for Production Web Traffic |
| **SMB/NetBIOS (137-139, 445)** | **Blocked** | High Risk - Not utilized |
| **Telnet/SSH (22, 23)** | **Blocked** | SSH managed via Northflank internal console |
| **Database (5432)** | **Blocked** | Database is on a private subnet; no WAN access |
| **TFTP/RPC/Rlogin** | **Blocked** | Not installed in container images |

**Note:** All container images are based on minimal distros (e.g., Alpine or Distroless) to ensure that even if a firewall rule failed, the underlying OS does not contain the binaries for these insecure protocols.

## 7. Authorized Inbound Rule Register

The following rules represent the only permitted exceptions to our 'Deny-All' boundary policy.

| Rule ID | Port | Protocol | Source | Destination | Business Justification | Approved By |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| FW-01 | 443 | TCP (HTTPS) | Any (Public) | Load Balancer | Primary application ingress for users. | {{ siro_name }} (CTO) |
| FW-02 | 80 | TCP (HTTP) | Any (Public) | Load Balancer | Redirect only; to force upgrade to TLS. | {{ siro_name }} (CTO) |

**Note on Internal Traffic:** All other service communication (e.g., App to Database) occurs over a private, non-routable service mesh and does not require boundary firewall exceptions.

**Review Date:** 03/01/2026
**Next Review:** 03/04/2026
