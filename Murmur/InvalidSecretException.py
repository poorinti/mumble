# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidSecretException(MurmurException):
    """
    This is thrown when you supply the wrong secret in the calling context.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::InvalidSecretException``.
    """

    _ice_id = "::Murmur::InvalidSecretException"

_Murmur_InvalidSecretException_t = IcePy.defineException(
    "::Murmur::InvalidSecretException",
    InvalidSecretException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(InvalidSecretException, '_ice_type', _Murmur_InvalidSecretException_t)

__all__ = ["InvalidSecretException", "_Murmur_InvalidSecretException_t"]
