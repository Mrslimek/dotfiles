---
node: mkinitcpio
title: mkinitcpio
section: Boot
status: done
---

# mkinitcpio

## Role

Generates the UKI (kernel + initramfs + cmdline) and the boot entries systemd-boot consumes.

## Facts

- Preset: `default_uki=/boot/EFI/Linux/arch-linux.efi` (+ fallback)
- Hooks: base systemd autodetect microcode modconf kms keyboard sd-vconsole block sd-encrypt filesystems fsck

## Links

- [ArchWiki: mkinitcpio](https://wiki.archlinux.org/title/Mkinitcpio)
