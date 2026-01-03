"""Schema utilities for tap-pingdom.

Copyright (c) 2025 Edgar Ramírez-Mondragón
"""

from __future__ import annotations

import copy
from typing import Any


def apply_schema_patch(
    base_schema: dict[str, Any],
    patches: dict[str, Any],
) -> dict[str, Any]:
    """Recursively apply patches to a base schema.

    This function performs a deep merge of patches into the base schema.
    Setting a value to None in the patches dict will remove that key from the result.

    Args:
        base_schema: Base JSON Schema dictionary to patch.
        patches: Dictionary of patches to apply. Use None as value to remove keys.

    Returns:
        Patched schema dictionary.

    Examples:
        >>> base = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        >>> patches = {'properties': {'age': {'type': 'integer'}}}
        >>> result = apply_schema_patch(base, patches)
        >>> result['properties']
        {'name': {'type': 'string'}, 'age': {'type': 'integer'}}

        >>> # Remove a key by setting it to None
        >>> patches = {'properties': {'name': None}}
        >>> result = apply_schema_patch(base, patches)
        >>> 'name' in result['properties']
        False
    """
    result = copy.deepcopy(base_schema)

    def merge_dict(target: dict[str, Any], source: dict[str, Any]) -> None:
        """Recursively merge source into target, removing keys set to None."""
        for key, value in source.items():
            if value is None and key in target:
                # None means delete the key
                del target[key]
            elif (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                merge_dict(target[key], value)
            else:
                target[key] = value

    merge_dict(result, patches)
    return result
