# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.CertificateDer import _Murmur_CertificateDer_t

_Murmur_CertificateList_t = IcePy.defineSequence("::Murmur::CertificateList", (), _Murmur_CertificateDer_t)

__all__ = ["_Murmur_CertificateList_t"]
