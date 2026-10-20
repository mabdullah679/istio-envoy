ISTIO-ENVOY, PLAIN-ENGLISH VERSION

What this is
Two small Java web services (service-a and service-b) running on Amazon's managed Kubernetes (EKS) inside an Istio service mesh. Every user is allowed 50 requests per minute; the 51st gets an HTTP 429 "too many requests". The whole thing is built by Terraform and GitHub Actions, and it was proven live through a public web address.

What was done
- Made the Java services safer: they now reject bad user ids and over-long messages with a clean 400 error, turn a failing or slow service-b into a clean 429, 502 or 504 error instead of a crash, report health and readiness for Kubernetes, shut down gracefully, send safe security headers, and log in JSON. 17 automated tests cover this (11 for service-a, 6 for service-b). Before fixing, three of these problems were reproduced with failing tests; after fixing, two of the guards were deliberately broken to prove the tests catch them, then restored.
- The Docker images are multi-stage and run as a non-root user.
- Kubernetes: two copies of each service, health probes, CPU and memory limits, rules that stop Kubernetes taking the last copy down, read-only file systems, and mutual TLS (services must prove who they are to each other) switched to STRICT.
- Terraform builds a private network, an EKS cluster with two t3.medium servers, and two image repositories (ECR). Its record of what exists is kept in a locked, versioned S3 bucket.
- GitHub Actions logs in to AWS with a short-lived token (no passwords or keys stored anywhere) and runs: tests, Terraform plan, Terraform apply, build and push images, install Istio and the apps, then a live smoke test. This ran successfully end to end on 2026-10-20 (run 39392988777).

What was proven on the live address
Live address (changes every rebuild): http://a1f3ee6776b754e72938d7ed9b07ec66-239342470.ap-southeast-2.elb.amazonaws.com
- service-a calling service-b worked and returned both answers.
- 55 requests from one user: the first 50 returned 200, the last 5 returned 429.
- Service to service traffic: also 50 times 200 then 5 times 429.
- A pod with no mesh sidecar that tried a plain, unencrypted call to service-b was cut off ("connection reset by peer"). A pod inside the mesh got 200. To be sure the test really tests this, mutual TLS was temporarily loosened: the plain call then succeeded and the test failed; it was put back to STRICT and passed again.
- Bad inputs returned 400.

What could not be done as asked
- The brief asked for a Network Load Balancer. This AWS account refuses to create that kind of load balancer ("account currently does not support creating load balancers"), both from Kubernetes and from the AWS command line. The older Classic load balancer is allowed, so that is what is used. If the account is ever enabled for modern load balancers, one line in k8s/istio/helm/gateway-values.yaml switches it to a Network Load Balancer.
- No NetworkPolicy was added: it would block the plain call before mutual TLS gets to reject it, which would hide the very thing being proven. There is also no per-service access rule yet (AuthorizationPolicy); that is future work.

Things that went wrong and were fixed
- The first deploy stopped at the load balancer step because of the account limit above. Fixed by using the Classic load balancer.
- The first smoke test printed a FAIL but the pipeline still showed green, because a pipe hid the failure. Fixed so a failed check now fails the pipeline.
- The old cluster diagram picture showed the old local layout and the local drawing tool crashed on the new one, so the old picture was removed and the diagram source file is kept.

Not tested
Draining a server, shutting down under load, Redis or the rate-limit service going down (it is set to let traffic through if it does), ECR vulnerability scan results, and the old local kind path after these changes. Cost numbers are estimates from list prices, not a bill.

Cost and cleanup
It cost about 0.31 US dollars per hour while running (estimate from list prices, not a bill): cluster 0.10, two servers 0.106, load balancer 0.028, public addresses 0.02, disks 0.007.
It was verified live on 2026-10-20 and then torn down the same day to save money. The live address above no longer works.
The teardown worked on its first run. It removed the load balancer first, then everything Terraform built, then (last) the state bucket and the CI role. Lookups afterwards found nothing left with the pf-istio-envoy name or the repo=istio-envoy tag. For a few minutes the old address still answered, but from addresses that no longer belonged to this account (DNS caching); it then stopped resolving.
One correction: the command "gh workflow run" does not work here, because GitHub only runs manually-started workflows that exist on the main branch and this work is on prod-hardening. Pushing to the branch starts a deploy. Pushing a file called .github/DESTROY containing the word destroy starts a teardown. Pushes that only change documentation do not start a deploy.
To rebuild: run the bootstrap step again (terraform -chdir=terraform/bootstrap init, then apply), then push any commit to prod-hardening. It takes about 20 minutes.

How to run it yourself
1. terraform -chdir=terraform/bootstrap init, then apply (once).
2. git push origin prod-hardening (this starts the deploy).
3. aws eks update-kubeconfig --name pf-istio-envoy-eks --region ap-southeast-2, then python3 scripts/verify.py to repeat the proof.
Tests without any cluster: mvn -B verify (needs Java 25 and Maven).
