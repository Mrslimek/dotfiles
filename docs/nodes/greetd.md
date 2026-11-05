---
node: greetd
title: greetd
section: User session
status: done
---

# greetd

## Role

Minimal login manager on VT1. Starts the Noctalia greeter session (user `greeter`); the greeter authenticates and launches the user session via uwsm.

## Facts

- Config: `/etc/greetd/config.toml` → `command = "noctalia-greeter-session"`

## Links

- [greetd manual](https://man.sr.ht/~kennylevinsen/greetd/)
- [ArchWiki: Greetd](https://wiki.archlinux.org/title/Greetd)
