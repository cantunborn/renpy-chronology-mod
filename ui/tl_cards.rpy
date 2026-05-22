## =============================================================================
## CHRONOLOGY MOD — tl_cards.rpy
## Card screens: dispatcher, past card body, current card body.
## =============================================================================

## =============================================================================
## Shared thumbnail frame — used by tl_card and ghost cards.
## img_disp: pre-sized displayable or None. Caller is responsible for sizing.
## locked/taken/highlighted: ghost card state overlays (all False/True/False for
## regular cards = no overlay).
## fallback_text: shown when img_disp is None (regular cards only).
## =============================================================================

screen tl_thumbnail_frame(cw, th, img_disp=None, locked=False, taken=True, highlighted=False, fallback_text=None):

    frame:
        style "tl_frame_base"
        xsize cw
        ysize th
        background Solid(TL["thumb_bg"])

        if img_disp is not None:
            add img_disp:
                xalign 0.5
                yalign 0.5
        elif fallback_text is not None:
            text fallback_text:
                style "tl_base_bold"
                size TL_SIZE_TITLE
                color "#2a2820"
                xalign 0.5 yalign 0.5

        if locked:
            frame:
                xfill True
                yfill True
                background Solid("#000000bb")
            if _tl_lock_displayable:
                add _tl_lock_displayable:
                    xalign 0.5
                    yalign 0.5
                    xsize 36
                    ysize 36
                    fit "contain"
        elif not taken:
            frame:
                xfill True
                yfill True
                background Solid("#000000aa")

        if highlighted:
            add Solid(TL["accent"]):
                xsize cw
                ysize 3
                yalign 0.0


## =============================================================================
## Card screen
## =============================================================================

screen tl_card(node, cw=300):

    python:
        _tl_is_current = (node["index"] == len(_tl_history) - 1 and
                            node.get("chosen_index") is None)
        _tl_img_name   = node.get("img_name")
        _tl_use_thumb_first = bool(_tl_img_name and _tl_img_name_is_movie(_tl_img_name))
        _tl_thumb      = _tl_node_thumb(node) if (not _tl_img_name or _tl_use_thumb_first) else None
        _tl_has_thumb  = _tl_img_name is not None or _tl_thumb is not None
        _tl_thumb_h    = int(cw * 9 / 16)
        ## Resolve to a single pre-sized displayable for tl_thumbnail_frame.
        _tl_img_disp   = None
        if _tl_img_name and not (_tl_use_thumb_first and _tl_thumb):
            _tl_img_disp = _tl_img_thumb_displayable(_tl_img_name, cw, _tl_thumb_h, "cover")
        elif _tl_thumb:
            _tl_img_disp = Transform(
                _tl_thumb_displayable(_tl_thumb, node["index"]),
                xsize=cw, ysize=_tl_thumb_h, fit="contain")
        _tl_fallback = "#{:02d}".format(node["index"] + 1) if _tl_img_disp is None else None
        _tl_chosen_label = (
            node["options"][node["chosen_index"]]
            if node.get("chosen_index") is not None
            else None)
        _tl_has_new = _tl_node_has_new(node)

    vbox:
        xsize cw
        spacing 0

        use tl_thumbnail_frame(cw, _tl_thumb_h, img_disp=_tl_img_disp, fallback_text=_tl_fallback)

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

        python:
            _tl_diverged = node.get("_shadow_orig_chosen") is not None

        hbox:
            xsize cw
            spacing 0

            frame:
                style "tl_frame_base"
                xsize cw // 2
                ysize 46
                padding (12, 0, 8, 0)
                background Solid(TL["footer_bg"])

                if _tl_diverged:
                    text "⎇":
                        style "tl_icon"
                        size TL_SIZE_BODY
                        color TL["header_sub"]
                        yalign 0.5
                        italic False
                elif has_new:
                    text "●":
                        style "tl_icon"
                        size TL_SIZE_DOT
                        color TL["new_dot"]
                        yalign 0.5
                        italic False

            button:
                style "tl_frame_base"
                xsize cw // 2
                ysize 46
                padding (0, 0, 0, 0)
                background Solid(TL["footer_bg"])
                hover_background _tl_hover_gradient_wide
                action SetVariable("_tl_modal_node", node)

                text "All options {font=DejaVuSans.ttf}▾{/font}":
                    style "tl_base"
                    size TL_SIZE_BODY
                    color TL["btn_text"]
                    xalign 0.5 yalign 0.5


## =============================================================================
## Single option row — used by tl_card_current.
## =============================================================================

screen tl_card_option_row(node, i, opt, cw, shadow_ci):

    python:
        _tl_show_dot  = not _tl_option_seen(node, i)
        _tl_is_aid    = (shadow_ci is not None and i == shadow_ci)
        _tl_conds     = node.get("_option_conditions", [])
        _tl_cond_str  = (_tl_conds[i] if i < len(_tl_conds) else None) or ""
        _tl_opt_count = len(node["options"])

    vbox:
        xsize cw
        spacing 0

        frame:
            style "tl_frame_base"
            xsize cw
            padding (12, 8, 12, 8)
            background Solid("#00000033")

            vbox:
                xsize cw - 24
                spacing 3

                hbox:
                    xsize cw - 24
                    spacing 8
                    yalign 0.5

                    ## Replay-aid arrow takes priority over unseen dot.
                    if _tl_is_aid:
                        text "→":
                            style "tl_icon"
                            size TL_SIZE_BODY
                            color TL["header_sub"]
                            yalign 0.5
                            italic False
                    elif _tl_show_dot:
                        text "●":
                            style "tl_icon"
                            size TL_SIZE_DOT
                            color TL["opt_new_dot"]
                            yalign 0.5
                            italic False
                    else:
                        null xsize 14

                    text opt:
                        style "tl_base"
                        size TL_SIZE_BODY
                        color TL["opt_fg"]
                        xmaximum cw - 44
                        yalign 0.5

                if _tl_cond_str:
                    hbox:
                        xsize cw - 24
                        spacing 0
                        null xsize 22
                        text "[{}]".format(_tl_cond_str):
                            style "tl_base"
                            size TL_SIZE_SUBTITLE
                            color TL["header_sub"]
                            xmaximum cw - 46
                            substitute False

        if i < _tl_opt_count - 1:
            frame:
                style "tl_frame_base"
                xsize cw ysize 1
                background Solid(TL["divider"])


## =============================================================================
## Current card body — all options as rows
## =============================================================================

screen tl_card_current(node, cw=300):

    python:
        _shadow_ci = _tl_shadow_match(_tl_shadow_path or [], node)

    vbox:
        xsize cw
        spacing 0

        for _i, _opt in enumerate(node["options"]):
            use tl_card_option_row(node, _i, _opt, cw, _shadow_ci)

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