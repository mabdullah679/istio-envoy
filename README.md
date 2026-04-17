# Istio Envoy Global Rate Limit Demo

This repository provisions a small Istio mesh with:

- `service-a`: a public Spring Boot service
- `service-b`: a downstream Spring Boot service
- Envoy's reference global ratelimit service backed by Redis
- Istio `EnvoyFilter` resources that enforce `50 requests / minute / user`

The demo uses `x-user-id` as the user identity key. `service-a` propagates that header when it calls `service-b`.

Tested working state in this repo:

- Java 25
- Spring Boot 4.0.5
- `kind`
- Istio 1.29.2
- End-to-end verification result: `200=50`, `429=5` for both north-south and east-west checks

## Architecture

The rate-limit path is global, not local:

- North-south traffic is filtered on the Istio ingress gateway.
- East-west traffic is filtered on sidecar outbound listeners in the `demo-apps` namespace.
- Both paths generate the same Envoy descriptor: `("user_id", "<x-user-id>")`.
- The ratelimit service applies `50 req/min` to each unique descriptor value and Envoy returns HTTP `429` when the bucket is exhausted.

This choice matters because Istio local rate limiting is per proxy instance. The requirement here is mesh-wide per-user enforcement, which requires Envoy's global ratelimit service.

## Repository Layout

- `pom.xml`
- `services/service-a`
- `services/service-b`
- `k8s/base/apps.yaml`
- `k8s/ratelimit/ratelimit.yaml`
- `k8s/istio/envoyfilter-gateway.yaml`
- `k8s/istio/envoyfilter-sidecar-outbound.yaml`
- `scripts`

## Prerequisites

- Docker
- Python 3
- Kubernetes cluster
- Istio installed in the cluster
- `kubectl`
- Java 25
- Optional for the local bootstrap path: `kind`, `istioctl`

## Bootstrap Flow

If you want a local `kind` cluster and already have `kind` and `istioctl` installed:

```bash
python scripts/bootstrap_kind.py
```

This creates a cluster named `istio-envoy`, installs Istio's `demo` profile, and patches the ingress service to use NodePorts that map to the ports declared in `kind/cluster.yaml`.

## Build and Deploy

Build the Spring Boot service images:

```bash
python scripts/build_images.py
```

If you are using `kind`, load the images into the cluster:

```bash
python scripts/build_images.py --load-to-kind
```

Apply the manifests:

```bash
python scripts/deploy.py --wait
```

If you change the Java code after the initial deploy, rebuild and reload the images, then restart the app deployments:

```bash
mvn clean package -DskipTests
python scripts/build_images.py --load-to-kind
kubectl -n demo-apps rollout restart deploy/service-a
kubectl -n demo-apps rollout restart deploy/service-b
kubectl -n demo-apps rollout status deploy/service-a --timeout=180s
kubectl -n demo-apps rollout status deploy/service-b --timeout=180s
```

## Test

### North-south through ingress

Port-forward the ingress gateway:

```bash
kubectl -n istio-system port-forward svc/istio-ingressgateway 18080:80
```

Then send requests as a single user:

```bash
for i in $(seq 1 55); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Host: demo.local" \
    -H "x-user-id: alice" \
    "http://127.0.0.1:18080/api/public/hello?message=req-$i"
done
```

Expected behavior: the first 50 requests return `200`, then Envoy starts returning `429`.

### East-west inside the mesh

The `tester` pod exists only to generate in-mesh traffic with an injected sidecar:

```bash
pod=$(kubectl -n demo-apps get pod -l app=tester -o jsonpath='{.items[0].metadata.name}')
for i in $(seq 1 55); do
  kubectl -n demo-apps exec "$pod" -c curl -- sh -c \
    "curl -s -o /dev/null -w '%{http_code}\n' -H 'x-user-id: bob' 'http://service-b:8080/api/backend/echo?message=req-$i'"
done
```

Expected behavior: the first 50 requests return `200`, then the sidecar starts returning `429`.

You can also run the packaged verification script:

```bash
python scripts/verify.py
```

The script exits non-zero if the expected result is not met.

## Notes

- Missing `x-user-id` means no rate-limit descriptor is produced, so the request is not rate-limited by Envoy. The Java services intentionally require that header, which turns missing identity into an application `400`.
- `failure_mode_deny: false` is set in both `EnvoyFilter`s so traffic fails open if the ratelimit service is temporarily unavailable.
- A request that comes through ingress and then triggers an internal service-to-service hop consumes one quota unit at each protected hop. That is deliberate because both north-south and east-west traffic are independently covered.
- The ratelimit deployment mounts only the `config.yaml` file from the ConfigMap. Mounting the whole directory causes duplicate config discovery with the upstream distroless image in this setup.

## Quick Start

From the repo root:

```bash
python scripts/bootstrap_kind.py
mvn clean package -DskipTests
python scripts/build_images.py --load-to-kind
python scripts/deploy.py --wait
python scripts/verify.py
```

## Source Notes

The `EnvoyFilter` shape follows Istio's official rate-limit task and Envoy's HTTP ratelimit filter documentation:

- Istio rate limit task: https://istio.io/latest/docs/tasks/policy-enforcement/rate-limit/
- Istio EnvoyFilter reference: https://istio.io/latest/docs/reference/config/networking/envoy-filter/
- Envoy HTTP rate limit filter: https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/rate_limit_filter
- Envoy ratelimit service reference implementation: https://github.com/envoyproxy/ratelimit
