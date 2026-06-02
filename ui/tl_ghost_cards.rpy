## =============================================================================
## Ghost branch card — one branch of an If node.
## =============================================================================

screen tl_ghost_card(ghost, bi, cw, th):

    python:
        _gbc_taken  = (bi == ghost.get("taken_index"))
        _gbc_sfns   = ghost.get("seen_fns") or []
        _gbc_sfn    = _gbc_sfns[bi] if bi < len(_gbc_sfns) else None
        _gbc_eval   = _tl_eval_seen_fn(_gbc_sfn) if _gbc_sfn else False
        _gbc_seen   = _gbc_taken or _gbc_eval
        _gbc_locked = not _gbc_taken and not _gbc_seen
        _gbc_imgs   = ghost.get("branch_imgs") or []
        _gbc_img    = _gbc_imgs[bi] if bi < len(_gbc_imgs) else None
        _gbc_img_disp = Transform(
            _gbc_img, xsize=cw, ysize=th, fit="cover",
        ) if _gbc_img else None
        _gbc_cond   = _tl_prettify_condition(ghost["conditions"][bi])

    vbox:
        xsize cw
        spacing 0

        use tl_thumbnail_frame(cw, th,
            img_disp=_gbc_img_disp,
            locked=_gbc_locked,
            taken=_gbc_taken,
            highlighted=False,
        )

        ## Bottom bar: condition label
        frame:
            style "tl_frame_base"
            xsize cw
            padding (12, 8, 12, 8)
            background Solid("#00000044")

            text _gbc_cond:
                style "tl_base"
                size TL_SIZE_BODY
                color TL["opt_fg"]
                substitute False
                xmaximum cw - 24
                yalign 0.5


## =============================================================================
## Ghost branch rows — rendered below the main timeline cards.
## =============================================================================

screen tl_ghost_rows(ghost_nodes, card_w, cols, spacing, reverse_clusters=False):
    if ghost_nodes:
        vbox:
            spacing spacing
            ## Muted separator between last timeline row and ghost rows
            frame:
                style "tl_frame_base"
                xsize cols * card_w + (cols - 1) * spacing
                ysize 3
                background Solid(TL["divider"])
            python:
                _tl_gbc_th = int(card_w * 9 / 16)
                ## Optionally reverse by cluster (most recent first) while keeping
                ## card order within each cluster unchanged.
                if reverse_clusters:
                    _tl_gbc_clusters = []
                    for _gbc_g in ghost_nodes:
                        if not _tl_gbc_clusters or not _gbc_g.get("cluster_with_prev", False):
                            _tl_gbc_clusters.append([])
                        _tl_gbc_clusters[-1].append(_gbc_g)
                    _tl_gbc_ordered = []
                    for _cl in reversed(_tl_gbc_clusters):
                        _tl_gbc_ordered.extend(_cl)
                else:
                    _tl_gbc_ordered = list(ghost_nodes)
                ## Flatten: (ghost, branch_idx, needs_sep)
                ## needs_sep: True = insert thin divider before this card.
                ## Suppressed for first item in each row.
                _tl_gbc_flat = []
                for _gbc_gi, _gbc_g in enumerate(_tl_gbc_ordered):
                    _gbc_cluster_sep = (
                        _gbc_gi > 0 and
                        not _gbc_g.get("cluster_with_prev", False)
                    )
                    for _gbc_bi in range(len(_gbc_g["conditions"])):
                        _tl_gbc_flat.append((
                            _gbc_g, _gbc_bi,
                            _gbc_cluster_sep and _gbc_bi == 0
                        ))
                ## Chunk into rows; each row is a flat list of (ghost, bi, is_start).
                ## is_start = True for first card in row, or first card of a new cluster.
                _tl_gbc_rows = []
                for _gbc_ri in range(0, len(_tl_gbc_flat), cols):
                    _gbc_chunk = _tl_gbc_flat[_gbc_ri:_gbc_ri + cols]
                    _gbc_row   = []
                    for _gbc_ci, (_gbc_g, _gbc_bi, _gbc_sep) in enumerate(_gbc_chunk):
                        _gbc_row.append((_gbc_g, _gbc_bi, _gbc_ci == 0 or _gbc_sep))
                    _tl_gbc_rows.append(_gbc_row)

            vbox:
                spacing spacing
                for _tl_gbc_row in _tl_gbc_rows:
                    hbox:
                        spacing 0
                        for _gbc_ri2, (_gbc_ghost, _gbc_bi, _gbc_start) in enumerate(_tl_gbc_row):

                            ## Gap before each card except the first.
                            ## Filled with accent colour if same cluster as previous card.
                            if _gbc_ri2 > 0:
                                if _gbc_start:
                                    ## Transparent frame — null doesn't render inside nested if/for in RenPy
                                    frame:
                                        style "tl_frame_base"
                                        xsize spacing
                                        ysize _tl_gbc_th + 42
                                        background Solid("#00000000")
                                else:
                                    frame:
                                        style "tl_frame_base"
                                        xsize spacing
                                        ysize _tl_gbc_th + 42
                                        background Solid(TL["accent"] + "2a")

                            use tl_ghost_card(_gbc_ghost, _gbc_bi, card_w, _tl_gbc_th)

                        python:
                            _gbc_pad = cols - len(_tl_gbc_row)
                        for _p in range(_gbc_pad):
                            null xsize (spacing + card_w)