# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidCallbackException(MurmurException):
    """
    This is thrown when you supply an invalid callback.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::InvalidCallbackException``.
    """

    _ice_id = "::Murmur::InvalidCallbackException"

_Murmur_InvalidCallbackException_t = IcePy.defineException(
    "::Murmur::InvalidCallbackException",
    InvalidCallbackException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(InvalidCallbackException, '_ice_type', _Murmur_InvalidCallbackException_t)

__all__ = ["InvalidCallbackException", "_Murmur_InvalidCallbackException_t"]
