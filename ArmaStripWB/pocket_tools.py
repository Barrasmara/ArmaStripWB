# -*- coding: utf-8 -*-
import FreeCAD as App
import FreeCADGui as Gui
import Part
import math

try:
    from PySide2 import QtWidgets
except Exception:
    QtWidgets = None


# ---------------------------------------------------------
# Core selection helper
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Hole detection (flat-strip assumption)
# Merge top/bottom circular rims by XY proximity
# ---------------------------------------------------------
def _find_hole_centers_from_strip(strip_shape, center_tol=0.1):
    circles = []
    for e in strip_shape.Edges:
        if hasattr(e, "Curve") and isinstance(e.Curve, Part.Circle):
            circles.append((e.Curve.Center, e.Curve.Radius))

    if not circles:
        raise Exception("No circular holes found on the ArmaStrip.")

    holes = []  # list of (center, radius)
    for ctr, rad in circles:
        merged = False
        for i, (c_prev, r_prev) in enumerate(holes):
            dxy = (App.Vector(ctr.x, ctr.y, 0) - App.Vector(c_prev.x, c_prev.y, 0)).Length
            if dxy <= float(center_tol):
                holes[i] = (c_prev, min(r_prev, rad))
                merged = True
                break
        if not merged:
            holes.append((ctr, rad))

    App.Console.PrintMessage(f"[ArmaStrip] Detected {len(holes)} hole centers.\n")
    return [c for (c, _r) in holes]


# ---------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------
def _unit(v):
    ln = v.Length
    if ln < 1e-9:
        return App.Vector(0, 0, 0)
    return v.multiply(1.0 / ln)

def _make_hex_prism_xy(center, R, depth, z_extra):
    """Hex pocket cutter placed in XY, extruded +Z."""
    pts = []
    for k in range(6):
        ang = math.radians(60 * k)
        pts.append(App.Vector(center.x + R * math.cos(ang),
                              center.y + R * math.sin(ang),
                              center.z))
    pts.append(pts[0])
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)
    return face.extrude(App.Vector(0, 0, depth + z_extra))

def _teardrop_points_2d(r, steps):
    """
    Teardrop in 2D (U,V plane) with printable-ish slopes.
    """
    pts = []
    a0 = math.radians(135)
    a1 = math.radians(405)  # 360 + 45
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * (i / float(steps))
        pts.append((r * math.cos(a), r * math.sin(a)))

    # tip
    pts.append((0.0, math.sqrt(2.0) * r))
    pts.append(pts[0])
    return pts

def _make_teardrop_prism(center, axis, print_up, r, length, steps):
    """
    Robust teardrop cutter whose profile plane is perpendicular to axis.
    Tip points toward print_up projected into that plane.
    """
    A = _unit(axis)
    if A.Length < 1e-9:
        raise Exception("Invalid hole axis")

    # V: "up" in plane perpendicular to A
    p = print_up.sub(A.multiply(print_up.dot(A)))
    if p.Length > 1e-6:
        V = _unit(p)
    else:
        # print_up parallel to axis -> pick a stable V in plane
        ref = App.Vector(1, 0, 0)
        if abs(A.dot(ref)) > 0.9:
            ref = App.Vector(0, 1, 0)
        V = _unit(A.cross(ref))

    # U completes basis
    U = _unit(A.cross(V))
    if U.Length < 1e-9 or V.Length < 1e-9:
        # last-chance fallback
        ref = App.Vector(0, 1, 0)
        if abs(A.dot(ref)) > 0.9:
            ref = App.Vector(1, 0, 0)
        V = _unit(A.cross(ref))
        U = _unit(A.cross(V))

    if U.Length < 1e-9 or V.Length < 1e-9:
        raise Exception("Failed to build teardrop basis (degenerate).")

    base_center = center.sub(A.multiply(length * 0.5))

    pts2 = _teardrop_points_2d(r, int(steps))
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


# =========================================================
# NUT POCKETS (separate routine + GUI)
# =========================================================
def cut_nut_pockets_from_selection(
    nut_af=5.5,
    nut_clearance=0.0,
    pocket_depth=2.5,
    pocket_side="top",   # "top" or "bottom"
    Z_EXTRA=1.0,
    CENTER_TOL=0.1,
):
    part_obj, strip_obj = _get_selection_part_and_strip()
    part_shape = part_obj.Shape
    strip_shape = strip_obj.Shape

    bb = part_shape.BoundBox
    top_z, bot_z = bb.ZMax, bb.ZMin

    nut_af_eff = float(nut_af) + float(nut_clearance)
    nut_R = (nut_af_eff / 2.0) / math.cos(math.radians(30))

    centers = _find_hole_centers_from_strip(strip_shape, center_tol=float(CENTER_TOL))

    cutters = []
    for ctr in centers:
        x, y = ctr.x, ctr.y

        if pocket_side == "top":
            # start at the pocket "floor"
            base_z = top_z - float(pocket_depth)
        else:
            # start below part and extrude up into it
            base_z = bot_z - float(Z_EXTRA)

        pocket_center = App.Vector(x, y, base_z)
        cutters.append(_make_hex_prism_xy(pocket_center, nut_R, float(pocket_depth), float(Z_EXTRA)))

    cutters_compound = Part.makeCompound(cutters)
    result = part_shape.cut(cutters_compound)

    doc = App.ActiveDocument
    new_obj = doc.addObject("Part::Feature", part_obj.Name + "_NutPockets")
    new_obj.Shape = result

    doc.recompute()
    Gui.ActiveDocument.ActiveView.viewAxonometric()
    Gui.SendMsgToActiveView("ViewFit")
    App.Console.PrintMessage(f"[ArmaStrip] Done. Created: {new_obj.Name}\n")
    return new_obj


def cut_nut_pockets_gui():
    if QtWidgets is None:
        return cut_nut_pockets_from_selection()

    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("ArmaStrip – Cut Nut Pockets")

    layout = QtWidgets.QFormLayout(dlg)

    side = QtWidgets.QComboBox()
    side.addItems(["Top (ZMax)", "Bottom (ZMin)"])
    side.setCurrentIndex(0)

    nut_af = QtWidgets.QDoubleSpinBox()
    nut_af.setRange(1.0, 50.0)
    nut_af.setDecimals(2)
    nut_af.setValue(5.5)

    clear = QtWidgets.QDoubleSpinBox()
    clear.setRange(0.0, 1.0)
    clear.setDecimals(3)
    clear.setValue(0.0)

    depth = QtWidgets.QDoubleSpinBox()
    depth.setRange(0.1, 50.0)
    depth.setDecimals(2)
    depth.setValue(2.5)

    layout.addRow("Pocket side", side)
    layout.addRow("Nut AF (mm)", nut_af)
    layout.addRow("Nut clearance (mm)", clear)
    layout.addRow("Pocket depth (mm)", depth)

    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    layout.addRow(btns)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)

    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return None

    pocket_side = "top" if side.currentIndex() == 0 else "bottom"

    return cut_nut_pockets_from_selection(
        nut_af=nut_af.value(),
        nut_clearance=clear.value(),
        pocket_depth=depth.value(),
        pocket_side=pocket_side,
    )


# =========================================================
# BOLT HOLES (separate routine + GUI)
# =========================================================
def cut_bolt_holes_from_selection(
    bolt_d_nominal=3.2,
    bolt_clearance=0.0,
    hole_shape="teardrop",        # "teardrop" or "round"
    print_up=App.Vector(0, 0, 1), # used only for teardrop
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
    axis = App.Vector(0, 0, 1)  # flat-strip assumption
    mid_z = 0.5 * (top_z + bot_z)

    for ctr in centers:
        hole_center = App.Vector(ctr.x, ctr.y, mid_z)
        if hole_shape == "round":
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
    App.Console.PrintMessage(f"[ArmaStrip] Done. Created: {new_obj.Name}\n")
    return new_obj


def cut_bolt_holes_gui():
    if QtWidgets is None:
        return cut_bolt_holes_from_selection()

    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("ArmaStrip – Cut Bolt Holes")

    layout = QtWidgets.QFormLayout(dlg)

    bolt_d = QtWidgets.QDoubleSpinBox()
    bolt_d.setRange(1.0, 10.0)
    bolt_d.setDecimals(2)
    bolt_d.setValue(3.2)

    clear = QtWidgets.QDoubleSpinBox()
    clear.setRange(0.0, 1.0)
    clear.setDecimals(3)
    clear.setValue(0.0)

    shape = QtWidgets.QComboBox()
    shape.addItems(["Teardrop", "Round"])
    shape.setCurrentIndex(0)

    up = QtWidgets.QComboBox()
    up.addItems(["+Z (print up)", "-Z"])
    up.setCurrentIndex(0)

    steps = QtWidgets.QSpinBox()
    steps.setRange(6, 120)
    steps.setValue(20)

    layout.addRow("Bolt hole diameter (mm)", bolt_d)
    layout.addRow("Bolt clearance (mm)", clear)
    layout.addRow("Hole shape", shape)
    layout.addRow("Teardrop tip direction", up)
    layout.addRow("Teardrop smoothness (steps)", steps)

    def on_shape_change(_):
        is_td = (shape.currentIndex() == 0)
        up.setEnabled(is_td)
        steps.setEnabled(is_td)

    shape.currentIndexChanged.connect(on_shape_change)
    on_shape_change(None)

    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    layout.addRow(btns)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)

    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return None

    hole_shape = "teardrop" if shape.currentIndex() == 0 else "round"
    print_up = App.Vector(0, 0, 1) if up.currentIndex() == 0 else App.Vector(0, 0, -1)

    return cut_bolt_holes_from_selection(
        bolt_d_nominal=bolt_d.value(),
        bolt_clearance=clear.value(),
        hole_shape=hole_shape,
        print_up=print_up,
        teardrop_steps=steps.value(),
    )


# ---------------------------------------------------------
# Backwards compatibility
# If your commands.py still calls cut_fasteners_gui(), make it Nut Pockets.
# ---------------------------------------------------------
def cut_fasteners_gui():
    return cut_nut_pockets_gui()
