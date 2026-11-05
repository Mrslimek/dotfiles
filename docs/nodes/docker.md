---
node: docker
title: Docker
section: System services
status: open
---

# Docker

## Role

Container runtime for development. Installed but not part of the running system: service and socket disabled, started manually on demand.

## Facts

- docker, docker-compose, buildx installed

## Open questions

- Docker vs Podman (rootless, daemonless, systemd-native) — is the daemon model still acceptable?
- Is the toolchain actually used, or a leftover to remove?

## Links

- [Docker documentation](https://docs.docker.com)
- [Podman](https://podman.io)
