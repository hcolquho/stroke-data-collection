"""
Walker-Gait: ArUco Marker Generator
=====================================
Generates printable ArUco marker images for the 10MWT timing lines.

    ID 0  →  2m_marker.png   (place at 2m  — 10MWT timing start)
    ID 1  →  12m_marker.png  (place at 12m — 10MWT timing end)

Prints at 200x200 px by default — scale up when printing for visibility.
Recommended print size: ~15x15 cm (A5 or larger). Laminate if possible.

Usage:
    python scripts/generate_aruco_markers.py
    python scripts/generate_aruco_markers.py --output-dir markers/ --size 400
"""

import argparse
from pathlib import Path

import cv2


ARUCO_DICT_ID = cv2.aruco.DICT_4X4_50

MARKERS = [
    (0, "2m_marker",  "Place at 2m  line — 10MWT timing START"),
    (1, "12m_marker", "Place at 12m line — 10MWT timing END"),
]


def generate_markers(output_dir: Path, size_px: int = 200):
    output_dir.mkdir(parents=True, exist_ok=True)
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)

    for marker_id, filename, description in MARKERS:
        # Generate marker image (size - 2*border gives inner marker region)
        marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, size_px)

        # Add white border and label for easier identification when printed
        border = 30
        canvas_h = size_px + border * 2 + 40  # extra 40px for text
        canvas_w = size_px + border * 2
        canvas = 255 * __import__("numpy").ones((canvas_h, canvas_w), dtype="uint8")

        # Place marker
        canvas[border:border + size_px, border:border + size_px] = marker_img

        # Label
        label = f"ID {marker_id} | {filename}"
        cv2.putText(canvas, label,
                    (border, border + size_px + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, 0, 1)

        out_path = output_dir / f"{filename}.png"
        cv2.imwrite(str(out_path), canvas)
        print(f"Saved: {out_path}  ({description})")

    print(f"\nPrint at 15x15 cm or larger. Laminate and tape flat to the floor.")
    print(f"ID 0 → 2m line, ID 1 → 12m line.")


def main():
    parser = argparse.ArgumentParser(description="Generate ArUco floor markers")
    parser.add_argument("--output-dir", type=str, default="markers",
                        help="Directory to save marker images (default: markers/)")
    parser.add_argument("--size", type=int, default=300,
                        help="Marker image size in pixels (default: 300)")
    args = parser.parse_args()

    generate_markers(Path(args.output_dir), args.size)


if __name__ == "__main__":
    main()
