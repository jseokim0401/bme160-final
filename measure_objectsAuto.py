# Measure Objects Script (Python version for FIJI)
# Measures:
# - Area
# - Perimeter
# - Feret Diameter

from ij import IJ, ImagePlus, WindowManager
from ij.gui import GenericDialog
from ij.io import DirectoryChooser
from ij.plugin.frame import RoiManager
import os

# ----------------------------
# 1. Setup measurements
# ----------------------------
IJ.run("Set Measurements...", "area perimeter feret's redirect=None decimal=3")

# ----------------------------
# 2. Dialog
# ----------------------------
gd = GenericDialog("Measurement Options")
gd.addChoice("Source:", ["Current Image", "Directory"], "Current Image")
gd.addCheckbox("Show Results immediately?", True)
gd.showDialog()

if gd.wasCanceled():
    exit()

mode = gd.getNextChoice()
showResults = gd.getNextBoolean()


# ----------------------------
# Processing Function
# ----------------------------
def process_image(imp):

    # Convert to 8-bit if RGB
    if imp.getBitDepth() == 24:
        IJ.run(imp, "8-bit", "")

    # Auto-threshold (light objects)
    IJ.run(imp, "Auto Threshold", "method=Default white")

    # Optional: Convert to mask explicitly
    IJ.run(imp, "Convert to Mask", "")

    # Analyze Particles
    IJ.run(imp, "Analyze Particles...",
           "size=10000-Infinity show=Overlay display exclude include summarize")

    IJ.run(imp, "Select None", "")


# ----------------------------
# 3. Mode selection
# ----------------------------
if mode == "Current Image":

    imp = WindowManager.getCurrentImage()
    if imp is None:
        IJ.showMessage("Error", "No image is currently open!")
        exit()

    process_image(imp)

else:

    dc = DirectoryChooser("Choose a Directory containing images")
    dir_path = dc.getDirectory()
    if dir_path is None:
        exit()

    IJ.run("Close All")
    IJ.run("Clear Results")

    for filename in os.listdir(dir_path):

        if filename.lower().endswith((".tif", ".jpg", ".png")):

            full_path = os.path.join(dir_path, filename)
            imp = IJ.openImage(full_path)
            imp.show()

            process_image(imp)

            imp.close()

# Bring Results window forward
if showResults:
    IJ.selectWindow("Results")
