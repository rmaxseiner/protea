"""Product lookup service stub for protea.

This is a stub implementation. Real API integration for Amazon Product API
and UPCitemdb will be added in a future update.
"""

import logging

from protea.config import settings

logger = logging.getLogger("protea")


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
        """Look up product by UPC barcode.

        Args:
            upc: Universal Product Code

        Returns:
            Product information dict
        """
        if not self.upcitemdb_configured:
            logger.debug("UPCitemdb API not configured")
            return self._stub_response(upc, "upc")

        # TODO: Implement real UPCitemdb lookup
        # import requests
        # response = requests.get(
        #     f"https://api.upcitemdb.com/prod/trial/lookup?upc={upc}",
        #     headers={"user_key": settings.upcitemdb_api_key}
        # )
        # ...

        return self._stub_response(upc, "upc")

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
