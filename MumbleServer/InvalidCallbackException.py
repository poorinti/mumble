# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from MumbleServer.MurmurException import MurmurException
from MumbleServer.MurmurException import _MumbleServer_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidCallbackException(MurmurException):
    """
    This is thrown when you supply an invalid callback.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::MumbleServer::InvalidCallbackException``.
    """

    _ice_id = "::MumbleServer::InvalidCallbackException"

_MumbleServer_InvalidCallbackException_t = IcePy.defineException(
    "::MumbleServer::InvalidCallbackException",
    InvalidCallbackException,
    (),
    _MumbleServer_MurmurException_t,
    ())

setattr(InvalidCallbackException, '_ice_type', _MumbleServer_InvalidCallbackException_t)

__all__ = ["InvalidCallbackException", "_MumbleServer_InvalidCallbackException_t"]
