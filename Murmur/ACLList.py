# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.ACL import _Murmur_ACL_t

_Murmur_ACLList_t = IcePy.defineSequence("::Murmur::ACLList", (), _Murmur_ACL_t)

__all__ = ["_Murmur_ACLList_t"]
