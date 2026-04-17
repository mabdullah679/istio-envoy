#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time


def run(command, capture_output=False):
    print("+", " ".join(command))
    return subprocess.run(command, check=True, text=True, capture_output=capture_output)


def tester_pod_name():
    result = run(
        ["kubectl", "-n", "demo-apps", "get", "pod", "-l", "app=tester", "-o", "jsonpath={.items[0].metadata.name}"],
        capture_output=True,
    )
    name = result.stdout.strip()
    if not name:
        raise SystemExit("Tester pod not found.")
    return name


def count_codes(codes):
    return codes.count("200"), codes.count("429")


def assert_expected(label, ok_count, rate_limited_count):
    expected_ok = 50
    expected_rate_limited = 5
    if ok_count != expected_ok or rate_limited_count != expected_rate_limited:
        raise SystemExit(
            f"{label} verification failed: expected 200={expected_ok} and 429={expected_rate_limited}, "
            f"got 200={ok_count} and 429={rate_limited_count}."
        )


def east_west_check(user_id):
    pod = tester_pod_name()
    codes = []
    for i in range(1, 56):
        cmd = [
            "kubectl",
            "-n",
            "demo-apps",
            "exec",
            pod,
            "-c",
            "curl",
            "--",
            "sh",
            "-c",
            f"curl -s -o /dev/null -w '%{{http_code}}' -H 'x-user-id: {user_id}' 'http://service-b:8080/api/backend/echo?message=east-west-{i}'",
        ]
        result = run(cmd, capture_output=True)
        codes.append(result.stdout.strip())
    return count_codes(codes)


def north_south_check(user_id):
    port_forward = subprocess.Popen(
        [
            "kubectl",
            "-n",
            "istio-system",
            "port-forward",
            "svc/istio-ingressgateway",
            "18080:80",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(5)
    try:
        codes = []
        for i in range(1, 56):
            result = run(
                [
                    "curl.exe",
                    "-s",
                    "-o",
                    "NUL",
                    "-w",
                    "%{http_code}",
                    "-H",
                    "Host: demo.local",
                    "-H",
                    f"x-user-id: {user_id}",
                    f"http://127.0.0.1:18080/api/public/hello?message=north-south-{i}",
                ],
                capture_output=True,
            )
            codes.append(result.stdout.strip())
        return count_codes(codes)
    finally:
        port_forward.terminate()
        try:
            port_forward.wait(timeout=5)
        except subprocess.TimeoutExpired:
            port_forward.kill()


def main():
    parser = argparse.ArgumentParser(description="Verify ingress and mesh rate limiting.")
    parser.add_argument("--user-id", default="alice", help="Base user id for the verification run.")
    args = parser.parse_args()

    east_200, east_429 = east_west_check(args.user_id)
    print(f"East-west results: 200={east_200} 429={east_429}")
    assert_expected("East-west", east_200, east_429)

    north_200, north_429 = north_south_check(f"{args.user_id}-ingress")
    print(f"North-south results: 200={north_200} 429={north_429}")
    assert_expected("North-south", north_200, north_429)

    print("Verification passed.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
