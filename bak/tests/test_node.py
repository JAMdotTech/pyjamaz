import asyncio
import argparse
import termios, tty, select, sys

from pyjamaz.transport.protocol_jamnp_s import JAMNPS

def key_pressed():
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])


async def handle_input(protocol, server):
    stdin_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        loop = asyncio.get_running_loop()

        while True:
            key = await loop.run_in_executor(None, sys.stdin.read, 1)
            if key == 'c':
                print("Connect to server, enter address (defaults to ::)")
                server_addr = input()
                server_addr = server_addr or "::1" #"0.0.0.0"
                print("Enter server port(defaults to 9000):")
                server_port = input()
                server_port = server_port or 9000
                #connect_task = asyncio.create_task(protocol.connect(server_addr, server_port))
                await protocol.connect(server_addr, server_port)
            elif key == 'o':
                print("LIST ALL OUTGOING CONNECTIONS")
            elif key == 'i':
                print("LIST ALL INGOING CONNECTIONS")
            elif key == 's':
                # print("Connect to server, enter address (defaults to ::)")
                # server_addr = input()
                # server_addr = server_addr or "0.0.0.0"
                # print("Enter port nr (defaults to 9000):")
                # server_port = input()
                # server_port = server_port or 9000
                # print("Enter message to send (defaults to 'hello'):")
                # msg = input()
                #conn = protocol.conn_in.get((server_addr, server_port))
                #await conn.query(msg)
                #msg_task = asyncio.create_task(conn.query(msg))
                #asyncio.create_task(protocol.broadcast_block_announcement("1", "2"))
                protocol.request_blocks(1, 1, b"")
                print("SENDED?")
            elif key == 'q':
                print("QUIT")
                server.cancel()
                break
            else:
                print(f"UNKNOWN KEY: {key}")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, stdin_settings)


class dummy_app():
    pass

class dummy_pubsub():
    pass

async def main():
    parser = argparse.ArgumentParser(description="DNS over QUIC server")
    parser.add_argument(
        "--host",
        type=str,
        default="::",
        help="listen on the specified address (defaults to ::)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="listen on the specified port",
    )
    parser.add_argument(
        "-k",
        "--private-key",
        type=str,
        help="load the TLS private key from the specified file",
    )
    parser.add_argument(
        "-c",
        "--certificate",
        type=str,
        required=True,
        help="load the TLS certificate from the specified file",
    )

    args = parser.parse_args()
    app = dummy_app()
    pubsub = dummy_pubsub()
    protocol = JAMNPS(args.host, args.port, args.certificate, args.private_key, dummy_app, dummy_pubsub)
    print(f"STARTING NODE {args.host}:{args.port}")
    server_task = asyncio.create_task(protocol.listen())
    await handle_input(protocol, server_task)


if __name__ == "__main__":
    asyncio.run(main())