#!/usr/bin/env python3
"""Bridge script to connect Claude Desktop to remote MCP SSE server."""

import asyncio
import json
import sys
import httpx
from httpx_sse import aconnect_sse


SSE_URL = "http://server-container-01:8085/sse"
MESSAGES_URL = "http://server-container-01:8085/messages/"


async def main():
    async with httpx.AsyncClient(timeout=None) as client:
        # Connect to SSE endpoint
        async with aconnect_sse(client, "GET", SSE_URL) as event_source:
            # Get session ID from endpoint event
            session_id = None

            async def read_sse():
                nonlocal session_id
                async for event in event_source.aiter_sse():
                    if event.event == "endpoint":
                        # Extract session ID from endpoint URL
                        session_id = event.data.split("session_id=")[-1] if "session_id=" in event.data else None
                    elif event.event == "message":
                        # Forward message to stdout
                        print(event.data, flush=True)

            async def read_stdin():
                loop = asyncio.get_event_loop()
                reader = asyncio.StreamReader()
                protocol = asyncio.StreamReaderProtocol(reader)
                await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    # Post message to server
                    url = f"{MESSAGES_URL}?session_id={session_id}" if session_id else MESSAGES_URL
                    await client.post(url, content=line, headers={"Content-Type": "application/json"})

            await asyncio.gather(read_sse(), read_stdin())


if __name__ == "__main__":
    asyncio.run(main())
