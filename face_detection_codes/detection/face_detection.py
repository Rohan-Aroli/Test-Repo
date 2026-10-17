import cv2
import mediapipe as mp

import sys



class FaceDetector:
    def __init__(self):
        if not hasattr(mp, "solutions"):
            version = getattr(mp, "__version__", "unknown")
            raise RuntimeError(
                "This project requires MediaPipe's legacy solutions API "
                f"(mediapipe==0.10.9); installed version is {version}."
            )
        self.mp_face = mp.solutions.face_detection
        self.detector = self.mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.6)

        # For smoothing
        self.prev_bbox = None

    def detect(self, frame):
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb)

        if results.detections:
            # Pick largest face (important if multiple)
            best_det = None
            max_area = 0

            for det in results.detections:
                bbox = det.location_data.relative_bounding_box
                bw = int(bbox.width * w)
                bh = int(bbox.height * h)
                area = bw * bh

                if area > max_area:
                    max_area = area
                    best_det = bbox

            bbox = best_det

            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            bw = int(bbox.width * w)
            bh = int(bbox.height * h)

            # Clamp values (avoid negative / overflow)
            x = max(0, x)
            y = max(0, y)
            bw = min(w - x, bw)
            bh = min(h - y, bh)

            # 🔥 SMOOTHING
            if self.prev_bbox is not None:
                px, py, pw, ph = self.prev_bbox
                x = int(0.7 * px + 0.3 * x)
                y = int(0.7 * py + 0.3 * y)
                bw = int(0.7 * pw + 0.3 * bw)
                bh = int(0.7 * ph + 0.3 * bh)

            self.prev_bbox = (x, y, bw, bh)

            return {
                "frame": frame,
                "face_bbox": (x, y, bw, bh),
                "face_detected": True
            }

        else:
            self.prev_bbox = None

            return {
                "frame": frame,
                "face_bbox": None,
                "face_detected": False
            }