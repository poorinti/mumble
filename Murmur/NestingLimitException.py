# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class NestingLimitException(MurmurException):
    """
    This is thrown when the channel operation would excede the channel nesting limit
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::NestingLimitException``.
    """

    _ice_id = "::Murmur::NestingLimitException"

_Murmur_NestingLimitException_t = IcePy.defineException(
    "::Murmur::NestingLimitException",
    NestingLimitException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(NestingLimitException, '_ice_type', _Murmur_NestingLimitException_t)

__all__ = ["NestingLimitException", "_Murmur_NestingLimitException_t"]
