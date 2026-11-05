---
node: systemd
title: systemd
section: Boot
status: done
---

# systemd

## Role

PID 1: init, service and unit manager. Owns both the system manager (all services below) and the per-user manager (`systemd --user`) that runs the whole session stack via uwsm.

## Facts

- Default target: graphical
- User manager runs: PipeWire stack, MPD, Syncthing, Vicinae, MPRIS bridges, gnome-keyring

## Links

- [ArchWiki: systemd](https://wiki.archlinux.org/title/Systemd)
