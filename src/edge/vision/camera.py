"""Frame capture from the webcam or a video file (for the offline demo).

opencv is imported lazily. If the source is a video file, it restarts from the
beginning when the video ends (useful for a looping demo). Supports a frame
rotation (e.g. phone mounted upside down -> rotate=180).
"""
from __future__ import annotations

from typing import Union


class Camera:
    def __init__(self, source: Union[int, str], rotate: int = 0):
        # if it is a numeric string, treat it as a webcam index
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        self.source = source
        self.rotate = rotate
        self._cap = None
        self._is_file = isinstance(source, str)

    def open(self):
        import cv2  # lazy import
        self._cap = cv2.VideoCapture(self.source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self.source!r}")
        return self

    def _apply_rotation(self, frame):
        import cv2
        if self.rotate == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        if self.rotate == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        if self.rotate == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    def read(self):
        """Read a BGR frame. If it is a file and it ended, rewind and re-read."""
        import cv2
        ok, frame = self._cap.read()
        if not ok:
            if self._is_file:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
            if not ok:
                return None
        return self._apply_rotation(frame)

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
