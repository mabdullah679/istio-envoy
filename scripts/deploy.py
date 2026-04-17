#!/usr/bin/env python3
import argparse
import subprocess
import sys


def run(command):
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="Apply Kubernetes manifests for the demo.")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for deployments to finish rolling out.",
    )
    args = parser.parse_args()

    manifests = [
        "k8s/base/namespace.yaml",
        "k8s/ratelimit/ratelimit.yaml",
        "k8s/base/apps.yaml",
        "k8s/istio/gateway-and-routing.yaml",
        "k8s/istio/envoyfilter-gateway.yaml",
        "k8s/istio/envoyfilter-sidecar-outbound.yaml",
    ]
    for manifest in manifests:
        run(["kubectl", "apply", "-f", manifest])

    if args.wait:
        rollout_targets = [
            ("istio-system", "deploy/redis"),
            ("istio-system", "deploy/ratelimit"),
            ("demo-apps", "deploy/service-a"),
            ("demo-apps", "deploy/service-b"),
            ("demo-apps", "deploy/tester"),
        ]
        for namespace, target in rollout_targets:
            run(["kubectl", "-n", namespace, "rollout", "status", target, "--timeout=180s"])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

