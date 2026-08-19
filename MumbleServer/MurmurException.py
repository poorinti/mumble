# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Ice.UserException import UserException

from dataclasses import dataclass


@dataclass
class MurmurException(UserException):
    """
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::MumbleServer::MurmurException``.
    """

    _ice_id = "::MumbleServer::MurmurException"

_MumbleServer_MurmurException_t = IcePy.defineException(
    "::MumbleServer::MurmurException",
    MurmurException,
    (),
    None,
    ())

setattr(MurmurException, '_ice_type', _MumbleServer_MurmurException_t)

__all__ = ["MurmurException", "_MumbleServer_MurmurException_t"]
