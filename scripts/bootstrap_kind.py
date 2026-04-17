#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys


def run(command):
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="Create a kind cluster and install Istio.")
    parser.add_argument(
        "--cluster-name",
        default="istio-envoy",
        help="kind cluster name.",
    )
    args = parser.parse_args()

    if shutil.which("kind") is None:
        raise SystemExit("kind is required for this script.")
    if shutil.which("istioctl") is None:
        raise SystemExit("istioctl is required for this script.")

    run(["kind", "create", "cluster", "--name", args.cluster_name, "--config", "kind/cluster.yaml"])
    run(["istioctl", "install", "-y", "--set", "profile=demo"])
    run(
        [
            "kubectl",
            "-n",
            "istio-system",
            "patch",
            "svc",
            "istio-ingressgateway",
            "--type",
            "merge",
            "-p",
            '{"spec":{"type":"NodePort","ports":[{"name":"status-port","port":15021,"targetPort":15021,"nodePort":30021},{"name":"http2","port":80,"targetPort":8080,"nodePort":30080},{"name":"https","port":443,"targetPort":8443,"nodePort":30443}]}}',
        ]
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

