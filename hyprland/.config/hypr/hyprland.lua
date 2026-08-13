-- ============================================================================
-- HYPRLAND LUA CONFIG — v0.55+
-- ============================================================================

-- ============================================================================
-- THEME VARIABLES
-- ============================================================================
-- OPTION 1: Libadwaita Neutral (Grey/Graphite)

local THEME = {
    active_border_1 = "rgba(b0b0b0ff)",
    active_border_2 = "rgba(666666ff)",
    inactive_border = "rgba(303030ff)",
    main_bg_alt     = "rgba(242424ff)",
    warning_color   = "rgba(f5c211ff)",
    gtk_theme_env   = "adw-gtk3-dark"
}

-- ============================================================================
-- ENVIRONMENT VARIABLES
-- ============================================================================

hl.env("GTK_THEME", THEME.gtk_theme_env)

-- Отключаем DRM buffer modifiers (тилинг/DCC).
-- На amdgpu DCN 3.1.4 (Radeon 780M) некоторые modifiers дают артефакты на
-- последнем scanline — мерцающую белую 1px линию внизу экрана. Проявляется во
-- ВСЕХ Wayland-композиторах (Hyprland, GNOME — Aquamarine/Mutter используют
-- modifiers для DMA-BUF), но НЕ на TTY (там простой линейный framebuffer).
-- Линейные буферы убирают артефакт ценой чуть большего потребления памяти.
hl.env("AQ_DRM_NO_MODIFIERS", "1")

-- ============================================================================
-- AUTOSTART
-- ============================================================================

hl.on("hyprland.start", function()
    hl.exec_cmd("uwsm app -- noctalia")
    hl.exec_cmd("hyprpm reload")
end)

-- ============================================================================
-- MONITORS
-- ============================================================================

hl.monitor({
    output   = "eDP-1",
    mode     = "3200x2000@120",
    -- mode     = "3200x2000@60",
    position = "1841x1080",
    scale    = 2.0,
})

hl.monitor({
    output   = "DP-1",
    mode     = "1920x1080@74.97",
    position = "1720x0",
    scale    = 1.0,
})

-- ============================================================================
-- CONFIG
-- ============================================================================

hl.config({
    input = {
        kb_layout   = "us,ru",
        kb_options  = "grp:win_space_toggle",
        sensitivity = 0.3,
        touchpad    = {
            natural_scroll       = true,
            tap_to_click         = true,
            disable_while_typing = true,
        },
    },

    general = {
        border_size = 2,
        gaps_in     = 5,
        gaps_out    = 10,
        layout      = "dwindle",

        col         = {
            active_border   = { colors = { THEME.active_border_1, THEME.active_border_2 }, angle = 45 },
            inactive_border = THEME.inactive_border,
        },
    },

    decoration = {
        rounding         = 8,
        active_opacity   = 1.0,
        inactive_opacity = 0.90,

        blur             = {
            enabled = false,
        },

        shadow           = {
            enabled = false,
        },
    },

    group = {
        col = {
            border_active   = THEME.active_border_1,
            border_inactive = THEME.inactive_border,
        },

        groupbar = {
            enabled       = true,
            font_family   = "Open Sans",
            font_size     = 10,
            height        = 10,
            render_titles = true,

            col           = {
                active        = THEME.active_border_1,
                inactive      = THEME.main_bg_alt,
                locked_active = THEME.warning_color,
            },
        },
    },

    misc = {
        vrr                      = 0,
        disable_hyprland_logo    = true,
        disable_splash_rendering = true,
        force_default_wallpaper  = 0,
        mouse_move_enables_dpms  = true,
        key_press_enables_dpms   = true,
    },

    xwayland = {
        enabled            = true,
        force_zero_scaling = true,
    },
})

-- ============================================================================
-- ANIMATIONS
-- ============================================================================

hl.curve("quick", { type = "bezier", points = { { 0.05, 0.9 }, { 0.1, 1.05 } } })

hl.animation({ leaf = "windows", enabled = true, speed = 1.5, bezier = "quick", style = "popin 80%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 1.2, bezier = "quick", style = "slide" })
hl.animation({ leaf = "fade", enabled = true, speed = 1.5, bezier = "quick" })

-- ============================================================================
-- DEVICES
-- ============================================================================

hl.device({
    name   = "huion-huion-tablet_h420x-pen",
    output = "HDMI-A-1",
})

-- ============================================================================
-- GESTURES
-- ============================================================================

-- ============================================================================
-- WINDOW RULES
-- ============================================================================
hl.window_rule({
    name   = "float-all-by-default",
    match  = { class = ".*" },
    float  = true,
    center = true,
})

hl.window_rule({
    name              = "pip-rules",
    match             = { title = "^([Pp]icture[-\\s]?[Ii]n[-\\s]?[Pp]icture)(.*)$" },
    float             = true,
    keep_aspect_ratio = true,
    move              = "73% 72%",
    size              = "25% 25%",
    pin               = true,
})

hl.window_rule({
    name  = "satty",
    match = { class = "^com.gabm.satty$" },
    float = true,
    max_size = { 1280, 720 },
})

local CASCADE_STEP = 36
local CASCADE_WRAP  = 8

hl.on("window.open", function(w)
    if not w then return end

    local is_float, wname = false, nil
    pcall(function() is_float = w.floating; wname = w.workspace.name end)
    if not is_float or not wname then return end

    local count = 0
    pcall(function()
        for _, o in ipairs(hl.get_windows() or {}) do
            local of, oname = false, nil
            pcall(function() of = o.floating; oname = o.workspace.name end)
            if of and oname == wname then count = count + 1 end
        end
    end)
    if count < 2 then return end
    local off = ((count - 1) % CASCADE_WRAP) * CASCADE_STEP
    pcall(hl.dispatch, hl.dsp.window.move({ x = off, y = off, relative = true, window = w }))
end)

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


-- For Noctalia Color templates
require("noctalia").apply_theme()
