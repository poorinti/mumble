# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from MumbleServer.MurmurException import MurmurException
from MumbleServer.MurmurException import _MumbleServer_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidChannelException(MurmurException):
    """
    This is thrown when you specify an invalid channel id. This may happen if the channel was removed by another provess. It can also be thrown if you try to add an invalid channel.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::MumbleServer::InvalidChannelException``.
    """

    _ice_id = "::MumbleServer::InvalidChannelException"

_MumbleServer_InvalidChannelException_t = IcePy.defineException(
    "::MumbleServer::InvalidChannelException",
    InvalidChannelException,
    (),
    _MumbleServer_MurmurException_t,
    ())

setattr(InvalidChannelException, '_ice_type', _MumbleServer_InvalidChannelException_t)

__all__ = ["InvalidChannelException", "_MumbleServer_InvalidChannelException_t"]
