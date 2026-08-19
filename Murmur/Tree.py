# Copyright (c) ZeroC, Inc.

# slice2py version 3.8.1

from __future__ import annotations
import IcePy

from Ice.Value import Value

from Murmur.Channel import Channel
from Murmur.Channel import _Murmur_Channel_t

from Murmur.TreeList import _Murmur_TreeList_t

from Murmur.Tree_forward import _Murmur_Tree_t

from Murmur.UserList import _Murmur_UserList_t

from dataclasses import dataclass
from dataclasses import field

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Murmur.User import User

@dataclass(eq=False)
class Tree(Value):
    """
    User and subchannel state. Read-only.
    
    Attributes
    ----------
    c : Channel
        Channel definition of current channel.
    children : list[Tree | None]
        List of subchannels.
    users : list[User]
        Users in this channel.
    
    Notes
    -----
        The Slice compiler generated this dataclass from Slice class ``::Murmur::Tree``.
    """
    c: Channel = field(default_factory=Channel)
    children: list[Tree | None] = field(default_factory=list)
    users: list[User] = field(default_factory=list)

    @staticmethod
    def ice_staticId() -> str:
        return "::Murmur::Tree"

_Murmur_Tree_t = IcePy.defineValue(
    "::Murmur::Tree",
    Tree,
    -1,
    (),
    False,
    None,
    (
        ("c", (), _Murmur_Channel_t, False, 0),
        ("children", (), _Murmur_TreeList_t, False, 0),
        ("users", (), _Murmur_UserList_t, False, 0)
    ))

setattr(Tree, '_ice_type', _Murmur_Tree_t)

__all__ = ["Tree", "_Murmur_Tree_t"]
