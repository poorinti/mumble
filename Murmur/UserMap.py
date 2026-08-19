# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.User import _Murmur_User_t

_Murmur_UserMap_t = IcePy.defineDictionary("::Murmur::UserMap", (), IcePy._t_int, _Murmur_User_t)

__all__ = ["_Murmur_UserMap_t"]
