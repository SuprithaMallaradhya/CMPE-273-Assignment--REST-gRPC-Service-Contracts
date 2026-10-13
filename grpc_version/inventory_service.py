import argparse
import time
from concurrent import futures

import grpc

from grpc_contract import inventory_pb2, inventory_pb2_grpc

INVENTORY = {"keyboard": 10, "mouse": 25, "monitor": 3}


class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    def __init__(self, delay_seconds=0.0):
        self.delay_seconds = delay_seconds

    def CheckInventory(self, request, context):
        if request.quantity <= 0 or not request.item_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "item_id and a positive quantity are required")
        if self.delay_seconds:
            print(f"[gRPC Inventory] Delaying response for {self.delay_seconds:.1f}s", flush=True)
            time.sleep(self.delay_seconds)

        available_quantity = INVENTORY.get(request.item_id, 0)
        available = available_quantity >= request.quantity
        if not available:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Insufficient inventory for {request.item_id}: requested {request.quantity}, available {available_quantity}",
            )
        return inventory_pb2.CheckInventoryResponse(
            available=True,
            item_id=request.item_id,
            requested_quantity=request.quantity,
            available_quantity=available_quantity,
            message="Inventory available",
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--delay", type=float, default=0.0)
    args = parser.parse_args()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(args.delay), server)
    server.add_insecure_port(f"localhost:{args.port}")
    server.start()
    print(f"gRPC Inventory Service listening on localhost:{args.port} (delay={args.delay}s)", flush=True)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    main()
