# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidChannelException(MurmurException):
    """
    This is thrown when you specify an invalid channel id. This may happen if the channel was removed by another provess. It can also be thrown if you try to add an invalid channel.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::InvalidChannelException``.
    """

    _ice_id = "::Murmur::InvalidChannelException"

_Murmur_InvalidChannelException_t = IcePy.defineException(
    "::Murmur::InvalidChannelException",
    InvalidChannelException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(InvalidChannelException, '_ice_type', _Murmur_InvalidChannelException_t)

__all__ = ["InvalidChannelException", "_Murmur_InvalidChannelException_t"]
