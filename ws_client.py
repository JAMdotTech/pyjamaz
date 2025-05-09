import asyncio
import json
import websockets

SERVER_URI = "ws://localhost:19800"

async def main():
    async with websockets.connect(SERVER_URI) as ws:

        async def listener():
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    print("⟨message⟩ →", msg)
            except asyncio.CancelledError:
                # clean exit
                pass
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed by server")

        listener_task = asyncio.create_task(listener())
        await asyncio.sleep(10)
        listener_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
