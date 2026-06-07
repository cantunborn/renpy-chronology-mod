## =============================================================================
## CHRONOLOGY MOD — tl_menu_options.rpy
## Choice menu entry helpers: raw item parsing, filtering, indexing, choice-return population.
## =============================================================================

init -2 python:

    def _tl_parse_menu_items(items):
        """
        Parse raw Ren'Py menu items (label, condition, block) into (prompt, valid_labels).
        Caption entries (block=None) contribute to the prompt string; option entries
        with a falsy condition are excluded. String conditions are evaluated via py_eval;
        options are included on eval failure so a broken condition doesn't silently vanish.
        Returns (prompt_str, valid_label_list).
        """
        prompt       = ""
        valid_labels = []
        for entry in items:
            label = entry[0]
            cond  = entry[1] if len(entry) > 1 else None
            block = entry[2] if len(entry) > 2 else None
            if block is None:
                ## No block → caption / prompt entry
                if not prompt:
                    prompt = label
            elif cond in (None, True, "True"):
                valid_labels.append(label)
            elif cond is False or cond == "False":
                pass  ## explicitly locked
            else:
                try:
                    if renpy.python.py_eval(cond):
                        valid_labels.append(label)
                except Exception:
                    valid_labels.append(label)  ## include on eval failure
        return prompt, valid_labels

    def _tl_valid_choice_entries(items):
        out = []
        for entry in items:
            label = entry[0]
            value = entry[1] if len(entry) > 1 else None
            if value is None:
                continue
            out.append((label, value))
        return out

    def _tl_choice_entry_for_index(items, choice_index):
        if choice_index is None or choice_index < 0:
            return None
        valid_items = _tl_valid_choice_entries(items)
        if choice_index >= len(valid_items):
            return None
        return valid_items[choice_index]

    def _tl_choice_index_from_return_value(items, rv):
        _valid = list(_tl_valid_choice_entries(items))
        for i, (_label, value) in enumerate(_valid):
            if value is rv:
                return i
        for i, (_label, value) in enumerate(_valid):
            if value == rv:
                return i
            try:
                if value.value == rv:
                    return i
            except AttributeError:
                pass
        return None

    def _tl_populate_choice_returns(node, items):
        if node is None:
            return
        _crs = _tl_runtime_choice_returns(node, create=True)
        if _crs is None:
            return
        for i, (_label, value) in enumerate(_tl_valid_choice_entries(items)):
            if i >= len(_crs):
                break
            if value is not None and hasattr(value, "get_chosen"):
                _crs[i] = value
