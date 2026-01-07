# -*- coding: utf-8 -*-
import math
import FreeCAD as App
import FreeCADGui as Gui
import Part

try:
    from PySide2 import QtWidgets
except Exception:
    QtWidgets = None

from .common import (
    filter_hole_centers,
    find_hole_centers_from_strip,
    get_selection_part_and_strip,
    make_hex_prism_xy,
)


def cut_nut_pockets_from_selection(
    nut_af=5.5,
    nut_clearance=0.0,
    pocket_depth=2.5,
    pocket_side="top",  # "top" or "bottom"
    preview_cutters=False,
    pocket_offset=0.0,
    hole_selection="all",
    every_n=1,
    start_hole=1,
    CENTER_TOL=0.1,
):
    part_obj, strip_obj = get_selection_part_and_strip()
    part_shape = part_obj.Shape
    strip_shape = strip_obj.Shape

    bb = part_shape.BoundBox
    top_z, bot_z = bb.ZMax, bb.ZMin

    nut_af_eff = float(nut_af) + float(nut_clearance)
    nut_R = (nut_af_eff / 2.0) / math.cos(math.radians(30))

    centers = find_hole_centers_from_strip(strip_shape, center_tol=float(CENTER_TOL))
    centers = filter_hole_centers(
        centers,
        selection_mode=hole_selection,
        every_n=every_n,
        start_index=start_hole,
    )

    cutters = []
    depth_val = float(pocket_depth)
    offset_val = float(pocket_offset)

    for ctr in centers:
        x, y = ctr.x, ctr.y

        if pocket_side == "top":
            base_z = top_z - depth_val - offset_val
        else:
            base_z = bot_z - offset_val

        pocket_center = App.Vector(x, y, base_z)
        cutters.append(make_hex_prism_xy(pocket_center, nut_R, depth_val + offset_val))

    if not cutters:
        raise Exception("Failed to build nut pocket cutters.")

    cutters_compound = Part.makeCompound(cutters)

    doc = App.ActiveDocument
    if preview_cutters:
        preview_obj = doc.addObject("Part::Feature", part_obj.Name + "_NutPocketCutters")
        preview_obj.Shape = cutters_compound
        doc.recompute()
        Gui.ActiveDocument.ActiveView.viewAxonometric()
        Gui.SendMsgToActiveView("ViewFit")
        App.Console.PrintMessage(f"[ArmaStrip] Preview only. Created: {preview_obj.Name}\n")
        return preview_obj

    result = part_shape.cut(cutters_compound)
    new_obj = doc.addObject("Part::Feature", part_obj.Name + "_NutPockets")
    new_obj.Shape = result

    doc.recompute()
    Gui.ActiveDocument.ActiveView.viewAxonometric()
    Gui.SendMsgToActiveView("ViewFit")
    App.Console.PrintMessage(f"[ArmaStrip] Done. Created: {new_obj.Name}\n")
    return new_obj


class NutPocketTaskPanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("ArmaStrip – Cut Nut Pockets")
        layout = QtWidgets.QFormLayout(self.form)

        self.side = QtWidgets.QComboBox()
        self.side.addItems(["Top (ZMax)", "Bottom (ZMin)"])
        self.side.setCurrentIndex(0)

        self.nut_af = QtWidgets.QDoubleSpinBox()
        self.nut_af.setRange(1.0, 100.0)
        self.nut_af.setDecimals(2)
        self.nut_af.setValue(5.5)

        self.clear = QtWidgets.QDoubleSpinBox()
        self.clear.setRange(0.0, 5.0)
        self.clear.setDecimals(3)
        self.clear.setValue(0.0)

        self.depth = QtWidgets.QDoubleSpinBox()
        self.depth.setRange(0.1, 100.0)
        self.depth.setDecimals(2)
        self.depth.setValue(2.5)

        self.offset = QtWidgets.QDoubleSpinBox()
        self.offset.setRange(0.0, 10.0)
        self.offset.setDecimals(2)
        self.offset.setValue(0.0)

        self.preview = QtWidgets.QCheckBox("Preview cutters only (no cut)")

        self.hole_mode = QtWidgets.QComboBox()
        self.hole_mode.addItems([
            "All holes",
            "First and last",
            "Every n holes (start at x)",
        ])

        self.every_n = QtWidgets.QSpinBox()
        self.every_n.setRange(1, 999)
        self.every_n.setValue(2)

        self.start_hole = QtWidgets.QSpinBox()
        self.start_hole.setRange(1, 999)
        self.start_hole.setValue(1)

        self.hole_mode.currentIndexChanged.connect(self._update_selection_enabled)
        self._update_selection_enabled()

        layout.addRow("Pocket side", self.side)
        layout.addRow("Nut AF (mm)", self.nut_af)
        layout.addRow("Nut clearance (mm)", self.clear)
        layout.addRow("Pocket depth (mm)", self.depth)
        layout.addRow("Z offset/overcut (mm)", self.offset)
        layout.addRow("Hole selection", self.hole_mode)
        layout.addRow("Every n holes", self.every_n)
        layout.addRow("Start at hole x", self.start_hole)
        layout.addRow("Preview cutters", self.preview)

    def accept(self):
        pocket_side = "top" if self.side.currentIndex() == 0 else "bottom"
        selection_mode = "all"
        if self.hole_mode.currentIndex() == 1:
            selection_mode = "ends"
        elif self.hole_mode.currentIndex() == 2:
            selection_mode = "step"
        cut_nut_pockets_from_selection(
            nut_af=self.nut_af.value(),
            nut_clearance=self.clear.value(),
            pocket_depth=self.depth.value(),
            pocket_side=pocket_side,
            pocket_offset=self.offset.value(),
            preview_cutters=self.preview.isChecked(),
            hole_selection=selection_mode,
            every_n=self.every_n.value(),
            start_hole=self.start_hole.value(),
        )
        Gui.Control.closeDialog()

    def reject(self):
        Gui.Control.closeDialog()

    def getStandardButtons(self):
        return int(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

    def _update_selection_enabled(self):
        enable_step = self.hole_mode.currentIndex() == 2
        self.every_n.setEnabled(enable_step)
        self.start_hole.setEnabled(enable_step)


def cut_nut_pockets_gui():
    if QtWidgets is None:
        return cut_nut_pockets_from_selection()

    panel = NutPocketTaskPanel()
    Gui.Control.showDialog(panel)
    return panel
