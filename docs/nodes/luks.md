---
node: luks
title: LUKS2
section: Boot
status: done
---

# LUKS2

## Role

LUKS2 encryption of the root partition. Unlocked in early userspace by systemd with a key sealed in TPM2 (PCR policy); discards enabled.

## Facts

- Cmdline: `rd.luks.options=tpm2-device=auto,discard`
- Recovery: `systemd-boot/TPM2-RECOVERY.md` in this repo

## Links

- [ArchWiki: dm-crypt/Encrypting an entire system](https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system)
- [systemd-cryptenroll](https://www.freedesktop.org/software/systemd/man/latest/systemd-cryptenroll.html)
