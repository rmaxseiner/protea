#!/usr/bin/env python3
"""Local stdio-to-SSE bridge for Claude Desktop.

This script connects to a remote MCP SSE server and bridges it to stdio
for Claude Desktop compatibility.

Usage:
  python mcp-sse-client.py http://server-container-01:8085/sse
"""

import asyncio
import sys

from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client


async def main():
    if len(sys.argv) < 2:
        print("Usage: mcp-sse-client.py <sse-url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]

    async with sse_client(url) as (read, write):
        # Bridge SSE to stdio
        async def forward_stdin():
            loop = asyncio.get_event_loop()
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)

            while True:
                line = await reader.readline()
                if not line:
                    break
                await write.send(line.decode())

        async def forward_stdout():
            async for message in read:
                print(message, flush=True)

        await asyncio.gather(forward_stdin(), forward_stdout())


if __name__ == "__main__":
    asyncio.run(main())
