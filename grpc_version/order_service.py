import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import grpc

from grpc_contract import inventory_pb2, inventory_pb2_grpc

INVENTORY_TARGET = "localhost:50051"
GRPC_DEADLINE_SECONDS = 1.0


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class OrderHandler(BaseHTTPRequestHandler):
    def log_message(self, format_string, *args):
        print(f"[gRPC Order Adapter] {self.address_string()} - {format_string % args}", flush=True)

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

        try:
            with grpc.insecure_channel(INVENTORY_TARGET) as channel:
                stub = inventory_pb2_grpc.InventoryServiceStub(channel)
                inventory = stub.CheckInventory(
                    inventory_pb2.CheckInventoryRequest(item_id=item_id, quantity=quantity),
                    timeout=GRPC_DEADLINE_SECONDS,
                )
        except grpc.RpcError as error:
            if error.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                self.send_json(504, {
                    "error": "Inventory Service deadline exceeded",
                    "grpc_status": "DEADLINE_EXCEEDED",
                    "order_service": "still running",
                })
            elif error.code() == grpc.StatusCode.FAILED_PRECONDITION:
                self.send_json(409, {
                    "error": error.details(),
                    "grpc_status": "FAILED_PRECONDITION",
                    "order_service": "running",
                })
            else:
                self.send_json(503, {
                    "error": error.details(),
                    "grpc_status": error.code().name,
                    "order_service": "still running",
                })
            return

        self.send_json(200, {
            "available": inventory.available,
            "item_id": item_id,
            "quantity": quantity,
            "message": "Order accepted",
        })


def main():
    global INVENTORY_TARGET
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--inventory-target", default=INVENTORY_TARGET)
    args = parser.parse_args()
    INVENTORY_TARGET = args.inventory_target
    server = ReusableThreadingHTTPServer(("localhost", args.port), OrderHandler)
    print(f"gRPC Order Service listening on http://localhost:{args.port} (deadline={GRPC_DEADLINE_SECONDS}s)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
