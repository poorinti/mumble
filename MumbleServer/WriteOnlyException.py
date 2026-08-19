# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from MumbleServer.MurmurException import MurmurException
from MumbleServer.MurmurException import _MumbleServer_MurmurException_t

from dataclasses import dataclass


@dataclass
class WriteOnlyException(MurmurException):
    """
    This is thrown when you ask the server to disclose something that should be secret.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::MumbleServer::WriteOnlyException``.
    """

    _ice_id = "::MumbleServer::WriteOnlyException"

_MumbleServer_WriteOnlyException_t = IcePy.defineException(
    "::MumbleServer::WriteOnlyException",
    WriteOnlyException,
    (),
    _MumbleServer_MurmurException_t,
    ())

setattr(WriteOnlyException, '_ice_type', _MumbleServer_WriteOnlyException_t)

__all__ = ["WriteOnlyException", "_MumbleServer_WriteOnlyException_t"]
