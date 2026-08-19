# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from enum import Enum

class ChannelInfo(Enum):
    """
    Notes
    -----
        The Slice compiler generated this enum class from Slice enumeration ``::Murmur::ChannelInfo``.
    """

    ChannelDescription = 0

    ChannelPosition = 1

_Murmur_ChannelInfo_t = IcePy.defineEnum(
    "::Murmur::ChannelInfo",
    ChannelInfo,
    (),
    {
        0: ChannelInfo.ChannelDescription,
        1: ChannelInfo.ChannelPosition,
    }
)

__all__ = ["ChannelInfo", "_Murmur_ChannelInfo_t"]
