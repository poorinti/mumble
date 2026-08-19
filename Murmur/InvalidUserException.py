# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidUserException(MurmurException):
    """
    This is thrown when you specify an invalid userid.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::InvalidUserException``.
    """

    _ice_id = "::Murmur::InvalidUserException"

_Murmur_InvalidUserException_t = IcePy.defineException(
    "::Murmur::InvalidUserException",
    InvalidUserException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(InvalidUserException, '_ice_type', _Murmur_InvalidUserException_t)

__all__ = ["InvalidUserException", "_Murmur_InvalidUserException_t"]
