---
node: sdboot
title: systemd-boot
section: Boot
status: done
---

# systemd-boot

## Role

EFI bootloader shipped with systemd. Launches the signed UKI (`arch-linux.efi`) straight from the ESP, no menu.

## Facts

- UKI = kernel + initramfs + cmdline in one EFI binary, built by mkinitcpio
- TPM2 recovery notes: `systemd-boot/TPM2-RECOVERY.md` in this repo

## Links

- [ArchWiki: systemd-boot](https://wiki.archlinux.org/title/Systemd-boot)
- [systemd-boot manual](https://www.freedesktop.org/software/systemd/man/latest/systemd-boot.html)
