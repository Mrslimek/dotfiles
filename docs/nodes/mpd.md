---
node: mpd
title: MPD
section: Audio & media
status: open
---

# MPD

## Role

Headless music server: plays `~/Music`, outputs to PipeWire (PulseAudio API). Controlled by Euphonica (native protocol) and Noctalia (via mpd-mpris MPRIS).

## Facts

- User service; config `~/.config/mpd/mpd.conf`; `auto_update yes`

## Open questions

- Is the server/client split (MPD + separate UIs) still the right model vs a single local player?
- Is the MPD → PipeWire (PulseAudio API) output path the right one, or is direct ALSA / bit-perfect worth it?
- Which client set is final: Euphonica + Noctalia + mpd-mpris, or fewer layers?

## Links

- [MPD documentation](https://mpd.readthedocs.io)
- [ArchWiki: MPD](https://wiki.archlinux.org/title/Music_Player_Daemon)
