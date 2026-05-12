## =============================================================================
## CHRONOLOGY MOD — tl_menu_options.rpy
## Choice menu entry helpers: filtering, indexing, choice-return population.
## =============================================================================

init -2 python:

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
