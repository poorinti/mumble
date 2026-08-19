# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class ServerBootedException(MurmurException):
    """
    This happens if you try to fetch user or channel state on a stopped server, if you try to stop an already stopped server or start an already started server.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::ServerBootedException``.
    """

    _ice_id = "::Murmur::ServerBootedException"

_Murmur_ServerBootedException_t = IcePy.defineException(
    "::Murmur::ServerBootedException",
    ServerBootedException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(ServerBootedException, '_ice_type', _Murmur_ServerBootedException_t)

__all__ = ["ServerBootedException", "_Murmur_ServerBootedException_t"]
