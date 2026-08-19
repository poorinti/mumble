# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidServerException(MurmurException):
    """
    This is thrown when you try to do an operation on a server that does not exist. This may happen if someone has removed the server.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::InvalidServerException``.
    """

    _ice_id = "::Murmur::InvalidServerException"

_Murmur_InvalidServerException_t = IcePy.defineException(
    "::Murmur::InvalidServerException",
    InvalidServerException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(InvalidServerException, '_ice_type', _Murmur_InvalidServerException_t)

__all__ = ["InvalidServerException", "_Murmur_InvalidServerException_t"]
