import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide2 import QtWidgets


def _unit(v):
    ln = v.Length
    if ln < 1e-12:
        return App.Vector(0, 0, 0)
    return v.multiply(1.0 / ln)


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


def _planar_normal_from_wire(wire, up_hint):
    length = wire.Length
    if length <= 1e-9:
        raise Exception("Selected path has zero length.")

    p0, t0 = _wire_point_tangent_at_s(wire, 0.0)
    p1, t1 = _wire_point_tangent_at_s(wire, min(length * 0.25, length))
    n = t0.cross(t1)
    if n.Length < 1e-9:
        p2, t2 = _wire_point_tangent_at_s(wire, min(length * 0.5, length))
        n = t0.cross(t2)
    if n.Length < 1e-9:
        raise Exception("Unable to determine a plane normal for the selected path.")
    n = _unit(n)
    if up_hint.Length > 1e-9 and n.dot(_unit(up_hint)) < 0:
        n = n.multiply(-1)
    return n


def _reversed_edges(edges):
    reversed_edges = []
    for edge in reversed(edges):
        edge_copy = edge.copy()
        edge_copy.reverse()
        reversed_edges.append(edge_copy)
    return reversed_edges


def _wire_from_offset_shape(shape, label):
    if hasattr(shape, "Wires") and shape.Wires:
        if len(shape.Wires) > 1:
            raise Exception(f"Offset for {label} produced multiple wires.")
        return shape.Wires[0]
    if hasattr(shape, "Edges") and shape.Edges:
        sorted_edges = Part.sortEdges(shape.Edges)
        if not sorted_edges:
            raise Exception(f"Offset for {label} produced no edges.")
        return Part.Wire(sorted_edges[0])
    raise Exception(f"Offset for {label} produced no wire.")


def _wire_bbox_size(wire):
    return wire.BoundBox.DiagonalLength


def _build_strip_face_from_edge_wire(wire, thickness, offset_dir):
    offset = float(thickness)
    if offset <= 0:
        raise ValueError("strip_thickness must be > 0")

    offset_wire = _wire_from_offset_shape(
        wire.makeOffset2D(offset * float(offset_dir)), "offset"
    )

    if wire.isClosed():
        outer = offset_wire
        inner = wire
        if _wire_bbox_size(inner) > _wire_bbox_size(outer):
            outer, inner = inner, outer
        return Part.Face([outer, inner])

    offset_start = offset_wire.Vertexes[0].Point
    offset_end = offset_wire.Vertexes[-1].Point
    base_start = wire.Vertexes[0].Point
    base_end = wire.Vertexes[-1].Point

    cap_end = Part.makeLine(offset_end, base_end)
    cap_start = Part.makeLine(base_start, offset_start)

    outline_edges = (
        offset_wire.Edges
        + [cap_end]
        + _reversed_edges(wire.Edges)
        + [cap_start]
    )
    sorted_edges = Part.sortEdges(outline_edges)
    if not sorted_edges:
        raise Exception("Unable to build open strip outline.")
    outline = Part.Wire(sorted_edges[0])
    return Part.Face(outline)


def _build_strip_face_from_centerline_wire(wire, thickness):
    offset = float(thickness) * 0.5
    if offset <= 0:
        raise ValueError("strip_thickness must be > 0")

    offset_plus = _wire_from_offset_shape(wire.makeOffset2D(offset), "positive")
    offset_minus = _wire_from_offset_shape(wire.makeOffset2D(-offset), "negative")

    if wire.isClosed():
        outer = offset_plus
        inner = offset_minus
        if _wire_bbox_size(inner) > _wire_bbox_size(outer):
            outer, inner = inner, outer
        return Part.Face([outer, inner])

    plus_start = offset_plus.Vertexes[0].Point
    plus_end = offset_plus.Vertexes[-1].Point
    minus_start = offset_minus.Vertexes[0].Point
    minus_end = offset_minus.Vertexes[-1].Point

    cap_end = Part.makeLine(plus_end, minus_end)
    cap_start = Part.makeLine(minus_start, plus_start)

    outline_edges = (
        offset_plus.Edges
        + [cap_end]
        + _reversed_edges(offset_minus.Edges)
        + [cap_start]
    )
    sorted_edges = Part.sortEdges(outline_edges)
    if not sorted_edges:
        raise Exception("Unable to build open strip outline.")
    outline = Part.Wire(sorted_edges[0])
    return Part.Face(outline)

def create_strip_along_path(
    strip_width=12.0,
    strip_thickness=0.8,
    hole_d=5.0,
    pitch=15.0,
    n_holes=None,
    start_offset=0.0,
    fit_holes_to_path=True,
    up_hint=App.Vector(0, 0, 0),
    offset_dir=1,
    path_is_centerline=False,
    keep_history=False,
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
    if offset_dir not in (-1, 1):
        raise ValueError("offset_dir must be -1 or 1")
    _, _, _, length = _wire_edges_and_lengths(wire)

    if n_holes is None:
        hole_count = max(1, int(round(length / float(pitch))))
    else:
        hole_count = max(1, int(n_holes))

    effective_pitch = float(pitch)
    if is_closed and fit_holes_to_path:
        effective_pitch = length / float(hole_count)

    normal = _planar_normal_from_wire(wire, up_hint)
    width_dir = normal
    align_to_z = App.Rotation(width_dir, App.Vector(0, 0, 1))
    to_z = App.Placement(App.Vector(0, 0, 0), align_to_z)
    to_world = App.Placement(App.Vector(0, 0, 0), align_to_z.inverted())

    wire_local = wire.copy()
    wire_local.transformShape(to_z.toMatrix())

    offset_wire_world = None
    if path_is_centerline:
        face_local = _build_strip_face_from_centerline_wire(wire_local, strip_thickness)
    else:
        offset_wire_local = _wire_from_offset_shape(
            wire_local.makeOffset2D(strip_thickness * float(offset_dir)), "offset"
        )
        offset_wire_world = offset_wire_local.copy()
        offset_wire_world.transformShape(to_world.toMatrix())
        face_local = _build_strip_face_from_edge_wire(
            wire_local, strip_thickness, offset_dir
        )
    face_local.transformShape(to_world.toMatrix())

    base_solid = face_local.extrude(width_dir.multiply(float(strip_width)))
    if base_solid.isNull():
        raise Exception("Failed to build strip solid from the selected path.")
    solid = base_solid

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

        center, tangent = _wire_point_tangent_at_s(wire, s)
        if path_is_centerline:
            thickness_dir = _unit(tangent.cross(width_dir))
        else:
            offset_len = offset_wire_world.Length if offset_wire_world else 0.0
            if offset_len > 1e-9:
                s_offset = (s / length) * offset_len
                offset_point, _ = _wire_point_tangent_at_s(offset_wire_world, s_offset)
                thickness_dir = _unit(offset_point.sub(center))
                center = center.add(offset_point).multiply(0.5)
            else:
                thickness_dir = _unit(tangent.cross(width_dir)).multiply(float(offset_dir))
                center = center + thickness_dir.multiply(float(strip_thickness) * 0.5)
        center = center + width_dir.multiply(float(strip_width) * 0.5)
        axis = thickness_dir

        base = center - axis.multiply(hole_length * 0.5)
        cyl = Part.makeCylinder(hole_radius, hole_length, base, axis)
        cutters.append(cyl)
        hole_centers.append(center)
        hole_axes.append(axis)

    cutters_compound = Part.makeCompound(cutters) if cutters else None
    if cutters_compound:
        if solid.isNull():
            raise Exception("Strip solid is null before cutting holes.")
        solid = solid.cut(cutters_compound)
        if solid.isNull():
            raise Exception("Cut operation resulted in a null shape.")

    if keep_history:
        profile_obj = doc.addObject("Part::Feature", f"{name}_Profile")
        profile_obj.Shape = face_local
        base_obj = doc.addObject("Part::Feature", f"{name}_Base")
        base_obj.Shape = base_solid
        if cutters_compound:
            cutters_obj = doc.addObject("Part::Feature", f"{name}_Cutters")
            cutters_obj.Shape = cutters_compound

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
            "App::PropertyBool", "FitHolesToPath", "Armstrip", "fit holes to path"
        ).FitHolesToPath = bool(fit_holes_to_path)
        obj.addProperty(
            "App::PropertyInteger", "OffsetDir", "Armstrip", "offset side (+/-1)"
        ).OffsetDir = int(offset_dir)
        obj.addProperty(
            "App::PropertyBool",
            "PathIsCenterline",
            "Armstrip",
            "path is strip centerline",
        ).PathIsCenterline = bool(path_is_centerline)
        obj.addProperty(
            "App::PropertyBool",
            "KeepHistory",
            "Armstrip",
            "keep construction history",
        ).KeepHistory = bool(keep_history)
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

    flip_offset = QtWidgets.QCheckBox("Flip offset side")
    flip_offset.setChecked(False)

    path_is_centerline = QtWidgets.QCheckBox("Path is strip centerline")
    path_is_centerline.setChecked(False)

    keep_history = QtWidgets.QCheckBox("Keep construction history")
    keep_history.setChecked(False)

    layout.addRow("Strip width", strip_width)
    layout.addRow("Strip thickness", strip_thickness)
    layout.addRow("Hole diameter", hole_d)
    layout.addRow("Hole pitch", pitch)
    layout.addRow("Hole count (0 = auto)", hole_count)
    layout.addRow("", fit_to_path)
    layout.addRow("Start offset", start_offset)
    layout.addRow("", flip_offset)
    layout.addRow("", path_is_centerline)
    layout.addRow("", keep_history)

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
        offset_dir=-1 if flip_offset.isChecked() else 1,
        path_is_centerline=path_is_centerline.isChecked(),
        keep_history=keep_history.isChecked(),
        path_obj=selected[0],
    )
