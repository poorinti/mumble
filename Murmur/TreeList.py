# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.Tree_forward import _Murmur_Tree_t

_Murmur_TreeList_t = IcePy.defineSequence("::Murmur::TreeList", (), _Murmur_Tree_t)

__all__ = ["_Murmur_TreeList_t"]
