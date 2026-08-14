-- ============================================================================
-- ANIMATIONS
-- ============================================================================

hl.curve("quick", { type = "bezier", points = { { 0.05, 0.9 }, { 0.1, 1.05 } } })

hl.animation({ leaf = "windows", enabled = true, speed = 1.5, bezier = "quick", style = "popin 80%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 1.2, bezier = "quick", style = "slide" })
hl.animation({ leaf = "fade", enabled = true, speed = 1.5, bezier = "quick" })
