"""Product lookup service for protea.

Provides product information lookup from barcodes (UPC/EAN) and ASINs.
Uses UPCitemdb API for barcode lookups (free tier: 100 requests/day).
"""

import logging

import requests

from protea.config import settings

logger = logging.getLogger("protea")

# UPCitemdb API endpoints
UPCITEMDB_TRIAL_URL = "https://api.upcitemdb.com/prod/trial/lookup"
UPCITEMDB_PAID_URL = "https://api.upcitemdb.com/prod/v1/lookup"


class ProductLookupService:
    """Service for looking up product information from barcodes/ASINs.

    Currently a stub - returns mock data.
    Future: Integrate with Amazon Product API and UPCitemdb.
    """

    def __init__(self):
        """Initialize product lookup service."""
        self.amazon_configured = bool(
            settings.amazon_product_api_key
            and settings.amazon_product_api_secret
            and settings.amazon_partner_tag
        )
        self.upcitemdb_configured = bool(settings.upcitemdb_api_key)

    def lookup_asin(self, asin: str) -> dict:
        """Look up product by Amazon ASIN.

        Args:
            asin: Amazon Standard Identification Number

        Returns:
            Product information dict
        """
        if not self.amazon_configured:
            logger.debug("Amazon Product API not configured")
            return self._stub_response(asin, "asin")

        # TODO: Implement real Amazon Product API lookup
        # from paapi5_python_sdk.api.default_api import DefaultApi
        # ...

        return self._stub_response(asin, "asin")

    def lookup_upc(self, upc: str) -> dict:
        """Look up product by UPC barcode using UPCitemdb API.

        Args:
            upc: Universal Product Code (or EAN)

        Returns:
            Product information dict
        """
        # Choose endpoint based on whether API key is configured
        if self.upcitemdb_configured:
            url = UPCITEMDB_PAID_URL
            headers = {
                "user_key": settings.upcitemdb_api_key,
                "key_type": "3scale",
            }
        else:
            # Use free trial endpoint (100 requests/day, no key needed)
            url = UPCITEMDB_TRIAL_URL
            headers = {}

        try:
            logger.debug(f"Looking up UPC: {upc}")
            response = requests.get(
                url,
                params={"upc": upc},
                headers=headers,
                timeout=10,
            )

            if response.status_code == 429:
                logger.warning("UPCitemdb rate limit exceeded")
                return {
                    "found": False,
                    "code": upc,
                    "code_type": "upc",
                    "error": "Rate limit exceeded (100 requests/day for free tier)",
                    "error_code": "RATE_LIMITED",
                }

            if response.status_code != 200:
                logger.warning(f"UPCitemdb API error: {response.status_code}")
                return {
                    "found": False,
                    "code": upc,
                    "code_type": "upc",
                    "error": f"API error: {response.status_code}",
                    "error_code": "API_ERROR",
                }

            data = response.json()

            # Check if product was found
            if data.get("code") == "OK" and data.get("items"):
                item = data["items"][0]  # Use first match
                return {
                    "found": True,
                    "code": upc,
                    "code_type": "upc",
                    "name": item.get("title"),
                    "description": item.get("description"),
                    "brand": item.get("brand"),
                    "category": item.get("category"),
                    "image_url": item.get("images", [None])[0] if item.get("images") else None,
                    "contents": [],
                    "source_url": item.get("offers", [{}])[0].get("link")
                    if item.get("offers")
                    else None,
                    "ean": item.get("ean"),
                    "upc": item.get("upc"),
                    "asin": item.get("asin"),
                    "model": item.get("model"),
                    "lowest_price": item.get("lowest_recorded_price"),
                    "highest_price": item.get("highest_recorded_price"),
                }
            else:
                return {
                    "found": False,
                    "code": upc,
                    "code_type": "upc",
                    "name": None,
                    "description": None,
                    "message": "Product not found in database",
                }

        except requests.exceptions.Timeout:
            logger.warning("UPCitemdb API timeout")
            return {
                "found": False,
                "code": upc,
                "code_type": "upc",
                "error": "API request timed out",
                "error_code": "TIMEOUT",
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"UPCitemdb API request failed: {e}")
            return {
                "found": False,
                "code": upc,
                "code_type": "upc",
                "error": f"API request failed: {str(e)}",
                "error_code": "REQUEST_ERROR",
            }

    def lookup_ean(self, ean: str) -> dict:
        """Look up product by EAN barcode.

        Args:
            ean: European Article Number

        Returns:
            Product information dict
        """
        # EAN lookup can use same services as UPC
        return self.lookup_upc(ean)

    def lookup(self, code: str, code_type: str | None = None) -> dict:
        """Look up product by any code type.

        Args:
            code: Product code
            code_type: Type hint ("asin", "upc", "ean")

        Returns:
            Product information dict
        """
        # Auto-detect code type if not specified
        if not code_type:
            code_type = self._detect_code_type(code)

        if code_type == "asin":
            return self.lookup_asin(code)
        elif code_type in ("upc", "ean"):
            return self.lookup_upc(code)
        else:
            return self._stub_response(code, "unknown")

    def _detect_code_type(self, code: str) -> str:
        """Detect the type of product code.

        Args:
            code: Product code to analyze

        Returns:
            Code type string
        """
        code = code.strip().upper()

        # ASIN: 10 alphanumeric starting with B0
        if len(code) == 10 and code.startswith("B0"):
            return "asin"

        # UPC-A: 12 digits
        if len(code) == 12 and code.isdigit():
            return "upc"

        # EAN-13: 13 digits
        if len(code) == 13 and code.isdigit():
            return "ean"

        # UPC-E: 8 digits
        if len(code) == 8 and code.isdigit():
            return "upc"

        # ISBN-10: 10 characters (9 digits + check)
        if len(code) == 10 and code[:-1].isdigit():
            return "isbn"

        # ISBN-13: 13 digits starting with 978 or 979
        if len(code) == 13 and code.isdigit() and code.startswith(("978", "979")):
            return "isbn"

        return "unknown"

    def _stub_response(self, code: str, code_type: str) -> dict:
        """Generate a stub response.

        Args:
            code: Product code
            code_type: Type of code

        Returns:
            Stub product information
        """
        return {
            "found": False,
            "code": code,
            "code_type": code_type,
            "name": None,
            "description": None,
            "brand": None,
            "category": None,
            "image_url": None,
            "contents": [],
            "source_url": None,
            "_stub": True,
            "_message": (
                "Product lookup is not configured. "
                "Set INVENTORY_AMAZON_PRODUCT_API_KEY or INVENTORY_UPCITEMDB_API_KEY "
                "for real lookups."
            ),
        }


# Singleton instance
product_lookup = ProductLookupService()
