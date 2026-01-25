"""Tests for product lookup service."""

from unittest.mock import MagicMock, patch

import pytest

from protea.services.product_lookup import ProductLookupService, product_lookup


class TestCodeTypeDetection:
    """Tests for code type detection."""

    def test_detect_upc_a(self):
        """UPC-A is 12 digits."""
        service = ProductLookupService()
        assert service._detect_code_type("049000042566") == "upc"

    def test_detect_upc_e(self):
        """UPC-E is 8 digits."""
        service = ProductLookupService()
        assert service._detect_code_type("04900004") == "upc"

    def test_detect_ean_13(self):
        """EAN-13 is 13 digits."""
        service = ProductLookupService()
        assert service._detect_code_type("4006381333931") == "ean"

    def test_detect_asin(self):
        """ASIN is 10 chars starting with B0."""
        service = ProductLookupService()
        assert service._detect_code_type("B000QYG8HE") == "asin"

    def test_detect_isbn_10(self):
        """ISBN-10 is 10 chars (9 digits + check)."""
        service = ProductLookupService()
        assert service._detect_code_type("0596007124") == "isbn"

    def test_detect_isbn_13_as_ean(self):
        """ISBN-13 (978/979 prefix) is detected as EAN since EAN check comes first."""
        service = ProductLookupService()
        # ISBN-13s are valid EAN-13s, so they're detected as EAN (which works for lookup)
        assert service._detect_code_type("9780596007126") == "ean"

    def test_detect_unknown(self):
        """Unknown codes return 'unknown'."""
        service = ProductLookupService()
        assert service._detect_code_type("ABC123") == "unknown"
        assert service._detect_code_type("12345") == "unknown"


class TestUPCLookup:
    """Tests for UPC lookup with mocked API."""

    @patch("protea.services.product_lookup.requests.get")
    def test_successful_lookup(self, mock_get):
        """Test successful UPC lookup."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "OK",
            "total": 1,
            "items": [
                {
                    "title": "Test Product",
                    "description": "A test product description",
                    "brand": "Test Brand",
                    "category": "Test > Category",
                    "images": ["https://example.com/image.jpg"],
                    "offers": [{"link": "https://example.com/product"}],
                    "ean": "0049000042566",
                    "upc": "049000042566",
                    "asin": "B000TEST00",
                    "model": "TEST-123",
                    "lowest_recorded_price": 199,
                    "highest_recorded_price": 499,
                }
            ],
        }
        mock_get.return_value = mock_response

        service = ProductLookupService()
        result = service.lookup_upc("049000042566")

        assert result["found"] is True
        assert result["name"] == "Test Product"
        assert result["brand"] == "Test Brand"
        assert result["category"] == "Test > Category"
        assert result["image_url"] == "https://example.com/image.jpg"
        assert result["asin"] == "B000TEST00"

    @patch("protea.services.product_lookup.requests.get")
    def test_product_not_found(self, mock_get):
        """Test when product is not in database."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "OK",
            "total": 0,
            "items": [],
        }
        mock_get.return_value = mock_response

        service = ProductLookupService()
        result = service.lookup_upc("000000000000")

        assert result["found"] is False
        assert "not found" in result.get("message", "").lower()

    @patch("protea.services.product_lookup.requests.get")
    def test_rate_limit_exceeded(self, mock_get):
        """Test rate limit handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        service = ProductLookupService()
        result = service.lookup_upc("049000042566")

        assert result["found"] is False
        assert result["error_code"] == "RATE_LIMITED"

    @patch("protea.services.product_lookup.requests.get")
    def test_api_error(self, mock_get):
        """Test API error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        service = ProductLookupService()
        result = service.lookup_upc("049000042566")

        assert result["found"] is False
        assert result["error_code"] == "API_ERROR"

    @patch("protea.services.product_lookup.requests.get")
    def test_timeout(self, mock_get):
        """Test timeout handling."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout()

        service = ProductLookupService()
        result = service.lookup_upc("049000042566")

        assert result["found"] is False
        assert result["error_code"] == "TIMEOUT"

    @patch("protea.services.product_lookup.requests.get")
    def test_request_exception(self, mock_get):
        """Test general request exception handling."""
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        service = ProductLookupService()
        result = service.lookup_upc("049000042566")

        assert result["found"] is False
        assert result["error_code"] == "REQUEST_ERROR"


class TestLookupRouter:
    """Tests for the lookup() method that routes to correct handler."""

    @patch("protea.services.product_lookup.requests.get")
    def test_auto_detect_upc(self, mock_get):
        """Test auto-detection routes UPC to lookup_upc."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": "OK", "items": []}
        mock_get.return_value = mock_response

        service = ProductLookupService()
        service.lookup("049000042566")  # 12-digit UPC

        # Verify the API was called
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]["params"]["upc"] == "049000042566"

    def test_explicit_code_type(self):
        """Test explicit code_type parameter is respected."""
        service = ProductLookupService()

        with patch.object(service, "lookup_upc") as mock_upc:
            mock_upc.return_value = {"found": False}
            service.lookup("049000042566", code_type="upc")
            mock_upc.assert_called_once_with("049000042566")

        with patch.object(service, "lookup_asin") as mock_asin:
            mock_asin.return_value = {"found": False}
            service.lookup("B000QYG8HE", code_type="asin")
            mock_asin.assert_called_once_with("B000QYG8HE")


class TestSingletonInstance:
    """Test the singleton instance."""

    def test_singleton_exists(self):
        """Verify product_lookup singleton is available."""
        assert product_lookup is not None
        assert isinstance(product_lookup, ProductLookupService)


# Optional: Live API test (skipped by default to preserve rate limit)
@pytest.mark.skip(reason="Live API test - run manually to avoid rate limits")
class TestLiveAPI:
    """Live API tests - skipped by default."""

    def test_live_upc_lookup(self):
        """Test actual API call with known UPC."""
        result = product_lookup.lookup_upc("049000042566")

        assert result["found"] is True
        assert "coca" in result["name"].lower() or "coke" in result["name"].lower()
        assert result["code_type"] == "upc"
