#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
INV_LOG="/tmp/module3_grpc_inventory.log"
ORDER_LOG="/tmp/module3_grpc_order.log"
cleanup() { kill "$INV_PID" "$ORDER_PID" 2>/dev/null || true; wait "$INV_PID" "$ORDER_PID" 2>/dev/null || true; }
trap cleanup EXIT

wait_for_order_service() {
  for attempt in $(seq 1 20); do
    if curl -sS -o /dev/null http://localhost:5002/not-found 2>/dev/null; then
      return 0
    fi
    sleep 0.25
  done
  echo "The gRPC Order Service did not start. Its log is:"
  cat "$ORDER_LOG"
  return 1
}

python "$ROOT/grpc_version/inventory_service.py" --delay 0 >"$INV_LOG" 2>&1 & INV_PID=$!
python "$ROOT/grpc_version/order_service.py" >"$ORDER_LOG" 2>&1 & ORDER_PID=$!
sleep 1
wait_for_order_service
echo "=== gRPC successful request ==="
curl -sS -i -X POST http://localhost:5002/orders -H 'Content-Type: application/json' -d '{"item_id":"keyboard","quantity":2}'
echo
echo "=== gRPC unavailable inventory ==="
curl -sS -i -X POST http://localhost:5002/orders -H 'Content-Type: application/json' -d '{"item_id":"monitor","quantity":99}'
echo
kill "$INV_PID" 2>/dev/null || true; wait "$INV_PID" 2>/dev/null || true
python "$ROOT/grpc_version/inventory_service.py" --delay 2 >"$INV_LOG" 2>&1 & INV_PID=$!
sleep 1
echo "=== gRPC deadline (2s service delay > 1s client deadline) ==="
curl -sS -i -X POST http://localhost:5002/orders -H 'Content-Type: application/json' -d '{"item_id":"keyboard","quantity":2}'
echo
echo "=== gRPC Order Service is still running ==="
kill "$INV_PID" 2>/dev/null || true; wait "$INV_PID" 2>/dev/null || true
python "$ROOT/grpc_version/inventory_service.py" >"$INV_LOG" 2>&1 & INV_PID=$!
sleep 1
curl -sS -i -X POST http://localhost:5002/orders -H 'Content-Type: application/json' -d '{"item_id":"mouse","quantity":1}'
echo
