# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from dataclasses import dataclass


@dataclass(order=True, unsafe_hash=True)
class LogEntry:
    """
    A entry in the log.
    
    Attributes
    ----------
    timestamp : int
        Timestamp in UNIX time_t
    txt : str
        The log message.
    
    Notes
    -----
        The Slice compiler generated this dataclass from Slice struct ``::Murmur::LogEntry``.
    """
    timestamp: int = 0
    txt: str = ""

_Murmur_LogEntry_t = IcePy.defineStruct(
    "::Murmur::LogEntry",
    LogEntry,
    (),
    (
        ("timestamp", (), IcePy._t_int),
        ("txt", (), IcePy._t_string)
    ))

__all__ = ["LogEntry", "_Murmur_LogEntry_t"]
