#!/usr/bin/env python3
"""Apply the mesh + app manifests. Used by CI (EKS) and locally (kind).

  python scripts/deploy.py --install-istio --image-a <uri> --image-b <uri> --wait    # EKS / CI
  python scripts/deploy.py --wait                                                    # kind (local images)
"""
import argparse
import subprocess
import sys

ISTIO_VERSION = "1.29.9"
ISTIO_REPO = "https://istio-release.storage.googleapis.com/charts"

MANIFESTS = [
    "k8s/base/namespace.yaml",
    "k8s/ratelimit/ratelimit.yaml",
    "k8s/base/apps.yaml",
    "k8s/base/peer-authentication.yaml",
    "k8s/istio/gateway-and-routing.yaml",
    "k8s/istio/gateway-pdb.yaml",
    "k8s/istio/envoyfilter-gateway.yaml",
    "k8s/istio/envoyfilter-sidecar-outbound.yaml",
]


def run(command, stdin=None):
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, input=stdin, text=True)


def install_istio():
    run(["helm", "repo", "add", "istio", ISTIO_REPO, "--force-update"])
    run(["helm", "repo", "update"])
    common = ["--namespace", "istio-system", "--create-namespace", "--version", ISTIO_VERSION, "--wait", "--timeout", "10m"]
    run(["helm", "upgrade", "--install", "istio-base", "istio/base", *common])
    run(["helm", "upgrade", "--install", "istiod", "istio/istiod", *common, "-f", "k8s/istio/helm/istiod-values.yaml"])
    run(["helm", "upgrade", "--install", "istio-ingressgateway", "istio/gateway", *common,
         "-f", "k8s/istio/helm/gateway-values.yaml"])


def apply(path, image_a, image_b):
    text = open(path, encoding="utf-8").read()
    text = text.replace("IMAGE_SERVICE_A", image_a).replace("IMAGE_SERVICE_B", image_b)
    run(["kubectl", "apply", "-f", "-"], stdin=text)


def main():
    parser = argparse.ArgumentParser(description="Apply Kubernetes manifests for the demo.")
    parser.add_argument("--wait", action="store_true", help="Wait for rollouts to finish.")
    parser.add_argument("--install-istio", action="store_true", help="helm install Istio (base, istiod, ingress gateway) first.")
    parser.add_argument("--with-tester", action="store_true", help="Also deploy the in-mesh tester used by verify.py.")
    parser.add_argument("--image-a", default="istio-envoy/service-a:local")
    parser.add_argument("--image-b", default="istio-envoy/service-b:local")
    args = parser.parse_args()

    if args.install_istio:
        install_istio()

    manifests = list(MANIFESTS) + (["k8s/test/tester.yaml"] if args.with_tester else [])
    for manifest in manifests:
        apply(manifest, args.image_a, args.image_b)

    if args.wait:
        targets = [("istio-system", "deploy/redis"), ("istio-system", "deploy/ratelimit"),
                   ("demo-apps", "deploy/service-a"), ("demo-apps", "deploy/service-b")]
        if args.with_tester:
            targets.append(("demo-apps", "deploy/tester"))
        for namespace, target in targets:
            run(["kubectl", "-n", namespace, "rollout", "status", target, "--timeout=300s"])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
