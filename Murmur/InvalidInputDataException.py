# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class InvalidInputDataException(MurmurException):
    """
    This is thrown when invalid input data was specified.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::InvalidInputDataException``.
    """

    _ice_id = "::Murmur::InvalidInputDataException"

_Murmur_InvalidInputDataException_t = IcePy.defineException(
    "::Murmur::InvalidInputDataException",
    InvalidInputDataException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(InvalidInputDataException, '_ice_type', _Murmur_InvalidInputDataException_t)

__all__ = ["InvalidInputDataException", "_Murmur_InvalidInputDataException_t"]
