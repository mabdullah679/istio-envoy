#!/usr/bin/env python3
"""End-to-end proof for the mesh. Works against a kind cluster or the AWS NLB.

Checks (all run by default):
  relay        service-a -> service-b through the mesh returns 200 with service-b's payload
  validation   malformed x-user-id is rejected with 400 by the application
  north-south  55 requests from one user through the public URL: 50x 200 then 5x 429
  east-west    55 requests from the in-mesh tester pod to service-b: 50x 200 then 5x 429
  mtls         a pod WITHOUT a sidecar calling service-b in plaintext is rejected,
               while the in-mesh tester (mTLS) gets 200 from the same URL

Needs kubectl access to the cluster for east-west / mtls. Exits non-zero on any miss.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

LIMIT = 50
BURST = 55
CHECKS = ["relay", "validation", "north-south", "east-west", "mtls"]


def sh(cmd, check=True, timeout=120):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, text=True, capture_output=True, timeout=timeout)


def http_get(url, headers=None, timeout=10):
    """Returns (status, body). 4xx/5xx are returned, not raised."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def discover_base_url():
    out = sh(["kubectl", "-n", "istio-system", "get", "svc", "istio-ingressgateway",
              "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"]).stdout.strip()
    if not out:
        raise SystemExit("No load balancer hostname on istio-ingressgateway; pass --base-url or --port-forward.")
    return f"http://{out}"


def wait_until_serving(base_url, timeout_s=420):
    """NLB DNS + target registration can lag the Kubernetes Service by a few minutes."""
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            status, _ = http_get(f"{base_url}/api/public/hello", {"x-user-id": f"warmup-{uuid.uuid4().hex[:6]}"}, 5)
            if status == 200:
                print(f"endpoint is serving (HTTP 200) at {base_url}")
                return
            last = status
        except Exception as exc:  # DNS not yet resolvable, connection refused, timeout
            last = repr(exc)
        time.sleep(10)
    raise SystemExit(f"{base_url} never returned 200 within {timeout_s}s (last: {last})")


def wait_for_window():
    """The limiter uses fixed per-minute windows; start a burst early in the minute so it cannot straddle a reset."""
    sec = time.gmtime().tm_sec
    if sec > 40:
        time.sleep(61 - sec)


def tally(codes):
    return {c: codes.count(c) for c in sorted(set(codes))}


def expect_burst(label, codes):
    summary = tally(codes)
    print(f"{label}: first 50 = {tally(codes[:LIMIT])}, last 5 = {tally(codes[LIMIT:])}, total = {summary}")
    if codes[:LIMIT] != ["200"] * LIMIT or codes[LIMIT:] != ["429"] * (BURST - LIMIT):
        raise SystemExit(f"FAIL {label}: expected 50x200 then 5x429, got {summary}")
    print(f"PASS {label}")


def check_relay(base_url):
    user = f"relay-{uuid.uuid4().hex[:8]}"
    status, body = http_get(f"{base_url}/api/public/relay?message=hello-b", {"x-user-id": user})
    print(f"relay -> HTTP {status} {body}")
    payload = json.loads(body)
    if status != 200 or payload.get("downstream", {}).get("service") != "service-b" \
            or payload["downstream"].get("userId") != user:
        raise SystemExit("FAIL relay: service-a did not return service-b's payload with the forwarded user id")
    print("PASS relay (service-a -> service-b over the mesh, x-user-id propagated)")


def check_validation(base_url):
    results = {}
    results["illegal chars"] = http_get(f"{base_url}/api/public/hello", {"x-user-id": "bad user;id"})[0]
    results["65 chars"] = http_get(f"{base_url}/api/public/hello", {"x-user-id": "a" * 65})[0]
    results["missing header"] = http_get(f"{base_url}/api/public/hello")[0]
    print(f"validation -> {results}")
    if set(results.values()) != {400}:
        raise SystemExit("FAIL validation: expected HTTP 400 for every malformed request")
    print("PASS validation")


def check_north_south(base_url):
    user = f"ns-{uuid.uuid4().hex[:8]}"
    wait_for_window()
    codes = []
    for i in range(1, BURST + 1):
        codes.append(str(http_get(f"{base_url}/api/public/hello?message=ns-{i}", {"x-user-id": user})[0]))
    expect_burst(f"north-south via {base_url}", codes)


def tester_pod():
    name = sh(["kubectl", "-n", "demo-apps", "get", "pod", "-l", "app=tester",
               "-o", "jsonpath={.items[0].metadata.name}"]).stdout.strip()
    if not name:
        raise SystemExit("tester pod not found (apply k8s/test/tester.yaml)")
    return name


def check_east_west():
    pod = tester_pod()
    user = f"ew-{uuid.uuid4().hex[:8]}"
    wait_for_window()
    script = (f"for i in $(seq 1 {BURST}); do curl -s -o /dev/null -w '%{{http_code}}\\n' "
              f"-H 'x-user-id: {user}' \"http://service-b:8080/api/backend/echo?message=ew-$i\"; done")
    out = sh(["kubectl", "-n", "demo-apps", "exec", pod, "-c", "curl", "--", "sh", "-c", script]).stdout
    expect_burst("east-west tester -> service-b", out.split())


def check_mtls():
    pod = tester_pod()
    url = "http://service-b.demo-apps.svc.cluster.local:8080/api/backend/echo?message=mtls"
    hdr = f"x-user-id: mtls-{uuid.uuid4().hex[:6]}"
    fmt = "%{http_code}"
    meshed = sh(["kubectl", "-n", "demo-apps", "exec", pod, "-c", "curl", "--", "curl", "-s", "-m", "5",
                 "-o", "/dev/null", "-w", fmt, "-H", hdr, url]).stdout.strip()
    print(f"meshed caller (sidecar, mTLS) -> HTTP {meshed}")

    sh(["kubectl", "create", "namespace", "plain-test"], check=False)  # no istio-injection label on purpose
    name = f"plain-{uuid.uuid4().hex[:6]}"
    try:
        run = sh(["kubectl", "-n", "plain-test", "run", name, "--image=curlimages/curl:8.8.0",
                  "--restart=Never", "--rm", "-i", "--quiet", "--command", "--",
                  "curl", "-sS", "-m", "5", "-o", "/dev/null", "-w", fmt, "-H", hdr, url],
                 check=False, timeout=180)
        plain = run.stdout.strip()
        print(f"plaintext caller (no sidecar) -> HTTP '{plain}' exit={run.returncode} stderr={run.stderr.strip()[-200:]}")
    finally:
        sh(["kubectl", "delete", "namespace", "plain-test", "--wait=false"], check=False)
    # curl exit 56 (reset) / 52 (empty reply) with http_code 000 = connection killed by STRICT mTLS
    rejected = plain in ("", "000") and run.returncode in (52, 56)
    if meshed != "200" or not rejected:
        raise SystemExit("FAIL mtls: expected meshed=200 and plaintext connection reset (curl exit 52/56)")
    print("PASS mtls (STRICT PeerAuthentication rejects plaintext; mTLS caller gets 200)")


def main():
    parser = argparse.ArgumentParser(description="Verify routing, validation, rate limiting and mTLS.")
    parser.add_argument("--base-url", help="Public URL, e.g. http://<nlb-dns>. Default: read from the istio-ingressgateway Service.")
    parser.add_argument("--port-forward", action="store_true", help="kind/local: port-forward the gateway to 127.0.0.1:18080.")
    parser.add_argument("--check", choices=["all"] + CHECKS, default="all")
    args = parser.parse_args()

    pf = None
    try:
        if args.port_forward:
            pf = subprocess.Popen(["kubectl", "-n", "istio-system", "port-forward", "svc/istio-ingressgateway", "18080:80"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(5)
            base_url = "http://127.0.0.1:18080"
        else:
            base_url = (args.base_url or discover_base_url()).rstrip("/")
        wanted = CHECKS if args.check == "all" else [args.check]
        if any(c in wanted for c in ("relay", "validation", "north-south")):
            wait_until_serving(base_url)
        if "relay" in wanted:
            check_relay(base_url)
        if "validation" in wanted:
            check_validation(base_url)
        if "north-south" in wanted:
            check_north_south(base_url)
        if "east-west" in wanted:
            check_east_west()
        if "mtls" in wanted:
            check_mtls()
        print("Verification passed.")
    finally:
        if pf:
            pf.terminate()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, file=sys.stderr)
        sys.exit(exc.returncode)
