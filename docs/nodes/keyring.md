---
node: keyring
title: gnome-keyring
section: User session
status: open
---

# gnome-keyring

## Role

Session secret storage: keyring daemon + libsecret provider; runs as a user socket service.

## Facts

- KeePassXC installed in parallel (password databases — different role)

## Open questions

- Is gnome-keyring still needed, or does KeePassXC's agent cover the secrets role?
- What actually consumes keyring secrets on this system (Wi-Fi, Git, browser)?

## Links

- [GNOME Keyring](https://wiki.gnome.org/Projects/GnomeKeyring)
- [ArchWiki: GNOME/Keyring](https://wiki.archlinux.org/title/GNOME/Keyring)
