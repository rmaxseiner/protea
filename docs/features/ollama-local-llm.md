# Local LLM Integration with Ollama

## Overview

Use local LLMs via Ollama to interact with Protea's MCP server, enabling fully local/private AI-powered inventory management without cloud dependencies.

## Why Local LLMs?

- **Privacy**: Keep all data and conversations on your hardware
- **No API costs**: Run unlimited queries without per-token charges
- **Offline capable**: Works without internet after initial model download
- **Customization**: Fine-tune models for your specific use case

## Requirements

- Ollama installed locally
- A model with tool/function calling support
- An MCP bridge (Ollama doesn't natively support MCP yet)
- Sufficient RAM/VRAM for your chosen model

## Hardware Recommendations

| RAM/VRAM | Recommended Models | Expected Speed |
|----------|-------------------|----------------|
| 8GB | Qwen2.5-VL-3B | Fast, basic capability |
| 16GB | Qwen2.5-VL-7B | Good balance |
| 32GB | Qwen2.5-VL-7B FP16 or 32B Q4 | Better quality |
| 64GB+ | Qwen2.5-VL-32B Q8 or 72B Q4 | Best quality, slower |
| 96GB+ | Qwen2.5-VL-72B Q4/Q8 | Production quality |

For effective tool calling and image recognition, 32B+ models are recommended.

---

## Setup Guide

### 1. Install Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Start the service
ollama serve
```

### 2. Pull a Vision + Tool Calling Model

```bash
# Recommended for most users (balance of quality/speed)
ollama pull qwen2.5vl:32b

# For high-memory systems (best quality)
ollama pull qwen2.5vl:72b-q4_K_M

# For limited hardware (faster, less capable)
ollama pull qwen2.5vl:7b
```

### 3. Install an MCP Bridge

Ollama doesn't have native MCP support, so you need a bridge. Options:

#### Option A: mcp-client-for-ollama (Recommended)

A Python TUI client with multi-server support:

```bash
# Install via pipx (recommended)
pipx install mcp-client-for-ollama

# Or via pip
pip install mcp-client-for-ollama
```

#### Option B: ollama-mcp-bridge

A TypeScript bridge:

```bash
npx ollama-mcp-bridge
```

### 4. Configure MCP Connection to Protea

Create a configuration file for the MCP bridge.

#### For mcp-client-for-ollama

Create `~/.config/ollmcp/config.json`:

```json
{
  "mcpServers": {
    "protea": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://your-protea-server.example.com/sse",
        "--header",
        "Authorization:Bearer prot_YOUR_API_KEY_HERE"
      ]
    }
  }
}
```

Or for local Protea without auth:

```json
{
  "mcpServers": {
    "protea": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "http://localhost:8081/sse"
      ]
    }
  }
}
```

### 5. Run the MCP Client

```bash
# Start the TUI client
ollmcp

# Select your model (e.g., qwen2.5vl:32b)
# The client will connect to configured MCP servers
```

---

## Example Usage

Once connected, you can interact with Protea using natural language:

```
You: Show me all locations in my inventory

[Model calls get_locations tool]
Assistant: You have 3 locations:
1. Garage - Main storage area
2. Office - Electronics and supplies
3. Kitchen - Cooking equipment

You: Add a new screwdriver set to the Garage tool bin

[Model calls search_bins with query "tool" in location "Garage"]
[Model calls create_item with name "Screwdriver Set", bin_id=...]

Assistant: Done! I have added "Screwdriver Set" to your Tool Storage bin in the Garage.
```

---

## Vision Capabilities

With vision-enabled models (Qwen2.5-VL), you can:

- Take photos of items and have the model describe them
- Extract text from labels or packaging
- Identify items for categorization

Note: Vision capabilities require passing images through the MCP bridge, which may require additional configuration depending on your setup.

---

## Troubleshooting

### Model Not Calling Tools

- Ensure you are using a model trained for function/tool calling
- Larger models (32B+) have better tool calling reliability
- Try rephrasing your request to be more explicit

### Slow Performance

- Use quantized models (Q4, Q5) for faster inference
- Ensure sufficient RAM/VRAM is available
- Consider smaller models for interactive use

### Connection Errors

- Verify Ollama is running: `ollama list`
- Check Protea SSE endpoint is accessible
- Ensure API key is valid if authentication is enabled

---

## Resources

- [Ollama](https://ollama.com/)
- [mcp-client-for-ollama](https://github.com/jonigl/mcp-client-for-ollama)
- [ollama-mcp-bridge](https://github.com/patruff/ollama-mcp-bridge)
- [Qwen2.5-VL Models](https://ollama.com/library/qwen2.5vl)
