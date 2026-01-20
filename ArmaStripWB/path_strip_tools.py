import math
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide2 import QtWidgets


def _unit(v):
    ln = v.Length
    if ln < 1e-12:
        return App.Vector(0, 0, 0)
    return v.multiply(1.0 / ln)


def _rotate_about_axis(vec, axis, angle_rad):
    a = _unit(axis)
    if a.Length < 1e-9:
        return vec
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return vec.multiply(c) + a.cross(vec).multiply(s) + a.multiply(a.dot(vec) * (1 - c))


def _edge_point_tangent_at_u(edge, u):
    p = edge.Curve.value(u)
    t = edge.Curve.tangent(u)[0]
    return p, _unit(t)


def _wire_edges_and_lengths(wire):
    edges = wire.Edges
    lens = [e.Length for e in edges]
    cum = []
    total = 0.0
    for length in lens:
        total += length
        cum.append(total)
    return edges, lens, cum, total


def _wire_point_tangent_at_s(wire, s):
    edges, lens, cum, total = _wire_edges_and_lengths(wire)
    s = max(0.0, min(float(s), total))

    prev_cum = 0.0
    for edge, length, total_so_far in zip(edges, lens, cum):
        if s <= total_so_far + 1e-9:
            local_s = s - prev_cum
            try:
                u0, u1 = edge.ParameterRange
                u = edge.Curve.parameterAtDistance(local_s, u0)
                u = max(min(u, u1), u0)
            except Exception:
                u0, u1 = edge.ParameterRange
                u = u0 + (u1 - u0) * (local_s / max(length, 1e-9))
            return _edge_point_tangent_at_u(edge, u)
        prev_cum = total_so_far

    edge = edges[-1]
    u1 = edge.ParameterRange[1]
    return _edge_point_tangent_at_u(edge, u1)


def _make_rect_profile(center, U, V, width, thickness):
    U = _unit(U)
    V = _unit(V)
    w = float(width) * 0.5
    t = float(thickness) * 0.5

    p1 = center + U.multiply(-w) + V.multiply(-t)
    p2 = center + U.multiply(+w) + V.multiply(-t)
    p3 = center + U.multiply(+w) + V.multiply(+t)
    p4 = center + U.multiply(-w) + V.multiply(+t)

    wire = Part.makePolygon([p1, p2, p3, p4, p1])
    return Part.Face(wire)


def _initial_frame_from_up_hint(tangent, up_hint):
    v0 = up_hint - tangent.multiply(up_hint.dot(tangent))
    if v0.Length < 1e-6:
        tmp = App.Vector(1, 0, 0)
        if abs(tangent.dot(tmp)) > 0.9:
            tmp = App.Vector(0, 1, 0)
        v0 = tmp - tangent.multiply(tmp.dot(tangent))
    V = _unit(v0)
    U = _unit(tangent.cross(V))
    return U, V


def _build_frames(wire, steps, up_hint, total_twist_deg):
    edges, lens, cum, length = _wire_edges_and_lengths(wire)
    if length <= 1e-9:
        raise Exception("Selected path has zero length.")

    p0, t0 = _wire_point_tangent_at_s(wire, 0.0)
    U, V = _initial_frame_from_up_hint(t0, up_hint)
    prev_t = t0
    total_twist = math.radians(float(total_twist_deg))

    frames = []
    for i in range(steps + 1):
        s = (length * i) / float(steps)
        p, t = _wire_point_tangent_at_s(wire, s)

        axis = prev_t.cross(t)
        if axis.Length > 1e-9:
            ang = math.atan2(axis.Length, prev_t.dot(t))
            V = _rotate_about_axis(V, axis, ang)
            U = _rotate_about_axis(U, axis, ang)

        V = V - t.multiply(V.dot(t))
        V = _unit(V)
        U = _unit(t.cross(V))

        if abs(total_twist) > 1e-12:
            frac = s / max(length, 1e-9)
            twist_here = total_twist * frac
            Vt = _rotate_about_axis(V, t, twist_here)
            Ut = _rotate_about_axis(U, t, twist_here)
        else:
            Vt, Ut = V, U

        frames.append(
            {
                "s": s,
                "point": p,
                "tangent": t,
                "U": Ut,
                "V": Vt,
            }
        )

        prev_t = t

    return frames, length


def _nearest_frame(frames, s):
    return min(frames, key=lambda f: abs(f["s"] - s))


def create_strip_along_path(
    strip_width=12.0,
    strip_thickness=0.8,
    hole_d=5.0,
    pitch=15.0,
    n_holes=None,
    start_offset=0.0,
    fit_holes_to_path=True,
    samples_per_pitch=6,
    up_hint=App.Vector(0, 0, 1),
    total_twist_deg=0.0,
    name="ArmaStrip_Path",
    path_obj=None,
):
    doc = App.ActiveDocument or App.newDocument("Armstrip")

    if path_obj is None:
        sel = Gui.Selection.getSelection()
        if len(sel) != 1:
            raise Exception("Select ONE path object (edge/wire/sketch).")
        path_obj = sel[0]

    shape = path_obj.Shape
    if shape.isNull():
        raise Exception("Selected path has no shape.")

    if len(shape.Wires) > 0:
        wire = shape.Wires[0]
    elif len(shape.Edges) > 0:
        wire = Part.Wire(shape.Edges)
    else:
        raise Exception("Selected path contains no edges.")

    is_closed = wire.isClosed() or (
        (wire.Vertexes[0].Point - wire.Vertexes[-1].Point).Length < 1e-6
    )

    if pitch <= 0:
        raise ValueError("pitch must be > 0")
    if hole_d <= 0:
        raise ValueError("hole_d must be > 0")
    if strip_thickness <= 0:
        raise ValueError("strip_thickness must be > 0")
    if strip_width <= 0:
        raise ValueError("strip_width must be > 0")
    if samples_per_pitch < 2:
        raise ValueError("samples_per_pitch must be >= 2")

    _, _, _, length = _wire_edges_and_lengths(wire)

    if n_holes is None:
        hole_count = max(1, int(round(length / float(pitch))))
    else:
        hole_count = max(1, int(n_holes))

    effective_pitch = float(pitch)
    if is_closed and fit_holes_to_path:
        effective_pitch = length / float(hole_count)

    approx_steps = max(
        6,
        int(math.ceil((length / max(effective_pitch, 1e-9)) * samples_per_pitch)),
    )
    steps = approx_steps + (1 if is_closed else 0)

    frames, length = _build_frames(wire, steps, up_hint, total_twist_deg)

    faces = []
    for frame in frames:
        face = _make_rect_profile(
            frame["point"],
            frame["U"],
            frame["V"],
            strip_width,
            strip_thickness,
        )
        faces.append(face)

    loft = Part.makeLoft([f.OuterWire for f in faces], True, False)
    solid = loft

    hole_radius = float(hole_d) * 0.5
    hole_length = float(strip_thickness) + 2.0
    cutters = []
    hole_centers = []
    hole_axes = []

    for i in range(hole_count):
        s = float(start_offset) + (i + 0.5) * effective_pitch
        if is_closed:
            s = s % length
        elif s < 0.0 or s > length:
            continue

        frame = _nearest_frame(frames, s)
        center = frame["point"]
        axis = frame["V"]

        base = center - axis.multiply(hole_length * 0.5)
        cyl = Part.makeCylinder(hole_radius, hole_length, base, axis)
        cutters.append(cyl)
        hole_centers.append(center)
        hole_axes.append(axis)

    if cutters:
        solid = solid.cut(Part.makeCompound(cutters))

    obj = doc.addObject("Part::Feature", name)
    obj.Shape = solid

    try:
        obj.addProperty(
            "App::PropertyFloat", "Width", "Armstrip", "strip width"
        ).Width = float(strip_width)
        obj.addProperty(
            "App::PropertyFloat", "Thickness", "Armstrip", "strip thickness"
        ).Thickness = float(strip_thickness)
        obj.addProperty(
            "App::PropertyFloat", "HoleDiameter", "Armstrip", "hole diameter"
        ).HoleDiameter = float(hole_d)
        obj.addProperty(
            "App::PropertyFloat", "Pitch", "Armstrip", "hole pitch"
        ).Pitch = float(effective_pitch)
        obj.addProperty(
            "App::PropertyInteger", "HoleCount", "Armstrip", "number of holes"
        ).HoleCount = int(hole_count)
        obj.addProperty(
            "App::PropertyFloat", "StartOffset", "Armstrip", "hole start offset"
        ).StartOffset = float(start_offset)
        obj.addProperty(
            "App::PropertyFloat", "TotalTwist", "Armstrip", "total twist degrees"
        ).TotalTwist = float(total_twist_deg)
        obj.addProperty(
            "App::PropertyBool", "FitHolesToPath", "Armstrip", "fit holes to path"
        ).FitHolesToPath = bool(fit_holes_to_path)
        obj.addProperty(
            "App::PropertyVectorList",
            "HoleCenters",
            "Armstrip",
            "detected hole centers",
        ).HoleCenters = hole_centers
        obj.addProperty(
            "App::PropertyVectorList",
            "HoleAxes",
            "Armstrip",
            "hole axes",
        ).HoleAxes = hole_axes
    except Exception:
        pass

    doc.recompute()
    Gui.ActiveDocument.ActiveView.viewAxonometric()
    Gui.SendMsgToActiveView("ViewFit")

    App.Console.PrintMessage(
        f"[Armstrip] Path strip: holes={hole_count}, pitch={effective_pitch}, length={length}\n"
    )
    return obj


def create_strip_along_path_gui():
    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("Create ArmaStrip Along Path")
    layout = QtWidgets.QFormLayout(dlg)

    strip_width = QtWidgets.QDoubleSpinBox()
    strip_width.setRange(0.1, 200.0)
    strip_width.setDecimals(2)
    strip_width.setValue(12.0)

    strip_thickness = QtWidgets.QDoubleSpinBox()
    strip_thickness.setRange(0.1, 50.0)
    strip_thickness.setDecimals(2)
    strip_thickness.setValue(0.8)

    hole_d = QtWidgets.QDoubleSpinBox()
    hole_d.setRange(0.1, 100.0)
    hole_d.setDecimals(2)
    hole_d.setValue(5.0)

    pitch = QtWidgets.QDoubleSpinBox()
    pitch.setRange(0.1, 500.0)
    pitch.setDecimals(2)
    pitch.setValue(15.0)

    hole_count = QtWidgets.QSpinBox()
    hole_count.setRange(0, 1000)
    hole_count.setValue(0)
    hole_count.setToolTip("0 = auto-fit to path length.")

    fit_to_path = QtWidgets.QCheckBox("Fit holes to closed path")
    fit_to_path.setChecked(True)

    start_offset = QtWidgets.QDoubleSpinBox()
    start_offset.setRange(-5000.0, 5000.0)
    start_offset.setDecimals(2)
    start_offset.setValue(0.0)

    twist_deg = QtWidgets.QDoubleSpinBox()
    twist_deg.setRange(-720.0, 720.0)
    twist_deg.setDecimals(1)
    twist_deg.setValue(0.0)

    samples_per_pitch = QtWidgets.QSpinBox()
    samples_per_pitch.setRange(2, 50)
    samples_per_pitch.setValue(6)

    layout.addRow("Strip width", strip_width)
    layout.addRow("Strip thickness", strip_thickness)
    layout.addRow("Hole diameter", hole_d)
    layout.addRow("Hole pitch", pitch)
    layout.addRow("Hole count (0 = auto)", hole_count)
    layout.addRow("", fit_to_path)
    layout.addRow("Start offset", start_offset)
    layout.addRow("Total twist (deg)", twist_deg)
    layout.addRow("Samples per pitch", samples_per_pitch)

    btns = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
    )
    layout.addRow(btns)

    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)

    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return

    selected = Gui.Selection.getSelection()
    if len(selected) != 1:
        QtWidgets.QMessageBox.warning(
            None,
            "ArmaStrip",
            "Select ONE path object (edge/wire/sketch) before running.",
        )
        return

    count = hole_count.value()
    create_strip_along_path(
        strip_width=strip_width.value(),
        strip_thickness=strip_thickness.value(),
        hole_d=hole_d.value(),
        pitch=pitch.value(),
        n_holes=None if count == 0 else count,
        start_offset=start_offset.value(),
        fit_holes_to_path=fit_to_path.isChecked(),
        samples_per_pitch=samples_per_pitch.value(),
        total_twist_deg=twist_deg.value(),
        path_obj=selected[0],
    )
