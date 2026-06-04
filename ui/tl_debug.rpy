## =============================================================================
## CHRONOLOGY MOD — tl_debug.rpy
## Debug overlay, key listener, and debug data rows.
## =============================================================================

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
            xsize 440

            vbox:
                xfill True
                spacing 5

                hbox:
                    xfill True
                    text "CHRONOLOGY DEBUG":
                        style "tl_base_bold"
                        size TL_SIZE_BODY
                        color "#a5b4fc"
                        xfill True
                    button:
                        style "tl_frame_base"
                        background None
                        hover_background None
                        padding (0, 0, 0, 0)
                        yalign 0.0
                        action ToggleVariable("_tl_debug_visible")
                        text "✕":
                            style "tl_icon"
                            size TL_SIZE_BODY
                            color "#64748b"
                            hover_color "#f1f5f9"

                null ysize 4
                use tl_dbrow("RenPy", "{}.{}.{}".format(renpy.version_tuple[0], renpy.version_tuple[1], renpy.version_tuple[2]))
                use tl_dbrow("branch_id",   _tl_branch_id or "(none)")
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
                    use tl_dbrow("thumb",   "{}b".format(len(_tl_node_thumb(_dbnode) or b"")) if _tl_node_thumb(_dbnode) else "none")
                    use tl_dbrow("ast_key", str(_dbnode.get("ast_key")))

                null ysize 8
                textbutton "Dump CFG AST (all)":
                    style "tl_frame_base"
                    background Solid("#1e293b")
                    hover_background Solid("#334155")
                    padding (8, 6, 8, 6)
                    action Function(_tl_cfg_dump_ast)
                    text_style "tl_base"
                    text_size TL_SIZE_DOT
                    text_color "#7dd3fc"
                    text_hover_color "#ffffff"

                null ysize 4
                textbutton "Salvage history ast_keys":
                    style "tl_frame_base"
                    background Solid("#1e293b")
                    hover_background Solid("#334155")
                    padding (8, 6, 8, 6)
                    action Function(_tl_salvage_history_ast_keys)
                    text_style "tl_base"
                    text_size TL_SIZE_DOT
                    text_color "#7dd3fc"
                    text_hover_color "#ffffff"

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