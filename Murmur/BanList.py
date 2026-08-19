# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.Ban import _Murmur_Ban_t

_Murmur_BanList_t = IcePy.defineSequence("::Murmur::BanList", (), _Murmur_Ban_t)

__all__ = ["_Murmur_BanList_t"]
