# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Murmur.IntList import _Murmur_IntList_t

from dataclasses import dataclass
from dataclasses import field

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Buffer


@dataclass
class TextMessage:
    """
    A text message between users.
    
    Attributes
    ----------
    sessions : list[int]
        Sessions (connected users) who were sent this message.
    channels : list[int]
        Channels who were sent this message.
    trees : list[int]
        Trees of channels who were sent this message.
    text : str
        The contents of the message.
    
    Notes
    -----
        The Slice compiler generated this dataclass from Slice struct ``::Murmur::TextMessage``.
    """
    sessions: list[int] = field(default_factory=list)
    channels: list[int] = field(default_factory=list)
    trees: list[int] = field(default_factory=list)
    text: str = ""

_Murmur_TextMessage_t = IcePy.defineStruct(
    "::Murmur::TextMessage",
    TextMessage,
    (),
    (
        ("sessions", (), _Murmur_IntList_t),
        ("channels", (), _Murmur_IntList_t),
        ("trees", (), _Murmur_IntList_t),
        ("text", (), IcePy._t_string)
    ))

__all__ = ["TextMessage", "_Murmur_TextMessage_t"]
