"""DETECTION SPIKE (risk #1): check whether YOLOv11 recognizes the mockup toy cars
BEFORE building on top of it. To be run on day 1.

Usage:
    # on a photo of the mockup
    python scripts/spike_detect.py --image mockup_photo.jpg
    # live from the webcam (press 'q' to quit)
    python scripts/spike_detect.py --webcam 0

Prints how many detections it finds and with what confidence, and saves/shows the
annotated image. If the toy cars are not seen as car/bus/truck, we consider plan B
(occupancy via classic CV) or a light fine-tuning.
"""
import _bootstrap  # noqa: F401

import argparse

from src.edge.vision.detector import YoloDetector

# all the COCO classes that could "trigger" on a toy car
CANDIDATE_CLASSES = {2: "car", 5: "bus", 7: "truck", 3: "motorcycle"}


def annotate(frame, dets):
    import cv2
    for d in dets:
        x1, y1, x2, y2 = d.xyxy
        label = f"{CANDIDATE_CLASSES.get(d.cls_id, d.cls_id)} {d.conf:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        cv2.putText(frame, label, (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 0), 2)
    return frame


def main():
    import cv2

    parser = argparse.ArgumentParser(description="Spike: test YOLO detection on the mockup")
    parser.add_argument("--image", help="path to a photo of the mockup")
    parser.add_argument("--webcam", type=int, help="webcam index for the live test")
    parser.add_argument("--conf", type=float, default=0.15, help="low threshold to explore")
    parser.add_argument("--out", default="spike_out.jpg")
    args = parser.parse_args()

    # accept all candidate classes to understand WHAT the model sees
    detector = YoloDetector(conf=args.conf, vehicle_classes=list(CANDIDATE_CLASSES))

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            raise SystemExit(f"Image not found: {args.image}")
        dets = detector.detect(frame)
        print(f"\n{len(dets)} detections (conf>={args.conf}):")
        for d in dets:
            print(f"  - {CANDIDATE_CLASSES.get(d.cls_id, d.cls_id):12s} conf={d.conf:.2f} bbox={d.xyxy}")
        cv2.imwrite(args.out, annotate(frame, dets))
        print(f"\nAnnotated image saved to: {args.out}")
    elif args.webcam is not None:
        cap = cv2.VideoCapture(args.webcam)
        print("Press 'q' to quit.")
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            dets = detector.detect(frame)
            cv2.imshow("YOLO spike (q to quit)", annotate(frame, dets))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        cap.release()
        cv2.destroyAllWindows()
    else:
        raise SystemExit("Specify --image PATH or --webcam INDEX")


if __name__ == "__main__":
    main()
