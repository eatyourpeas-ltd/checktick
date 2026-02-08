---
title: "Network Security & Infrastructure Statement"
category: dspt-9-it-protection
---

# Network Security & Infrastructure Statement

## 1. Network Architecture

{{ platform_name }} is deployed on Northflank using a multi-tier architecture:

* **Public Tier:** Only the Load Balancer/Ingress is public-facing, accepting traffic only on Port 443 (HTTPS).
* **Application Tier:** Django containers reside in a private network. They handle logic and authentication.
* **Data Tier:** PostgreSQL and HashiCorp Vault are isolated in a private subnet with **zero public internet access**.

## 2. Encryption Standards

* **In-Transit:** We enforce TLS 1.2 as a minimum (TLS 1.3 preferred). We use HSTS (HTTP Strict Transport Security) to prevent protocol downgrade attacks.
* **Internal:** Traffic between the Load Balancer and our containers travels over the provider's secure private backbone.

## 3 Boundary Protection (Firewall)

**Cloud Infrastructure:**

* **Ingress Rules:** Northflank manages our firewall rules. All ports except 443 are blocked by default.
* **Egress Rules:** Our containers are restricted to communicating only with verified external services (e.g., OIDC providers, SendGrid) via secure encrypted channels.

**Local Network (Development/Administrative Access):**

* BT Smart Hub 2 router configured with default-deny inbound policy
* All administrative access to cloud services conducted from devices on trusted local network
* Software firewalls enabled on all endpoint devices (macOS Application Firewall with Stealth Mode)

## 4. Application-Layer Defense

* **django-ratelimit:** Applied to login and recovery endpoints to block IP-based flooding.
* **django-axes:** Integrated to provide account-level lockouts.
* **IP Preservation:** We maintain the `X-Forwarded-For` headers to ensure our logs accurately reflect the source of network traffic for forensic audit.
