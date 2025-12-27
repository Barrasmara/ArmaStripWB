# -*- coding: utf-8 -*-
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
    make_round_hole_cyl,
    make_teardrop_prism,
)

Z_AXIS = App.Vector(0, 0, 1)


def cut_bolt_holes_from_selection(
    bolt_d_nominal=3.2,
    bolt_clearance=0.0,
    hole_shape="teardrop",  # "teardrop" or "round"
    print_up=App.Vector(0, 0, 1),
    teardrop_steps=20,
    preview_cutters=False,
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

    cutters = []
    axis = Z_AXIS  # flat strip assumption for now
    mid_z = 0.5 * (top_z + bot_z)

    for ctr in centers:
        hole_center = App.Vector(ctr.x, ctr.y, mid_z)
        if hole_shape == "round":
            cutters.append(make_round_hole_cyl(hole_center, axis, r, bolt_len))
        else:
            cutters.append(
                make_teardrop_prism(
                    hole_center, axis, print_up, r, bolt_len, int(teardrop_steps)
                )
            )

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

        self.shape = QtWidgets.QComboBox()
        self.shape.addItems(["Teardrop", "Round"])
        self.shape.setCurrentIndex(0)

        self.up = QtWidgets.QComboBox()
        self.up.addItems(
            [
                "+Z (print up)",
                "-Z",
                "+X",
                "-X",
                "+Y",
                "-Y",
                "+X+Y",
                "+X-Y",
                "-X+Y",
                "-X-Y",
            ]
        )
        self.up.setCurrentIndex(0)

        self.steps = QtWidgets.QSpinBox()
        self.steps.setRange(6, 180)
        self.steps.setValue(20)

        self.preview = QtWidgets.QCheckBox("Preview cutters only (no cut)")

        layout.addRow("Bolt diameter (mm)", self.bolt_d)
        layout.addRow("Clearance (mm)", self.clear)
        layout.addRow("Hole shape", self.shape)
        layout.addRow("Teardrop tip direction", self.up)
        layout.addRow("Teardrop smoothness (steps)", self.steps)
        layout.addRow("Preview cutters", self.preview)

        self.shape.currentIndexChanged.connect(self._on_shape_change)
        self._on_shape_change()

    def _on_shape_change(self, *_args):
        is_td = self.shape.currentIndex() == 0
        self.up.setEnabled(is_td)
        self.steps.setEnabled(is_td)

    def accept(self):
        hole_shape = "teardrop" if self.shape.currentIndex() == 0 else "round"
        up_idx = self.up.currentIndex()
        up_map = {
            0: App.Vector(0, 0, 1),
            1: App.Vector(0, 0, -1),
            2: App.Vector(1, 0, 0),
            3: App.Vector(-1, 0, 0),
            4: App.Vector(0, 1, 0),
            5: App.Vector(0, -1, 0),
            6: App.Vector(1, 1, 0),
            7: App.Vector(1, -1, 0),
            8: App.Vector(-1, 1, 0),
            9: App.Vector(-1, -1, 0),
        }
        print_up = up_map.get(up_idx, App.Vector(0, 0, 1))
        cut_bolt_holes_from_selection(
            bolt_d_nominal=self.bolt_d.value(),
            bolt_clearance=self.clear.value(),
            hole_shape=hole_shape,
            print_up=print_up,
            teardrop_steps=self.steps.value(),
            preview_cutters=self.preview.isChecked(),
        )
        Gui.Control.closeDialog()

    def reject(self):
        Gui.Control.closeDialog()

    def getStandardButtons(self):
        return int(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)


def cut_bolt_holes_gui():
    if QtWidgets is None:
        return cut_bolt_holes_from_selection()

    panel = BoltHoleTaskPanel()
    Gui.Control.showDialog(panel)
    return panel
