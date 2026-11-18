# CLAUDE.md (istio-envoy)

Global working rules: `~/.claude/CLAUDE.md` (read it; not copied here). Repo-specific only below.

## Commands (run 2026-11-18)

```
JAVA_HOME=<JDK 25+> mvn -B -ntp verify       # 11 (service-a) + 6 (service-b) tests pass
python3 -m py_compile scripts/*.py
```
The default `mvn` on the owner's Mac uses Homebrew JDK 24 and fails with "release version 25 not supported"; use the Temurin 27 JDK at `/Library/Java/JavaVirtualMachines/temurin-27.jdk/Contents/Home`.
Terraform, kind and istioctl are not installed on the owner machine; `terraform fmt`/`validate` run in CI only, and `scripts/verify.py` needs a live cluster.

## Layout
`services/service-a|b` Spring Boot, `k8s/` manifests + Istio/Helm values + ratelimit, `terraform/` (+ `bootstrap/`), `scripts/` (deploy, verify, kind helpers), `diagrams/`, workflows: `ci.yml` (PRs, no AWS), `deploy.yml` (push to `prod-hardening`), `destroy.yml` (push of `.github/DESTROY` on `prod-hardening`).

## Conventions
- Feature branch + PR; never push to `main`. A push to `prod-hardening` runs `terraform apply` on EKS (~$0.31/h); a push touching `.github/DESTROY` there tears it down. Do not push to that branch without the owner's say-so.
- Pin third-party actions to full commit SHAs with a version comment.
- Logic fixes need a test seen failing first (mutate, see red, reverse the exact edit).

## Do NOT
- Run `terraform apply`/`destroy`, `kubectl`/`helm` against a cluster, `scripts/deploy.py`, or any `aws` call without explicit owner consent. The stack was torn down 2026-10-20.
- Edit `.github/DESTROY` (it triggers a teardown on `prod-hardening`).
