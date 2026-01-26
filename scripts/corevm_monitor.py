import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import pyjamaz
from pyjamaz.logger import setup_logging
from pyjamaz.rpc.ws_client import WebsocketClient

import pygame


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


JAM_RPC_SERVER = os.getenv("JAM_RPC_SERVER", "ws://127.0.0.1:19800")

FRAME_WIDTH = 640
FRAME_HEIGHT = 400
BYTES_PER_PIXEL = 4
FRAME_BYTES = FRAME_WIDTH * FRAME_HEIGHT * BYTES_PER_PIXEL
SEGMENT_SIZE = 4104
# Note: Doom exports 4104-byte segments..the frist 8 bytes are treated as a header
SEGMENT_HEADER_SIZE = 8
SEGMENT_PAYLOAD_SIZE = SEGMENT_SIZE - SEGMENT_HEADER_SIZE
SEGMENTS_PER_FRAME = FRAME_BYTES // SEGMENT_PAYLOAD_SIZE
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


# async def log_best_blocks(client: WebsocketClient, stop_event: asyncio.Event):
#     best_block_sub = await client.subscribeBestBlock()
#     async for best_block in best_block_sub:
#         if stop_event.is_set():
#             break
#         logging.info("Best block = %s", best_block)


async def main(args):
    setup_logging(logging.INFO)
    screen = init_display()
    frame_rgba = bytearray(FRAME_BYTES)
    frame_surface = pygame.image.frombuffer(frame_rgba, (FRAME_WIDTH, FRAME_HEIGHT), "RGBA")
    stop_event = asyncio.Event()
    pump_task = asyncio.create_task(pygame_pump(stop_event))
    #best_block_task = None
    frame_counter = {"count": 0}
    logging.info("pyjamaz module path: %s", pyjamaz.__file__)

    try:
        async with WebsocketClient(JAM_RPC_SERVER) as client:
            # Init vars
            service_id = int.from_bytes(bytes.fromhex(args.service_id.zfill(8)), byteorder='big')

            # best_block = await client.bestBlock()
            # if best_block:
            #     services = await client.listServices(best_block["header_hash"])
            #     if services is not None and service_id not in services:
            #         logging.warning("Service %s not present in listServices response", service_id)
            # else:
            #     logging.warning("No best block yet; skipping listServices check")
            #
            # best_block_task = asyncio.create_task(log_best_blocks(client, stop_event))
            export_sub = await client.subscribeExportSegments(service_id)
            logging.info("Waiting for export segments ...")

            current_stream_key = None
            current_frame_index = -1
            update_ticks = 0

            async for export in export_sub:
                if stop_event.is_set():
                    break
                if export is None:
                    continue

                stream_key = (
                    export["work_package_hash"],
                    export["work_item_index"],
                    export["export_segment_offset"],
                )
                if stream_key != current_stream_key:
                    current_stream_key = stream_key
                    current_frame_index = -1
                    frame_rgba[:] = b"\x00" * FRAME_BYTES
                    logging.info(
                        "New export stream wp=%s item=%s offset=%s",
                        export["work_package_hash"].hex(),
                        export["work_item_index"],
                        export["export_segment_offset"],
                    )

                segment_index = export.get("segment_index")
                if segment_index is None:
                    segment_index = export["export_index"] - export["export_segment_offset"]
                frame_index = segment_index // SEGMENTS_PER_FRAME
                frame_segment_index = segment_index % SEGMENTS_PER_FRAME

                if frame_index != current_frame_index and frame_segment_index == 0:
                    current_frame_index = frame_index
                    frame_rgba[:] = b"\x00" * FRAME_BYTES
                    logging.info("Frame %s start", current_frame_index)

                segment_bytes = export.get("segment")
                if not segment_bytes:
                    logging.warning("Export segment missing bytes for index=%s", export.get("export_index"))
                    continue
                payload = segment_bytes[SEGMENT_HEADER_SIZE:SEGMENT_HEADER_SIZE + SEGMENT_PAYLOAD_SIZE]
                if len(payload) < SEGMENT_PAYLOAD_SIZE:
                    payload = payload.ljust(SEGMENT_PAYLOAD_SIZE, b"\x00")
                dst_offset = frame_segment_index * SEGMENT_PAYLOAD_SIZE
                blit_segment(frame_rgba, payload, dst_offset)

                update_ticks += 1
                if update_ticks % DISPLAY_UPDATE_EVERY == 0:
                    screen.blit(frame_surface, (0, 0))
                    pygame.display.flip()

                if frame_segment_index == SEGMENTS_PER_FRAME - 1:
                    frame_counter["count"] += 1
                    pygame.display.set_caption(f"PVM Doom Viewer - frame {frame_counter['count']}")
                    screen.blit(frame_surface, (0, 0))
                    pygame.display.flip()
                    logging.info("Frame %s complete", current_frame_index)

    except ConnectionRefusedError:
        logging.error(f'⚠️ Cannot connect to JAM RPC server @ {JAM_RPC_SERVER}')
    finally:
        stop_event.set()
        # if best_block_task:
        #     best_block_task.cancel()
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
