import cv2

from detection.face_detection import FaceDetector
from detection.mouth_landmark_extractor import (
    MouthLandmarkExtractor
)

from metrics.mar_calculator import MARCalculator
from metrics.yawn_detector import YawnDetector

def run_demo():
    cap = cv2.VideoCapture(0)

    detector = FaceDetector()

    extractor = MouthLandmarkExtractor()

    mar_calculator = MARCalculator()

    yawn_detector = YawnDetector(
        mar_threshold=0.6,
        min_yawn_duration=1.0
    )

    while True:

        ret, frame = cap.read()

        if not ret:
            continue

        data = detector.detect(frame)

        if data["face_detected"]:

            x, y, w, h = data["face_bbox"]

            face = frame[y:y+h, x:x+w]

            mouth = extractor.extract(
                face,
                (x, y, w, h)
            )

            mouth_points = mouth["mouth"]

            if len(mouth_points) == 8:

                mar = mar_calculator.calculate_mar(
                    mouth_points
                )

                yawn_metrics = (
                    yawn_detector.update(mar)
                )

                cv2.putText(
                    frame,
                    f"MAR: {mar:.2f}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"Yawns: {yawn_metrics['yawn_count']}",
                    (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"Yawning: {yawn_metrics['is_yawning']}",
                    (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2
                )

                for px, py in mouth_points:
                    cv2.circle(
                        frame,
                        (px, py),
                        3,
                        (0, 255, 255),
                        -1
                    )

        cv2.imshow(
            "Yawn Detector Test",
            frame
        )

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_demo()