"""Vision extraction tools for protea using Claude API."""

import json
import logging
import re

import anthropic

from protea.config import settings

logger = logging.getLogger("protea")

# Extraction prompt for Claude
EXTRACTION_PROMPT = """Analyze this image and identify inventory items visible.

For each item you can identify, provide:
1. name: A clear, descriptive name
2. quantity_estimate: One of:
   - "exact:N" if you can count exactly N items
   - "approximate:description" for uncountable items (e.g., "approximate:assorted", "approximate:many", "approximate:roll")
   - "boolean" if it's a single tool/object that you don't count
3. confidence: Your confidence level (0.0-1.0)
4. category_suggestion: Best matching category from this list:
   - Screws, Bolts, Nuts, Washers, Nails, Anchors (under Fasteners > Hardware)
   - Hand Tools, Power Tools, Measuring (under Tools)
   - Components, Cables & Connectors, Boards & Modules (under Electronics)
   - Adhesives & Tape, Lubricants, Safety Equipment (under Supplies)
   - Wood, Metal, Plastic (under Materials)
   - Other

Also note:
- labels_detected: Any readable text, barcodes, product codes, or ASIN labels you can see
- suggestions: Any helpful observations (e.g., "I see a product label with barcode", "This appears to be a kit with multiple items")

{context}

Respond with valid JSON in this exact format:
{{
  "items": [
    {{
      "name": "M3 socket head cap screws",
      "quantity_estimate": "exact:50",
      "confidence": 0.9,
      "category_suggestion": "Screws"
    }}
  ],
  "labels_detected": ["ASIN: B08XYZ123", "UPC: 123456789"],
  "suggestions": "The package label shows this is a 50-piece kit"
}}
"""


def extract_items_from_image(
    image_base64: str,
    context: str | None = None,
) -> dict:
    """Analyze an image and extract potential inventory items using Claude API.

    Args:
        image_base64: Base64-encoded image data
        context: Optional context hint (e.g., "this is a hardware bin")

    Returns:
        Dict with items, labels_detected, and suggestions
    """
    if not settings.claude_api_key:
        return {
            "error": "Claude API key not configured. Set INVENTORY_CLAUDE_API_KEY environment variable.",
            "error_code": "API_ERROR",
            "details": {"hint": "Vision extraction requires Claude API access"},
        }

    # Build prompt with context
    prompt = EXTRACTION_PROMPT
    if context:
        prompt = prompt.format(context=f"Context: {context}")
    else:
        prompt = prompt.format(context="")

    # Determine media type from base64 header or default to jpeg
    media_type = "image/jpeg"
    if image_base64.startswith("/9j/"):
        media_type = "image/jpeg"
    elif image_base64.startswith("iVBOR"):
        media_type = "image/png"
    elif image_base64.startswith("UklGR"):
        media_type = "image/webp"

    try:
        client = anthropic.Anthropic(api_key=settings.claude_api_key)

        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # Extract text response
        response_text = message.content[0].text

        # Parse JSON from response
        # Try to find JSON in the response (it might be wrapped in markdown code blocks)
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            # Try to parse the whole response as JSON
            # Find first { and last }
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                response_text = response_text[start:end]

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse vision response: {e}")
            logger.debug(f"Response was: {response_text}")
            return {
                "error": "Failed to parse vision extraction response",
                "error_code": "API_ERROR",
                "details": {"parse_error": str(e)},
            }

        # Normalize the response
        items = []
        for item in result.get("items", []):
            quantity_estimate = item.get("quantity_estimate", "boolean")

            # Parse quantity_estimate
            if quantity_estimate.startswith("exact:"):
                quantity_type = "exact"
                try:
                    quantity_value = int(quantity_estimate.split(":")[1])
                except (ValueError, IndexError):
                    quantity_value = 1
                quantity_label = None
            elif quantity_estimate.startswith("approximate:"):
                quantity_type = "approximate"
                quantity_value = 1
                quantity_label = quantity_estimate.split(":", 1)[1] if ":" in quantity_estimate else "various"
            else:
                quantity_type = "boolean"
                quantity_value = 1
                quantity_label = None

            items.append({
                "name": item.get("name", "Unknown item"),
                "quantity_type": quantity_type,
                "quantity_value": quantity_value,
                "quantity_label": quantity_label,
                "confidence": item.get("confidence", 0.5),
                "category_suggestion": item.get("category_suggestion"),
            })

        return {
            "items": items,
            "labels_detected": result.get("labels_detected", []),
            "suggestions": result.get("suggestions", ""),
        }

    except anthropic.APIConnectionError as e:
        logger.error(f"Claude API connection error: {e}")
        return {
            "error": "Failed to connect to Claude API",
            "error_code": "API_ERROR",
            "details": {"connection_error": str(e)},
        }
    except anthropic.RateLimitError as e:
        logger.error(f"Claude API rate limit: {e}")
        return {
            "error": "Claude API rate limit exceeded",
            "error_code": "API_ERROR",
            "details": {"rate_limit": str(e)},
        }
    except anthropic.APIStatusError as e:
        logger.error(f"Claude API error: {e}")
        return {
            "error": f"Claude API error: {e.message}",
            "error_code": "API_ERROR",
            "details": {"status_code": e.status_code},
        }
    except Exception as e:
        logger.error(f"Unexpected error in vision extraction: {e}", exc_info=True)
        return {
            "error": f"Vision extraction failed: {str(e)}",
            "error_code": "INTERNAL_ERROR",
        }


def lookup_product(
    code: str,
    code_type: str | None = None,
) -> dict:
    """Lookup product details from barcode/ASIN.

    Note: This is a stub implementation. Real API integration coming later.

    Args:
        code: Product code (UPC, EAN, ASIN, etc.)
        code_type: Type of code ("asin", "upc", "ean")

    Returns:
        Product information dict
    """
    # Stub implementation - returns mock data
    # Real implementation would call Amazon Product API or UPCitemdb

    # Detect code type if not specified
    if not code_type:
        if code.startswith("B0") and len(code) == 10:
            code_type = "asin"
        elif len(code) == 12 and code.isdigit():
            code_type = "upc"
        elif len(code) == 13 and code.isdigit():
            code_type = "ean"
        else:
            code_type = "unknown"

    return {
        "name": f"Product {code}",
        "description": f"Product looked up via {code_type}: {code}",
        "contents": [],
        "source_url": None,
        "source": code_type,
        "code": code,
        "_stub": True,
        "_message": "This is a stub implementation. Configure Amazon/UPC API keys for real lookups.",
    }
