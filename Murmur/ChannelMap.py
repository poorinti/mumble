# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.Channel import _Murmur_Channel_t

_Murmur_ChannelMap_t = IcePy.defineDictionary("::Murmur::ChannelMap", (), IcePy._t_int, _Murmur_Channel_t)

__all__ = ["_Murmur_ChannelMap_t"]
