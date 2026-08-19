# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class ServerFailureException(MurmurException):
    """
    This is thrown if ``Server.start`` fails, and should generally be the cause for some concern.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::ServerFailureException``.
    """

    _ice_id = "::Murmur::ServerFailureException"

_Murmur_ServerFailureException_t = IcePy.defineException(
    "::Murmur::ServerFailureException",
    ServerFailureException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(ServerFailureException, '_ice_type', _Murmur_ServerFailureException_t)

__all__ = ["ServerFailureException", "_Murmur_ServerFailureException_t"]
