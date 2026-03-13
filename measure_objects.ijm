/* bme160-final

/*
 * Measure Objects Script
 * 
 * This script measures the following for objects in an image:
 * - Surface Area (Area)
 * - Circumference (Perimeter)
 * - Diameter (Feret's Diameter)
 * 
 * Usage:
 * 1. Run the script.
 * 2. Choose to process the "Current Image" or a "Directory" of images.
 * 
 * Author: Antigravity, JaffaHunter
 */

macro "Measure Objects" {
    // 1. Setup Measurements
    // We need Area, Perimeter, and Feret's Diameter (which includes max caliper diameter)
    run("Set Measurements...", "area perimeter feret's redirect=None decimal=3");

    // 2. Dialog to choose mode
    Dialog.create("Measurement Options");
    Dialog.addMessage("Select Processing Mode:");
    Dialog.addChoice("Source:", newArray("Current Image", "Directory"));
    Dialog.addCheckbox("Show Results immediately?", true);
    Dialog.show();

    mode = Dialog.getChoice();
    showResults = Dialog.getCheckbox();

    if (mode == "Current Image") {
        if (nImages == 0) {
            showMessage("Error", "No image is currently open!");
            return;
        }
        processImage();
    } else {
        dir = getDirectory("Choose a Directory containing images");
        if (dir == "") return; // User cancelled
        
        list = getFileList(dir);
        setBatchMode(true); // Run in background for speed
        
        for (i = 0; i < list.length; i++) {
            if (endsWith(list[i], ".tif") || endsWith(list[i], ".jpg") || endsWith(list[i], ".png")) {
                open(dir + list[i]);
                processImage();
                close();
            }
        }
        setBatchMode(false);
    }
    
    if (showResults) {
        selectWindow("Results");
    }
}

function processImage() {
    // Get image title for results
    title = getTitle();
    run("Duplicate...", "title=working_copy");
    selectWindow("working_copy"); // Work on a copy to avoid modifying original if possible, or just undo later
    // For simplicity in macro, we work on active image.
    
    // 3. Pre-processing
    // Always convert to 8-bit (grayscale) for thresholding 
    run("8-bit");                       
    
    // 4. Thresholding
    // Auto-threshold to separate objects from background
    // "dark" means dark objects on light background. If your objects are light, uncheck this in UI manually or we can try to detect.
    // For general purpose, we usually assume 'Auto' works.
    
    //-------> changing from dark to light - Jacob
    // setAutoThreshold("Default light");
   
    // Allow user to use preset thresholding or manually set personally. (Jenni)
    threshMode = getBoolean("Use automatic thresholding?\n'Yes' = Auto (Otsu)\n'No' = Set Manually");
    if (threshMode) {
    	// Otsu works better than default for Brightfield images
    	// No "dark" suffix since these organoids are dark against light background. 
    	setAutoThreshold("Otsu");
    } else {
    	run("Threshold...");
    	waitForUser("Adjust threshold, click 'Apply', then press 'OK' to continue.");
    }
    
    // Converting to binary mask so Analyze Image detects objects 
    run("Convert to Mask");
	run("Fill Holes");   // fill organoid interior -> more accurate area measurement
	
    // 5. Analyze Particles
    // size=0-Infinity: measure everything
    // circularity=0.00-1.00: explicit shape not filtered
    // show=Overlay: Visualizes what was measured
    // display: Shows results in the Results table
    // exclude: exlude particles touching edges (optional, standard good practice)
    // clear: DO NOT clear results if batch processing, so we accumulate. 
    // But if single image, maybe we want to clear? Let's not clear to be safe, user can clear.
    
    //-----------> changed sized particles (e.g., 2000, 10000, 50000 depending on image scale) - Jacob
    run("Analyze Particles...", "size=5000-Infinity show=Overlay display exclude include summarize");
    
    // Reset threshold to clean up view
    resetThreshold();
}
