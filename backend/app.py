import os
import sys
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import torch
import numpy as np
from PIL import Image, ImageFile
import cv2

# Allow PIL to open truncated PNG files without error
ImageFile.LOAD_TRUNCATED_IMAGES = True

# ----------------- Add SAM2 repo to path -----------------
sys.path.append("segment-anything-2")
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

# ----------------- Flask App -----------------
app = Flask(__name__)
CORS(app)

# ----------------- Paths -----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ORIGINAL_FOLDER = os.path.join(UPLOAD_FOLDER, "original")
EDITED_FOLDER = os.path.join(UPLOAD_FOLDER, "edited")

os.makedirs(ORIGINAL_FOLDER, exist_ok=True)
os.makedirs(EDITED_FOLDER, exist_ok=True)

MODEL_CFG = os.path.join(BASE_DIR, "configs", "sam2_hiera_b+.yaml")
MODEL_CKPT = os.path.join(BASE_DIR, "models", "sam2_hiera_base_plus.pt")

if not os.path.exists(MODEL_CFG):
    raise FileNotFoundError(f"Config file not found: {MODEL_CFG}")
if not os.path.exists(MODEL_CKPT):
    raise FileNotFoundError(f"Checkpoint file not found: {MODEL_CKPT}")

# ----------------- Load SAM2 Model -----------------
device = "cuda" if torch.cuda.is_available() else "cpu"
predictor = SAM2ImagePredictor(build_sam2(MODEL_CFG, MODEL_CKPT, device=device))

# ----------------- State -----------------
last_uploaded_path = None
last_image_np = None
click_points = []
click_labels = []
stored_masks = []  # store binary masks as NumPy arrays
image_loaded_in_predictor = False  # NEW FLAG

# ----------------- Mask Cleaning -----------------
def clean_mask(mask):
    """Binarize + small noise removal, keep shape intact."""
    mask = (mask > 0.5).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask.astype(np.float32)

# ----------------- Routes -----------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Server is running"}), 200

@app.route("/upload", methods=["POST"])
def upload_file():
    global last_uploaded_path, last_image_np, click_points, click_labels, stored_masks, image_loaded_in_predictor

    if "image" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["image"]
    save_path = os.path.join(ORIGINAL_FOLDER, file.filename)
    file.save(save_path)
    last_uploaded_path = save_path

    # Load image into numpy and predictor
    with Image.open(save_path).convert("RGB") as im:
        last_image_np = np.array(im)

    predictor.set_image(last_image_np)
    image_loaded_in_predictor = True  # Mark as loaded

    click_points, click_labels, stored_masks = [], [], []

    # Remove previous edited file safely
    edited_path = os.path.join(EDITED_FOLDER, "edited.png")
    if os.path.exists(edited_path):
        try:
            os.remove(edited_path)
        except PermissionError:
            pass

    return jsonify({"message": "Image uploaded successfully"})

@app.route("/generate_masks", methods=["POST"])
def generate_masks():
    """Add click, generate mask, store it, return mask_id."""
    global click_points, click_labels, stored_masks, image_loaded_in_predictor

    data = request.json
    x, y = data.get("x"), data.get("y")
    positive = data.get("positive", True)
    reset_selection = data.get("reset", False)

    if x is None or y is None:
        return jsonify({"error": "Missing coordinates"}), 400

    if not image_loaded_in_predictor:
        if last_image_np is None:
            return jsonify({"error": "No image loaded"}), 400
        predictor.set_image(last_image_np)
        image_loaded_in_predictor = True

    if reset_selection:
        click_points, click_labels = [], []

    click_points.append([x, y])
    click_labels.append(1 if positive else 0)

    masks, _, _ = predictor.predict(
        point_coords=np.array(click_points),
        point_labels=np.array(click_labels),
        multimask_output=False
    )

    binary_mask = clean_mask(masks[0])  # keep binary
    stored_masks.append(binary_mask)

    return jsonify({"mask_id": len(stored_masks) - 1})

@app.route("/apply_color", methods=["POST"])
def apply_color():
    """Apply chosen color to stored mask region."""
    data = request.json
    mask_id = data.get("mask_id")
    color = data.get("color")  # [R, G, B]
    alpha = float(data.get("alpha", 0.6))

    if mask_id is None or color is None:
        return jsonify({"error": "Missing mask_id or color"}), 400

    if mask_id >= len(stored_masks):
        return jsonify({"error": "Invalid mask_id"}), 400

    mask = stored_masks[mask_id]  # binary mask

    edited_path = os.path.join(EDITED_FOLDER, "edited.png")

    # Load image safely
    if os.path.exists(edited_path):
        with Image.open(edited_path).convert("RGB") as im:
            img = np.array(im, dtype=np.float32)
    else:
        with Image.open(last_uploaded_path).convert("RGB") as im:
            img = np.array(im, dtype=np.float32)

    color_layer = np.ones_like(img) * np.array(color, dtype=np.float32)

    # Blend
    img = img * (1 - mask[..., None] * alpha) + color_layer * (mask[..., None] * alpha)
    img = np.clip(img, 0, 255).astype(np.uint8)

    # Save edited image
    Image.fromarray(img).save(edited_path)

    return jsonify({"message": "Color applied successfully"})

@app.route("/download", methods=["GET"])
def download():
    """Download final edited image."""
    edited_path = os.path.join(EDITED_FOLDER, "edited.png")
    if not os.path.exists(edited_path):
        return jsonify({"error": "No edited image"}), 404
    return send_file(edited_path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
