# sam2_segmentation.py
from sam2.build_sam import build_sam2
import torch
from PIL import Image
import numpy as np

# Load SAM-2 model once when the file is imported
sam2_model = build_sam2("models/sam2_hiera_base_plus.pt", device="cpu")

def segment_image(image_path):
    """
    Segments the given image and returns the generated masks.
    """
    image = Image.open(image_path).convert("RGB")
    image_np = np.array(image)

    # Run segmentation (API might vary depending on SAM-2 version)
    masks = sam2_model.predict(image_np)

    return masks
