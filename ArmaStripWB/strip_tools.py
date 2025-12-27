import FreeCAD as App
import FreeCADGui as Gui
import Part
import math

try:
    from PySide2 import QtWidgets
except Exception:
    QtWidgets = None


def _ensure_doc():
    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("Armstrip")
    return doc


def create_strip_constant_width(
    mode="holes",             # "holes" or "length"
    n_holes=3,                # used when mode="holes"
    strip_length=45.0,        # used when mode="length"
    hole_d=5.0,
    hole_pitch=15.0,
    strip_thickness=0.8,
    strip_width=12.0,
    name="Armastrip"
):
    """
    Creates a constant-width strip with holes.

    Important detail:
      - mode="holes": length = n_holes * pitch, and ends land midway between holes
                      (the easiest place to cut in real life)
      - mode="length": picks nearest n_holes to fit, and centers the pattern in the length
    """
    doc = _ensure_doc()

    if hole_pitch <= 0:
        raise ValueError("hole_pitch must be > 0")
    if hole_d <= 0:
        raise ValueError("hole_d must be > 0")
    if strip_thickness <= 0:
        raise ValueError("strip_thickness must be > 0")
    if strip_width <= 0:
        raise ValueError("strip_width must be > 0")

    # --- Determine n_holes and band length ---
    if mode == "holes":
        n_holes = max(1, int(n_holes))
        band_length = n_holes * hole_pitch
        x_offset = 0.0  # ends are mid-span between holes (nice for cutting)
    elif mode == "length":
        strip_length = float(strip_length)
        n_holes = max(1, int(round(strip_length / hole_pitch)))
        band_length = n_holes * hole_pitch
        x_offset = 0.5 * (strip_length - band_length)  # center the hole pattern
    else:
        raise ValueError('mode must be "holes" or "length"')

    # Use strip_length as the final solid length if mode="length"
    final_length = band_length if mode == "holes" else float(strip_length)

    # --- Make 2D rectangle profile in XY ---
    w = float(strip_width)
    x0 = 0.0
    x1 = final_length

    pts = [
        App.Vector(x0, -w * 0.5, 0),
        App.Vector(x1, -w * 0.5, 0),
        App.Vector(x1,  w * 0.5, 0),
        App.Vector(x0,  w * 0.5, 0),
        App.Vector(x0, -w * 0.5, 0),
    ]
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)

    # --- Extrude to 3D solid ---
    solid = face.extrude(App.Vector(0, 0, float(strip_thickness)))

    # --- Drill holes (vertical, global Z) ---
    for i in range(n_holes):
        x_local = (i + 0.5) * hole_pitch  # holes halfway between cut points
        x = x_offset + x_local

        cyl = Part.makeCylinder(
            hole_d * 0.5,
            float(strip_thickness),
            App.Vector(x, 0, 0),
            App.Vector(0, 0, 1)
        )
        solid = solid.cut(cyl)

    # --- Add to doc ---
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = solid

    # Helpful metadata (Phase A friendly; Phase B we'll store VectorLists properly)
    try:
        obj.addProperty("App::PropertyString", "ArmstripMode", "Armstrip", "holes or length").ArmstripMode = mode
        obj.addProperty("App::PropertyInteger", "HoleCount", "Armstrip", "number of holes").HoleCount = int(n_holes)
        obj.addProperty("App::PropertyFloat", "Pitch", "Armstrip", "hole pitch").Pitch = float(hole_pitch)
        obj.addProperty("App::PropertyFloat", "Width", "Armstrip", "strip width").Width = float(strip_width)
        obj.addProperty("App::PropertyFloat", "Thickness", "Armstrip", "strip thickness").Thickness = float(strip_thickness)
        obj.addProperty("App::PropertyFloat", "HoleDiameter", "Armstrip", "hole diameter").HoleDiameter = float(hole_d)
    except Exception:
        # If properties already exist or FreeCAD version quirks, ignore for now
        pass

    doc.recompute()
    Gui.ActiveDocument.ActiveView.viewAxonometric()
    Gui.SendMsgToActiveView("ViewFit")

    App.Console.PrintMessage(
        f"[Armstrip] mode={mode}, holes={n_holes}, pitch={hole_pitch}, length={final_length}, x_offset={x_offset}\n"
    )

    return obj


def create_strip_constant_width_gui():
    """
    Simple dialog-based UI (not a full task panel yet).
    Later we can replace this with a proper Task panel.
    """
    if QtWidgets is None:
        # Fallback: create with hardcoded defaults
        create_strip_constant_width(
            mode="holes",
            n_holes=3,
            hole_d=5.0,
            hole_pitch=15.0,
            strip_thickness=0.8,
            strip_width=12.0
        )
        return

    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("Create Armstrip (constant width)")

    layout = QtWidgets.QFormLayout(dlg)

    mode = QtWidgets.QComboBox()
    mode.addItems(["holes", "length"])

    n_holes = QtWidgets.QSpinBox()
    n_holes.setRange(1, 500)
    n_holes.setValue(3)

    strip_length = QtWidgets.QDoubleSpinBox()
    strip_length.setRange(1.0, 5000.0)
    strip_length.setDecimals(2)
    strip_length.setValue(45.0)

    hole_d = QtWidgets.QDoubleSpinBox()
    hole_d.setRange(0.1, 100.0)
    hole_d.setDecimals(2)
    hole_d.setValue(5.0)

    pitch = QtWidgets.QDoubleSpinBox()
    pitch.setRange(0.1, 500.0)
    pitch.setDecimals(2)
    pitch.setValue(15.0)

    thickness = QtWidgets.QDoubleSpinBox()
    thickness.setRange(0.1, 50.0)
    thickness.setDecimals(2)
    thickness.setValue(0.8)

    width = QtWidgets.QDoubleSpinBox()
    width.setRange(0.1, 200.0)
    width.setDecimals(2)
    width.setValue(12.0)

    layout.addRow("Mode", mode)
    layout.addRow("Hole count (mode=holes)", n_holes)
    layout.addRow("Strip length (mode=length)", strip_length)
    layout.addRow("Hole diameter", hole_d)
    layout.addRow("Hole pitch", pitch)
    layout.addRow("Thickness", thickness)
    layout.addRow("Width", width)

    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    layout.addRow(btns)

    def on_mode_changed(_):
        m = mode.currentText()
        n_holes.setEnabled(m == "holes")
        strip_length.setEnabled(m == "length")

    mode.currentIndexChanged.connect(on_mode_changed)
    on_mode_changed(None)

    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)

    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return

    create_strip_constant_width(
        mode=mode.currentText(),
        n_holes=n_holes.value(),
        strip_length=strip_length.value(),
        hole_d=hole_d.value(),
        hole_pitch=pitch.value(),
        strip_thickness=thickness.value(),
        strip_width=width.value()
    )
