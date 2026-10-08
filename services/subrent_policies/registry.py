# -*- coding: utf-8 -*-
"""Registry for subrent management policies."""
from odoo.exceptions import UserError

_REGISTRY = {}


def register(policy_cls):
    """Decorator / helper to register a policy class."""
    inst = policy_cls()
    if not inst.code:
        raise ValueError("Policy must define code")
    _REGISTRY[inst.code] = inst
    return policy_cls


def get_policy(code):
    if code not in _REGISTRY:
        raise UserError("Unknown subrent policy: %s" % code)
    return _REGISTRY[code]


def list_policies():
    return list(_REGISTRY.values())


def selection_list():
    return [(p.code, p.label) for p in sorted(_REGISTRY.values(), key=lambda p: p.code)]
