# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.MurmurException import MurmurException
from Murmur.MurmurException import _Murmur_MurmurException_t

from dataclasses import dataclass


@dataclass
class WriteOnlyException(MurmurException):
    """
    This is thrown when you ask the server to disclose something that should be secret.
    
    Notes
    -----
        The Slice compiler generated this exception dataclass from Slice exception ``::Murmur::WriteOnlyException``.
    """

    _ice_id = "::Murmur::WriteOnlyException"

_Murmur_WriteOnlyException_t = IcePy.defineException(
    "::Murmur::WriteOnlyException",
    WriteOnlyException,
    (),
    _Murmur_MurmurException_t,
    ())

setattr(WriteOnlyException, '_ice_type', _Murmur_WriteOnlyException_t)

__all__ = ["WriteOnlyException", "_Murmur_WriteOnlyException_t"]
