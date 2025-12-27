import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui

App.Console.PrintMessage("[ArmaStripWB] InitGui.py starting (ultra-safe)...\n")


class ArmaStripWorkbench(Gui.Workbench):
    MenuText = "ArmaStrip"
    ToolTip = "Tools for creating ArmaStrip and generating fastener pockets"

    def __init__(self):
        icon_path = ""
        try:
            user_dir = App.getUserAppDataDir()
            mod_dir = os.path.join(user_dir, "Mod", "ArmaStripWB")
            pkg_dir = os.path.join(mod_dir, "ArmaStripWB")
            cand = os.path.join(pkg_dir, "Resources", "icons", "ArmaStripWB.svg")

            App.Console.PrintMessage(f"[ArmaStripWB] icon candidate: {cand}\n")
            if os.path.isfile(cand):
                icon_path = cand
        except Exception:
            App.Console.PrintError("[ArmaStripWB] Icon path compute failed:\n")
            App.Console.PrintError(traceback.format_exc() + "\n")

        self.__class__.Icon = icon_path
        App.Console.PrintMessage(
            f"[ArmaStripWB] Workbench __init__: Icon='{icon_path}'\n"
        )

    def Initialize(self):
        App.Console.PrintMessage("[ArmaStripWB] Workbench Initialize() start\n")
        try:
            from ArmaStripWB import commands

            App.Console.PrintMessage("[ArmaStripWB] Imported ArmaStripWB.commands OK\n")
            commands.register_commands()
            App.Console.PrintMessage("[ArmaStripWB] Registered commands OK\n")
        except Exception:
            App.Console.PrintError("[ArmaStripWB] Failed importing/registering commands:\n")
            App.Console.PrintError(traceback.format_exc() + "\n")
            return

        self.appendToolbar(
            "ArmaStrip",
            [
                "ArmaStrip_CreateStrip",
                "ArmaStrip_NutPockets",
                "ArmaStrip_BoltHoles",
            ],
        )
        self.appendMenu(
            "ArmaStrip",
            [
                "ArmaStrip_CreateStrip",
                "ArmaStrip_NutPockets",
                "ArmaStrip_BoltHoles",
            ],
        )
        App.Console.PrintMessage("[ArmaStripWB] Workbench Initialize() complete\n")


try:
    Gui.addWorkbench(ArmaStripWorkbench())
    App.Console.PrintMessage("[ArmaStripWB] Gui.addWorkbench() succeeded\n")
except Exception:
    App.Console.PrintError("[ArmaStripWB] Gui.addWorkbench() failed:\n")
    App.Console.PrintError(traceback.format_exc() + "\n")
