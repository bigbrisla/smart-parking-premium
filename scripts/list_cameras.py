"""Probe the available webcam indices and save one snapshot from each.

Useful to find which index corresponds to the iPhone (Iriun/EpocCam) or the right
webcam. Look at the snapshots saved in data/cam_<i>.jpg.

Usage:
    python scripts/list_cameras.py
    python scripts/list_cameras.py --max 6
"""
import _bootstrap  # noqa: F401

import argparse


def main():
    import cv2

    parser = argparse.ArgumentParser(description="List the available webcams")
    parser.add_argument("--max", type=int, default=4, help="indices to try: 0..max-1")
    args = parser.parse_args()

    found = []
    for i in range(args.max):
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            print(f"  index {i}: not available")
            cap.release()
            continue
        ok, frame = cap.read()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            path = f"data/cam_{i}.jpg"
            cv2.imwrite(path, frame)
            print(f"  index {i}: OK  {w}x{h}  -> snapshot saved to {path}")
            found.append(i)
        else:
            print(f"  index {i}: opened but no frame")
        cap.release()

    if not found:
        print("\nNo camera readable by OpenCV.")
        print("If Iriun does not appear, it is the limit of virtual webcams on macOS.")
    else:
        print(f"\nUsable indices: {found}. Open the snapshots and see which one frames the mockup.")


if __name__ == "__main__":
    main()
