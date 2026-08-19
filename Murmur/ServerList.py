# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.Server_forward import _Murmur_ServerPrx_t

_Murmur_ServerList_t = IcePy.defineSequence("::Murmur::ServerList", (), _Murmur_ServerPrx_t)

__all__ = ["_Murmur_ServerList_t"]
