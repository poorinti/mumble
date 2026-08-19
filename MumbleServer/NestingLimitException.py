# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from MumbleServer.MurmurException import MurmurException
from MumbleServer.MurmurException import _MumbleServer_MurmurException_t

from dataclasses import dataclass


@dataclass
class NestingLimitException(MurmurException):
    """
    This is thrown when the channel operation would exceed the channel nesting limit
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::MumbleServer::NestingLimitException``.
    """

    _ice_id = "::MumbleServer::NestingLimitException"

_MumbleServer_NestingLimitException_t = IcePy.defineException(
    "::MumbleServer::NestingLimitException",
    NestingLimitException,
    (),
    _MumbleServer_MurmurException_t,
    ())

setattr(NestingLimitException, '_ice_type', _MumbleServer_NestingLimitException_t)

__all__ = ["NestingLimitException", "_MumbleServer_NestingLimitException_t"]
