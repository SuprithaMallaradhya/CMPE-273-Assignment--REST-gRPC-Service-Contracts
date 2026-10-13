#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INV_LOG="/tmp/module3_rest_inventory.log"
ORDER_LOG="/tmp/module3_rest_order.log"
cleanup() { kill "$INV_PID" "$ORDER_PID" 2>/dev/null || true; wait "$INV_PID" "$ORDER_PID" 2>/dev/null || true; }
trap cleanup EXIT

wait_for_order_service() {
  for attempt in $(seq 1 20); do
    if curl -sS -o /dev/null http://localhost:5000/not-found 2>/dev/null; then
      return 0
    fi
    sleep 0.25
  done
  echo "The REST Order Service did not start. Its log is:"
  cat "$ORDER_LOG"
  return 1
}

python "$ROOT/rest/inventory_service.py" --delay 0 >"$INV_LOG" 2>&1 & INV_PID=$!
python "$ROOT/rest/order_service.py" >"$ORDER_LOG" 2>&1 & ORDER_PID=$!
sleep 1
wait_for_order_service
echo "=== REST successful request ==="
curl -sS -i -X POST http://localhost:5000/orders -H 'Content-Type: application/json' -d '{"item_id":"keyboard","quantity":2}'
echo
echo "=== REST unavailable inventory ==="
curl -sS -i -X POST http://localhost:5000/orders -H 'Content-Type: application/json' -d '{"item_id":"monitor","quantity":99}'
echo
kill "$INV_PID" 2>/dev/null || true; wait "$INV_PID" 2>/dev/null || true
python "$ROOT/rest/inventory_service.py" --delay 2 >"$INV_LOG" 2>&1 & INV_PID=$!
sleep 1
echo "=== REST timeout (2s service delay > 1s client timeout) ==="
curl -sS -i -X POST http://localhost:5000/orders -H 'Content-Type: application/json' -d '{"item_id":"keyboard","quantity":2}'
echo
echo "=== REST Order Service is still running ==="
kill "$INV_PID" 2>/dev/null || true; wait "$INV_PID" 2>/dev/null || true
python "$ROOT/rest/inventory_service.py" >"$INV_LOG" 2>&1 & INV_PID=$!
sleep 1
curl -sS -i -X POST http://localhost:5000/orders -H 'Content-Type: application/json' -d '{"item_id":"mouse","quantity":1}'
echo
