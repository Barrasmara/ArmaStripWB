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
    Z_EXTRA=1.0,
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

    cutters = []
    for ctr in centers:
        x, y = ctr.x, ctr.y

        if pocket_side == "top":
            base_z = top_z - float(pocket_depth)
        else:
            base_z = bot_z - float(Z_EXTRA)

        pocket_center = App.Vector(x, y, base_z)
        cutters.append(
            make_hex_prism_xy(
                pocket_center, nut_R, float(pocket_depth), float(Z_EXTRA)
            )
        )

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

        self.preview = QtWidgets.QCheckBox("Preview cutters only (no cut)")

        layout.addRow("Pocket side", self.side)
        layout.addRow("Nut AF (mm)", self.nut_af)
        layout.addRow("Nut clearance (mm)", self.clear)
        layout.addRow("Pocket depth (mm)", self.depth)
        layout.addRow("Preview cutters", self.preview)

    def accept(self):
        pocket_side = "top" if self.side.currentIndex() == 0 else "bottom"
        cut_nut_pockets_from_selection(
            nut_af=self.nut_af.value(),
            nut_clearance=self.clear.value(),
            pocket_depth=self.depth.value(),
            pocket_side=pocket_side,
            preview_cutters=self.preview.isChecked(),
        )
        Gui.Control.closeDialog()

    def reject(self):
        Gui.Control.closeDialog()

    def getStandardButtons(self):
        return int(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)


def cut_nut_pockets_gui():
    if QtWidgets is None:
        return cut_nut_pockets_from_selection()

    panel = NutPocketTaskPanel()
    Gui.Control.showDialog(panel)
    return panel
