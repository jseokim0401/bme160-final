# ------------------------------------------------------------
# Organoid Morphology Pipeline for FIJI (Python / Jython)
# ------------------------------------------------------------
#
# Purpose:
#   Measure organoid morphology from brightfield images in FIJI.
#
# This script is designed to run INSIDE FIJI, not in regular Python.
#
# What it measures:
#   - Area
#   - Perimeter
#   - Feret diameter
#   - MinFeret
#   - Shape descriptors (such as circularity)
#
# What it does:
#   1. Ask whether to process one image or a whole directory
#   2. Preprocess each image
#   3. Threshold the image into a binary mask
#   4. Clean the mask
#   5. Detect organoid-like particles
#   6. Measure morphology
#   7. Save the filename into the Results table
#
# Run in FIJI:
#   Plugins -> New -> Script
#   Language -> Python
#
# ------------------------------------------------------------

# Import ImageJ / FIJI classes
from ij import IJ, WindowManager
from ij.gui import GenericDialog
from ij.io import DirectoryChooser
from ij.measure import ResultsTable
import os


# ------------------------------------------------------------
# 1. Tell ImageJ which measurements to collect
# ------------------------------------------------------------
#
# "Set Measurements..." controls which columns appear in the
# Results table after Analyze Particles is run.
#
# area        = number of pixels inside the segmented object
# perimeter   = length of the outer boundary
# feret's     = longest caliper diameter across the object
# shape       = includes shape descriptors like circularity
# redirect=None = measure directly on this image
# decimal=3   = show 3 decimal places in results
#
IJ.run(
    "Set Measurements...",
    "area perimeter feret's shape redirect=None decimal=3"
)

# Get the main FIJI Results table object so we can add values later
rt = ResultsTable.getResultsTable()


# ------------------------------------------------------------
# 2. Create a user dialog
# ------------------------------------------------------------
#
# This pop-up lets the user choose:
#   - process current image OR all images in a directory
#   - whether to bring the Results window to the front
#   - minimum allowed particle size
#   - background subtraction radius
#   - threshold method
#   - whether objects are light or dark
#   - whether to fill holes and smooth the mask
#
gd = GenericDialog("Organoid Morphology Pipeline")

# Ask whether to process one image or a folder of images
gd.addChoice("Source:", ["Current Image", "Directory"], "Current Image")

# Ask whether to bring Results table forward at the end
gd.addCheckbox("Show Results immediately?", True)

# Minimum particle area allowed in Analyze Particles
# This helps remove tiny dust specks / noise
gd.addNumericField("Minimum particle size (pixels^2):", 10000, 0)

# Radius used for rolling-ball background subtraction
# Larger values remove broad background gradients
gd.addNumericField("Background subtraction radius:", 150, 0)

# Choose the thresholding algorithm
gd.addChoice("Threshold method:", ["Default", "Otsu", "Triangle", "Moments"], "Default")

# Choose whether organoids are treated as lighter or darker than background
gd.addChoice("Object type:", ["Light objects", "Dark objects"], "Light objects")

# Decide whether internal holes should be filled in the binary mask
gd.addCheckbox("Fill holes?", True)

# Decide whether to smooth the mask with Open + Close
gd.addCheckbox("Smooth mask?", True)

# Show the dialog to the user
gd.showDialog()

# If the user pressed Cancel, stop the script
if gd.wasCanceled():
    raise SystemExit

# Read the values the user entered in the dialog
mode = gd.getNextChoice()
showResults = gd.getNextBoolean()
min_size = int(gd.getNextNumber())
bg_radius = int(gd.getNextNumber())
threshold_method = gd.getNextChoice()
object_type = gd.getNextChoice()
fill_holes = gd.getNextBoolean()
smooth_mask = gd.getNextBoolean()


# ------------------------------------------------------------
# 3. Helper function: add filename to new result rows
# ------------------------------------------------------------
#
# Why do we need this?
#   Analyze Particles adds measurement rows to the Results table,
#   but it does not automatically store the image filename in each row.
#
# So:
#   - we remember how many rows existed BEFORE measuring
#   - after measuring, we loop through the new rows
#   - we write the filename into a custom "Filename" column
#
def add_filename_to_new_rows(filename, start_row):
    """
    Add the image filename to all newly created rows in the Results table.

    Parameters
    ----------
    filename : str
        Name of the image file currently being processed.
    start_row : int
        Row index in the Results table before Analyze Particles was run.
        Any row from start_row to the end belongs to the current image.
    """
    end_row = rt.size()
    for row in range(start_row, end_row):
        rt.setValue("Filename", row, filename)


# ------------------------------------------------------------
# 4. Main function: process one image
# ------------------------------------------------------------
#
# This function does the actual morphology workflow.
#
# Steps:
#   1. Duplicate image so original is preserved
#   2. Convert to 8-bit grayscale
#   3. Subtract uneven background
#   4. Reduce noise with median filter
#   5. Threshold the image
#   6. Convert threshold to binary mask
#   7. Fill holes / smooth mask if requested
#   8. Analyze particles
#   9. Add filename to result rows
#   10. Close working copy
#
def process_image(imp, filename):
    """
    Process one FIJI image and measure organoid morphology.

    Parameters
    ----------
    imp : ImagePlus
        The currently opened FIJI image object.
    filename : str
        The image filename, used for labeling rows in the Results table.
    """

    # Record the number of rows already in Results before this image is measured
    start_row = rt.size()

    # Make a duplicate so the original image is not permanently changed
    work = imp.duplicate()
    work.setTitle("working_" + filename)
    work.show()

    # --------------------------------------------------------
    # Step 1: Convert image to 8-bit grayscale
    # --------------------------------------------------------
    #
    # Thresholding works most simply on grayscale images.
    # If the image is RGB (24-bit), convert it to 8-bit.
    # If it is some other bit depth, also convert to 8-bit
    # for consistency in processing.
    #
    if work.getBitDepth() == 24:
        IJ.run(work, "8-bit", "")
    elif work.getBitDepth() != 8:
        IJ.run(work, "8-bit", "")

    # --------------------------------------------------------
    # Step 2: Background subtraction
    # --------------------------------------------------------
    #
    # Brightfield images often have uneven illumination.
    # "Subtract Background..." reduces slow intensity gradients
    # so thresholding is based more on the organoid itself.
    #
    # rolling=bg_radius means:
    #   use a rolling-ball radius of bg_radius pixels
    #
    # "light" means:
    #   background is treated as relatively light
    #
    IJ.run(work, "Subtract Background...", "rolling=%d light" % bg_radius)

    # --------------------------------------------------------
    # Step 3: Reduce small speckle noise
    # --------------------------------------------------------
    #
    # A median filter smooths tiny noisy spots while preserving
    # edges better than a simple blur.
    #
    IJ.run(work, "Median...", "radius=2")
    IJ.run(work, "Gaussian Blur...", "sigma=3")

    # --------------------------------------------------------
    # Step 4: Threshold the image
    # --------------------------------------------------------
    #
    # Thresholding converts a grayscale image into foreground
    # and background.
    #
    # Example:
    #   "Otsu light" means use Otsu thresholding assuming
    #   the objects are brighter than the background.
    #
    if object_type == "Light objects":
        IJ.setAutoThreshold(work, threshold_method + " light")
    else:
        IJ.setAutoThreshold(work, threshold_method + " dark")

    # --------------------------------------------------------
    # Step 5: Convert threshold to binary mask
    # --------------------------------------------------------
    #
    # After thresholding, "Convert to Mask" creates a black/white image:
    #   white = detected object
    #   black = background
    #
    IJ.run(work, "Convert to Mask", "")

    # --------------------------------------------------------
    # Step 6: Optional cleanup of the binary mask
    # --------------------------------------------------------

    # Fill internal dark holes inside white organoid masks
    # This is important for area measurement so the organoid
    # is treated as one filled object rather than a shell.
    if fill_holes:
        IJ.run(work, "Fill Holes", "")

    # Smooth the mask using morphological opening and closing
    #
    # Open:
    #   removes tiny bright specks and small protrusions
    #
    # Close:
    #   fills small gaps and smooths the outer contour
    #
    if smooth_mask:
        IJ.run(work, "Open", "")
        IJ.run(work, "Close-", "")

    # Optional watershed:
    # Uncomment this if touching organoids need to be split apart.
    #
    # IJ.run(work, "Watershed", "")

    # --------------------------------------------------------
    # Step 7: Analyze particles and measure morphology
    # --------------------------------------------------------
    #
    # Analyze Particles finds connected white objects in the binary mask.
    #
    # size=min_size-Infinity
    #   keep only particles at least min_size pixels^2 in area
    #
    # show=Overlay
    #   draw the outlines on the image
    #
    # display
    #   send measurements to Results table
    #
    # exclude
    #   exclude particles touching the image border
    #
    # summarize
    #   create a Summary table
    #
    IJ.run(
        work,
        "Analyze Particles...",
         "size=10000-Infinity show=Overlay display exclude summarize"
    )

    # --------------------------------------------------------
    # Step 8: Write filename into all rows created by this image
    # --------------------------------------------------------
    add_filename_to_new_rows(filename, start_row)
''''
    # --------------------------------------------------------
    # Step 9: Close working copy
    # --------------------------------------------------------
    #
    # work.changes = False prevents FIJI from asking whether
    # to save changes when closing the image
    #
    work.changes = False
    work.close()
'''

# ------------------------------------------------------------
# 5. Run script on one image or a full directory
# ------------------------------------------------------------

# ---------- Case A: current image ----------
if mode == "Current Image":
    imp = WindowManager.getCurrentImage()

    # Stop if no image is open
    if imp is None:
        IJ.showMessage("Error", "No image is currently open.")
        raise SystemExit

    # Process the active image
    process_image(imp, imp.getTitle())


# ---------- Case B: directory of images ----------
else:
    dc = DirectoryChooser("Choose a directory of images")
    dir_path = dc.getDirectory()

    # Stop if the user cancels directory selection
    if dir_path is None:
        raise SystemExit

    # Clear old results so this run starts fresh
    IJ.run("Clear Results")
    rt = ResultsTable.getResultsTable()

    # Allowed image file extensions
    valid_ext = (".tif", ".tiff", ".jpg", ".jpeg", ".png")

    # Loop through each file in the selected folder
    for filename in os.listdir(dir_path):
        if filename.lower().endswith(valid_ext):

            # Build full file path
            full_path = os.path.join(dir_path, filename)

            # Open the image
            imp = IJ.openImage(full_path)

            # Only process if the image opened successfully
            if imp is not None:
                imp.show()
                process_image(imp, filename)

                # Close original image after processing
                imp.changes = False
                imp.close()


# ------------------------------------------------------------
# 6. Show the results table
# ------------------------------------------------------------
rt.show("Results")

# Bring Results table to front if user requested it
if showResults:
    IJ.selectWindow("Results")
