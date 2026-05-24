## =============================================================================
## CHRONOLOGY MOD — tl_route_screen.rpy
## Route screen: chip bar showing current store values for tracked vars.
## =============================================================================

## =============================================================================
## Mod notification screen — separate from the game's screen notify so we
## don't affect game-side notifications at all.
##
## Font: FontGroup that uses the game's default font for all characters, with
## DejaVuSans overriding only the arrow/bullet codepoints the game font may lack.
## This avoids inline {font=} tag switches (which cause baseline misalignment)
## while still rendering correctly on games whose fonts include these glyphs.
## =============================================================================


transform _tl_notify_appear:
    on show:
        alpha 0
        linear .25 alpha 1.0
    on hide:
        linear .5 alpha 0.0

screen _tl_notify(message):
    zorder 100
    style_prefix "notify"
    frame at _tl_notify_appear:
        text "[message!t]":
            font _tl_fontgroup
    timer 3.25 action Hide('_tl_notify')


## =============================================================================
## Route screen body — chip bar
## =============================================================================

screen tl_route(tl_route_expanded, tl_route_hover):
    ## Suppress rollback/forward so scroll wheel doesn't exit the screen
    key "rollback"   action NullAction()
    key "rollforward" action NullAction()

    python:
        _tl_route_chips = _tl_build_route_chips()
        _tl_chip_h      = 36
        _tl_chip_gap    = 10
        _TL_ROUTE_FOLD  = 24
        _tl_side_pad    = 40
        _tl_avail       = config.screen_width - (_tl_side_pad * 2)
        _tl_chip_est    = 300   ## estimated chip width for column calc
        _tl_chips_per_row = max(1, (_tl_avail + _tl_chip_gap) // (_tl_chip_est + _tl_chip_gap))
        _tl_chip_w      = (_tl_avail - _tl_chip_gap * (_tl_chips_per_row - 1)) // _tl_chips_per_row
        _tl_key_w       = _tl_chip_w * 55 // 100
        _tl_val_w       = _tl_chip_w - _tl_key_w
        _tl_ghost_vars  = set()
        for _g in (_tl_ghost_nodes or []):
            _tl_ghost_vars.update(_g.get("affecting_vars") or [])
        _tl_highlighted = _tl_ghost_vars | (getattr(store, "_tl_recently_changed_vars", None) or set())
        _tl_hl_count    = sum(1 for _n, _v in _tl_route_chips if _n in _tl_highlighted)
        _tl_hl_rows     = max(3, -(-_tl_hl_count // _tl_chips_per_row)) if _tl_chips_per_row else 3
        _TL_ROUTE_FOLD  = _tl_hl_rows * _tl_chips_per_row
        _tl_card_spacing = 16
        _tl_max_cols = max(1, (_tl_avail + _tl_card_spacing) // (160 + _tl_card_spacing))
        _tl_card_cols = _tl_max_cols if _tl_max_cols < 5 else 5
        _tl_card_w   = (_tl_avail - _tl_card_spacing * (_tl_card_cols - 1)) // _tl_card_cols

    if not _tl_route_chips:
        frame:
            style "tl_frame_base"
            xfill True yfill True
            background None

            vbox:
                xalign 0.5 yalign 0.5
                spacing 10

                text "No route vars tracked yet.":
                    style "tl_base_bold"
                    size TL_SIZE_BODY
                    color TL["header_text"]
                    xalign 0.5

                text "Route vars are detected from game scripts on first load.":
                    style "tl_base"
                    size TL_SIZE_BODY
                    color TL["header_sub"]
                    xalign 0.5

    else:
        viewport:
            xfill True yfill True
            mousewheel True
            draggable True

            frame:
                style "tl_frame_base"
                xfill True
                background None
                padding (40, 24, 40, 24)

                vbox:
                    xfill True
                    spacing 4

                    ## ── Chip bar — rows computed in Python ─────────────────
                    python:
                        _visible_chips = _tl_route_chips if tl_route_expanded \
                            else _tl_route_chips[:_TL_ROUTE_FOLD]
                        _hidden_count  = len(_tl_route_chips) - len(_visible_chips)
                        _chip_rows = [
                            _visible_chips[_i:_i + _tl_chips_per_row]
                            for _i in range(0, len(_visible_chips), _tl_chips_per_row)
                        ]

                    for _crow in _chip_rows:
                        hbox:
                            spacing _tl_chip_gap

                            for _chip_name, _chip_val in _crow:
                                python:
                                    _chip_key_label = _tl_prettify_var(_chip_name)
                                    _chip_val_label = str(_chip_val)
                                    _chip_key_bg    = (TL["accent"] + "44") if _chip_name in _tl_highlighted else TL["btn_hover_bg"]

                                button:
                                    background None
                                    hover_background None
                                    padding (0, 0, 0, 0)
                                    xsize _tl_chip_w
                                    yminimum _tl_chip_h

                                    action NullAction()
                                    hovered [SetScreenVariable("tl_route_hover", _chip_name), Function(_tl_capture_hover_pos)]
                                    unhovered SetScreenVariable("tl_route_hover", None)

                                    hbox:
                                        spacing 0
                                        yalign 0.5

                                        ## Key half
                                        frame:
                                            style "tl_frame_base"
                                            background Solid(_chip_key_bg)
                                            padding (10, 6, 10, 6)
                                            xmaximum _tl_key_w
                                            yminimum _tl_chip_h

                                            text _chip_key_label:
                                                style "tl_base"
                                                size TL_SIZE_BODY
                                                color TL["btn_text"]
                                                yalign 0.5

                                        ## Value half
                                        frame:
                                            style "tl_frame_base"
                                            background Solid(TL["btn_bg"])
                                            padding (10, 6, 10, 6)
                                            xmaximum _tl_val_w
                                            yminimum _tl_chip_h

                                            text _chip_val_label:
                                                style "tl_base"
                                                size TL_SIZE_BODY
                                                color TL["header_text"]
                                                yalign 0.5

                    if _hidden_count > 0:
                        hbox:
                            spacing _tl_chip_gap
                            button:
                                background Solid(TL["btn_bg"])
                                hover_background Solid(TL["btn_hover_bg"])
                                padding (10, 6, 10, 6)
                                yminimum _tl_chip_h
                                action SetScreenVariable("tl_route_expanded", True)

                                text "+{} more".format(_hidden_count):
                                    style "tl_base"
                                    size TL_SIZE_BODY
                                    color TL["header_sub"]
                                    yalign 0.5

                    elif tl_route_expanded and _TL_ROUTE_FOLD < len(_tl_route_chips):
                        hbox:
                            spacing _tl_chip_gap
                            button:
                                background Solid(TL["btn_bg"])
                                hover_background Solid(TL["btn_hover_bg"])
                                padding (10, 6, 10, 6)
                                yminimum _tl_chip_h
                                action SetScreenVariable("tl_route_expanded", False)

                                text "Show less":
                                    style "tl_base"
                                    size TL_SIZE_BODY
                                    color TL["header_sub"]
                                    yalign 0.5

                    frame:
                        background None
                        xfill True
                        ysize 24

                    ## ── Ghost cards ───────────────────────────────────────────
                    use tl_ghost_rows(_tl_ghost_nodes, _tl_ghost_highlight, _tl_card_w, _tl_card_cols, _tl_card_spacing, True)

                    frame:
                        background None
                        xfill True
                        ysize 8
