# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.Channel import _Murmur_Channel_t

_Murmur_ChannelList_t = IcePy.defineSequence("::Murmur::ChannelList", (), _Murmur_Channel_t)

__all__ = ["_Murmur_ChannelList_t"]
