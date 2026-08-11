#!/usr/bin/env python3
"""
mjpeg_stream.py - live camera stream for the WRO car.

Open http://raspberrypi:8000/ in a browser on the same network to watch the
camera feed (180-flipped, manual focus for deep depth-of-field).

Only ONE process can use the camera at a time - stop this (Ctrl+C, or
`pkill -f mjpeg_stream`) before running a challenge or capture script.
"""
import io
import socketserver
from http import server
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform, controls

LENS_POS = 2.0    # ~0.5 m focus -> deeper DOF so far cubes stay sharp (tune here)
SIZE = (1280, 720)
PORT = 8000

PAGE = """<!doctype html><html><head><title>WRO cam</title></head>
<body style="margin:0;background:#111;text-align:center">
<img src="stream.mjpg" style="max-width:100%;height:auto"></body></html>"""


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


output = StreamingOutput()


class Handler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception:
                pass
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(
    main={"size": SIZE}, transform=Transform(hflip=1, vflip=1)))
picam2.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": LENS_POS})
picam2.start_recording(MJPEGEncoder(), FileOutput(output))
try:
    print(f"streaming on http://raspberrypi:{PORT}/  (Ctrl+C to stop)")
    StreamingServer(('', PORT), Handler).serve_forever()
finally:
    picam2.stop_recording()
