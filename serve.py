#!/usr/bin/env python

import os
import http.server
import sys
import time

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_my_headers()
        http.server.SimpleHTTPRequestHandler.end_headers(self)

    def send_my_headers(self):
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

def start_debug_server(port,bind):
    http.server.test(HandlerClass=MyHTTPRequestHandler, port=port, bind=bind)


if __name__ == '__main__':

    import multiprocessing
    proc = multiprocessing.Process(target=start_debug_server, args=(9999, "0.0.0.0"))
    proc.start()