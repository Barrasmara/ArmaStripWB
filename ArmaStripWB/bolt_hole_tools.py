# -*- coding: utf-8 -*-
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
    make_round_hole_cyl,
)

Z_AXIS = App.Vector(0, 0, 1)


def _find_parent_body(obj):
    if obj.TypeId == "PartDesign::Body":
        return obj
    getter = getattr(obj, "getParentGeoFeatureGroup", None)
    if getter is None:
        return None
    parent = getter()
    if parent and parent.TypeId == "PartDesign::Body":
        return parent
    return None


def cut_bolt_holes_from_selection(
    bolt_d_nominal=3.2,
    bolt_clearance=0.0,
    preview_cutters=False,
    hole_selection="all",
    every_n=1,
    start_hole=1,
    Z_EXTRA=1.0,
    CENTER_TOL=0.1,
):
    part_obj, strip_obj = get_selection_part_and_strip()
    part_shape = part_obj.Shape
    strip_shape = strip_obj.Shape

    bb = part_shape.BoundBox
    top_z, bot_z = bb.ZMax, bb.ZMin
    bolt_len = bb.ZLength + 2.0 * float(Z_EXTRA)

    r = (float(bolt_d_nominal) + float(bolt_clearance)) / 2.0

    centers = find_hole_centers_from_strip(strip_shape, center_tol=float(CENTER_TOL))
    centers = filter_hole_centers(
        centers,
        selection_mode=hole_selection,
        every_n=every_n,
        start_index=start_hole,
    )

    cutters = []
    axis = Z_AXIS  # flat strip assumption for now
    mid_z = 0.5 * (top_z + bot_z)

    for ctr in centers:
        hole_center = App.Vector(ctr.x, ctr.y, mid_z)
        cutters.append(make_round_hole_cyl(hole_center, axis, r, bolt_len))

    if not cutters:
        raise Exception("Failed to build bolt hole cutters.")

    cutters_compound = Part.makeCompound(cutters)

    doc = App.ActiveDocument
    if preview_cutters:
        preview_obj = doc.addObject("Part::Feature", part_obj.Name + "_BoltHoleCutters")
        preview_obj.Shape = cutters_compound
        doc.recompute()
        Gui.ActiveDocument.ActiveView.viewAxonometric()
        Gui.SendMsgToActiveView("ViewFit")
        App.Console.PrintMessage(
            f"[ArmaStrip] Preview only. Created: {preview_obj.Name}\n"
        )
        return preview_obj

    result = part_shape.cut(cutters_compound)

    body = _find_parent_body(part_obj)
    if body is not None:
        new_obj = body.newObject("PartDesign::Feature", part_obj.Name + "_BoltHoles")
        new_obj.Shape = result
        body.Tip = new_obj
    else:
        new_obj = doc.addObject("Part::Feature", part_obj.Name + "_BoltHoles")
        new_obj.Shape = result

    doc.recompute()

    Gui.ActiveDocument.ActiveView.viewAxonometric()
    Gui.SendMsgToActiveView("ViewFit")
    App.Console.PrintMessage(f"[ArmaStrip] Done. Created: {new_obj.Name}\n")
    return new_obj


class BoltHoleTaskPanel:
    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("ArmaStrip – Cut Bolt Holes")
        layout = QtWidgets.QFormLayout(self.form)

        self.bolt_d = QtWidgets.QDoubleSpinBox()
        self.bolt_d.setRange(1.0, 50.0)
        self.bolt_d.setDecimals(2)
        self.bolt_d.setValue(3.2)

        self.clear = QtWidgets.QDoubleSpinBox()
        self.clear.setRange(0.0, 5.0)
        self.clear.setDecimals(3)
        self.clear.setValue(0.0)

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

        self.info = QtWidgets.QLabel(
            "After creating round holes, you can select them and apply"
            " teardrop shaping with the FusedFilamentDesign addon."
        )
        self.info.setWordWrap(True)

        layout.addRow("Bolt diameter (mm)", self.bolt_d)
        layout.addRow("Clearance (mm)", self.clear)
        layout.addRow("Hole selection", self.hole_mode)
        layout.addRow("Every n holes", self.every_n)
        layout.addRow("Start at hole x", self.start_hole)
        layout.addRow("Preview cutters", self.preview)
        layout.addRow(self.info)

    def accept(self):
        selection_mode = "all"
        if self.hole_mode.currentIndex() == 1:
            selection_mode = "ends"
        elif self.hole_mode.currentIndex() == 2:
            selection_mode = "step"
        cut_bolt_holes_from_selection(
            bolt_d_nominal=self.bolt_d.value(),
            bolt_clearance=self.clear.value(),
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


def cut_bolt_holes_gui():
    if QtWidgets is None:
        return cut_bolt_holes_from_selection()

    panel = BoltHoleTaskPanel()
    Gui.Control.showDialog(panel)
    return panel
