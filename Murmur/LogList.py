# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.LogEntry import _Murmur_LogEntry_t

_Murmur_LogList_t = IcePy.defineSequence("::Murmur::LogList", (), _Murmur_LogEntry_t)

__all__ = ["_Murmur_LogList_t"]
