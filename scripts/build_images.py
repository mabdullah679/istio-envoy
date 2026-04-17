#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys


def run(command):
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="Build demo service images.")
    parser.add_argument(
        "--load-to-kind",
        action="store_true",
        help="Load images into a kind cluster after building them.",
    )
    parser.add_argument(
        "--kind-cluster-name",
        default="istio-envoy",
        help="kind cluster name to load images into.",
    )
    args = parser.parse_args()

    run(["docker", "build", "-t", "istio-envoy/service-a:local", "-f", "services/service-a/Dockerfile", "."])
    run(["docker", "build", "-t", "istio-envoy/service-b:local", "-f", "services/service-b/Dockerfile", "."])

    if args.load_to_kind:
        if shutil.which("kind") is None:
            raise SystemExit("kind is not installed but --load-to-kind was requested.")
        run(["kind", "load", "docker-image", "istio-envoy/service-a:local", "--name", args.kind_cluster_name])
        run(["kind", "load", "docker-image", "istio-envoy/service-b:local", "--name", args.kind_cluster_name])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

