## =============================================================================
## CHRONOLOGY MOD — timeline_screen.rpy
## =============================================================================

## -- Keybind ------------------------------------------------------------------
init python:
    config.keymap["chronology_toggle"] = ["t"]
    config.overlay_screens.append("_tl_keylistener")
    config.overlay_screens.append("_tl_debug_overlay")

init:
    transform tl_layer_blur:
        blur 48
        matrixcolor SaturationMatrix(0.6)

init python:
    def _tl_toggle():
        if renpy.get_screen("timeline"):
            renpy.layer_at_list([], layer="master")
            renpy.hide_screen("timeline")
        else:
            renpy.layer_at_list([tl_layer_blur], layer="master")
            renpy.show_screen("timeline")

## =============================================================================
## Design tokens — all colours and sizes in one place
## =============================================================================

init python:
    # ── Contrast helpers ───────────────────────────────────────────────────
    def hex_to_rgb(hex_color):
        """Convert #rrggbb to (r,g,b) 0–255."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def relative_luminance(rgb):
        """Return relative luminance for contrast calculation (0–1)."""
        def channel(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = rgb
        return 0.2126*channel(r) + 0.7152*channel(g) + 0.0722*channel(b)

    def contrast_ratio(rgb1, rgb2):
        """Contrast ratio as per WCAG (1–21)."""
        l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
        if l1 < l2: l1, l2 = l2, l1
        return (l1 + 0.05) / (l2 + 0.05)

    def pick_accent_color(bg_colors, fallback="#e8c97e"):
        """Choose a readable accent color over given bg_colors."""
        candidates = [
            getattr(gui, "accent_color", None),
            getattr(gui, "choice_button_text_hover_color", None),
            getattr(gui, "hover_color", None),
            getattr(gui, "selected_color", None),
        ]

        for c in candidates:
            if not c:
                continue
            rgb = hex_to_rgb(c)
            if rgb == (255,255,255):  # skip pure white
                continue

            # check contrast against all backgrounds
            ok = all(contrast_ratio(rgb, hex_to_rgb(bg)) >= 3.0 for bg in bg_colors)
            if ok:
                return c

        return fallback  # nothing suitable found

    # ── Backgrounds to contrast against ──────────────────────────────────
    header_bg = "#000000bb"   # same as TL["header_bg"]
    footer_bg = "#00000055"   # same as TL["footer_bg"]
    accent_color = pick_accent_color([header_bg, footer_bg])

    # ── Timeline mod colors ──────────────────────────────────────────────
    TL = {
        ## Accent color
        "accent": accent_color,

        ## Overlay
        "overlay_bg"    : "#00000099",   ## 60% black base
        "noise_alpha"   : "#ffffff0c",   ## subtle noise tint

        ## Header
        "header_bg"     : header_bg,
        "header_text"   : "#f0ece4",
        "header_sub"    : "#9a9183",
        "new_dot"       : accent_color,     ## warm gold for new-content dot

        ## Card
        "card_bg"       : "#00000000",   ## transparent — no card bg
        "thumb_bg"      : "#0a0a0a",
        "divider"       : accent_color + "55",  ## semi-transparent

        ## Option rows
        "opt_chosen_fg" : "#f0ece4",     ## chosen this run — kept for arrow colour
        "opt_fg"        : "#f0ece4",     ## all option text — uniform, no muting
        "opt_new_dot"   : accent_color,     ## gold dot for unseen options

        ## Footer row
        "footer_bg"     : footer_bg,
        "footer_text"   : "#9a9183",
        "btn_bg"        : "#ffffff14",
        "btn_hover_bg"  : "#ffffff28",
        "btn_text"      : "#c8c0b4",

        ## Modal
        "modal_bg"      : "#1a1814ee",
        "modal_header"  : "#f0ece4",
    }

## =============================================================================
## Styles — fully explicit, no inheritance from game or mod style chains
## =============================================================================

init python:
    import os as _os
    _tl_mod_abs    = _os.path.join(renpy.config.gamedir, "timeline-mod", "fonts")

    default_font = None
    default_bold  = None

    try:
        default_font = getattr(gui, "text_font", None)
    except Exception:
        default_font = None

    try:
        default_bold = getattr(gui, "name_text_font", None) or getattr(gui, "interface_text_font", None)
    except Exception:
        default_bold = None

    if default_font:
        _tl_font_reg = default_font
    else:
        _tl_font_reg = "timeline-mod/fonts/Inter-Regular.ttf"

    if default_bold:
        _tl_font_bold = default_bold
    else:
        _tl_font_bold = "timeline-mod/fonts/Inter-Bold.ttf"

    _tl_mod_abs = _os.path.join(renpy.config.gamedir, "timeline-mod", "fonts")
    if not _os.path.exists(_os.path.join(_tl_mod_abs, "Inter-Regular.ttf")):
        if _os.path.exists(_os.path.join(_tl_mod_abs, "InterVariable.ttf")):
            _tl_font_reg  = "timeline-mod/fonts/InterVariable.ttf"
            _tl_font_bold = "timeline-mod/fonts/InterVariable.ttf"
        else:
            _tl_font_reg  = "DejaVuSans.ttf"
            _tl_font_bold = "DejaVuSans-Bold.ttf"


init python:
    _tl_renpy_major = renpy.version_tuple[0]   ## 7 or 8
    _tl_renpy_minor = renpy.version_tuple[1]

style tl_base is text:
    font _tl_font_reg
    size TL_SIZE_BODY
    color "#f0ece4"
    italic False
    bold False
    underline False
    strikethrough False
    outlines []
    drop_shadow None
    kerning 0.0
    layout "tex"

style tl_base_bold is text:
    font _tl_font_bold
    size TL_SIZE_BODY
    color "#f0ece4"
    italic False
    bold False
    underline False
    strikethrough False
    outlines []
    drop_shadow None
    kerning 0.0

style tl_icon is text:
    font "DejaVuSans.ttf"
    size TL_SIZE_DOT
    color "#f0ece4"
    italic False
    bold False
    outlines []
    drop_shadow None

style tl_frame_base is _default:
    background None
    padding (0, 0, 0, 0)

init python:
    def _tl_noise_bg():
        return Solid(TL["noise_alpha"])

## =============================================================================
## Main timeline screen
## =============================================================================

screen timeline():
    modal True
    zorder 200

    key "chronology_toggle" action Function(_tl_toggle)
    key "K_ESCAPE"        action Function(_tl_toggle)

    add tl_layer_blur
    add Solid("#111111cc")
    add _tl_noise_bg()

    vbox:
        xfill True yfill True
        spacing 0

        frame:
            style "tl_frame_base"
            xfill True
            background Solid(TL["header_bg"])
            padding (40, 20, 40, 20)

            hbox:
                xfill True
                spacing 0
                yalign 0.5

                vbox:
                    spacing 4
                    text "CHRONOLOGY":
                        style "tl_base_bold"
                        size TL_SIZE_TITLE
                        color TL["header_text"]
                    text "Choice History":
                        style "tl_base"
                        size TL_SIZE_BODY
                        color TL["header_sub"]

                null xfill True

                python:
                    _tl_playthrough_new = sum(
                        1 for _n in _tl_history if _tl_node_has_new(_n))

                if _tl_playthrough_new > 0:
                    hbox:
                        spacing 10
                        yalign 0.5

                        text "●":
                            style "tl_icon"
                            size TL_SIZE_DOT
                            color TL["new_dot"]
                            yalign 0.5
                            italic False

                        text "{} choice{} with new paths".format(
                                _tl_playthrough_new,
                                "s" if _tl_playthrough_new != 1 else ""):
                            style "tl_base"
                            size TL_SIZE_BODY
                            color TL["new_dot"]
                            yalign 0.5

        frame:
            style "tl_frame_base"
            xfill True ysize 3
            background Solid(TL["divider"])

        if not _tl_history:
            frame:
                style "tl_frame_base"
                xfill True yfill True
                background None

                vbox:
                    xalign 0.5 yalign 0.5
                    spacing 12
                    text "No choices recorded yet.":
                        style "tl_base_bold"
                        size TL_SIZE_BODY
                        color TL["header_text"]
                        xalign 0.5
                    text "Chronology records choices from the point it was installed.":
                        style "tl_base"
                        size TL_SIZE_BODY
                        color TL["header_sub"]
                        xalign 0.5
                    text "Continue playing and choices will appear here.":
                        style "tl_base"
                        size TL_SIZE_BODY
                        color TL["header_sub"]
                        xalign 0.5
        else:
            viewport:
                xfill True yfill True
                mousewheel True
                draggable True
                yadjustment ui.adjustment(value=999999)

                python:
                    _tl_side_pad = 40
                    _tl_spacing  = 16
                    _tl_avail    = config.screen_width - (_tl_side_pad * 2)
                    _tl_max_cols = max(1, (_tl_avail + _tl_spacing) // (160 + _tl_spacing))
                    _tl_cols     = min(5, _tl_max_cols)
                    _tl_card_w   = (_tl_avail - (_tl_spacing * (_tl_cols - 1))) // _tl_cols
                    _tl_rows_list = []
                    for _i in range(0, len(_tl_history), _tl_cols):
                        _tl_rows_list.append(_tl_history[_i:_i+_tl_cols])

                frame:
                    style "tl_frame_base"
                    xfill True
                    padding (40, 30, 40, 30)
                    background None

                    vbox:
                        xfill True
                        spacing _tl_spacing

                        for _row in _tl_rows_list:
                            hbox:
                                spacing _tl_spacing

                                for _node in _row:
                                    use tl_card(_node, _tl_card_w)

                                python:
                                    _tl_pad_count = _tl_cols - len(_row)
                                for _p in range(_tl_pad_count):
                                    null xsize _tl_card_w

    if _tl_modal_node is not None:
        use tl_modal(_tl_modal_node)

    button:
        style "tl_frame_base"
        xpos config.screen_width - 20
        ypos 20
        xanchor 1.0
        yanchor 0.0
        background None
        hover_background None
        padding (12, 12, 12, 12)
        action Function(_tl_toggle)

        text "✕":
            style "tl_icon"
            size TL_SIZE_BODY
            color TL["btn_text"]
            hover_color TL["header_text"]
            italic False


## =============================================================================
## Card screen
## =============================================================================

screen tl_card(node, cw=300):

    python:
        _tl_is_current = (node["index"] == len(_tl_history) - 1 and
                            node.get("chosen_index") is None)
        _tl_has_thumb  = node.get("thumb_bytes") is not None
        _tl_thumb_h    = int(cw * 9 / 16)
        if _tl_has_thumb:
            _tl_tdisp = _tl_thumb_displayable(
                node["thumb_bytes"],
                node["index"])
        _tl_chosen_label = (
            node["options"][node["chosen_index"]]
            if node.get("chosen_index") is not None
            else None)
        _tl_has_new = _tl_node_has_new(node)

    vbox:
        xsize cw
        spacing 0

        frame:
            style "tl_frame_base"
            xsize cw
            ysize _tl_thumb_h
            background Solid(TL["thumb_bg"])

            if _tl_has_thumb:
                add _tl_tdisp:
                    xsize cw
                    ysize _tl_thumb_h
                    fit "contain"
                    xalign 0.5
                    yalign 0.5
            else:
                text "#{:02d}".format(node["index"] + 1):
                    style "tl_base_bold"
                    size TL_SIZE_TITLE
                    color "#2a2820"
                    xalign 0.5 yalign 0.5

        if _tl_is_current:
            use tl_card_current(node, cw)
        else:
            use tl_card_past(node, _tl_chosen_label, _tl_has_new, cw)


## =============================================================================
## Past card body
## =============================================================================

screen tl_card_past(node, chosen_label, has_new, cw=300):

    vbox:
        xsize cw
        spacing 0

        frame:
            style "tl_frame_base"
            xsize cw
            padding (12, 10, 12, 10)
            background Solid("#00000044")

            hbox:
                xsize cw - 24
                spacing 8
                yalign 0.5

                text (chosen_label or "—"):
                    style "tl_base"
                    size TL_SIZE_BODY
                    color TL["opt_chosen_fg"]
                    xmaximum cw - 28
                    yalign 0.5

        frame:
            style "tl_frame_base"
            xsize cw ysize 1
            background Solid(TL["divider"])

        hbox:
            xsize cw
            spacing 0

            frame:
                style "tl_frame_base"
                xsize cw // 2
                ysize 46
                padding (12, 0, 8, 0)
                background Solid(TL["footer_bg"])

                if has_new:
                    hbox:
                        spacing 6 yalign 0.5

                        text "●":
                            style "tl_icon"
                            size TL_SIZE_DOT
                            color TL["new_dot"]
                            yalign 0.5
                            italic False

                        text "New":
                            style "tl_base"
                            size TL_SIZE_BODY
                            color TL["new_dot"]
                            yalign 0.5
                else:
                    text "All seen":
                        style "tl_base"
                        size TL_SIZE_BODY
                        color TL["header_sub"]
                        yalign 0.5

            button:
                style "tl_frame_base"
                xsize cw // 2
                ysize 46
                padding (0, 0, 0, 0)
                background Solid(TL["footer_bg"])
                hover_background Solid(TL["btn_hover_bg"])
                action SetVariable("_tl_modal_node", node)

                text "All options {font=DejaVuSans.ttf}▾{/font}":
                    style "tl_base"
                    size TL_SIZE_BODY
                    color TL["btn_text"]
                    hover_color TL["header_text"]
                    xalign 0.5 yalign 0.5


## =============================================================================
## Current card body — all options as rows
## =============================================================================

screen tl_card_current(node, cw=300):

    vbox:
        xsize cw
        spacing 0

        for _i, _opt in enumerate(node["options"]):
            python:
                _tl_show_dot = not _tl_option_seen(node, _i)

            frame:
                style "tl_frame_base"
                xsize cw
                padding (12, 10, 12, 10)
                background Solid("#00000033")

                hbox:
                    xsize cw - 24
                    spacing 8
                    yalign 0.5

                    if _tl_show_dot:
                        text "●":
                            style "tl_icon"
                            size TL_SIZE_DOT
                            color TL["opt_new_dot"]
                            yalign 0.5
                    else:
                        null xsize 14

                    text _opt:
                        style "tl_base"
                        size TL_SIZE_BODY
                        color TL["opt_fg"]
                        xmaximum cw - 44
                        yalign 0.5

            if _i < len(node["options"]) - 1:
                frame:
                    style "tl_frame_base"
                    xsize cw ysize 1
                    background Solid(TL["divider"])

        frame:
            style "tl_frame_base"
            xsize cw
            padding (0, 6, 10, 6)
            background None

            frame:
                style "tl_frame_base"
                padding (10, 5, 10, 5)
                background Solid(TL["accent"])
                xalign 0.0

                text "NOW":
                    style "tl_base_bold"
                    size TL_SIZE_BODY
                    color "#1a1408"
                    italic False


## =============================================================================
## Modal
## =============================================================================

screen tl_modal(node):
    modal True
    zorder 300

    key "K_ESCAPE" action SetVariable("_tl_modal_node", None)

    frame:
        style "tl_frame_base"
        xfill True yfill True
        background Solid("#000000aa")

        button:
            style "tl_frame_base"
            xfill True yfill True
            background None
            action SetVariable("_tl_modal_node", None)

    python:
        _tl_m_w         = 500
        _tl_m_pad       = 28
        _tl_m_has_thumb = node.get("thumb_bytes") is not None
        _tl_m_thumb_w   = _tl_m_w - (_tl_m_pad * 2)
        _tl_m_thumb_h   = int(_tl_m_thumb_w * 9 / 16)
        if _tl_m_has_thumb:
            _tl_m_tdisp = _tl_thumb_displayable(node["thumb_bytes"], node["index"])
        _tl_m_row_h        = 52
        _tl_m_opt_count    = len(node.get("options", []))
        _tl_m_list_h       = _tl_m_opt_count * (_tl_m_row_h + 2)
        _tl_m_max_list     = 300
        _tl_m_needs_scroll = _tl_m_list_h > _tl_m_max_list

    frame:
        xsize _tl_m_w + 32
        xalign 0.5
        yalign 0.45
        background None
        padding (0,0,0,0)

        frame:
            style "tl_frame_base"
            xfill True
            background Solid("#111111cc")
            padding (28, 16, 28, 16)

            vbox:
                xfill True
                spacing 0

                frame:
                    style "tl_frame_base"
                    xfill True
                    padding (8, 2, 8, 2)
                    background None

                    button:
                        style "tl_frame_base"
                        xalign 1.0
                        background None
                        hover_background Solid("#ffffff14")
                        padding (12, 6, 12, 6)
                        action SetVariable("_tl_modal_node", None)

                        text "✕":
                            style "tl_icon"
                            size TL_SIZE_BODY
                            color TL["btn_text"]
                            hover_color TL["header_text"]
                            italic False

                frame:
                    style "tl_frame_base"
                    xfill True
                    padding (28, 16, 28, 16)
                    background None

                    vbox:
                        xfill True
                        spacing 0

                        if _tl_m_has_thumb:
                            frame:
                                style "tl_frame_base"
                                xfill True
                                background Solid(TL["thumb_bg"])
                                padding (0, 0, 0, 0)

                                add _tl_m_tdisp:
                                    ysize _tl_m_thumb_h
                                    fit "cover"
                                    xalign 0.5
                                    yalign 0.5

                        frame:
                            style "tl_frame_base"
                            xfill True
                            padding (0, 28, 0, 12)
                            background None

                            text "All options":
                                style "tl_base_bold"
                                size TL_SIZE_HEADER
                                color TL["modal_header"]

                        frame:
                            style "tl_frame_base"
                            xfill True ysize 3
                            background Solid(TL["divider"])

                        frame:
                            style "tl_frame_base"
                            xfill True ysize 10
                            background None

                        if _tl_m_needs_scroll:
                            viewport:
                                xfill True
                                ysize _tl_m_max_list
                                mousewheel True
                                draggable True

                                vbox:
                                    xfill True
                                    spacing 0

                                    for _i, _opt in enumerate(node["options"]):
                                        python:
                                            _tl_is_chosen = (node.get("chosen_index") == _i)
                                            _tl_show_dot  = not _tl_option_seen(node, _i) and not _tl_is_chosen

                                        frame:
                                            style "tl_frame_base"
                                            xfill True
                                            padding (0, 12, 0, 12)
                                            background None

                                            hbox:
                                                xfill True
                                                spacing 10
                                                yalign 0.5

                                                if _tl_is_chosen:
                                                    text "→":
                                                        style "tl_icon"
                                                        size TL_SIZE_BODY
                                                        color TL["opt_chosen_fg"]
                                                        yalign 0.5
                                                elif _tl_show_dot:
                                                    text "●":
                                                        style "tl_icon"
                                                        size TL_SIZE_DOT
                                                        color TL["opt_new_dot"]
                                                        yalign 0.5
                                                        italic False
                                                else:
                                                    null xsize 13

                                                text _opt:
                                                    style "tl_base"
                                                    size TL_SIZE_BODY
                                                    color TL["opt_fg"]
                                                    xmaximum _tl_m_w - 60
                                                    yalign 0.5

                                        if _i < _tl_m_opt_count - 1:
                                            frame:
                                                style "tl_frame_base"
                                                xfill True ysize 2
                                                padding (20, 0, 20, 0)
                                                background None

                                                frame:
                                                    style "tl_frame_base"
                                                    xfill True ysize 1
                                                    background Solid(TL["divider"])

                        else:
                            vbox:
                                xfill True
                                spacing 0

                                for _i, _opt in enumerate(node["options"]):
                                    python:
                                        _tl_is_chosen = (node.get("chosen_index") == _i)
                                        _tl_show_dot  = not _tl_option_seen(node, _i) and not _tl_is_chosen

                                    frame:
                                        style "tl_frame_base"
                                        xfill True
                                        padding (0, 12, 0, 12)
                                        background None

                                        hbox:
                                            xfill True
                                            spacing 10
                                            yalign 0.5

                                            if _tl_is_chosen:
                                                text "→":
                                                    style "tl_icon"
                                                    size TL_SIZE_BODY
                                                    color TL["opt_chosen_fg"]
                                                    yalign 0.5
                                            elif _tl_show_dot:
                                                text "●":
                                                    style "tl_icon"
                                                    size TL_SIZE_DOT
                                                    color TL["opt_new_dot"]
                                                    yalign 0.5
                                                    italic False
                                            else:
                                                null xsize 13

                                            text _opt:
                                                style "tl_base"
                                                size TL_SIZE_BODY
                                                color TL["opt_fg"]
                                                xmaximum _tl_m_w - 60
                                                yalign 0.5

                                    if _i < _tl_m_opt_count - 1:
                                        frame:
                                            style "tl_frame_base"
                                            xfill True ysize 2
                                            padding (20, 0, 20, 0)
                                            background None

                                            frame:
                                                style "tl_frame_base"
                                                xfill True ysize 1
                                                background Solid(TL["divider"])

                        null ysize 14


## =============================================================================
## Overlay screens
## =============================================================================

screen _tl_keylistener():
    key "chronology_toggle" action Function(_tl_toggle)
    key "tl_debug_toggle" action ToggleVariable("_tl_debug_visible")

default _tl_debug_visible = False

screen _tl_debug_overlay():
    if _tl_debug_visible:
        use tl_debug()

init python:
    config.keymap["tl_debug_toggle"] = ["K_BACKQUOTE"]

screen tl_debug():
    zorder 999
    modal False

    drag:
        drag_name "tl_debug"
        xpos 10 ypos 10

        frame:
            style "tl_frame_base"
            background Solid("#000000dd")
            padding (14, 12, 14, 12)
            xminimum 360

            vbox:
                spacing 5

                hbox:
                    xfill True
                    text "CHRONOLOGY DEBUG":
                        style "tl_base_bold"
                        size TL_SIZE_BODY
                        color "#a5b4fc"
                    null xfill True
                    button:
                        style "tl_frame_base"
                        background None
                        hover_background None
                        padding (4, 4, 4, 4)
                        action ToggleVariable("_tl_debug_visible")
                        text "✕":
                            style "tl_base"
                            size 16
                            color "#64748b"
                            hover_color "#f1f5f9"
                            italic False

                null ysize 4
                use tl_dbrow("RenPy", "{}.{}.{}".format(renpy.version_tuple[0], renpy.version_tuple[1], renpy.version_tuple[2]))
                use tl_dbrow("branch_id",   _tl_branch_id or "[none]")
                use tl_dbrow("node_count",  str(_tl_node_count))
                use tl_dbrow("history len", str(len(_tl_history)))
                use tl_dbrow("ast_ready",   str(_tl_ast_ready))
                use tl_dbrow("ast_menus",   str(len(_tl_ast_map)))

                null ysize 4
                if _tl_history:
                    python:
                        _dbnode = _tl_history[-1]
                    text "LAST NODE:":
                        style "tl_base_bold"
                        size 16
                        color "#fb923c"
                    use tl_dbrow("prompt",  (_dbnode["prompt"] or "(none)")[:50])
                    use tl_dbrow("chosen",  str(_dbnode.get("chosen_index")))
                    use tl_dbrow("options", str(len(_dbnode["options"])))
                    use tl_dbrow("thumb",   "{}b".format(len(_dbnode["thumb_bytes"])) if _dbnode.get("thumb_bytes") else "none")
                    use tl_dbrow("ast_key", str(_dbnode.get("ast_key")))

                null ysize 4
                text "` to hide":
                    style "tl_base"
                    size TL_SIZE_DOT
                    color "#334155"

screen tl_dbrow(label, value):
    hbox:
        spacing 8
        text (label + ":"):
            style "tl_base"
            size TL_SIZE_BADGE
            color "#64748b"
            xminimum 120
        text value:
            style "tl_base"
            size TL_SIZE_DOT
            color "#e2e8f0"
