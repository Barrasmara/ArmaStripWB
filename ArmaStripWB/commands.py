import os
import FreeCADGui as Gui

ICON_DIR = os.path.join(os.path.dirname(__file__), "Resources", "icons")

def _icon(name):
    return os.path.join(ICON_DIR, name)

def register_commands():
    Gui.addCommand("ArmaStrip_CreateStrip", CmdCreateStrip())
    Gui.addCommand("ArmaStrip_NutPockets",  CmdNutPockets())
    Gui.addCommand("ArmaStrip_BoltHoles",   CmdBoltHoles())

class CmdCreateStrip:
    def GetResources(self):
        return {
            "Pixmap": _icon("ArmaStrip_CreateStrip.svg"),
            "MenuText": "Create ArmaStrip (constant width)",
            "ToolTip": "Create a constant-width ArmaStrip with holes"
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
            "ToolTip": "Select part first, then strip. Cuts hex nut pockets."
        }

    def IsActive(self):
        return Gui.ActiveDocument is not None

    def Activated(self):
        from ArmaStripWB import pocket_tools
        nut_pocket_tools.cut_nut_pockets_gui()


class CmdBoltHoles:
    def GetResources(self):
        return {
            "Pixmap": _icon("ArmaStrip_BoltHoles.svg"),  # make a new icon or reuse NutPockets.svg
            "MenuText": "Cut Bolt Holes",
            "ToolTip": "Select part first, then strip. Cuts bolt holes (round or teardrop)."
        }

    def IsActive(self):
        return Gui.ActiveDocument is not None

    def Activated(self):
        from ArmaStripWB import bolt_hole_tools
        bolt_hole_tools.cut_bolt_holes_gui()
        
