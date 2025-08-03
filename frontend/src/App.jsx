import { useState, useEffect } from "react";

export default function App() {
  const [image, setImage] = useState(null);
  const [file, setFile] = useState(null);
  const [selectedMaskIds, setSelectedMaskIds] = useState([]);
  const [color, setColor] = useState("#ff0000");
  const [alpha, setAlpha] = useState(0.6);
  const [editedImage, setEditedImage] = useState(null);

  const bgImages = ["/image1.jpg", "/image2.jpg", "/image3.jpg"];
  const [bgIndex, setBgIndex] = useState(0);

  // Background slideshow
  useEffect(() => {
    const interval = setInterval(() => {
      setBgIndex((prev) => (prev + 1) % bgImages.length);
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Image upload preview
  function handleImageUpload(e) {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setImage(URL.createObjectURL(selectedFile));
      setEditedImage(null);
      setSelectedMaskIds([]);
    }
  }

  // Upload to backend
  async function handleSubmit() {
    if (!file) return alert("Please upload an image first.");
    const formData = new FormData();
    formData.append("image", file);

    try {
      const res = await fetch("http://127.0.0.1:5000/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      alert(data.message);
    } catch (error) {
      console.error("Upload failed", error);
    }
  }

  // Click to generate mask ID
  async function handleImageClick(e) {
    if (!image && !editedImage) return;

    const rect = e.target.getBoundingClientRect();
    const x = Math.round(e.clientX - rect.left);
    const y = Math.round(e.clientY - rect.top);

    try {
      const res = await fetch("http://127.0.0.1:5000/generate_masks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ x, y, positive: true }),
      });

      const data = await res.json();
      if (data.mask_id !== undefined) {
        setSelectedMaskIds((prev) => [...prev, data.mask_id]);
      }
    } catch (error) {
      console.error("Mask generation failed", error);
    }
  }

  // Apply color
  async function handleApplyColor() {
    if (!selectedMaskIds.length) return alert("Select an area first!");
    const rgb = hexToRgb(color);

    for (let maskId of selectedMaskIds) {
      try {
        await fetch("http://127.0.0.1:5000/apply_color", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mask_id: maskId, color: rgb, alpha }),
        });
      } catch (error) {
        console.error("Color apply failed", error);
      }
    }

    // Fetch updated image
    const imgRes = await fetch("http://127.0.0.1:5000/download");
    const blob = await imgRes.blob();
    setEditedImage(URL.createObjectURL(blob));
  }

  // Download final image
  async function handleDownload() {
    const res = await fetch("http://127.0.0.1:5000/download");
    if (res.status !== 200) return alert("No edited image found!");
    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "colored_house.png";
    link.click();
  }

  function hexToRgb(hex) {
    const bigint = parseInt(hex.slice(1), 16);
    return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center">
      {/* Background slideshow */}
      <div
        className="absolute top-0 left-0 w-full h-full bg-cover bg-center transition-all duration-1000 ease-in-out"
        style={{ backgroundImage: `url(${bgImages[bgIndex]})`, zIndex: -2 }}
      ></div>
      <div className="absolute top-0 left-0 w-full h-full bg-black bg-opacity-40 backdrop-blur-sm z-[-1]"></div>

      {/* UI */}
      <div className="bg-white bg-opacity-90 p-6 rounded-lg shadow-lg space-y-4 w-[90%] max-w-3xl">
        <h1 className="text-2xl font-bold text-center">🏠 Building Wall Colorizer</h1>

        {/* Upload */}
        <input type="file" accept="image/*" onChange={handleImageUpload} />

        {/* Image */}
        { (editedImage || image) && (
          <div
            className="relative flex justify-center"
            onContextMenu={(e) => e.preventDefault()}
          >
            <img
              src={editedImage || image}
              alt="Preview"
              className="max-w-lg rounded shadow-lg cursor-crosshair"
              onClick={handleImageClick}
            />
          </div>
        )}

        {/* Buttons */}
        <button
          onClick={handleSubmit}
          className="px-4 py-2 bg-blue-500 text-white rounded w-full"
        >
          Upload to Server
        </button>

        {/* Color picker */}
        <div className="flex items-center space-x-2">
          <label>🎨 Color:</label>
          <input type="color" value={color} onChange={(e) => setColor(e.target.value)} />
        </div>

        {/* Transparency */}
        <div className="flex items-center space-x-2">
          <label>Opacity: {alpha}</label>
          <input
            type="range"
            min="0.1"
            max="1"
            step="0.05"
            value={alpha}
            onChange={(e) => setAlpha(parseFloat(e.target.value))}
          />
        </div>

        {/* Apply & Download */}
        <button
          onClick={handleApplyColor}
          className="px-4 py-2 bg-green-500 text-white rounded w-full"
        >
          Apply Color
        </button>
        <button
          onClick={handleDownload}
          className="px-4 py-2 bg-orange-500 text-white rounded w-full"
        >
          Download Image
        </button>
      </div>
    </div>
  );
}
