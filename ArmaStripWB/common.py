# -*- coding: utf-8 -*-
"""
Common helpers for ArmaStripWB fastener tools.

Flat-strip assumption: hole axes point along +Z.
"""
import math
import FreeCAD as App
import FreeCADGui as Gui
import Part


def get_selection_part_and_strip():
    doc = App.ActiveDocument
    if doc is None:
        raise Exception("No active document")

    sel = Gui.Selection.getSelection()
    if len(sel) != 2:
        raise Exception("Select FIRST the target part/body, THEN the ArmaStrip.")

    part_obj, strip_obj = sel[0], sel[1]

    if part_obj.Shape.isNull() or strip_obj.Shape.isNull():
        raise Exception("Selection contains invalid shapes.")

    return part_obj, strip_obj


def find_hole_centers_from_strip(strip_shape, center_tol=0.1):
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

    centers = [c for (c, _r) in holes]
    centers = sorted(centers, key=lambda v: (round(v.x, 6), round(v.y, 6), round(v.z, 6)))
    App.Console.PrintMessage(f"[ArmaStrip] Detected {len(centers)} hole centers.\n")
    return centers


def filter_hole_centers(centers, selection_mode="all", every_n=1, start_index=1):
    mode = selection_mode or "all"
    total = len(centers)

    if mode == "ends":
        if total <= 1:
            selected = centers
        else:
            selected = [centers[0], centers[-1]]
    elif mode == "step":
        step = int(every_n)
        start = int(start_index)
        if step < 1:
            raise Exception("Every-N value must be >= 1.")
        if start < 1:
            raise Exception("Start hole index must be >= 1.")
        if start > total:
            raise Exception("Start hole index exceeds available holes.")
        if start >= step:
            raise Exception("Start hole index must be less than the Every-N value.")

        selected = []
        for idx, ctr in enumerate(centers, start=1):
            if idx < start:
                continue
            if (idx - start) % step == 0:
                selected.append(ctr)
    else:
        selected = centers

    App.Console.PrintMessage(
        f"[ArmaStrip] Using {len(selected)} of {total} detected hole centers (mode: {mode}).\n"
    )
    return selected


def unit(v):
    ln = v.Length
    if ln < 1e-9:
        return App.Vector(0, 0, 0)
    return v.multiply(1.0 / ln)


def make_hex_prism_xy(center, R, height):
    """Hex pocket cutter placed in XY, extruded +Z."""
    pts = []
    for k in range(6):
        ang = math.radians(60 * k)
        pts.append(
            App.Vector(
                center.x + R * math.cos(ang),
                center.y + R * math.sin(ang),
                center.z,
            )
        )
    pts.append(pts[0])
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)
    return face.extrude(App.Vector(0, 0, height))


def _teardrop_points_2d(r, steps):
    pts = []
    a0 = math.radians(135)
    a1 = math.radians(405)  # 360 + 45
    for i in range(int(steps) + 1):
        a = a0 + (a1 - a0) * (i / float(steps))
        pts.append((r * math.cos(a), r * math.sin(a)))

    pts.append((0.0, math.sqrt(2.0) * r))
    pts.append(pts[0])
    return pts


def make_teardrop_prism(center, axis, print_up, r, length, steps):
    """Teardrop cutter whose profile plane is perpendicular to axis."""
    A = unit(axis)
    if A.Length < 1e-9:
        raise Exception("Invalid hole axis")

    p = print_up.sub(A.multiply(print_up.dot(A)))
    if p.Length > 1e-6:
        V = unit(p)
    else:
        ref = App.Vector(1, 0, 0)
        if abs(A.dot(ref)) > 0.9:
            ref = App.Vector(0, 1, 0)
        V = unit(A.cross(ref))

    U = unit(A.cross(V))
    if U.Length < 1e-9 or V.Length < 1e-9:
        ref = App.Vector(0, 1, 0)
        if abs(A.dot(ref)) > 0.9:
            ref = App.Vector(1, 0, 0)
        V = unit(A.cross(ref))
        U = unit(A.cross(V))

    if U.Length < 1e-9 or V.Length < 1e-9:
        raise Exception("Failed to build teardrop basis (degenerate).")

    base_center = center.sub(A.multiply(length * 0.5))

    pts2 = _teardrop_points_2d(r, int(steps))
    pts3 = [base_center.add(U.multiply(x)).add(V.multiply(y)) for (x, y) in pts2]

    wire = Part.makePolygon(pts3)
    face = Part.Face(wire)
    return face.extrude(A.multiply(length))


def make_round_hole_cyl(center, axis, r, length):
    A = unit(axis)
    if A.Length < 1e-9:
        raise Exception("Invalid hole axis")
    base = center.sub(A.multiply(length * 0.5))
    return Part.makeCylinder(r, length, base, A)
