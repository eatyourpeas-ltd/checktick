---
title: "IP Address Management (IPAM) Register"
category: dspt-4-managing-access
---

# IP Address Management (IPAM) Register

**Last Reviewed:** March 2026
**Owner:** Dr Simon Chapman (CTO)

## 1. Production Infrastructure (Northflank)

| Asset | Type | IP Address / Range | Purpose |
| :--- | :--- | :--- | :--- |
| Web Production | Ingress | Assigned by Northflank — recorded in Northflank console | Public access to CheckTick web application |
| Service Egress | Egress | Assigned by Northflank — recorded in Northflank console | Outbound requests to OIDC providers and mail delivery services |
| Database | Internal | Northflank private network (not publicly routable) | Internal communication between application and PostgreSQL |
| Vault | Internal | Northflank private network (not publicly routable) | Internal communication between application and HashiCorp Vault |

Specific IP values are recorded in the Northflank console and reviewed
quarterly by the CTO. Production ingress and egress IPs are noted for
reference when registering with external services such as NCSC Early Warning.

## 2. Administrative Access (EatYourPeas Ltd Staff)

| Person | Access Method | IP Configuration | Security Control |
| :--- | :--- | :--- | :--- |
| Dr Simon Chapman (CTO) | Home broadband (dynamic IP) | No IP restriction — dynamic ISP-assigned address | MFA enforced on all administrative accounts |
| Dr Serena Haywood (SIRO) | Home broadband (dynamic IP) | No IP restriction — dynamic ISP-assigned address | MFA enforced on all administrative accounts |

EatYourPeas Ltd operates as a fully remote organisation. Both administrators
connect from home broadband connections with ISP-assigned dynamic IP addresses.
IP-based access restrictions are not applied as the IP addresses are not
static. Access to all administrative systems is instead controlled through
mandatory MFA on individually named accounts, which provides equivalent or
superior protection — a stolen credential cannot be used without the
registered hardware authenticator regardless of the source IP address.

## 3. Review Process

The CTO reviews all IP ranges and infrastructure networking configuration
quarterly, confirming that production IP assignments in Northflank are
current and that no unauthorised ingress rules have been added. Any change
to production IP assignments is logged in the Infrastructure Technical
Change Log. Reviews are documented in the Internal Audit and Spot Check Log.
