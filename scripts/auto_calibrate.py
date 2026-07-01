"""AUTOMATIC slot calibration via contour detection (OpenCV).

Exploits the fact that the mockup is made of black rectangles on white paper: it
detects the cells from a photo of the EMPTY parking, orders them, assigns the names
P01.., estimates the central lane and prints the YAML block to paste into the
config. It also saves an annotated preview to check.

Usage:
    python scripts/auto_calibrate.py --image empty_photo.jpg
    python scripts/auto_calibrate.py --webcam 0          # 'c' calibrate, 'q' quit

Ordering options (if the numbers do not match the mockup):
    --layout rows|columns   slots on horizontal rows or vertical columns
    --columns rtl|ltr       column / within-row order
    --rows ttb|btt          row / within-column order
"""
import _bootstrap  # noqa: F401

import argparse


def detect_cells(frame, min_area_frac=0.005, max_area_frac=0.2):
    """Return a list of boxes [x1,y1,x2,y2] of the detected rectangles."""
    import cv2
    import numpy as np

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 31, 10)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(th, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    H, W = gray.shape
    area_img = H * W
    boxes = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a < area_img * min_area_frac or a > area_img * max_area_frac:
            continue
        peri = cv2.arcLength(c, True)
        ap = cv2.approxPolyDP(c, 0.04 * peri, True)
        if len(ap) == 4 and cv2.isContourConvex(ap):
            x, y, w, h = cv2.boundingRect(ap)
            if 0.3 < w / float(h) < 4.0:
                boxes.append([x, y, x + w, y + h])
    return _remove_containers(_dedup(boxes))


def _remove_containers(boxes):
    """Discard the boxes that enclose other boxes (e.g. the outer border of a row)."""
    centers = [((b[0] + b[2]) // 2, (b[1] + b[3]) // 2) for b in boxes]

    def contains(a, c):
        return a[0] <= c[0] <= a[2] and a[1] <= c[1] <= a[3]

    kept = []
    for i, a in enumerate(boxes):
        inside = sum(1 for j, c in enumerate(centers) if j != i and contains(a, c))
        if inside >= 2:            # encloses 2+ cells -> it is a container
            continue
        kept.append(a)
    return kept


def _iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(area_a + area_b - inter)


def _dedup(boxes, iou_thr=0.5):
    """Remove overlapping boxes (outer border + inner of the same cell)."""
    kept = []
    for b in sorted(boxes, key=lambda z: (z[2] - z[0]) * (z[3] - z[1]), reverse=True):
        if all(_iou(b, k) < iou_thr for k in kept):
            kept.append(b)
    return kept


def _cx(b):
    return (b[0] + b[2]) / 2


def _cy(b):
    return (b[1] + b[3]) / 2


def _cluster_1d(boxes, key, gap):
    """Group the boxes by ordering them on an axis: new group if the jump > gap."""
    s = sorted(boxes, key=key)
    groups = [[s[0]]]
    for b in s[1:]:
        if key(b) - key(groups[-1][-1]) > gap:
            groups.append([b])
        else:
            groups[-1].append(b)
    return groups


def order_and_name(boxes, layout="columns", columns="rtl", rows="ttb", prefix="P"):
    """Assign the names P01, P02, ... following the layout (rows or columns).

    - layout=rows:    group by rows (y axis); order the rows (rows) and, within
                      each row, left/right (columns).
    - layout=columns: group by columns (x axis); order the columns (columns) and,
                      within each column, top/bottom (rows).
    """
    if not boxes:
        return []
    med_w = sorted(b[2] - b[0] for b in boxes)[len(boxes) // 2]
    med_h = sorted(b[3] - b[1] for b in boxes)[len(boxes) // 2]

    named, i = [], 1
    if layout == "rows":
        groups = _cluster_1d(boxes, _cy, med_h * 0.5)
        if rows == "btt":
            groups = groups[::-1]
        for g in groups:
            for b in sorted(g, key=_cx, reverse=(columns == "rtl")):
                named.append((f"{prefix}{i:02d}", b)); i += 1
    else:
        groups = _cluster_1d(boxes, _cx, med_w * 0.5)
        if columns == "rtl":
            groups = groups[::-1]
        for g in groups:
            for b in sorted(g, key=_cy, reverse=(rows == "btt")):
                named.append((f"{prefix}{i:02d}", b)); i += 1
    return named


def estimate_road(boxes, layout="columns"):
    """Estimate the central lane as the gap between the two blocks of slots.

    layout=columns -> vertical lane (gap between left and right column).
    layout=rows    -> horizontal lane (gap between top and bottom row).
    """
    if len(boxes) < 2:
        return None
    if layout == "rows":
        mid = sorted(_cy(b) for b in boxes)[len(boxes) // 2]
        top = [b for b in boxes if _cy(b) < mid]
        bot = [b for b in boxes if _cy(b) >= mid]
        if not top or not bot:
            return None
        y1 = max(b[3] for b in top)
        y2 = min(b[1] for b in bot)
        x1 = min(b[0] for b in boxes)
        x2 = max(b[2] for b in boxes)
        return [x1, y1, x2, y2] if y2 > y1 else None
    mid = sorted(_cx(b) for b in boxes)[len(boxes) // 2]
    left = [b for b in boxes if _cx(b) < mid]
    right = [b for b in boxes if _cx(b) >= mid]
    if not left or not right:
        return None
    x1 = max(b[2] for b in left)
    x2 = min(b[0] for b in right)
    y1 = min(b[1] for b in boxes)
    y2 = max(b[3] for b in boxes)
    return [x1, y1, x2, y2] if x2 > x1 else None


def emit(named, road, out_preview, frame, layout="columns"):
    import cv2

    barrier_edge = "left" if layout == "rows" else "top"
    print("\n# --- paste this into config/granreno.yaml ---")
    print("slots:")
    for name, b in named:
        print(f"  - {{ id: {name}, roi: [{b[0]}, {b[1]}, {b[2]}, {b[3]}] }}")
    if road:
        print("approach:")
        print("  enabled: true")
        print(f"  road_roi: [{road[0]}, {road[1]}, {road[2]}, {road[3]}]")
        print(f"  barrier_edge: {barrier_edge}   # side near the barrier; adjust if needed")
        print("  length_m: 300")
    print(f"\n# slots detected: {len(named)}")

    for name, b in named:
        cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (0, 200, 0), 2)
        cv2.putText(frame, name, (b[0] + 4, b[1] + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
    if road:
        cv2.rectangle(frame, (road[0], road[1]), (road[2], road[3]), (255, 150, 0), 2)
        cv2.putText(frame, "lane", (road[0] + 4, road[3] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 150, 0), 2)
    cv2.imwrite(out_preview, frame)
    print(f"# preview saved to: {out_preview}")


def run_on_frame(frame, args):
    boxes = detect_cells(frame, args.min_area, args.max_area)
    named = order_and_name(boxes, args.layout, args.columns, args.rows, args.prefix)
    road = estimate_road(boxes, args.layout)
    emit(named, road, args.out, frame, args.layout)   # emit draws on `frame`
    return frame


def main():
    import cv2

    parser = argparse.ArgumentParser(description="Automatic slot calibration")
    parser.add_argument("--image")
    parser.add_argument("--webcam", type=int)
    parser.add_argument("--layout", choices=["columns", "rows"], default="columns",
                        help="rows = slots on horizontal rows; columns = vertical columns")
    parser.add_argument("--columns", choices=["rtl", "ltr"], default="rtl")
    parser.add_argument("--rows", choices=["ttb", "btt"], default="ttb")
    parser.add_argument("--prefix", default="P")
    parser.add_argument("--min-area", type=float, default=0.005, dest="min_area")
    parser.add_argument("--max-area", type=float, default=0.2, dest="max_area")
    parser.add_argument("--out", default="auto_calib_preview.jpg")
    args = parser.parse_args()

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            raise SystemExit(f"Image not found: {args.image}")
        run_on_frame(frame, args)
    elif args.webcam is not None:
        cap = cv2.VideoCapture(args.webcam)
        print("Frame the EMPTY mockup. 'c' = calibrate, 'q' = quit.")
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            cv2.imshow("auto-calibration ('c' calibrate, 'q' quit)", frame)
            key = cv2.waitKey(20) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                annotated = run_on_frame(frame.copy(), args)
                cv2.imshow("calibration preview", annotated)
                print(">> review the preview; press 'c' again to retry, 'q' to quit.")
        cap.release()
        cv2.destroyAllWindows()
    else:
        raise SystemExit("Specify --image PATH or --webcam INDEX")


if __name__ == "__main__":
    main()
