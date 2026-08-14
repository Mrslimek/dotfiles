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
