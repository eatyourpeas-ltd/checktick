---
title: "Protective DNS & Web Filtering Standard"
category: dspt-9-it-protection
---

# Protective DNS & Web Filtering Standard

## 1. Infrastructure DNS (Production)

* **Resolver:** Northflank default secure resolvers (UK-based).
* **Policy:** Our production containers are restricted from making outbound requests to the general internet except for a whitelist of known-good API endpoints (e.g., UK Government OIDC providers).
* **NCSC PDNS:** We have registered our primary domains with the NCSC PDNS to monitor for and block resolution of known malicious domains.

## 2. Endpoint DNS (Staff Laptops)

* **Configuration:** Staff laptops must not use default ISP DNS. They are manually configured to use a filtered PDNS provider (e.g., Quad9 `9.9.9.9` or Cloudflare for Families `1.1.1.2`).
* **Filtering Logic:** These services automatically block resolution for domains categorized as:
    * Malware & Botnet C2
    * Phishing & Deception
    * Known Spyware
* **Verification:** The CTO checks DNS settings during the quarterly hardware audit.

## 3. Browser-Level Protection

* **Safe Browsing:** All browsers used for {{ platform_name }} administrative work (GitHub, Northflank, AWS) must have 'Safe Browsing' technology enabled.
* **Ad-Blocking:** We utilize reputable content-filtering extensions (e.g., uBlock Origin) to mitigate 'Malvertising' risks.
