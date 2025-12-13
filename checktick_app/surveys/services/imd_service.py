"""
IMD Service - Index of Multiple Deprivation lookup.

Provides functionality to look up IMD (Index of Multiple Deprivation)
data from postcodes using the RCPCH Deprivation API.

The IMD is a measure of relative deprivation for small areas in England.
It combines information from seven domains:
- Income
- Employment
- Education, Skills and Training
- Health and Disability
- Crime
- Barriers to Housing and Services
- Living Environment

IMD data is returned as a quantile (decile by default), where:
- 1 = Most deprived 10%
- 10 = Least deprived 10%
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from django.conf import settings
import requests

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class IMDResult:
    """Result from an IMD lookup."""

    postcode: str
    imd_decile: int | None
    imd_rank: int | None
    error: str | None = None

    @property
    def is_valid(self) -> bool:
        """Return True if the lookup was successful."""
        return self.error is None and self.imd_decile is not None


class IMDService:
    """
    Service for looking up Index of Multiple Deprivation data.

    Uses the RCPCH Deprivation API to look up IMD quantile from postcodes.

    Configuration:
        - IMD_API_URL: Base URL for the IMD API
        - IMD_API_KEY: API key for authentication

    API Endpoint:
        GET /deprivation/v1/index_of_multiple_deprivation_quantile
        Parameters:
            - postcode: UK postcode (spaces removed)
            - quantile: Number of quantiles (default 10 for deciles)

    Response format:
        {
            "postcode": "SW1A1AA",
            "imd_decile": 8,
            "imd_rank": 12345,
            ...
        }
    """

    # Default timeout for API requests
    DEFAULT_TIMEOUT = 5

    # Default quantile (10 = deciles)
    DEFAULT_QUANTILE = 10

    @classmethod
    def is_configured(cls) -> bool:
        """Check if the IMD API is configured."""
        api_url = getattr(settings, "IMD_API_URL", None)
        api_key = getattr(settings, "IMD_API_KEY", None)
        return bool(api_url and api_key)

    @classmethod
    def lookup_imd(
        cls,
        postcode: str,
        quantile: int = DEFAULT_QUANTILE,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> IMDResult:
        """
        Look up IMD data for a UK postcode.

        Args:
            postcode: UK postcode (with or without spaces)
            quantile: Number of quantiles (default 10 for deciles)
            timeout: Request timeout in seconds

        Returns:
            IMDResult with imd_decile and imd_rank, or error message if failed

        Example:
            result = IMDService.lookup_imd("SW1A 1AA")
            if result.is_valid:
                print(f"IMD Decile: {result.imd_decile}")
        """
        # Normalize postcode (remove spaces, uppercase)
        clean_postcode = postcode.replace(" ", "").strip().upper()

        if not clean_postcode:
            return IMDResult(
                postcode=postcode,
                imd_decile=None,
                imd_rank=None,
                error="Empty postcode",
            )

        # Check API configuration
        api_url = getattr(settings, "IMD_API_URL", None)
        api_key = getattr(settings, "IMD_API_KEY", None)

        if not api_url or not api_key:
            logger.warning("IMD API not configured")
            return IMDResult(
                postcode=postcode,
                imd_decile=None,
                imd_rank=None,
                error="IMD API not configured",
            )

        try:
            # Build request URL
            # API expects: ?postcode={postcode}&quantile={quantile}
            response = requests.get(
                api_url,
                params={
                    "postcode": clean_postcode,
                    "quantile": quantile,
                },
                headers={
                    "Ocp-Apim-Subscription-Key": api_key,
                },
                timeout=timeout,
            )

            if response.status_code == 200:
                data = response.json()
                # Extract IMD data from response
                # The API returns different field names depending on quantile
                imd_decile = data.get("imd_decile") or data.get("quantile")
                imd_rank = data.get("imd_rank") or data.get("rank")

                if imd_decile is not None:
                    return IMDResult(
                        postcode=postcode,
                        imd_decile=int(imd_decile),
                        imd_rank=int(imd_rank) if imd_rank is not None else None,
                    )
                else:
                    logger.warning(
                        f"IMD API returned no decile for postcode {clean_postcode}: {data}"
                    )
                    return IMDResult(
                        postcode=postcode,
                        imd_decile=None,
                        imd_rank=None,
                        error="No IMD data available for this postcode",
                    )

            elif response.status_code == 404:
                logger.info(f"Postcode not found in IMD data: {clean_postcode}")
                return IMDResult(
                    postcode=postcode,
                    imd_decile=None,
                    imd_rank=None,
                    error="Postcode not found in IMD data",
                )

            else:
                logger.error(
                    f"IMD API error: status={response.status_code}, "
                    f"postcode={clean_postcode}"
                )
                return IMDResult(
                    postcode=postcode,
                    imd_decile=None,
                    imd_rank=None,
                    error=f"API error: {response.status_code}",
                )

        except requests.Timeout:
            logger.error(f"IMD API timeout for postcode: {clean_postcode}")
            return IMDResult(
                postcode=postcode,
                imd_decile=None,
                imd_rank=None,
                error="API timeout",
            )

        except requests.RequestException as e:
            logger.error(f"IMD API request error: {e}")
            return IMDResult(
                postcode=postcode,
                imd_decile=None,
                imd_rank=None,
                error=f"Request error: {str(e)}",
            )

        except (ValueError, KeyError) as e:
            logger.error(f"IMD API response parsing error: {e}")
            return IMDResult(
                postcode=postcode,
                imd_decile=None,
                imd_rank=None,
                error=f"Invalid API response: {str(e)}",
            )
