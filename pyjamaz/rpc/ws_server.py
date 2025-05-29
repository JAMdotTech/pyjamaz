import asyncio
import json
import signal
import logging
import typing
from asyncio import CancelledError
from typing import Set
import websockets

from pyjamaz.rpc.rpc import RPC_REQUESTS, RPC_TYPE_SUBSCRIBE, RPC_TYPE_UNSUBSCRIBE, jsonapi_response, jsonapi_parse, RPCCallException, jsonapi_ws_subscribed, \
    jsonapi_ws_response, RPC_ERROR, jsonapi_error
from pyjamaz.rpc.ws_server_subscriptions import SubscriptionManager


if typing.TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp


class WebSocketServer:

    def __init__(self, app: 'PyjamazApp', host: str, port: int):
        self.app = app
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        self.shutdown_event = asyncio.Event()
        self.subscriptions = SubscriptionManager(self)


    async def handle_client(self, websocket: websockets.WebSocketServerProtocol):
        """Handle individual client connection"""
        #buffer = ""
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"

        try:
            self.clients.add(websocket)
            logging.info(f"New connection from {client_info}. Total clients: {len(self.clients)}")

            async for message in websocket:
                if self.shutdown_event.is_set():
                    break

                try:
                    if isinstance(message, bytes):
                        message = message.decode("utf8")

                    # Note: we can always trust we're dealing with one message at a time: https://stackoverflow.com/a/21025321
                    try:
                        # Process message and send response
                        try:
                            logging.debug(f"INCOMING MESSAGE: {message}")

                            req_id = None
                            req_id, rpc_call, params, rpc_type, _ = jsonapi_parse(message)

                            if rpc_type == RPC_TYPE_SUBSCRIBE:
                                result = await self.subscriptions.subscribe(websocket, req_id, rpc_call, params)
                                response = jsonapi_ws_subscribed(req_id, result.id)
                                logging.debug(f"RPC NEW SUBSCRIPTION request_id={req_id} subscription_id={result.id}")
                                await websocket.send(response)
                                response = None
                                # Directly trigger a first response
                                value = RPC_REQUESTS[rpc_call](self.app, params)
                                await result.send(jsonapi_ws_response(result.id, rpc_call, value))

                            elif rpc_type == RPC_TYPE_UNSUBSCRIBE:
                                sub_id = await self.subscriptions.unsubscribe(params[0])
                                response = jsonapi_response(req_id, rpc_call, sub_id is not None)

                            else:
                                resp_data = RPC_REQUESTS[rpc_call](self.app, params)
                                response = jsonapi_response(req_id, rpc_call, resp_data)

                        except RPCCallException as e:
                            logging.error(f"Invalid RPC method: {e.reason}")
                            if e.reason in RPC_ERROR:
                                return jsonapi_error(req_id or e.req_id, RPC_ERROR[e.reason])
                            else:
                                return jsonapi_error(req_id or e.req_id, RPC_ERROR["PARSE_ERROR"])

                        except Exception as e:
                            logging.error(f"Invalid message: {message}")
                            logging.error(e)
                            try:
                                return jsonapi_error(None, RPC_ERROR["PARSE_ERROR"])
                            except Exception as e:
                                pass

                        if response:
                            await websocket.send(response)

                    except Exception as e:
                        logging.error(f"Error processing message: {e}")
                        # Send error response if needed
                        error_response = jsonapi_response("ERROR", str(e))
                        await websocket.send(error_response)

                except Exception as e:
                    logging.error(f"Error handling message from {client_info}: {e}")

        except websockets.exceptions.ConnectionClosed:
            logging.info(f"Client {client_info} connection closed")
        finally:
            self.clients.remove(websocket)
            logging.info(f"Client {client_info} disconnected. Total clients: {len(self.clients)}")


    async def shutdown(self):
        """Gracefully shutdown the server"""
        logging.debug("Shutting down server...")
        self.shutdown_event.set()

        # Close all client connections
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients]
            )

        # Stop the server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logging.debug("Server shutdown complete")


    async def start(self):
        """Start the WebSocket server"""
        try:
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port
            )

            logging.info(f"Server started on ws://{self.host}:{self.port}")

            # Set up signal handlers for graceful shutdown
            for sig in (signal.SIGTERM, signal.SIGINT):
                asyncio.get_event_loop().add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.shutdown())
                )

            # Wait until shutdown is triggered
            await self.shutdown_event.wait()

        except Exception as e:
            logging.error(f"Server error: {e}")
            raise

        finally:
            await self.shutdown()


    async def serve(self):
        """Method to run server without blocking"""
        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port
        )
        logging.info(f"Server started on ws://{self.host}:{self.port}")
        await self.shutdown_event.wait()


async def start_rpc_server(server: WebSocketServer):
    try:
        await server.start()
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Main error: {e}")
    finally:
        await server.shutdown()
        logging.info("Server stopped")
        raise CancelledError()
