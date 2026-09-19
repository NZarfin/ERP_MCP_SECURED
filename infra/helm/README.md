# infra/helm

Helm charts for gateway, renderer, automation-engine, ingestion workers and each
plugin — all stateless, HPA-scaled (`docs/ARCHITECTURE.md` §3). A Silo-tier tenant
uses the same chart with its own values file. Added once there is a service worth
deploying past `docker-compose` (phase 2+); phase 0/1 run locally.
