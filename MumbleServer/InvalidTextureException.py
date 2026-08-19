# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from MumbleServer.MurmurException import MurmurException
from MumbleServer.MurmurException import _MumbleServer_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidTextureException(MurmurException):
    """
    This is thrown when you try to set an invalid texture.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::MumbleServer::InvalidTextureException``.
    """

    _ice_id = "::MumbleServer::InvalidTextureException"

_MumbleServer_InvalidTextureException_t = IcePy.defineException(
    "::MumbleServer::InvalidTextureException",
    InvalidTextureException,
    (),
    _MumbleServer_MurmurException_t,
    ())

setattr(InvalidTextureException, '_ice_type', _MumbleServer_InvalidTextureException_t)

__all__ = ["InvalidTextureException", "_MumbleServer_InvalidTextureException_t"]
