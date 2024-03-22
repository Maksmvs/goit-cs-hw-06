import mimetypes
import json
import socket
import logging
from urllib.parse import urlparse, unquote_plus
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from pymongo import MongoClient

URI = "mongodb://mongodb:27017"
BASE_DIR = Path(__file__).parent
BUFFER_SIZE = 1024
HTTP_PORT = 3000
SOCKET_PORT = 5000

class CatFramework(BaseHTTPRequestHandler):
    def do_GET(self):
        router = urlparse(self.path).path
        if router == "/":
            self.send_html("index.html")
        elif router == "/message":
            self.send_html("message.html")
        elif router == "/style.css":
            self.send_static("style.css")
        elif router == "/logo.png":
            self.send_static("logo.png", mimetype="image/png")
        else:
            self.send_html("error.html", status=404)

    def do_POST(self):
        size = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(size).decode()

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.sendto(data.encode(), ('0.0.0.0', SOCKET_PORT))
        client_socket.close()

        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html(self, filename, status=200):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(BASE_DIR.joinpath("templates", filename), "rb") as f:
            self.wfile.write(f.read())

    def send_static(self, filename, status=200, mimetype=None):
        if not mimetype:
            mimetype, _ = mimetypes.guess_type(filename)
        self.send_response(status)
        self.send_header("Content-type", mimetype)
        self.end_headers()
        with open(BASE_DIR.joinpath("static", filename), "rb") as f:
            self.wfile.write(f.read())

def save_data(data):
    client = MongoClient(URI)
    db = client.homework
    parse_data = unquote_plus(data.decode())
    try:
        parse_data = {key: value for key, value in [el.split("=") for el in parse_data.split("&")]}
        parse_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        db.messages.insert_one(parse_data)
    except ValueError as e:
        logging.error(f"Parse error: {e}")
    except Exception as e:
        logging.error(f"Failed to save: {e}")
    finally:
        client.close()

def run_http_server():
    httpd = HTTPServer(('0.0.0.0', HTTP_PORT), CatFramework)
    try:
        logging.info(f"HTTP Server started on http://0.0.0.0:{HTTP_PORT}")
        httpd.serve_forever()
    except Exception as e:
        logging.error(f"HTTP Server error: {e}")
    finally:
        logging.info("HTTP Server stopped")
        httpd.server_close()

def run_socket_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', SOCKET_PORT))
    logging.info(f"Socket Server started on 0.0.0.0:{SOCKET_PORT}")
    try:
        while True:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            logging.info(f"Received message from {addr}: {data.decode()}")
            save_data(data)
    except Exception as e:
        logging.error(f"Socket Server error: {e}")
    finally:
        logging.info("Socket Server stopped")
        sock.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    http_process = Process(target=run_http_server, name="http_server")
    http_process.start()

    socket_process = Process(target=run_socket_server, name="socket_server")
    socket_process.start()

