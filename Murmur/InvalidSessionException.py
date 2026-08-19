# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidSessionException(MurmurException):
    """
    This is thrown when you specify an invalid session. This may happen if the user has disconnected since your last call to ``Server.getUsers``. See ``User.session``
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::InvalidSessionException``.
    """

    _ice_id = "::Murmur::InvalidSessionException"

_Murmur_InvalidSessionException_t = IcePy.defineException(
    "::Murmur::InvalidSessionException",
    InvalidSessionException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(InvalidSessionException, '_ice_type', _Murmur_InvalidSessionException_t)

__all__ = ["InvalidSessionException", "_Murmur_InvalidSessionException_t"]
