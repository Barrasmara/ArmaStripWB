# ArmaStripWB

A FreeCAD workbench for creating perforated metal ArmaStrip and generating:
- hex nut pockets aligned to strip holes
- bolt holes (round or teardrop)

## Install
Copy (or clone) this folder into your FreeCAD Mod directory:

- Windows: %APPDATA%\FreeCAD\Mod\

Restart FreeCAD, then select the **ArmaStrip** workbench.

## Usage
1. Create an ArmaStrip
2. Select the target part first, then the strip
3. Run **Cut Nut Pockets** or **Cut Bolt Holes**

## How to test in FreeCAD
1. Launch FreeCAD and switch to the **ArmaStrip** workbench.
2. Create a new document, then click **Create ArmaStrip** and place a strip.
3. Model or import a target part; select the part/body first, then the ArmaStrip object.
4. Start **Cut Nut Pockets** or **Cut Bolt Holes** from the toolbar/menu.
5. Use the Task Panel fields to set dimensions, enable **Preview cutters** to inspect geometry,
   then press **OK** to perform the cut.
