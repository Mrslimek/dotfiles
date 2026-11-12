-- ============================================================================
-- HYPRLAND CONFIG
-- ============================================================================

hl.config({
    input = {
        kb_layout   = "us,ru",
        kb_options  = "grp:win_space_toggle",
        sensitivity = 0.1,
        
        accel_profile = "adaptive",
        
        touchpad    = {
        	scroll_factor  = 1,
            natural_scroll = true,
            tap_to_click   = true,
            -- clickfinger_behavior = true,
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
        -- layout      = "dwindle",
        layout      = "monocle",
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

	hl.config({
	    plugin = {
	        hymission = {
	            -- Layout
	            layout_engine = "natural",
	            outer_padding_top = 32,
	            outer_padding_right = 32,
	            outer_padding_bottom = 32,
	            outer_padding_left = 32,

	            row_spacing = 28,
	            column_spacing = 28,

	            min_window_length = 120,
	            small_window_boost = 1.35,
	            max_preview_scale = 0.95,

	            -- Workspace scope
	            only_active_workspace = 1,
	            only_active_monitor = 0,
	            show_special = 0,
	            multi_workspace_sort_recent_first = 1,

	            -- Window selection
	            selected_expand_scale = 1.18,
	            hover_expand_scale = 1.18,
	            overview_focus_follows_mouse = 1,

	            -- Workspace strip
	            workspace_strip_anchor = "top",
	            workspace_strip_thickness = 160,
	            workspace_strip_gap = 24,

	            -- Animations and behavior
	            workspace_change_keeps_overview = 1,
	            gesture_invert_vertical = 0,
	        },
	    },
	}),

	hl.plugin.hymission.gesture({
	    fingers = 3,
	    direction = "vertical",
	    action = "toggle",
	    scale = 0.5,
	})
})
