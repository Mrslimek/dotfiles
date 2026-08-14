-- ============================================================================
-- HYPRLAND CONFIG
-- ============================================================================

hl.config({
    input = {
        kb_layout   = "us,ru",
        kb_options  = "grp:win_space_toggle",
        sensitivity = 0.3,
        touchpad    = {
            natural_scroll       = true,
            tap_to_click   = true,
            -- NOTE: Commented, because i use keyd to remap some keyboard buttons and it conflicts with hyprland
            -- Configuration for this keyd virtual keyboard lives in /etc/libinput and /etc/keyd
            -- NOTE: Try to configure everything, related to keyboard on low level, using keyd and use hyprland only for compositor-level configs
            -- disable_while_typing = true,
        },
    },

    general = {
        border_size = 2,
        gaps_in     = 5,
        gaps_out    = 10,
        layout      = "dwindle",
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
        groupbar = {
            enabled       = true,
            font_family   = "Open Sans",
            font_size     = 10,
            height        = 10,
            render_titles = true,
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
