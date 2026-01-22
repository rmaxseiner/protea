"""Tests for vision extraction tools."""

import json
from unittest.mock import patch, MagicMock

import pytest

from protea.tools import vision


# =============================================================================
# Product Lookup Tests (Stub Implementation)
# =============================================================================


class TestLookupProduct:
    """Tests for lookup_product stub function."""

    def test_lookup_asin(self):
        """Test looking up an ASIN code."""
        result = vision.lookup_product("B0ABC12345")

        assert result["_stub"] is True
        assert result["code"] == "B0ABC12345"
        assert result["source"] == "asin"
        assert "Product B0ABC12345" in result["name"]

    def test_lookup_upc(self):
        """Test looking up a UPC code."""
        result = vision.lookup_product("123456789012")

        assert result["_stub"] is True
        assert result["code"] == "123456789012"
        assert result["source"] == "upc"

    def test_lookup_ean(self):
        """Test looking up an EAN code."""
        result = vision.lookup_product("1234567890123")

        assert result["_stub"] is True
        assert result["code"] == "1234567890123"
        assert result["source"] == "ean"

    def test_lookup_with_explicit_type(self):
        """Test looking up with explicit code type."""
        result = vision.lookup_product("CUSTOMCODE", code_type="custom")

        assert result["source"] == "custom"
        assert result["code"] == "CUSTOMCODE"

    def test_lookup_unknown_type(self):
        """Test looking up unknown code type."""
        result = vision.lookup_product("ABC")

        assert result["source"] == "unknown"


# =============================================================================
# Extract Items Tests (With Mocked API)
# =============================================================================


class TestExtractItemsFromImage:
    """Tests for extract_items_from_image with mocked Anthropic API."""

    def test_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = None

            result = vision.extract_items_from_image("base64data")

            assert "error" in result
            assert result["error_code"] == "API_ERROR"
            assert "API key not configured" in result["error"]

    def test_successful_extraction(self):
        """Test successful item extraction."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "items": [
                {
                    "name": "M3 Screws",
                    "quantity_estimate": "exact:50",
                    "confidence": 0.95,
                    "category_suggestion": "Screws"
                },
                {
                    "name": "Washers",
                    "quantity_estimate": "approximate:assorted",
                    "confidence": 0.8,
                    "category_suggestion": "Washers"
                }
            ],
            "labels_detected": ["ASIN: B08XYZ"],
            "suggestions": "Hardware kit"
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64imagedata")

        assert "items" in result
        assert len(result["items"]) == 2

        # Check exact quantity parsing
        screws = result["items"][0]
        assert screws["name"] == "M3 Screws"
        assert screws["quantity_type"] == "exact"
        assert screws["quantity_value"] == 50

        # Check approximate quantity parsing
        washers = result["items"][1]
        assert washers["name"] == "Washers"
        assert washers["quantity_type"] == "approximate"
        assert washers["quantity_label"] == "assorted"

        assert result["labels_detected"] == ["ASIN: B08XYZ"]

    def test_boolean_quantity(self):
        """Test parsing boolean quantity type."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "items": [
                {
                    "name": "Screwdriver",
                    "quantity_estimate": "boolean",
                    "confidence": 0.9,
                }
            ],
            "labels_detected": [],
            "suggestions": ""
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        assert result["items"][0]["quantity_type"] == "boolean"
        assert result["items"][0]["quantity_value"] == 1

    def test_json_in_markdown_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = """Here's the analysis:

```json
{
    "items": [{"name": "Test Item", "quantity_estimate": "exact:1", "confidence": 0.9}],
    "labels_detected": [],
    "suggestions": ""
}
```

That's what I found."""

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        assert "items" in result
        assert result["items"][0]["name"] == "Test Item"

    def test_json_parse_error(self):
        """Test handling of invalid JSON response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "This is not valid JSON at all"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        assert "error" in result
        assert result["error_code"] == "API_ERROR"

    def test_api_connection_error(self):
        """Test handling of API connection error."""
        import anthropic

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=MagicMock())

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        assert "error" in result
        assert result["error_code"] == "API_ERROR"
        assert "connect" in result["error"].lower()

    def test_api_rate_limit_error(self):
        """Test handling of rate limit error."""
        import anthropic

        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={}
        )

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        assert "error" in result
        assert result["error_code"] == "API_ERROR"
        assert "rate limit" in result["error"].lower()

    def test_api_status_error(self):
        """Test handling of API status error."""
        import anthropic

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIStatusError(
            message="Internal server error",
            response=mock_response,
            body={}
        )

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        assert "error" in result
        assert result["error_code"] == "API_ERROR"

    def test_unexpected_exception(self):
        """Test handling of unexpected exceptions."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("Unexpected error")

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        assert "error" in result
        assert result["error_code"] == "INTERNAL_ERROR"

    def test_context_included_in_prompt(self):
        """Test that context is included in the prompt."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "items": [],
            "labels_detected": [],
            "suggestions": ""
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                vision.extract_items_from_image("base64data", context="electronics drawer")

        # Check that the context was included in the API call
        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        prompt_text = messages[0]["content"][1]["text"]
        assert "electronics drawer" in prompt_text

    def test_media_type_detection_jpeg(self):
        """Test JPEG media type detection from base64 header."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "items": [],
            "labels_detected": [],
            "suggestions": ""
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                # /9j/ is JPEG header
                vision.extract_items_from_image("/9j/4AAQrest")

        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        image_content = messages[0]["content"][0]
        assert image_content["source"]["media_type"] == "image/jpeg"

    def test_media_type_detection_png(self):
        """Test PNG media type detection from base64 header."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "items": [],
            "labels_detected": [],
            "suggestions": ""
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                # iVBOR is PNG header
                vision.extract_items_from_image("iVBORw0KGrest")

        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        image_content = messages[0]["content"][0]
        assert image_content["source"]["media_type"] == "image/png"

    def test_invalid_exact_quantity(self):
        """Test handling of invalid exact quantity value."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "items": [
                {
                    "name": "Item",
                    "quantity_estimate": "exact:notanumber",
                    "confidence": 0.9,
                }
            ],
            "labels_detected": [],
            "suggestions": ""
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        # Should default to 1 if parsing fails
        assert result["items"][0]["quantity_value"] == 1

    def test_missing_item_fields(self):
        """Test handling of items with missing fields."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "items": [
                {
                    # Only confidence, no name
                    "confidence": 0.5
                }
            ],
            "labels_detected": [],
            "suggestions": ""
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch('protea.tools.vision.settings') as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-3-haiku-20240307"

            with patch('protea.tools.vision.anthropic.Anthropic', return_value=mock_client):
                result = vision.extract_items_from_image("base64data")

        # Should use defaults
        assert result["items"][0]["name"] == "Unknown item"
        assert result["items"][0]["quantity_type"] == "boolean"
