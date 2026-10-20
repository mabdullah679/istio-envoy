# istio-envoy

Two Spring Boot services on an Istio mesh with mesh-wide, per-user global rate limiting (Envoy ratelimit + Redis), deployed to AWS EKS by Terraform and GitHub Actions and proven through a public load-balancer URL.

Spec: there is no external requirements document; the behaviour this repo implements is the rate-limit design from Istio's [rate limit task](https://istio.io/latest/docs/tasks/policy-enforcement/rate-limit/) (`50 requests / minute / x-user-id`, HTTP 429 over the limit) plus the production requirements listed in the [What it does](#what-it-does) table.

## How it runs

```
                 git push prod-hardening
                          |
                          v
   GitHub Actions  --OIDC-->  AWS role pf-istio-envoy-ci-deploy   (no stored AWS keys)
   test -> plan -> apply -> images -> deploy -> smoke
                          |
        +-----------------+------------------------------------------+
        | AWS ap-southeast-2, VPC 10.20.0.0/16, 2 public subnets      |
        |                                                             |
 client |   Classic ELB :80                                           |
 -----> |        |                                                    |
        |   EKS pf-istio-envoy-eks (2 x t3.medium)                    |
        |        v                                                    |
        |   istio-ingressgateway x2 --(user_id)--> ratelimit x2 -> Redis
        |        | mTLS                                               |
        |        v                                                    |
        |   service-a x2 --mTLS--> service-b x2     (demo-apps, PeerAuthentication STRICT)
        |        ^ sidecar outbound also asks ratelimit per hop       |
        |   ECR: pf-istio-envoy-service-a / -service-b (tag = git SHA)|
        +-------------------------------------------------------------+
   Terraform state: S3 pf-istio-envoy-tfstate-346208529954 (versioned, lockfile)
```

Not contained in this repo: the AWS account itself, its GitHub OIDC provider (`token.actions.githubusercontent.com`) and the managed policy `portfolio-ci-boundary`. Both already exist in the shared account and are only referenced, never created.

More diagrams: [cluster data flow](diagrams/cluster-data-flow.mmd), [verify.py flow](diagrams/verify-script-flow.mmd), [deploy pipeline](diagrams/deploy-pipeline.mmd) (Mermaid source; rendered SVGs exist for verify.py and the pipeline; the cluster-data-flow SVG was removed because it showed the old kind layout and the local renderer crashed on the new one; open the .mmd in any Mermaid viewer, for example mermaid.live).

## Deployed on AWS

Evidence, 2026-10-20, account 346208529954, region ap-southeast-2. Pipeline run: https://github.com/mabdullah679/istio-envoy/actions/runs/39392988777 (jobs test, plan, apply, images, deploy, smoke all green, deploy and smoke executed by GitHub Actions through OIDC).

URL pattern: `http://<random-id>.ap-southeast-2.elb.amazonaws.com` (a new hostname every rebuild). The one that was live: `http://a1f3ee6776b754e72938d7ed9b07ec66-239342470.ap-southeast-2.elb.amazonaws.com`.

What was curled and what came back:

| Request | Observed |
|---|---|
| `GET /api/public/relay?message=hi` with `x-user-id: muhammad` | HTTP 200, body shows `service-a` and a nested `downstream` object from `service-b` carrying the same `userId` |
| 55 x `GET /api/public/hello` as one user | `200` x 50, then `429` x 5 (sequence: fifty `200`, then `429 429 429 429 429`) |
| `verify.py` mtls check, caller with a sidecar | HTTP 200 from `service-b` |
| `verify.py` mtls check, pod in a namespace with no sidecar, plaintext | `curl: (56) Recv failure: Connection reset by peer`, http code `000` |
| Same plaintext check with `PeerAuthentication` patched to `PERMISSIVE` (mutation) | HTTP 200, check went red; reverted to `STRICT` and re-checked green |
| malformed `x-user-id` (illegal chars, 65 chars, missing) | HTTP 400 each |

Resources (all prefixed `pf-istio-envoy-`, tagged `project=portfolio repo=istio-envoy managed-by=terraform`): VPC, internet gateway, 2 public subnets, route table, EKS cluster `pf-istio-envoy-eks` (Kubernetes 1.35), managed node group of 2 x t3.medium, `metrics-server` add-on, 2 IAM roles (cluster, node), 2 ECR repositories with lifecycle policies, 1 EKS access entry; from Kubernetes: one Classic ELB (made by the gateway Service), 3 Helm releases (`istio-base`, `istiod`, `istio-ingressgateway`). Outside the stack module: S3 state bucket and the IAM role `pf-istio-envoy-ci-deploy` (bootstrap).

Cost: the stack is ephemeral by design. Estimated from public list prices, not an invoice, about 0.31 USD/hour (EKS control plane 0.10, 2 x t3.medium 0.106, Classic ELB 0.028, 4 public IPv4 addresses 0.02, 2 x 20 GB EBS 0.007, rest negligible). Tear down:

```
gh workflow run destroy.yml --ref prod-hardening -f confirm=destroy      # removes the ELB first, then terraform destroy
terraform -chdir=terraform/bootstrap destroy                              # last: state bucket + CI role
```

Rebuild with one command (bootstrap already applied): `gh workflow run deploy.yml --ref prod-hardening`. About 20 minutes from nothing: EKS about 10 minutes, Istio and apps about 5, smoke about 1.

Status of this section: the destroy workflow had not been run at the time this was written; update this paragraph with the real teardown result once it has.

### Deviation from the original brief

The brief asked for an NLB. This account rejects `elbv2:CreateLoadBalancer` ("This AWS account currently does not support creating load balancers", reproduced from both Kubernetes and the AWS CLI, which rules out a Kubernetes-side cause). A Classic ELB is allowed, so the gateway Service uses the in-tree provider's default Classic ELB. If you run this in an account with elbv2 enabled, add `service.beta.kubernetes.io/aws-load-balancer-type: nlb` to [gateway-values.yaml](k8s/istio/helm/gateway-values.yaml).

## Prerequisites

- AWS account in which the GitHub OIDC provider and (optionally) a permissions-boundary policy already exist. This repo's defaults point at account 346208529954 and `portfolio-ci-boundary`; change the variables in [terraform/bootstrap/main.tf](terraform/bootstrap/main.tf) and [terraform/variables.tf](terraform/variables.tf) for any other account.
- Terraform 1.10 or newer (the S3 backend uses `use_lockfile`; CI pins 1.13.5). A GitHub repository with Actions enabled and `gh` logged in.
- For local runs: Java 25 and Maven (tests), Python 3, `kubectl`, `helm`, AWS CLI v2. Docker is only needed to build images locally.
- The host does NOT need Istio, `istioctl`, `kind`, or Docker for the AWS path: CI installs Istio with Helm and builds images on the runner.

## Run it (AWS)

1. Bootstrap once from a workstation (local state, creates the state bucket and the OIDC-assumable CI role):
   ```
   terraform -chdir=terraform/bootstrap init
   terraform -chdir=terraform/bootstrap apply
   ```
2. Push the branch (or run the workflow by hand):
   ```
   git push origin prod-hardening
   gh workflow run deploy.yml --ref prod-hardening
   ```
3. Find the URL and run the proof yourself:
   ```
   aws eks update-kubeconfig --name pf-istio-envoy-eks --region ap-southeast-2
   kubectl -n istio-system get svc istio-ingressgateway      # EXTERNAL-IP is the hostname
   python3 scripts/verify.py                                 # all checks; or --check relay|validation|north-south|east-west|mtls
   ```

If the pipeline fails at `images` or `deploy`, fix and push again: Terraform is idempotent and ECR tags are skipped when that SHA already exists.

## Run it (local kind, original path)

```
python scripts/bootstrap_kind.py                # kind cluster + istioctl demo profile
mvn clean package -DskipTests
python scripts/build_images.py --load-to-kind
python scripts/deploy.py --with-tester --wait
python scripts/verify.py --port-forward
```

Not re-run after the hardening changes; the AWS path is the proven one.

## What it does

| Action | Expected result | Requirement |
|---|---|---|
| `GET /api/public/hello` with `x-user-id` | 200 JSON echo from service-a | core |
| `GET /api/public/relay` | service-a calls service-b over mTLS and returns both payloads | service-a to service-b call |
| 51st+ request in a minute from one `x-user-id`, at the gateway | 429 from Envoy | 50/min/user, north-south |
| 51st+ request in a minute from one `x-user-id`, service to service | 429 from the caller's sidecar | 50/min/user, east-west |
| service-b returns 429 to service-a | service-a returns 429 JSON instead of a 500 | error handling |
| service-b down or slow | service-a returns 504 JSON after 2 s connect / 3 s read timeouts (configurable) | resilience |
| service-b returns other 5xx | service-a returns 502 JSON | error handling |
| `x-user-id` missing, over 64 chars or outside `[A-Za-z0-9._@:-]` | 400 JSON | input validation |
| `message` over 200 chars | 400 JSON | input validation |
| `message` containing `&` or `=` on relay | encoded, cannot inject query parameters downstream | input validation |
| plaintext call to service-b from a pod without a sidecar | connection reset | mTLS STRICT |
| drain one node / roll a deployment | at least 1 replica of each service stays up | PodDisruptionBudgets (declared, not drain-tested) |
| any response | `X-Content-Type-Options`, `X-Frame-Options`, `Cache-Control: no-store`, `Content-Security-Policy` headers | security headers |

## Interfaces

| Method and path | Served by | Reachable from | Auth |
|---|---|---|---|
| `GET /api/public/hello?message=` | service-a | internet via ELB | none; `x-user-id` header is required but is a client-supplied label, not authentication |
| `GET /api/public/relay?message=` | service-a | internet via ELB | same |
| `GET /api/backend/echo?message=` | service-b | mesh only (mTLS), not routed by the gateway | `x-user-id` required |
| `GET /actuator/health`, `/actuator/health/liveness`, `/actuator/health/readiness`, `/actuator/info` | both | pods only (probes), not routed by the gateway | none |

Configuration (environment): `SERVICE_B_BASE_URL` (default `http://service-b.demo-apps.svc.cluster.local:8080`), `SERVICE_B_CONNECT_TIMEOUT` (`2s`), `SERVICE_B_READ_TIMEOUT` (`3s`) on service-a. Logs are structured JSON (ECS format) on stdout.

## Tests

```
mvn -B verify          # needs Java 25 and Maven only; no cluster, no network services
python3 scripts/verify.py --base-url http://<elb-host>   # live; needs kubectl access for east-west and mtls
```

Unit tests: 11 for service-a, 6 for service-b (validation, header handling, error mapping 429/502/504, query-parameter encoding, security headers) using MockMvc and `MockRestServiceServer`. They run in CI before anything touches AWS. Guards were mutation-checked: loosening the user-id length rule and removing the 429 passthrough each turned a test red before being restored. `verify.py` is the live proof and exits non-zero on any miss; CI runs it as the `smoke` job.

## Layout

| Path | Role |
|---|---|
| [services/service-a](services/service-a) | public API; validation, relay to service-b, error mapping, tests |
| [services/service-b](services/service-b) | downstream API; same validation and headers, tests |
| [k8s/base/apps.yaml](k8s/base/apps.yaml) | Deployments (2 replicas, probes, limits, non-root, read-only FS), Services, PDBs |
| [k8s/base/peer-authentication.yaml](k8s/base/peer-authentication.yaml) | mTLS STRICT for `demo-apps` |
| [k8s/ratelimit/ratelimit.yaml](k8s/ratelimit/ratelimit.yaml) | Envoy ratelimit (2 replicas, digest-pinned) and Redis, limit config |
| [k8s/istio](k8s/istio) | Gateway/VirtualService, the two EnvoyFilters, gateway PDB, [Helm values](k8s/istio/helm) |
| [k8s/test/tester.yaml](k8s/test/tester.yaml) | in-mesh curl pod used by `verify.py` |
| [terraform](terraform) | VPC, EKS, node group, ECR, S3 backend config |
| [terraform/bootstrap](terraform/bootstrap) | state bucket and the GitHub OIDC CI role (local state) |
| [.github/workflows/deploy.yml](.github/workflows/deploy.yml) | test, plan, apply, images, deploy, smoke |
| [.github/workflows/destroy.yml](.github/workflows/destroy.yml) | manual teardown |
| [scripts/deploy.py](scripts/deploy.py) | Helm-installs Istio, applies manifests with image substitution (CI and local) |
| [scripts/verify.py](scripts/verify.py) | live proof: relay, validation, 50/5 rate limit both paths, mTLS rejection |
| [scripts/bootstrap_kind.py](scripts/bootstrap_kind.py), [scripts/build_images.py](scripts/build_images.py), [kind](kind) | original local kind path |
| [diagrams](diagrams) | Mermaid sources and renders |

## Design decisions

- Global, not local, rate limiting. Istio's local limiter is per proxy, so with 2 gateway replicas the real limit would be 100/min. The Envoy ratelimit service plus Redis gives one counter per user across the mesh.
- Counters are fixed one-minute windows. A burst that straddles a minute boundary can see more than 50 successes. `verify.py` therefore waits until early in the minute before bursting; a user who times their requests can still exceed 50 across a boundary.
- Fail open (`failure_mode_deny: false`). If ratelimit or Redis is down, traffic flows unlimited rather than the site going down. Redis is a single replica (counters are 1-minute data; ElastiCache would add cost and a failure domain). Fail-open was not tested by killing Redis.
- The rate-limit key is the client-supplied `x-user-id`, so anyone can rotate it to dodge the limit. This demonstrates the mechanism; production would key on an authenticated identity at the gateway.
- Istio is installed by CI with Helm, not by Terraform. A Terraform helm provider needs the cluster to exist at plan time, which breaks the first apply. Terraform owns AWS; `scripts/deploy.py` owns in-cluster state.
- Public subnets, no NAT gateway. A NAT would cost about 0.059 USD/hour plus data. Nodes have public IPs, but the node (cluster) security group accepts traffic only from itself and from the ELB's own security group (checked with `describe-security-groups`); the only internet-facing rule is TCP 80 on the ELB's security group.
- Public EKS API endpoint. GitHub-hosted runners have no fixed CIDR, so a private-only endpoint would need self-hosted runners. Access is via EKS access entries (IAM), not the aws-auth ConfigMap.
- CI role trust is one exact subject, `repo:mabdullah679/istio-envoy:ref:refs/heads/prod-hardening`, and it is permission-bounded. Its policy scopes IAM actions to `pf-istio-envoy-*` roles but allows `ec2:*`, `eks:*`, `ecr:*`: creating a VPC and cluster cannot be scoped by name in advance.
- Sizing was measured, not guessed. With everything running (19 pods): requests are 37 to 40 percent of node memory, actual use about 1.05 GiB per node (32 percent), CPU about 77m per node. Memory alone would fit one t3.medium, but the node pod cap is 17 and the stack has 19 pods, so one node cannot hold it; two nodes also let PDBs and rolling updates keep services up. Istio chart defaults (2 GiB for istiod) were reduced to 256 Mi requests.
- ECR tags are immutable and set to the git SHA, so a deployed tag can never be silently re-pointed. Re-runs of the same SHA skip the push.
- No NetworkPolicy. The VPC CNI would need network-policy mode enabled, and a pod-level deny would reset plaintext traffic before mTLS sees it, making the STRICT mTLS proof meaningless. Not built; mTLS STRICT is the control that is proven.
- No AuthorizationPolicy yet: any in-mesh workload with a valid mesh identity in `demo-apps` can call service-b. Listed as future work.
- A CI false-green was found and fixed: `verify.py | tee` hid a failing exit code (the first smoke run printed a FAIL and still went green). The step now runs with `pipefail`.

## Not established

- Node drain with PDBs, graceful shutdown under load, Redis or ratelimit outage behaviour, and the destroy workflow were not exercised.
- ECR image-scan findings were not reviewed. EKS control-plane logging is off to save cost.
- The local kind path was not re-run after these changes.
- Cost figures are list-price estimates; no invoice was read.
