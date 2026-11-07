"""Email deliverability validation via DNS.

Used by the ``prune_unconfirmed_users`` cron to identify unconfirmed
accounts whose signup email domain provably cannot receive mail. Bots
commonly sign up with addresses at domains that do not exist at all, so
a DNS check removes those accounts without waiting out the grace period
or sending warning emails that are guaranteed to bounce.

The check is deliberately conservative — a domain is only flagged
invalid when DNS gives a definitive answer:

* the domain does not exist (NXDOMAIN), or
* the domain exists but has neither an MX record nor an address record
  (RFC 5321 "implicit MX" routes mail to the A record when no MX exists).

Anything ambiguous (resolver timeouts, SERVFAIL, unexpected errors)
returns ``UNKNOWN`` so callers fail open and never prune on the basis of
a flaky resolver. Mailboxes that simply do not exist on an otherwise
valid domain cannot be detected here — only a real bounce (NDR) proves
that, and the Graph email backend does not surface those to the app.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
import dns.exception
import dns.resolver

DELIVERABLE = "deliverable"
INVALID = "invalid"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class DomainCheckResult:
    """Outcome of a DNS deliverability check on an email's domain."""

    status: str
    reason: str | None = None

    @property
    def is_invalid(self) -> bool:
        return self.status == INVALID

    @property
    def is_deliverable(self) -> bool:
        return self.status == DELIVERABLE


# Per-process cache so a cron run with many users on the same domain
# (common for bot signups) only performs one DNS query per domain.
_domain_cache: dict[str, DomainCheckResult] = {}


def clear_domain_check_cache() -> None:
    """Clear the per-process domain check cache (used by tests)."""
    _domain_cache.clear()


def check_email_deliverability(email: str, *, resolver=None) -> DomainCheckResult:
    """Check whether the domain of ``email`` can receive mail.

    Returns a ``DomainCheckResult`` with status DELIVERABLE, INVALID, or
    UNKNOWN. Only INVALID means the address provably cannot receive
    mail; UNKNOWN means DNS could not answer and the caller must not act.
    """
    domain = _extract_domain(email)
    if domain is None:
        return DomainCheckResult(INVALID, "malformed email address")

    cached = _domain_cache.get(domain)
    if cached is not None:
        return cached

    result = _check_domain(domain, resolver)
    _domain_cache[domain] = result
    return result


def _extract_domain(email: str) -> str | None:
    """Return the normalised A-label domain of an email address, or None."""
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].strip().rstrip(".").lower()
    if not domain:
        return None
    try:
        # IDNA-encode: rejects malformed labels ("a..b", oversized labels)
        # and converts unicode domains to their xn-- A-label form.
        return domain.encode("idna").decode("ascii")
    except UnicodeError:
        return None


def _check_domain(domain: str, resolver=None) -> DomainCheckResult:
    """Resolve one domain: MX first, then the implicit-MX A record."""
    if resolver is None:
        timeout = getattr(settings, "EMAIL_VALIDATION_DNS_TIMEOUT", 3.0)
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout

    # 1. MX records — the definitive "this domain accepts mail" signal.
    try:
        resolver.resolve(domain, "MX")
        return DomainCheckResult(DELIVERABLE, "MX record found")
    except dns.resolver.NXDOMAIN:
        return DomainCheckResult(INVALID, "email domain does not exist")
    except dns.resolver.NoAnswer:
        pass  # domain exists but has no MX — fall through to the A check
    except (dns.exception.Timeout, dns.resolver.NoNameservers):
        return DomainCheckResult(UNKNOWN, "DNS lookup failed")
    except Exception:
        # Unexpected resolver errors are never treated as invalid.
        return DomainCheckResult(UNKNOWN, "unexpected DNS error")

    # 2. Implicit MX (RFC 5321 §5.1): with no MX record, mail routes to
    #    the domain's A record.
    try:
        resolver.resolve(domain, "A")
        return DomainCheckResult(DELIVERABLE, "address record found (implicit MX)")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        # The MX query already proved the domain exists (NoAnswer, not
        # NXDOMAIN), so a missing A record means there is nowhere for
        # mail to go.
        return DomainCheckResult(
            INVALID, "email domain has no mail exchanger or address record"
        )
    except (dns.exception.Timeout, dns.resolver.NoNameservers):
        return DomainCheckResult(UNKNOWN, "DNS lookup failed")
    except Exception:
        return DomainCheckResult(UNKNOWN, "unexpected DNS error")
