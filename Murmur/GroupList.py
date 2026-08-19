# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.Group import _Murmur_Group_t

_Murmur_GroupList_t = IcePy.defineSequence("::Murmur::GroupList", (), _Murmur_Group_t)

__all__ = ["_Murmur_GroupList_t"]
