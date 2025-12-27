# -*- coding: utf-8 -*-
import FreeCAD as App
import FreeCADGui as Gui
import Part
import math

try:
    from PySide2 import QtWidgets
except Exception:
    QtWidgets = None


# ---- Shared helpers (copied locally to keep module standalone) ----
def _unit(v):
    ln = v.Length
    if ln < 1e-9:
        return App.Vector(0, 0, 0)
    return v.multiply(1.0 / ln)

def _find_hole_centers_from_strip(strip_shape, center_tol=0.1):
    circles = []
    for e in strip_shape.Edges:
        if hasattr(e, "Curve") and isinstance(e.Curve, Part.Circle):
            circles.append((e.Curve.Center, e.Curve.Radius))
    if not circles:
        raise Exception("No circular holes found on the ArmaStrip.")

    holes = []
    for ctr, rad in circles:
        merged = False
        for i, (c_prev, r_prev) in enumerate(holes):
            dxy = (App.Vector(ctr.x, ctr.y, 0) - App.Vector(c_prev.x, c_prev.y, 0)).Length
            if dxy <= center_tol:
                holes[i] = (c_prev, min(r_prev, rad))
                merged = True
                break
        if not merged:
            holes.append((ctr, rad))

    App.Console.PrintMessage(f"[ArmaStrip] Detected {len(holes)} hole centers.\n")
    return [c for (c, _r) in holes]

def _teardrop_points_2d(r, steps):
    pts = []
    a0 = math.radians(135)
    a1 = math.radians(405)
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * (i / float(steps))
        pts.append((r * math.cos(a), r * math.sin(a)))
    pts.append((0.0, math.sqrt(2.0) * r))
    pts.append(pts[0])
    return pts

def _make_teardrop_prism(center, axis, print_up, r, length, steps):
    A = _unit(axis)
    if A.Length < 1e-9:
        raise Exception("Invalid hole axis")

    p = print_up.sub(A.multiply(print_up.dot(A)))
    if p.Length > 1e-6:
        V = _unit(p)
    else:
        ref = App.Vector(1, 0, 0)
        if abs(A.dot(ref)) > 0.9:
            ref = App.Vector(0, 1, 0)
        V = _unit(A.cross(ref))

    U = _unit(A.cross(V))
    if U.Length < 1e-9 or V.Length < 1e-9:
        raise Exception("Failed to build teardrop basis (degenerate)")

    base_center = center.sub(A.multiply(length * 0.5))
    pts2 = _teardrop_points_2d(r, steps)
    pts3 = [base_center.add(U.multiply(x)).add(V.multiply(y)) for (x, y) in pts2]

    wire = Part.makePolygon(pts3)
    face = Part.Face(wire)
    return face.extrude(A.multiply(length))

def _make_round_hole_cyl(center, axis, r, length):
    A = _unit(axis)
    if A.Length < 1e-9:
        raise Exception("Invalid hole axis")
    base = center.sub(A.multiply(length * 0.5))
    return Part.makeCylinder(r, length, base, A)

def _get_selection_part_and_strip():
    doc = App.ActiveDocument
    if doc is None:
        raise Exception("No active document")
    sel = Gui.Selection.getSelection()
    if len(sel) != 2:
        raise Exception("Select FIRST the target part, THEN the ArmaStrip.")
    part_obj, strip_obj = sel[0], sel[1]
    if part_obj.Shape.isNull() or strip_obj.Shape.isNull():
        raise Exception("Selection contains invalid shapes.")
    return part_obj, strip_obj


# ---- Public API ----
def cut_bolt_holes_from_selection(
    bolt_d_nominal=3.2,
    bolt_clearance=0.0,
    shape="teardrop",       # "teardrop" or "round"
    print_up=App.Vector(0, 0, 1),
    teardrop_steps=20,
    Z_EXTRA=1.0,
    CENTER_TOL=0.1,
):
    part_obj, strip_obj = _get_selection_part_and_strip()
    part_shape = part_obj.Shape
    strip_shape = strip_obj.Shape

    bb = part_shape.BoundBox
    top_z, bot_z = bb.ZMax, bb.ZMin
    bolt_len = bb.ZLength + 2.0 * float(Z_EXTRA)

    r = (float(bolt_d_nominal) + float(bolt_clearance)) / 2.0
    centers = _find_hole_centers_from_strip(strip_shape, center_tol=float(CENTER_TOL))

    cutters = []
    axis = App.Vector(0, 0, 1)  # flat strip assumption for now
    mid_z = 0.5 * (top_z + bot_z)

    for ctr in centers:
        hole_center = App.Vector(ctr.x, ctr.y, mid_z)
        if shape == "round":
            cutters.append(_make_round_hole_cyl(hole_center, axis, r, bolt_len))
        else:
            cutters.append(_make_teardrop_prism(hole_center, axis, print_up, r, bolt_len, int(teardrop_steps)))

    cutters_compound = Part.makeCompound(cutters)
    result = part_shape.cut(cutters_compound)

    doc = App.ActiveDocument
    new_obj = doc.addObject("Part::Feature", part_obj.Name + "_BoltHoles")
    new_obj.Shape = result
    doc.recompute()

    Gui.ActiveDocument.ActiveView.viewAxonometric()
    Gui.SendMsgToActiveView("ViewFit")
    return new_obj


def cut_bolt_holes_gui():
    if QtWidgets is None:
        return cut_bolt_holes_from_selection()

    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("Cut Bolt Holes (ArmaStrip)")

    layout = QtWidgets.QFormLayout(dlg)

    bolt_d = QtWidgets.QDoubleSpinBox()
    bolt_d.setRange(1.0, 10.0)
    bolt_d.setDecimals(2)
    bolt_d.setValue(3.2)

    clear = QtWidgets.QDoubleSpinBox()
    clear.setRange(0.0, 1.0)
    clear.setDecimals(3)
    clear.setValue(0.0)

    hole_shape = QtWidgets.QComboBox()
    hole_shape.addItems(["Teardrop", "Round"])
    hole_shape.setCurrentIndex(0)

    up = QtWidgets.QComboBox()
    up.addItems(["+Z (print up)", "-Z"])
    up.setCurrentIndex(0)

    steps = QtWidgets.QSpinBox()
    steps.setRange(6, 120)
    steps.setValue(20)

    layout.addRow("Bolt hole diameter (mm)", bolt_d)
    layout.addRow("Bolt clearance (mm)", clear)
    layout.addRow("Hole shape", hole_shape)
    layout.addRow("Teardrop tip direction", up)
    layout.addRow("Teardrop smoothness (steps)", steps)

    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    layout.addRow(btns)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)

    def on_shape_change(_):
        is_td = (hole_shape.currentIndex() == 0)
        up.setEnabled(is_td)
        steps.setEnabled(is_td)

    hole_shape.currentIndexChanged.connect(on_shape_change)
    on_shape_change(None)

    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return None

    shape = "teardrop" if hole_shape.currentIndex() == 0 else "round"
    print_up = App.Vector(0, 0, 1) if up.currentIndex() == 0 else App.Vector(0, 0, -1)

    return cut_bolt_holes_from_selection(
        bolt_d_nominal=bolt_d.value(),
        bolt_clearance=clear.value(),
        shape=shape,
        print_up=print_up,
        teardrop_steps=steps.value(),
    )
