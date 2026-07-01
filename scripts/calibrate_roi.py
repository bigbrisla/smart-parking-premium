"""Slot ROI calibration tool.

Shows a frame (webcam or image), lets you draw the slot rectangles with the mouse
and prints the 'slots:' YAML block to paste into the config.

Usage:
    python scripts/calibrate_roi.py --webcam 0
    python scripts/calibrate_roi.py --image mockup_photo.jpg

Controls:
    - drag with the mouse to draw a slot (auto-named A1, A2, ...)
    - 'z' undo the last slot
    - 's' print the YAML and save a preview (rois_preview.jpg)
    - 'q' quit
"""
import _bootstrap  # noqa: F401

import argparse

rois: list[tuple[int, int, int, int]] = []
_drag = {"start": None, "cur": None}


def main():
    import cv2

    parser = argparse.ArgumentParser(description="Slot ROI calibration")
    parser.add_argument("--webcam", type=int)
    parser.add_argument("--image")
    parser.add_argument("--prefix", default="P", help="prefix for the slot names")
    args = parser.parse_args()

    if args.image:
        base = cv2.imread(args.image)
        if base is None:
            raise SystemExit(f"Image not found: {args.image}")
        cap = None
    elif args.webcam is not None:
        cap = cv2.VideoCapture(args.webcam)
        base = None
    else:
        raise SystemExit("Specify --webcam INDEX or --image PATH")

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            _drag["start"] = (x, y); _drag["cur"] = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and _drag["start"]:
            _drag["cur"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and _drag["start"]:
            x1, y1 = _drag["start"]; x2, y2 = (x, y)
            rois.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
            _drag["start"] = None; _drag["cur"] = None

    win = "ROI calibration (z=undo, s=save, q=quit)"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)

    def print_yaml():
        print("\nslots:")
        for i, (x1, y1, x2, y2) in enumerate(rois, 1):
            print(f"  - {{ id: {args.prefix}{i:02d}, roi: [{x1}, {y1}, {x2}, {y2}] }}")
        print()

    while True:
        frame = base.copy() if base is not None else None
        if cap is not None:
            ok, frame = cap.read()
            if not ok:
                break
        for i, (x1, y1, x2, y2) in enumerate(rois, 1):
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
            cv2.putText(frame, f"{args.prefix}{i:02d}", (x1 + 4, y1 + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        if _drag["start"] and _drag["cur"]:
            cv2.rectangle(frame, _drag["start"], _drag["cur"], (0, 200, 200), 1)

        cv2.imshow(win, frame)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("z") and rois:
            rois.pop()
        elif key == ord("s"):
            print_yaml()
            cv2.imwrite("rois_preview.jpg", frame)
            print("Preview saved to: rois_preview.jpg")

    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    print_yaml()


if __name__ == "__main__":
    main()
