"""
Address Lookup Service — UK postcode → address prefill.

Configuration (settings):
- ``ADDRESS_LOOKUP_API_URL`` (optional): an address-capable API endpoint.
  If unset, falls back to ``POSTCODES_API_URL``.
- ``ADDRESS_LOOKUP_API_KEY`` (optional): sent as an ``Ocp-Apim-Subscription-Key``
  header when present. Falls back to ``POSTCODES_API_KEY``.

Two response shapes are understood:

1. postcodes.io style::

    {"status": 200, "result": [ {"line_1": ..., "post_town": ...}, ... ]}

   (``result`` may also be a single object; handled.) Note: the open
   postcodes.io service returns postcode *metadata* only (district, ward,
   IMD) — it contains no delivery-point addresses, so this shape only
   prefills when the backing dataset actually includes addresses.

2. OS Places / DPA style (OS Data Hub Places API and compatible proxies)::

    {"results": [ {"DPA": {"ADDRESS": "1 HIGH STREET, LONDON, SW1A 1AA", ...}}, ... ]}

Coverage: ONSPD-derived sources cover England, Scotland, Wales and the Isle
of Man; Northern Ireland (BT) and Channel Islands (GY/JE) postcodes are not
included, so callers must always allow manual address entry as a fallback.

Logging: postcodes are potentially personal data. Never log the postcode
itself, request URLs with postcodes, or response bodies — log status codes
and error classes only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re

from django.conf import settings
import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5

ADDRESS_FIELD_KEYS = ("address_line_1", "address_line_2", "town_city", "county")


@dataclass
class AddressLookupResult:
    """Result from a postcode address lookup."""

    postcode: str
    addresses: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None

    @property
    def is_valid(self) -> bool:
        """Return True if the lookup returned at least one address."""
        return self.error is None and bool(self.addresses)


class AddressLookupService:
    """Service for looking up addresses for a UK postcode."""

    @classmethod
    def _api_base(cls) -> str | None:
        """Base URL for the lookup API (address-capable, else postcode API).

        Normalises common paste-from-docs mistakes: resolves the ``{path}``
        placeholder of OS Data Hub URL templates to ``find``, strips any query
        string (e.g. an embedded ``?key=...`` — the key is appended
        per-request), and warns if the OS Names API (place names only, no
        addresses) is configured instead of the OS Places API.
        """
        url = getattr(settings, "ADDRESS_LOOKUP_API_URL", None) or getattr(
            settings, "POSTCODES_API_URL", None
        )
        if not url:
            return None
        if "{path}" in url:
            url = url.replace("{path}", "find")
            logger.info(
                "Address lookup URL contained a {path} placeholder; resolved to find"
            )
        url = url.split("?", 1)[0]
        if "/names/" in url:
            logger.warning(
                "Address lookup URL appears to be the OS Names API (place names "
                "only, no addresses); use https://api.os.uk/search/places/v1/find"
            )
        # No forced trailing slash: OS-style URLs must end at "find", while
        # path-append style gets its slash added at call time.
        return url

    @classmethod
    def _api_key(cls) -> str | None:
        """API key for the lookup API (falls back to the postcode API key)."""
        return getattr(settings, "ADDRESS_LOOKUP_API_KEY", None) or getattr(
            settings, "POSTCODES_API_KEY", None
        )

    @classmethod
    def is_configured(cls) -> bool:
        """Check whether the address lookup API is configured."""
        return bool(cls._api_base())

    @classmethod
    def lookup(
        cls, postcode: str, timeout: int = DEFAULT_TIMEOUT
    ) -> AddressLookupResult:
        """
        Look up addresses for a UK postcode.

        Args:
            postcode: UK postcode (with or without spaces)
            timeout: Request timeout in seconds

        Returns:
            AddressLookupResult with a list of normalised addresses
            (``line_1``, ``line_2``, ``town_city``, ``county``, ``postcode``
            plus a ``summary`` for display in a select), or an error message.
        """
        postcode_norm = (postcode or "").replace("  ", " ").strip().upper()
        clean = postcode_norm.replace(" ", "")
        if not clean:
            return AddressLookupResult(postcode=postcode, error="Empty postcode")

        api_url = cls._api_base()
        if not api_url:
            logger.warning("Address lookup API not configured")
            return AddressLookupResult(
                postcode=postcode, error="Address lookup not configured"
            )

        api_key = cls._api_key()
        # OS Data Hub search APIs take the postcode, maxresults and key as
        # query parameters; path-style APIs (postcodes.io and APIM-style
        # proxies) append the postcode to the URL and pass the key via the
        # Ocp-Apim-Subscription-Key header.
        os_style = "/find" in api_url or "/places/" in api_url
        if os_style:
            # Normalise OS Places URLs to the dedicated postcode endpoint:
            # 'find' is fuzzy text search, 'postcode' returns every delivery
            # point at the postcode.
            m = re.search(r"/places/v\d+/", api_url)
            if m:
                api_url = api_url[: m.end()] + "postcode"
            elif not api_url.endswith("postcode"):
                api_url = api_url.rstrip("/") + "/postcode"
        if not os_style and not api_url.endswith("/"):
            api_url += "/"
        headers: dict[str, str] = {}
        params: dict[str, str] = {}
        if os_style:
            params = {"postcode": postcode_norm, "maxresults": "100"}
            if api_key:
                params["key"] = api_key
        else:
            if api_key:
                headers["Ocp-Apim-Subscription-Key"] = api_key

        try:
            response = requests.get(
                api_url if os_style else f"{api_url}{clean}",
                headers=headers or None,
                params=params or None,
                timeout=timeout,
            )
        except requests.Timeout:
            logger.error("Address lookup API timeout")
            return AddressLookupResult(postcode=postcode, error="Lookup timed out")
        except requests.RequestException as e:
            logger.error(f"Address lookup API request error: {type(e).__name__}")
            return AddressLookupResult(postcode=postcode, error="Lookup failed")

        if response.status_code == 404:
            # Common for valid-format but unknown postcodes (e.g. NI on ONSPD)
            logger.info("Address lookup: postcode not found")
            return AddressLookupResult(
                postcode=postcode, error="No addresses found for this postcode"
            )
        if response.status_code != 200:
            logger.error(f"Address lookup API error: status={response.status_code}")
            return AddressLookupResult(postcode=postcode, error="Lookup failed")

        try:
            data = response.json()
        except ValueError:
            logger.error("Address lookup API returned invalid JSON")
            return AddressLookupResult(postcode=postcode, error="Lookup failed")

        addresses: list[dict[str, str]] = []
        if isinstance(data, dict):
            result = data.get("result")
            if isinstance(result, dict):
                result = [result]
            if isinstance(result, list):
                addresses = [
                    cls._normalise(entry) for entry in result if isinstance(entry, dict)
                ]
            else:
                # OS Places / DPA shape: {"results": [{"DPA": {...}}, ...]}
                places = data.get("results")
                if isinstance(places, list):
                    addresses = [
                        cls._normalise_dpa(entry["DPA"])
                        for entry in places
                        if isinstance(entry, dict)
                        and isinstance(entry.get("DPA"), dict)
                    ]
        addresses = [a for a in addresses if a["line_1"]]
        if not addresses:
            logger.info("Address lookup: no results in response")
            return AddressLookupResult(
                postcode=postcode, error="No addresses found for this postcode"
            )
        return AddressLookupResult(postcode=postcode, addresses=addresses)

    @staticmethod
    def _normalise(entry: dict) -> dict[str, str]:
        """Normalise a postcodes.io result entry into flat address fields."""
        line_2 = " ".join(
            part
            for part in (
                str(entry.get("line_2") or "").strip(),
                str(entry.get("line_3") or "").strip(),
            )
            if part
        )
        town = (
            str(entry.get("post_town") or "").strip()
            or str(entry.get("dependant_locality") or "").strip()
        )
        return {
            "line_1": str(entry.get("line_1") or "").strip(),
            "line_2": line_2,
            "town_city": town,
            "county": str(entry.get("county") or "").strip(),
            "postcode": str(entry.get("postcode") or "").strip(),
            "summary": " ".join(
                part
                for part in (
                    str(entry.get("line_1") or "").strip(),
                    line_2,
                    town,
                )
                if part
            ),
        }

    @staticmethod
    def _normalise_dpa(entry: dict) -> dict[str, str]:
        """Normalise an OS Places DPA entry into flat address fields.

        The DPA ``ADDRESS`` field is the preformatted delivery point address,
        comma-joined with the postcode last (e.g. "1 HIGH STREET, LONDON,
        SW1A 1AA").
        """
        raw = str(entry.get("ADDRESS") or "")
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        postcode = str(entry.get("POSTCODE") or "").strip()
        if len(parts) >= 2 and parts[-1].upper() == postcode.upper():
            parts = parts[:-1]
        town = str(entry.get("POST_TOWN") or "").strip()
        if len(parts) >= 2 and parts[-1].upper() == town.upper():
            parts = parts[:-1]
        line_1 = parts[0] if parts else ""
        line_2 = ", ".join(parts[1:]) if len(parts) > 1 else ""
        return {
            "line_1": line_1,
            "line_2": line_2,
            "town_city": town,
            "county": "",
            "postcode": postcode,
            "summary": " ".join(p for p in (line_1, line_2, town) if p),
        }
