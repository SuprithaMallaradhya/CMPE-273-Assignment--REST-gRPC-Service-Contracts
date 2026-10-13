import argparse
import json
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INVENTORY_URL = "http://localhost:5001/inventory/check"
INVENTORY_TIMEOUT_SECONDS = 1.0


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class OrderHandler(BaseHTTPRequestHandler):
    def log_message(self, format_string, *args):
        print(f"[REST Order] {self.address_string()} - {format_string % args}", flush=True)

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/orders":
            self.send_json(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            item_id = request["item_id"]
            quantity = int(request["quantity"])
            if not item_id or quantity <= 0:
                raise ValueError
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.send_json(400, {"error": "item_id and a positive quantity are required"})
            return

        payload = json.dumps({"item_id": item_id, "quantity": quantity}).encode("utf-8")
        inventory_request = urllib.request.Request(
            INVENTORY_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(inventory_request, timeout=INVENTORY_TIMEOUT_SECONDS) as response:
                inventory = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 409:
                inventory = json.loads(error.read().decode("utf-8"))
                self.send_json(409, {**inventory, "order_service": "running"})
            else:
                self.send_json(502, {"error": "Inventory Service returned an error", "order_service": "still running"})
            return
        except (socket.timeout, TimeoutError, urllib.error.URLError) as error:
            reason = getattr(error, "reason", error)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                self.send_json(504, {"error": "Inventory Service timed out", "order_service": "still running"})
            else:
                self.send_json(503, {"error": "Inventory Service unavailable", "order_service": "still running"})
            return
        except Exception as error:
            # Keep the Order Service alive even if a platform-specific socket
            # exception is raised by the HTTP client.
            if "timed out" in str(error).lower() or "timeout" in str(error).lower():
                self.send_json(504, {"error": "Inventory Service timed out", "order_service": "still running"})
            else:
                self.send_json(503, {"error": "Inventory Service unavailable", "order_service": "still running"})
            return

        self.send_json(200, {
            "available": inventory["available"],
            "item_id": item_id,
            "quantity": quantity,
            "message": "Order accepted",
        })


def main():
    global INVENTORY_URL
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--inventory-url", default=INVENTORY_URL)
    args = parser.parse_args()
    INVENTORY_URL = args.inventory_url
    server = ReusableThreadingHTTPServer(("localhost", args.port), OrderHandler)
    print(f"REST Order Service listening on http://localhost:{args.port} (timeout={INVENTORY_TIMEOUT_SECONDS}s)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
