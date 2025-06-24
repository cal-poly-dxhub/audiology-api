import pytest
import os
import json
import ipdb
import asyncio
import websockets

WEBSOCKET_ENDPOINT = os.getenv("WEBSOCKET_ENDPOINT")
print(f"WebSocket endpoint: {WEBSOCKET_ENDPOINT}")
if not WEBSOCKET_ENDPOINT:
    pytest.skip("WebSocket endpoint not set", allow_module_level=True)


def test_websocket_connect_disconnect():
    """Test that the $connect and $disconnect routes exist and work."""

    received_messages = []

    async def websocket_client():
        assert WEBSOCKET_ENDPOINT is not None, "WEBSOCKET_ENDPOINT must be set"
        try:
            async with websockets.connect(WEBSOCKET_ENDPOINT) as websocket:
                await websocket.send(json.dumps({"action": "ping"}))

                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    received_messages.append(response)
                    print(f"Received: {response}")
                except asyncio.TimeoutError:
                    print("No response received within timeout")

        except Exception as error:
            print(f"WebSocket error: {error}")
            raise

    # Run the async client
    asyncio.run(websocket_client())

    # Verify we received a response
    assert len(received_messages) > 0, "No response received"


def test_websocket_default_route():
    """Test that the $default route exists and processes custom messages."""
    assert WEBSOCKET_ENDPOINT, "WEBSOCKET_ENDPOINT environment variable must be set"

    received_messages = []

    async def websocket_client():
        assert WEBSOCKET_ENDPOINT is not None, "WEBSOCKET_ENDPOINT must be set"
        try:
            async with websockets.connect(WEBSOCKET_ENDPOINT) as websocket:
                await websocket.send(json.dumps({"message": "hello"}))

                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    received_messages.append(response)
                    print(f"Received: {response}")
                except asyncio.TimeoutError:
                    print("No response received within timeout")

        except Exception as error:
            print(f"WebSocket error: {error}")
            raise

    # Run the async client
    asyncio.run(websocket_client())

    # Verify we received a response with expected content
    assert len(received_messages) > 0, "No response received"
    response = received_messages[0]
    assert "hello" in response, f"Unexpected response: {response}"
