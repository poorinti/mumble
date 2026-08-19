# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from MumbleServer.MurmurException import MurmurException
from MumbleServer.MurmurException import _MumbleServer_MurmurException_t

from dataclasses import dataclass


@dataclass
class ServerBootedException(MurmurException):
    """
    This happens if you try to fetch user or channel state on a stopped server, if you try to stop an already stopped server or start an already started server.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::MumbleServer::ServerBootedException``.
    """

    _ice_id = "::MumbleServer::ServerBootedException"

_MumbleServer_ServerBootedException_t = IcePy.defineException(
    "::MumbleServer::ServerBootedException",
    ServerBootedException,
    (),
    _MumbleServer_MurmurException_t,
    ())

setattr(ServerBootedException, '_ice_type', _MumbleServer_ServerBootedException_t)

__all__ = ["ServerBootedException", "_MumbleServer_ServerBootedException_t"]
