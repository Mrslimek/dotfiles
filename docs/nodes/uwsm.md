---
node: uwsm
title: uwsm
section: User session
status: done
---

# uwsm

## Role

Universal Wayland Session Manager. Wraps the compositor launch into systemd user units (`wayland-wm@hyprland`): clean session lifecycle, app slices (`uwsm app --`).

## Facts

- Greeter starts the session as `uwsm` (session "Hyprland (uwsm-managed)")
- Hyprland autostart runs `uwsm app -- noctalia`

## Links

- [uwsm GitHub](https://github.com/Vladimir-csp/uwsm)
