## =============================================================================
## CHRONOLOGY MOD — tl_modal.rpy
## Modal overlay: full option list with thumbnail, shown on "All options ▾".
## =============================================================================

## =============================================================================
## Single option row — used by tl_modal in both scroll and non-scroll paths.
## =============================================================================

screen tl_modal_option_row(node, i, opt, m_w, opt_count):

    python:
        _tl_is_chosen = (node.get("chosen_index") == i)
        _tl_show_dot  = not _tl_option_seen(node, i) and not _tl_is_chosen
        _tl_shadow_ci = node.get("_shadow_orig_chosen")
        if _tl_shadow_ci is None:
            _tl_shadow_ci = _tl_shadow_match(_tl_shadow_path or [], node)
        _tl_is_aid = (_tl_shadow_ci is not None and i == _tl_shadow_ci and not _tl_is_chosen)

    vbox:
        xfill True
        spacing 0

        button:
            xfill True
            padding (16, 12, 16, 12)
            background None
            hover_background _tl_hover_gradient
            action [Function(_tl_jump, node["index"], i), Hide("tl_modal"), Hide("timeline"), Jump("_tl_do_load")]

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
                elif _tl_is_aid:
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
                    null xsize 13

                text opt:
                    style "tl_base"
                    size TL_SIZE_BODY
                    color TL["opt_fg"]
                    xmaximum m_w - 60
                    yalign 0.5

        if i < opt_count - 1:
            frame:
                style "tl_frame_base"
                xfill True ysize 2
                padding (20, 0, 20, 0)
                background None

                frame:
                    style "tl_frame_base"
                    xfill True ysize 1
                    background Solid(TL["divider"])


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
        _tl_m_img_name  = node.get("img_name")
        _tl_m_use_thumb_first = bool(_tl_m_img_name and _tl_img_name_is_movie(_tl_m_img_name))
        _tl_m_thumb     = _tl_node_thumb(node) if (not _tl_m_img_name or _tl_m_use_thumb_first) else None
        _tl_m_has_thumb = _tl_m_img_name is not None or _tl_m_thumb is not None
        _tl_m_thumb_w   = _tl_m_w - (_tl_m_pad * 2)
        _tl_m_thumb_h   = int(_tl_m_thumb_w * 9 / 16)
        _tl_m_img_disp = None
        _tl_m_tdisp = None
        if _tl_m_img_name and not (_tl_m_use_thumb_first and _tl_m_thumb):
            _tl_m_img_disp = _tl_img_thumb_displayable(_tl_m_img_name, _tl_m_thumb_w, _tl_m_thumb_h, "cover")
        elif _tl_m_has_thumb and _tl_m_thumb:
            _tl_m_tdisp = _tl_thumb_displayable(_tl_m_thumb, node["index"])
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
                                ysize _tl_m_thumb_h
                                background Solid(TL["thumb_bg"])
                                padding (0, 0, 0, 0)

                                if _tl_m_img_disp is not None:
                                    add _tl_m_img_disp
                                elif _tl_m_tdisp is not None:
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
                                        use tl_modal_option_row(node, _i, _opt, _tl_m_w, _tl_m_opt_count)

                        else:
                            vbox:
                                xfill True
                                spacing 0

                                for _i, _opt in enumerate(node["options"]):
                                    use tl_modal_option_row(node, _i, _opt, _tl_m_w, _tl_m_opt_count)

                        null ysize 14