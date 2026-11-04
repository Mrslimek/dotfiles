# Arch Linux dotfiles

**Interactive system architecture graph:** <https://mrslimek.github.io/dotfiles/>

`index.html` in this repo is a live map of my actual system: boot chain (UEFI → systemd-boot → UKI kernel → LUKS2 → systemd), system services, user session and the audio/media stack — laid out as a vertical tree. Click a node to highlight its connections, scroll to zoom, drag to pan. The source of truth for what runs on the machine is the graph itself; it is regenerated from the real system state, not from this README.

This dotfiles were written on the system with packages that are listed in the pkglist.txt.
They can be installed using pacman with this command:
```bash
sudo pacman -S --needed - < pkglist.txt
```
