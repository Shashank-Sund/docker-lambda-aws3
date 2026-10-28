#!/usr/bin/env bash
# Builds the real Lambda image, runs it locally with the Lambda runtime emulator,
# and sends the same requests the website sends (real Yahoo Finance data).
#   scripts/smoke.sh              local container on port 9000
#   scripts/smoke.sh <api-url>    an API Gateway URL instead (for example staging)
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  docker build --quiet -t stock-eda:local image >/dev/null
  docker rm -f stock-eda-smoke >/dev/null 2>&1 || true
  # Read-only filesystem except /tmp, as on Lambda
  docker run -d --name stock-eda-smoke --read-only --tmpfs /tmp -p 9000:8080 stock-eda:local >/dev/null
  trap 'docker rm -f stock-eda-smoke >/dev/null 2>&1 || true' EXIT
  sleep 2
  TARGET="http://localhost:9000/2015-03-31/functions/function/invocations"
fi

fail=0
run_case() {
  local name="$1" payload="$2" expect="$3"
  local start end body imgs
  start=$(date +%s)
  body=$(curl -s -m 60 -X POST "$TARGET" -H 'Content-Type: application/json' -d "$payload")
  end=$(date +%s)
  imgs=$( (grep -o "data:image/png;base64," <<<"$body" || true) | wc -l | tr -d ' ')
  if [[ "$expect" == json:* ]]; then
    # json:<symbols>: a JSON body whose series are exactly these symbols (comma separated)
    got=$(python3 -c 'import json,sys; e=json.loads(sys.stdin.read()); b=json.loads(e["body"]); print(",".join(b.get("series", {})) or b.get("error"))' <<<"$body" 2>/dev/null || echo "not JSON")
    imgs="-"
    if [ "$got" = "${expect#json:}" ]; then status=PASS; else status=FAIL; fail=1; body="$got"; fi
  elif [[ "$expect" == err:* ]]; then
    if grep -q "${expect#err:}" <<<"$body"; then status=PASS; else status=FAIL; fail=1; fi
  else
    if [ "$imgs" = "$expect" ]; then status=PASS; else status=FAIL; fail=1; fi
  fi
  printf '%-5s %-34s images=%-2s %3ss  %s\n' "$status" "$name" "$imgs" "$((end - start))" \
    "$( [ "$status" = FAIL ] && head -c 200 <<<"$body" )"
}

run_case "single ticker, one year"  '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"AAPL"}' 4
run_case "single ticker, multi year" '{"start_date":"2023-01-03","end_date":"2025-06-30","symbol":"AAPL"}' 5
run_case "multiple tickers"          '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"AAPL,MSFT,GOOG"}' 1
run_case "lowercase ticker"          '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"msft"}' 4
run_case "messy input ' aapl , msft '"  '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":" aapl , msft "}' 1
run_case "trailing comma 'AAPL,'"      '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"AAPL,"}' 4
run_case "unknown ticker message"      '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"ZZZZNOTREAL"}' "err:No data found for ZZZZNOTREAL"
run_case "start after end message"     '{"start_date":"2025-06-30","end_date":"2025-01-02","symbol":"AAPL"}' "err:The start date must be before the end date."
run_case "json: one ticker plus SPY"     '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"AAPL","format":"json"}' "json:AAPL,SPY"
run_case "json: three tickers"           '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"msft, aapl,NVDA","format":"json"}' "json:MSFT,AAPL,NVDA,SPY"
run_case "json: 10 tickers, 20 years"    '{"start_date":"2005-07-01","end_date":"2025-06-30","symbol":"AAPL,MSFT,NVDA,GOOG,AMZN,META,TSLA,JPM,XOM,BRK-B","format":"json"}' "json:AAPL,MSFT,NVDA,GOOG,AMZN,META,TSLA,JPM,XOM,BRK-B,SPY"
run_case "json: unknown ticker message"  '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"QXZQZ","format":"json"}' "json:No data found for QXZQZ between 2025-01-02 and 2025-06-30. Check the ticker symbol and the date range."

exit $fail
