import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INVENTORY = {"keyboard": 10, "mouse": 25, "monitor": 3}
DELAY_SECONDS = 0.0


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class InventoryHandler(BaseHTTPRequestHandler):
    def log_message(self, format_string, *args):
        print(f"[REST Inventory] {self.address_string()} - {format_string % args}", flush=True)

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/inventory/check":
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

        if DELAY_SECONDS:
            print(f"[REST Inventory] Delaying response for {DELAY_SECONDS:.1f}s", flush=True)
            time.sleep(DELAY_SECONDS)

        available_quantity = INVENTORY.get(item_id, 0)
        available = available_quantity >= quantity
        status = 200 if available else 409
        self.send_json(status, {
            "available": available,
            "item_id": item_id,
            "requested_quantity": quantity,
            "available_quantity": available_quantity,
            "message": "Inventory available" if available else "Insufficient inventory",
        })


def main():
    global DELAY_SECONDS
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--delay", type=float, default=0.0)
    args = parser.parse_args()
    DELAY_SECONDS = args.delay
    server = ReusableThreadingHTTPServer(("localhost", args.port), InventoryHandler)
    print(f"REST Inventory Service listening on http://localhost:{args.port} (delay={DELAY_SECONDS}s)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
