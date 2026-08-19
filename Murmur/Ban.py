# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.NetAddress import _Murmur_NetAddress_t

from dataclasses import dataclass
from dataclasses import field

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Buffer


@dataclass
class Ban:
    """
    A single ip mask for a ban.
    
    Attributes
    ----------
    address : bytes
        Address to ban.
    bits : int
        Number of bits in ban to apply.
    name : str
        Username associated with ban.
    hash : str
        Hash of banned user.
    reason : str
        Reason for ban.
    start : int
        Date ban was applied in unix time format.
    duration : int
        Duration of ban.
    
    Notes
    -----
        The Slice compiler generated this dataclass from Slice struct ``::Murmur::Ban``.
    """
    address: bytes = field(default_factory=bytes)
    bits: int = 0
    name: str = ""
    hash: str = ""
    reason: str = ""
    start: int = 0
    duration: int = 0

_Murmur_Ban_t = IcePy.defineStruct(
    "::Murmur::Ban",
    Ban,
    (),
    (
        ("address", (), _Murmur_NetAddress_t),
        ("bits", (), IcePy._t_int),
        ("name", (), IcePy._t_string),
        ("hash", (), IcePy._t_string),
        ("reason", (), IcePy._t_string),
        ("start", (), IcePy._t_int),
        ("duration", (), IcePy._t_int)
    ))

__all__ = ["Ban", "_Murmur_Ban_t"]
