-- ============================================================================
-- AUTOSTART
-- ============================================================================

hl.on("hyprland.start", function()
    hl.exec_cmd("uwsm app -- noctalia")
    hl.exec_cmd("hyprpm reload")
end)
