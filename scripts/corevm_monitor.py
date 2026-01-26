import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path when running as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pygame

import pyjamaz
from pyjamaz.logger import setup_logging
from pyjamaz.rpc.ws_client import WebsocketClient
from pyjamaz.utils import base64_decode

JAM_RPC_SERVER = os.getenv("JAM_RPC_SERVER", "ws://127.0.0.1:19800")

FRAME_WIDTH = 640
FRAME_HEIGHT = 400
BYTES_PER_PIXEL = 4
FRAME_BYTES = FRAME_WIDTH * FRAME_HEIGHT * BYTES_PER_PIXEL
SEGMENT_SIZE = 4104
# Doom exports 4104-byte segments; the first 8 bytes are treated as a header.
SEGMENT_HEADER_SIZE = 8
SEGMENT_PAYLOAD_SIZE = SEGMENT_SIZE - SEGMENT_HEADER_SIZE
SEGMENTS_PER_FRAME = FRAME_BYTES // SEGMENT_PAYLOAD_SIZE
SEGMENT_BATCH_SIZE = 64
DISPLAY_UPDATE_EVERY = 8


def init_display():
    pygame.init()
    screen = pygame.display.set_mode((FRAME_WIDTH, FRAME_HEIGHT))
    pygame.display.set_caption("PVM Doom Viewer")
    screen.fill((255, 0, 0))
    font = pygame.font.Font(None, 32)
    text = font.render("LOADING DOOM FRAMES", True, (255, 255, 255))
    rect = text.get_rect(center=(FRAME_WIDTH // 2, FRAME_HEIGHT // 2))
    screen.blit(text, rect)
    pygame.display.flip()
    return screen


async def pygame_pump(stop_event: asyncio.Event):
    while not stop_event.is_set():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_event.set()
                break
        await asyncio.sleep(0.05)


def blit_segment(frame_rgba: bytearray, payload: bytes, dst_offset: int):
    view = memoryview(frame_rgba)
    for i in range(0, SEGMENT_PAYLOAD_SIZE, 4):
        view[dst_offset + i] = payload[i + 2]
        view[dst_offset + i + 1] = payload[i + 1]
        view[dst_offset + i + 2] = payload[i]
        view[dst_offset + i + 3] = 255


async def render_exports(
    client: WebsocketClient,
    export_root: bytes,
    export_offset: int,
    export_count: int,
    frame_rgba: bytearray,
    frame_surface: pygame.Surface,
    screen: pygame.Surface,
    stop_event: asyncio.Event,
    frame_counter: dict,
):
    segment_index = 0
    for start in range(export_offset, export_offset + export_count, SEGMENT_BATCH_SIZE):
        if stop_event.is_set():
            return False
        end = min(start + SEGMENT_BATCH_SIZE, export_offset + export_count)
        indices = list(range(start, end))
        segments = await client.fetchSegments(export_root, indices)
        for segment in segments:
            if stop_event.is_set():
                return False
            payload = segment[SEGMENT_HEADER_SIZE:SEGMENT_HEADER_SIZE + SEGMENT_PAYLOAD_SIZE]
            if len(payload) < SEGMENT_PAYLOAD_SIZE:
                payload = payload.ljust(SEGMENT_PAYLOAD_SIZE, b"\x00")
            dst_offset = (segment_index % SEGMENTS_PER_FRAME) * SEGMENT_PAYLOAD_SIZE
            blit_segment(frame_rgba, payload, dst_offset)
            segment_index += 1
            if segment_index % SEGMENTS_PER_FRAME == 0:
                frame_counter["count"] += 1
                pygame.display.set_caption(f"PVM Doom Viewer - frame {frame_counter['count']}")
            if segment_index % DISPLAY_UPDATE_EVERY == 0:
                screen.blit(frame_surface, (0, 0))
                pygame.display.flip()
        await asyncio.sleep(0)
    screen.blit(frame_surface, (0, 0))
    pygame.display.flip()
    return True


async def main(args):
    setup_logging(logging.INFO)
    screen = init_display()
    frame_rgba = bytearray(FRAME_BYTES)
    frame_surface = pygame.image.frombuffer(frame_rgba, (FRAME_WIDTH, FRAME_HEIGHT), "RGBA")
    stop_event = asyncio.Event()
    pump_task = asyncio.create_task(pygame_pump(stop_event))
    seen_exports = set()
    frame_counter = {"count": 0}
    logging.info("pyjamaz module path: %s", pyjamaz.__file__)

    try:
        async with WebsocketClient(JAM_RPC_SERVER) as client:
            # Init vars
            service_id = int.from_bytes(bytes.fromhex(args.service_id.zfill(8)), byteorder='big')

            best_block = await client.bestBlock()

            services = await client.listServices(best_block["header_hash"])

            # Get service info
            service_data = await client.serviceData(best_block["header_hash"], service_id)
            service_account = service_data["service"] if isinstance(service_data, dict) else service_data

            if service_account is None:
                logging.error(f'Service {service_id} not found')
                return

            best_block_sub = await client.subscribeBestBlock()
            logging.info("Waiting for best block ...")
            async for best_block in best_block_sub:
                if stop_event.is_set():
                    break

                logging.info(f'Best block = {best_block}')

                service_info = await client.serviceData(
                    best_block["header_hash"], service_id, include_exports=True
                )
                if isinstance(service_info, dict):
                    exports = service_info.get("exports", [])
                    logging.info("serviceData exports=%d", len(exports))
                else:
                    exports = []
                    logging.warning(
                        "serviceData did not return exports (type=%s); include_exports may be unsupported",
                        type(service_info).__name__,
                    )
                for export in exports:
                    export_key = (export["exports_root"], export["export_offset"], export["export_count"])
                    if export_key in seen_exports:
                        continue
                    seen_exports.add(export_key)
                    export_root = base64_decode(export["exports_root"])
                    export_offset = export["export_offset"]
                    export_count = export["export_count"]
                    expected_frames = export_count // SEGMENTS_PER_FRAME
                    remainder = export_count % SEGMENTS_PER_FRAME
                    logging.info(
                        "Exports root=%s offset=%s count=%s frames=%s remainder=%s",
                        export["exports_root"],
                        export_offset,
                        export_count,
                        expected_frames,
                        remainder,
                    )
                    if export_count > 0:
                        frame_rgba[:] = b"\x00" * FRAME_BYTES
                        ok = await render_exports(
                            client,
                            export_root,
                            export_offset,
                            export_count,
                            frame_rgba,
                            frame_surface,
                            screen,
                            stop_event,
                            frame_counter,
                        )
                        if not ok:
                            break
                if not exports:
                    logging.info(
                        "No exports for block slot=%s hash=%s",
                        best_block["slot"],
                        best_block["header_hash"].hex(),
                    )

    except ConnectionRefusedError:
        logging.error(f'⚠️ Cannot connect to JAM RPC server @ {JAM_RPC_SERVER}')
    finally:
        stop_event.set()
        await pump_task
        pygame.quit()


def parse_args():
    parser = argparse.ArgumentParser(description="My asyncio CLI app")
    parser.add_argument("service_id", help="Service ID to monitor e.g. 6e1a1155")
    # parser.add_argument(
    #     "--verbose",
    #     action="store_true",
    #     help="Enable verbose output",
    # )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
