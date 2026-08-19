# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.UserInfo import _Murmur_UserInfo_t

_Murmur_UserInfoMap_t = IcePy.defineDictionary("::Murmur::UserInfoMap", (), _Murmur_UserInfo_t, IcePy._t_string)

__all__ = ["_Murmur_UserInfoMap_t"]
