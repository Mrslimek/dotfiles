-- ============================================================================
-- KEYBINDINGS
-- ============================================================================

local APPS = {
    mod          = "SUPER",
    terminal     = "alacritty",
    explorer     = "nautilus",
    editor       = "codium",
    browser      = "zen-browser",
    ipc          = "qs -c noctalia-shell ipc call",
    noctalia_msg = "noctalia msg"
}

-- Launchers
hl.bind(APPS.mod .. " + T", hl.dsp.exec_cmd("uwsm app -- " .. APPS.terminal))
hl.bind(APPS.mod .. " + F", hl.dsp.exec_cmd("uwsm app -- " .. APPS.explorer))
hl.bind(APPS.mod .. " + B", hl.dsp.exec_cmd("uwsm app -- " .. APPS.browser))
-- hl.bind(APPS.mod .. " + L", hl.dsp.exec_cmd("loginctl lock-session"))
hl.bind(APPS.mod .. " + N", hl.dsp.exec_cmd("swaync-client -t -sw"))

-- Vicinae
hl.bind(APPS.mod .. " + A", hl.dsp.exec_cmd("vicinae toggle"))
hl.bind(APPS.mod .. " + V", hl.dsp.exec_cmd("vicinae vicinae://launch/clipboard/history"))
hl.bind(APPS.mod .. " + comma", hl.dsp.exec_cmd("vicinae vicinae://launch/core/search-emojis"))

-- Window Management
hl.bind(APPS.mod .. " + Q", hl.dsp.window.close())
hl.bind(APPS.mod .. " + W", hl.dsp.window.float({ action = "toggle" }))
hl.bind("SHIFT + F11", hl.dsp.window.fullscreen())

-- Groups
-- hl.bind(APPS.mod .. " + G", hl.dsp.group.toggle())
-- hl.bind(APPS.mod .. " + Tab", hl.dsp.group.prev())

hl.bind(APPS.mod .. " + Z", hl.dsp.window.drag(), { mouse = true })
hl.bind(APPS.mod .. " + X", hl.dsp.window.resize(), { mouse = true })

-- Noctalia Shell:
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd(APPS.noctalia_msg .. " volume-up"),
    { repeating = true, locked = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd(APPS.noctalia_msg .. " volume-down"),
    { repeating = true, locked = true })
hl.bind("XF86AudioMute", hl.dsp.exec_cmd(APPS.noctalia_msg .. " volume-mute"), { locked = true })
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd(APPS.noctalia_msg .. " brightness-up"),
    { repeating = true, locked = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd(APPS.noctalia_msg .. " brightness-down"),
    { repeating = true, locked = true })
hl.bind("SUPER + slash", hl.dsp.exec_cmd(APPS.noctalia_msg .. " settings-toggle"))
hl.bind("XF86Assistant", hl.dsp.exec_cmd(APPS.noctalia_msg .. " session lock-and-suspend"))
-- hl.bind("F23", hl.dsp.exec_cmd(APPS.noctalia_msg .. " session lock-and-suspend"))
hl.bind("CTRL + ALT + Delete", hl.dsp.exec_cmd(APPS.noctalia_msg .. " panel-toggle session"))
-- hl.bind("SUPER + c", hl.dsp.exec_cmd(APPS.noctalia_msg .. " panel-toggle control-center calendar"))
hl.bind("SUPER + m", hl.dsp.exec_cmd(APPS.noctalia_msg .. " panel-toggle control-center media"))
hl.bind("SUPER + p", hl.dsp.exec_cmd(APPS.noctalia_msg .. " media toggle"))
hl.bind("SUPER + bracketleft", hl.dsp.exec_cmd(APPS.noctalia_msg .. " media previous"))
hl.bind("SUPER + bracketright", hl.dsp.exec_cmd(APPS.noctalia_msg .. " media next"))

-- Screenshots
-- hl.bind(APPS.mod .. " + ALT + P", hl.dsp.exec_cmd("grimblast save area - | satty --filename -"))
hl.bind("ALT + SHIFT + 2", hl.dsp.exec_cmd("grimblast save area - | satty --filename -"))
hl.bind("Print", hl.plugin.hyprcapture.open)
-- hl.bind(APPS.mod .. " + ALT + o", hl.dsp.exec_cmd("grimblast save screen - | satty --filename -"))

-- Workspaces
for i = 1, 10 do
    local key = i % 10 -- 10 maps to key 0
    hl.bind(APPS.mod .. " + " .. key, hl.dsp.focus({ workspace = i }))
    hl.bind(APPS.mod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }))
end

-- Special workspaces
hl.bind(APPS.mod .. " + S", hl.dsp.workspace.toggle_special())
hl.bind(APPS.mod .. " + SHIFT + S", hl.dsp.window.move({ workspace = "special" }))
hl.bind(APPS.mod .. " + SHIFT + W", hl.dsp.window.move({ workspace = "+0" }))

-- hl.bind("ALT + TAB", hl.plugin.hymission.toggle)
hl.bind("ALT + TAB", function()
    hl.plugin.hymission.toggle("onlycurrentworkspace")
end)
-- hl.bind("SUPER + A", function()
--     hl.plugin.hymission.toggle("forceall")
-- end)
-- hl.bind("SUPER + M", hl.plugin.hymission.debug_current_layout)
