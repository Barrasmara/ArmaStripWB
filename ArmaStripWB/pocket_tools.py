# -*- coding: utf-8 -*-
"""Backward-compatible wrappers for legacy imports."""
from .nut_pocket_tools import cut_nut_pockets_from_selection, cut_nut_pockets_gui
from .bolt_hole_tools import cut_bolt_holes_from_selection, cut_bolt_holes_gui


def cut_fasteners_gui():
    return cut_nut_pockets_gui()
