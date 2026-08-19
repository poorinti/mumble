# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidTextureException(MurmurException):
    """
    This is thrown when you try to set an invalid texture.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::InvalidTextureException``.
    """

    _ice_id = "::Murmur::InvalidTextureException"

_Murmur_InvalidTextureException_t = IcePy.defineException(
    "::Murmur::InvalidTextureException",
    InvalidTextureException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(InvalidTextureException, '_ice_type', _Murmur_InvalidTextureException_t)

__all__ = ["InvalidTextureException", "_Murmur_InvalidTextureException_t"]
