#!/usr/bin/env python3
"""
Ollama-MCP Bridge for Protea Inventory System

This bridge connects a local Ollama LLM to Protea's MCP tools via SSE transport,
enabling AI-powered inventory management with a local LLM.

Architecture:
    User <-> Bridge <-> Ollama API <-> LLM
                   \
                    -> MCP Client (SSE) <-> Protea MCP-SSE Server <-> Database

How it works:
1. Bridge connects to Protea MCP server via SSE (HTTP)
2. Bridge fetches available tools and converts them to Ollama format
3. User sends a message to the bridge
4. Bridge sends message + tools to Ollama
5. If Ollama wants to call a tool:
   a. Bridge executes the tool via MCP over SSE
   b. Bridge sends tool result back to Ollama
   c. Repeat until Ollama gives final response
6. Bridge displays final response to user

Requirements:
    pip install ollama httpx-sse

Usage:
    # Run with SSE endpoint (recommended for remote Protea)
    python ollama_mcp_bridge.py \
        --mcp-url https://inventory-mcp.maxseiner.casa/sse \
        --api-key "your-api-key" \
        --ollama-url http://ollama.maxseiner.casa \
        --model llama3.1:70b

    # Run with local stdio transport (if Protea is local)
    python ollama_mcp_bridge.py --stdio --model llama3.1:8b
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass

try:
    from ollama import Client as OllamaClient
except ImportError:
    print("Error: ollama package not installed")
    print("Install with: pip install ollama")
    sys.exit(1)

try:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
except ImportError:
    print("Error: mcp package not installed")
    print("Install with: pip install mcp")
    sys.exit(1)

# Optional SSE support
try:
    from mcp.client.sse import sse_client

    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ollama-mcp-bridge")


@dataclass
class BridgeConfig:
    """Configuration for the Ollama-MCP Bridge."""

    # Ollama settings
    ollama_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"

    # MCP settings - SSE transport (for remote Protea)
    mcp_url: str | None = None  # e.g., https://inventory-mcp.maxseiner.casa/sse
    api_key: str = ""

    # MCP settings - stdio transport (for local Protea)
    use_stdio: bool = False
    protea_command: str = "protea"

    # Conversation settings
    system_prompt: str = """You are a helpful inventory management assistant using the Protea system.
You have access to tools for managing locations, bins, items, and searching inventory.

When users ask about their inventory:
- Use search_items or find_item to locate items
- Use get_bin or get_bins to see container contents
- Use get_locations to see storage areas

When users want to add or modify inventory:
- Use add_item to add new items
- Use move_item to relocate items
- Use update_item to change item details

Always be helpful and provide clear information about where items are located.
Use the full location path (Location > Bin > Sub-bin) when telling users where things are."""

    max_tool_rounds: int = 10  # Prevent infinite loops

    # Display settings
    show_tool_calls: bool = True
    verbose: bool = False


def convert_mcp_tools_to_ollama(mcp_tools: list) -> list[dict]:
    """
    Convert MCP tool definitions to Ollama's tool format.

    MCP tools use JSON Schema for input specification.
    Ollama tools use a similar but slightly different format.
    """
    ollama_tools = []

    for tool in mcp_tools:
        input_schema = tool.inputSchema if hasattr(tool, "inputSchema") else {}

        ollama_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": {
                    "type": "object",
                    "properties": input_schema.get("properties", {}),
                    "required": input_schema.get("required", []),
                },
            },
        }

        ollama_tools.append(ollama_tool)

    return ollama_tools


def format_tool_result(result: str) -> str:
    """Format a tool result for display and LLM consumption."""
    try:
        parsed = json.loads(result)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        return result


class OllamaMCPBridge:
    """
    Bridge between Ollama LLM and Protea MCP server.

    Supports two transport modes:
    - SSE: Connect to remote Protea via HTTPS (recommended)
    - stdio: Connect to local Protea via subprocess
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.ollama_client = OllamaClient(host=config.ollama_url)
        self.mcp_tools: list = []
        self.ollama_tools: list[dict] = []
        self.conversation: list[dict] = []

    async def _verify_ollama(self) -> bool:
        """Verify Ollama is reachable and model is available."""
        try:
            response = self.ollama_client.list()

            # Handle different response formats from ollama library
            # Could be {'models': [...]} or a list directly or have 'name' or 'model' keys
            available_models = []
            if isinstance(response, dict):
                models_list = response.get("models", [])
            elif isinstance(response, list):
                models_list = response
            else:
                models_list = []

            for m in models_list:
                if isinstance(m, dict):
                    # Try different key names
                    name = m.get("name") or m.get("model") or str(m)
                    available_models.append(name)
                elif isinstance(m, str):
                    available_models.append(m)

            logger.info(f"Ollama connected. Available models: {len(available_models)}")
            if self.config.verbose and available_models:
                logger.info(f"Models: {available_models[:5]}...")

            # Check if requested model exists
            model_found = any(
                self.config.model in m or f"{self.config.model}:latest" in m
                for m in available_models
            )
            if not model_found and available_models:
                logger.warning(
                    f"Model '{self.config.model}' not found locally. "
                    f"Available: {available_models[:3]}... "
                    f"Ollama will attempt to pull it on first use."
                )
            return True
        except Exception as e:
            logger.error(f"Cannot connect to Ollama at {self.config.ollama_url}: {e}")
            if self.config.verbose:
                import traceback

                traceback.print_exc()
            return False

    async def _execute_tool(self, session: ClientSession, tool_name: str, arguments: dict) -> str:
        """Execute a tool via MCP and return the result."""
        logger.info(f"Executing tool: {tool_name}")
        if self.config.verbose:
            logger.debug(f"Arguments: {json.dumps(arguments, indent=2)}")

        try:
            result = await session.call_tool(tool_name, arguments)

            if hasattr(result, "content") and result.content:
                for content in result.content:
                    if hasattr(content, "text"):
                        return content.text

            return json.dumps({"result": str(result)})

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return json.dumps({"error": str(e)})

    async def _run_conversation_loop(self, session: ClientSession, user_message: str) -> str:
        """Run the conversation loop with tool handling."""

        # Get tools on first message
        if not self.mcp_tools:
            tools_result = await session.list_tools()
            self.mcp_tools = tools_result.tools
            self.ollama_tools = convert_mcp_tools_to_ollama(self.mcp_tools)
            logger.info(f"Loaded {len(self.mcp_tools)} MCP tools")

        # Add user message
        self.conversation.append({"role": "user", "content": user_message})

        tool_rounds = 0
        content = ""

        while tool_rounds < self.config.max_tool_rounds:
            tool_rounds += 1

            # Build messages for Ollama
            messages = [{"role": "system", "content": self.config.system_prompt}]
            messages.extend(self.conversation)

            # Call Ollama
            try:
                response = self.ollama_client.chat(
                    model=self.config.model,
                    messages=messages,
                    tools=self.ollama_tools,
                    stream=False,
                )
            except Exception as e:
                logger.error(f"Ollama API error: {e}")
                return f"Error communicating with Ollama: {e}"

            message = response.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])

            # If no tool calls, we have the final response
            if not tool_calls:
                self.conversation.append({"role": "assistant", "content": content})
                return content

            # Process tool calls
            if self.config.show_tool_calls:
                print(f"\n[Calling {len(tool_calls)} tool(s)...]")

            # Add assistant message with tool calls
            self.conversation.append(
                {"role": "assistant", "content": content, "tool_calls": tool_calls}
            )

            # Execute each tool
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                tool_name = func.get("name", "")

                arguments = func.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                if self.config.show_tool_calls:
                    print(f"  -> {tool_name}({json.dumps(arguments)})")

                result = await self._execute_tool(session, tool_name, arguments)

                if self.config.verbose:
                    formatted = format_tool_result(result)
                    print(f"  <- {formatted[:200]}...")

                self.conversation.append({"role": "tool", "content": result})

        logger.warning(f"Hit max tool rounds ({self.config.max_tool_rounds})")
        return content or "Unable to complete request within allowed tool calls."

    async def chat_sse(self, user_message: str) -> str:
        """Send a message using SSE transport (remote Protea)."""
        if not SSE_AVAILABLE:
            return "Error: SSE support not available. Install with: pip install httpx"

        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            async with sse_client(self.config.mcp_url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await self._run_conversation_loop(session, user_message)
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
            return f"Error connecting to MCP server: {e}"

    async def chat_stdio(self, user_message: str) -> str:
        """Send a message using stdio transport (local Protea)."""
        env = os.environ.copy()
        if self.config.api_key:
            env["PROTEA_API_KEY"] = self.config.api_key

        server_params = StdioServerParameters(command=self.config.protea_command, args=[], env=env)

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await self._run_conversation_loop(session, user_message)
        except Exception as e:
            logger.error(f"Stdio connection error: {e}")
            return f"Error connecting to MCP server: {e}"

    async def chat(self, user_message: str) -> str:
        """Send a message and get a response."""
        if self.config.use_stdio:
            return await self.chat_stdio(user_message)
        else:
            return await self.chat_sse(user_message)

    def clear_conversation(self):
        """Clear the conversation history."""
        self.conversation = []
        logger.info("Conversation cleared")


async def interactive_session(bridge: OllamaMCPBridge):
    """Run an interactive chat session."""
    # Verify Ollama connection first
    if not await bridge._verify_ollama():
        print("Failed to connect to Ollama. Check the URL and try again.")
        return

    transport = "stdio (local)" if bridge.config.use_stdio else f"SSE ({bridge.config.mcp_url})"

    print("\n" + "=" * 60)
    print("Protea Inventory Assistant (powered by Ollama)")
    print("=" * 60)
    print(f"Model: {bridge.config.model}")
    print(f"Ollama: {bridge.config.ollama_url}")
    print(f"MCP Transport: {transport}")
    print("\nCommands:")
    print("  /clear  - Clear conversation history")
    print("  /tools  - List available tools")
    print("  /quit   - Exit")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "/quit":
                print("Goodbye!")
                break

            if user_input.lower() == "/clear":
                bridge.clear_conversation()
                print("Conversation cleared.\n")
                continue

            if user_input.lower() == "/tools":
                if bridge.mcp_tools:
                    print(f"\nAvailable tools ({len(bridge.mcp_tools)}):")
                    for tool in bridge.mcp_tools:
                        desc = (tool.description or "")[:50]
                        print(f"  - {tool.name}: {desc}...")
                else:
                    print("\nTools not yet loaded. Send a message first.\n")
                print()
                continue

            response = await bridge.chat(user_input)
            print(f"\nAssistant: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Bridge between Ollama LLM and Protea MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Connect to remote Protea via SSE (recommended)
  python ollama_mcp_bridge.py \\
      --mcp-url https://inventory-mcp.maxseiner.casa/sse \\
      --api-key "your-token" \\
      --ollama-url http://ollama.maxseiner.casa \\
      --model llama3.1:70b

  # Connect to local Protea via stdio
  python ollama_mcp_bridge.py --stdio --model llama3.1:8b

  # Verbose mode to see tool results
  python ollama_mcp_bridge.py --mcp-url https://... --verbose
""",
    )

    # MCP connection options
    mcp_group = parser.add_mutually_exclusive_group()
    mcp_group.add_argument(
        "--mcp-url",
        help="Protea MCP-SSE endpoint URL (e.g., https://inventory-mcp.example.com/sse)",
    )
    mcp_group.add_argument(
        "--stdio", action="store_true", help="Use stdio transport (local Protea installation)"
    )

    parser.add_argument(
        "--api-key",
        default=os.environ.get("PROTEA_API_KEY", ""),
        help="Protea API key (default: from PROTEA_API_KEY env var)",
    )

    # Ollama options
    parser.add_argument(
        "--model", "-m", default="llama3.1:8b", help="Ollama model to use (default: llama3.1:8b)"
    )
    parser.add_argument(
        "--ollama-url",
        "-u",
        default="http://localhost:11434",
        help="Ollama API URL (default: http://localhost:11434)",
    )

    # Other options
    parser.add_argument(
        "--protea-command",
        default="protea",
        help="Command to start Protea MCP server for stdio mode (default: protea)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed tool call information"
    )
    parser.add_argument("--no-tool-display", action="store_true", help="Hide tool call indicators")

    args = parser.parse_args()

    # Validate arguments
    if not args.stdio and not args.mcp_url:
        parser.error("Must specify either --mcp-url or --stdio")

    if not args.stdio and not SSE_AVAILABLE:
        print("Error: SSE transport requires additional packages.")
        print("Install with: pip install httpx")
        sys.exit(1)

    if not args.api_key:
        print("Warning: No API key set. Authentication may fail.")
        print("Set via --api-key or PROTEA_API_KEY environment variable.\n")

    # Create config
    config = BridgeConfig(
        ollama_url=args.ollama_url,
        model=args.model,
        mcp_url=args.mcp_url,
        api_key=args.api_key,
        use_stdio=args.stdio,
        protea_command=args.protea_command,
        show_tool_calls=not args.no_tool_display,
        verbose=args.verbose,
    )

    # Create and run bridge
    bridge = OllamaMCPBridge(config)
    await interactive_session(bridge)


if __name__ == "__main__":
    asyncio.run(main())
