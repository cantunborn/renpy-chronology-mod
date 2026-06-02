## =============================================================================
## CHRONOLOGY MOD — timeline_screen.rpy
## =============================================================================

## -- Keybind ------------------------------------------------------------------
init python:
    config.keymap["chronology_toggle"] = ["t"]
    config.keymap["chronology_route"]   = ["r"]
    config.overlay_screens.append("_tl_keylistener")
    config.overlay_screens.append("_tl_debug_overlay")

init:
    transform tl_layer_blur:
        blur 48
        matrixcolor SaturationMatrix(0.6)


init python:
    def _tl_capture_hover_pos():
        store._tl_route_hover_pos = renpy.get_mouse_pos()

    def _tl_toggle(view=None):
        if not hasattr(store, "_tl_history"):
            return
        scr = renpy.get_screen("timeline")
        if scr:
            current = scr.scope.get("tl_view", "cards")
            if view is None or current == view:
                ## Same tab key or Esc → close
                renpy.layer_at_list([], layer="master")
                renpy.hide_screen("timeline")
            else:
                ## Different tab key → switch view
                scr.scope["tl_view"] = view
                renpy.restart_interaction()
        else:
            renpy.layer_at_list([tl_layer_blur], layer="master")
            renpy.show_screen("timeline")
            if view is not None:
                scr2 = renpy.get_screen("timeline")
                if scr2:
                    scr2.scope["tl_view"] = view
                    renpy.restart_interaction()


## =============================================================================
## Chronology — jump helper label
## Called via renpy.jump() to escape screen context before loading a save.
## =============================================================================

label _tl_do_load:
    if _tl_load_slot:
        $ renpy.load(_tl_load_slot)
    return

label _tl_do_chap_end_jump:
    if _tl_chap_end_slot:
        $ renpy.load(_tl_chap_end_slot)
    else:
        $ renpy.jump(_tl_label_jump)


## =============================================================================
## Main timeline screen
## =============================================================================

screen timeline():
    modal True
    zorder 200

    default tl_view            = "cards"   ## "cards" | "route"
    default tl_route_expanded  = False
    default tl_route_hover     = None
    default _tl_locked_count   = _tl_count_locked_branches()

    key "chronology_toggle" action Function(_tl_toggle, "cards")
    key "chronology_route"  action Function(_tl_toggle, "route")
    key "K_ESCAPE"          action Function(_tl_toggle)

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
                    text ("Route Tracker" if tl_view == "route" else "Choice History"):
                        style "tl_base"
                        size TL_SIZE_BODY
                        color TL["header_sub"]

                null xfill True

                ## ── Route / Cards toggle ───────────────────────────────
                python:
                    _tl_btn_cards_bg    = TL["btn_hover_bg"] if tl_view == "cards" else TL["btn_bg"]
                    _tl_btn_route_bg    = TL["btn_hover_bg"] if tl_view == "route" else TL["btn_bg"]
                    _tl_btn_cards_color = TL["header_text"] if tl_view == "cards" else TL["header_sub"]
                    _tl_btn_route_color = TL["header_text"] if tl_view == "route" else TL["header_sub"]

                hbox:
                    spacing 2
                    yalign 0.5

                    button:
                        background Solid(_tl_btn_cards_bg)
                        hover_background Solid(TL["btn_hover_bg"])
                        padding (10, 6, 10, 6)
                        action SetScreenVariable("tl_view", "cards")
                        yalign 0.5

                        text "History":
                            style "tl_base"
                            size TL_SIZE_SUBTITLE
                            color _tl_btn_cards_color
                            hover_color TL["header_text"]
                            yalign 0.5

                    button:
                        background Solid(_tl_btn_route_bg)
                        hover_background Solid(TL["btn_hover_bg"])
                        padding (10, 6, 10, 6)
                        action SetScreenVariable("tl_view", "route")
                        yalign 0.5

                        text "Route":
                            style "tl_base"
                            size TL_SIZE_SUBTITLE
                            color _tl_btn_route_color
                            hover_color TL["header_text"]
                            yalign 0.5

                null xsize 16

                if tl_view == "route":
                    python:
                        _tl_notifs_on    = getattr(persistent, "_tl_var_notifs_enabled", True)
                        _tl_notifs_label = "Var change notifs ✓" if _tl_notifs_on else "Var change notifs ✗"
                        _tl_notifs_color = TL["header_text"] if _tl_notifs_on else TL["header_sub"]
                    button:
                        background Solid(TL["btn_bg"])
                        hover_background Solid(TL["btn_hover_bg"])
                        padding (10, 6, 10, 6)
                        yalign 0.5
                        action ToggleField(persistent, "_tl_var_notifs_enabled")

                        text _tl_notifs_label:
                            style "tl_base"
                            size TL_SIZE_SUBTITLE
                            color _tl_notifs_color
                            hover_color TL["header_text"]
                            yalign 0.5

                    null xsize 16

                python:
                    _tl_playthrough_new = sum(
                        1 for _n in _tl_history if _tl_node_has_new(_n))
                    _tl_show_locked  = _tl_locked_count > 0 or _tl_playthrough_new > 0

                if _tl_show_locked:
                    null xsize 20
                    vbox:
                        spacing 4
                        yalign 0.5

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

                        if _tl_locked_count > 0:
                            hbox:
                                spacing 10
                                yalign 0.5
                                text "●":
                                    style "tl_icon"
                                    size TL_SIZE_DOT
                                    color TL["new_dot"]
                                    yalign 0.5
                                    italic False
                                text "{} branch{} left to unlock".format(
                                        _tl_locked_count,
                                        "es" if _tl_locked_count != 1 else ""):
                                    style "tl_base"
                                    size TL_SIZE_BODY
                                    color TL["new_dot"]
                                    yalign 0.5
                    null xsize 20

                if persistent._tl_recovery_slot:
                    button:
                        action [Function(_tl_cancel_replay), Hide("timeline"), Jump("_tl_do_load")]
                        background None
                        hover_background None
                        yalign 0.5

                        hbox:
                            spacing 4
                            yalign 0.5

                            text "↺":
                                style "tl_base"
                                size TL_SIZE_BODY
                                color TL["header_sub"]
                                hover_color TL["accent"]
                                yalign 0.5

                            text "Back":
                                style "tl_base"
                                size TL_SIZE_BODY
                                color TL["header_sub"]
                                hover_color TL["accent"]
                                yalign 0.5

        frame:
            style "tl_frame_base"
            xfill True ysize 3
            background Solid(TL["divider"])

        if tl_view == "route":
            use tl_route(tl_route_expanded, tl_route_hover)

        elif not _tl_history:
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
                    _tl_max_cols = (_tl_avail + _tl_spacing) // (160 + _tl_spacing)
                    if _tl_max_cols < 1: _tl_max_cols = 1
                    _tl_cols     = _tl_max_cols if _tl_max_cols < 5 else 5
                    _tl_card_w   = (_tl_avail - (_tl_spacing * (_tl_cols - 1))) // _tl_cols
                    ## Build flat item list; chapter_end node flag drives divider position
                    _tl_items = []
                    _tl_cur_row = []
                    _tl_marked_chapters = set()
                    for _n in _tl_history:
                        _tl_cur_row.append(_n)
                        if len(_tl_cur_row) == _tl_cols:
                            _tl_items.append(("row", list(_tl_cur_row)))
                            _tl_cur_row = []
                        if _n.get("chapter_end"):
                            _ch = _n["chapter_end"]
                            _tl_marked_chapters.add(_ch)
                            if _tl_cur_row:
                                _tl_items.append(("row", list(_tl_cur_row)))
                                _tl_cur_row = []
                            _tl_items.append(("divider", _ch, _tl_chapters.get(_ch, "")))
                    if _tl_cur_row:
                        _tl_items.append(("row", list(_tl_cur_row)))
                    ## Chapters that fired before any history node (no node to mark)
                    for _m in _tl_chapter_markers:
                        if _m["chapter_name"] not in _tl_marked_chapters:
                            _tl_items.append(("divider", _m["chapter_name"], _m["end_label"]))

                frame:
                    style "tl_frame_base"
                    xfill True
                    padding (40, 30, 40, 30)
                    background None

                    vbox:
                        xfill True
                        spacing _tl_spacing

                        for _item in _tl_items:
                            if _item[0] == "divider":
                                use tl_chapter_divider(_item[1], _item[2])
                            else:
                                hbox:
                                    spacing _tl_spacing

                                    for _node in _item[1]:
                                        use tl_card(_node, _tl_card_w)

                                    python:
                                        _tl_pad_count = _tl_cols - len(_item[1])
                                    for _p in range(_tl_pad_count):
                                        null xsize _tl_card_w


    if _tl_modal_node is not None:
        use tl_modal(_tl_modal_node)

    ## ── Route tooltip — floats at mouse position, screen-level so xpos/ypos works
    if tl_view == "route" and tl_route_hover is not None:
        python:
            _tt_hx, _tt_hy = getattr(store, "_tl_route_hover_pos", (0, 0))
            _tt_x  = _TL_MIN(_tt_hx + 14, config.screen_width  - 240)
            _tt_y  = _TL_MIN(_tt_hy + 14, config.screen_height - 160)
            _tt_numeric = tl_route_hover in (getattr(persistent, "_tl_var_is_numeric", None) or set())
            _tt_domain  = [] if _tt_numeric else (
                (getattr(persistent, "_tl_var_domain", None) or {}).get(tl_route_hover) or []
            )
            _tt_cur    = str(getattr(store, tl_route_hover, ""))

        if _tt_domain:
            frame:
                style "tl_frame_base"
                background Solid(TL["modal_bg"])
                xpos _tt_x
                ypos _tt_y
                padding (14, 12, 14, 12)
                xsize 220

                vbox:
                    xfill True
                    spacing 10

                    text "Possible Routes":
                        style "tl_base_bold"
                        size TL_SIZE_BODY
                        color TL["header_text"]

                    frame:
                        style "tl_frame_base"
                        xfill True
                        ysize 1
                        background Solid(TL["header_sub"] + "44")

                    vbox:
                        xfill True
                        spacing 4
                        for _tt_val in _tt_domain:
                            python:
                                _tt_is_cur    = (_tt_val == _tt_cur)
                                _tt_val_color = TL["header_text"] if _tt_is_cur else TL["header_sub"]

                            hbox:
                                xfill True
                                spacing 6
                                xalign 0.5
                                yalign 0.5

                                if _tt_is_cur:
                                    text "→":
                                        style "tl_base"
                                        size TL_SIZE_BODY
                                        color _tt_val_color
                                        yalign 0.5
                                else:
                                    null xsize 14

                                text _tl_strip_renpy_tags(_tt_val):
                                    style "tl_base"
                                    size TL_SIZE_BODY
                                    color _tt_val_color
                                    yalign 0.5

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
## Chapter divider
## =============================================================================

screen tl_chapter_divider(chapter_name, end_label):

    python:
        _tl_div_label  = "End of {}".format(chapter_name)
        _tl_div_avail  = config.screen_width - 80   ## 40px side padding × 2
        _tl_div_max_tw = _tl_div_avail * 3 // 10    ## text: 30% of available (wraps if longer)
        _tl_div_lw     = _tl_div_avail // 4         ## each line: 25% of available

    button:
        xfill True
        padding (0, 48, 0, 48)
        background None
        hover_background None
        action [Function(_tl_begin_label_jump, end_label),
                Hide("timeline"), Jump("_tl_do_chap_end_jump")]

        ## Centered block: [line] [text] [line], with symmetric outer padding
        hbox:
            xalign 0.5
            yalign 0.5
            spacing 16

            frame:
                style "tl_frame_base"
                xsize _tl_div_lw
                ysize 5
                yalign 0.5
                background       Solid(TL["header_text"])
                hover_background Solid(TL["accent"])

            text _tl_div_label:
                style "tl_base"
                size TL_SIZE_HEADER
                color TL["header_text"]
                hover_color TL["accent"]
                xsize _tl_div_max_tw
                yalign 0.5
                text_align 0.5

            frame:
                style "tl_frame_base"
                xsize _tl_div_lw
                ysize 5
                yalign 0.5
                background       Solid(TL["header_text"])
                hover_background Solid(TL["accent"])


## Cards live in ui/tl_cards.rpy.
## Modal lives in ui/tl_modal.rpy.


## =============================================================================
## Key listener overlay
## =============================================================================

screen _tl_keylistener():
    key "chronology_toggle" action Function(_tl_toggle, "cards")
    key "chronology_route"  action Function(_tl_toggle, "route")
    key "tl_debug_toggle"   action ToggleVariable("_tl_debug_visible")

