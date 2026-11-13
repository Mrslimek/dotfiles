# uwsm

**Status: active — launch wrapper, not session manager.**

The session is NOT started via uwsm: `start-umbriel` (wayland-sessions entry)
starts the custom `umbriel.service` user unit directly.

uwsm is here because vicinae auto-detects it as the app launch prefix
(`uwsm-app --`, see vicinae journal: "Detected launch prefix"). Every app
launched from vicinae goes through `uwsm app-daemon`
(`wayland-wm-app-daemon.service`) into a systemd scope in
`app-graphical.slice` — per-app cgroups and clean teardown.

Historical: before the Umbriel migration (2026-11) the session itself was
uwsm-managed (`wayland-wm@hyprland`).
