import os
import FreeCAD as App
import FreeCADGui as Gui


def _icon(name):
    try:
        user_dir = App.getUserAppDataDir()
        mod_dir = os.path.join(user_dir, "Mod", "ArmaStripWB", "ArmaStripWB")
        cand = os.path.join(mod_dir, "Resources", "icons", name)
        if os.path.isfile(cand):
            return cand
    except Exception:
        pass
    # Fallback to package-relative path for dev installs
    pkg_dir = os.path.dirname(__file__)
    cand = os.path.join(pkg_dir, "Resources", "icons", name)
    if os.path.isfile(cand):
        return cand
    return ""


def register_commands():
    Gui.addCommand("ArmaStrip_CreateStrip", CmdCreateStrip())
    Gui.addCommand("ArmaStrip_NutPockets", CmdNutPockets())
    Gui.addCommand("ArmaStrip_BoltHoles", CmdBoltHoles())


class CmdCreateStrip:
    def GetResources(self):
        return {
            "Pixmap": _icon("ArmaStrip_CreateStrip.svg"),
            "MenuText": "Create ArmaStrip (constant width)",
            "ToolTip": "Create a constant-width ArmaStrip with holes",
        }

    def IsActive(self):
        return True

    def Activated(self):
        from ArmaStripWB import strip_tools

        strip_tools.create_strip_constant_width_gui()


class CmdNutPockets:
    def GetResources(self):
        return {
            "Pixmap": _icon("ArmaStrip_NutPockets.svg"),
            "MenuText": "Cut Nut Pockets",
            "ToolTip": "Select part/body first, then ArmaStrip. Cuts hex nut pockets.",
        }

    def IsActive(self):
        return Gui.ActiveDocument is not None

    def Activated(self):
        from ArmaStripWB import nut_pocket_tools

        nut_pocket_tools.cut_nut_pockets_gui()


class CmdBoltHoles:
    def GetResources(self):
        return {
            "Pixmap": _icon("ArmaStrip_BoltHoles.svg"),
            "MenuText": "Cut Bolt Holes",
            "ToolTip": "Select part/body first, then ArmaStrip. Cuts bolt holes (round or teardrop).",
        }

    def IsActive(self):
        return Gui.ActiveDocument is not None

    def Activated(self):
        from ArmaStripWB import bolt_hole_tools

        bolt_hole_tools.cut_bolt_holes_gui()
