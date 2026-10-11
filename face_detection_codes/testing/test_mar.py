import cv2

from detection.face_detection import FaceDetector
from detection.mouth_landmark_extractor import MouthLandmarkExtractor
from metrics.mar_calculator import MARCalculator


def run_demo():
    cap = cv2.VideoCapture(0)

    detector = FaceDetector()
    extractor = MouthLandmarkExtractor()
    mar_calculator = MARCalculator()

    while True:

        ret, frame = cap.read()

        if not ret:
            continue

        data = detector.detect(frame)

        if data["face_detected"]:

            x, y, w, h = data["face_bbox"]

            face_region = frame[y:y+h, x:x+w]

            mouth_data = extractor.extract(
                face_region,
                (x, y, w, h)
            )

            mouth_points = mouth_data["mouth"]

            if len(mouth_points) == 8:

                mar = mar_calculator.calculate_mar(
                    mouth_points
                )

                cv2.putText(
                    frame,
                    f"MAR: {mar:.2f}",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )

                for px, py in mouth_points:

                    cv2.circle(
                        frame,
                        (px, py),
                        4,
                        (0, 0, 255),
                        -1
                    )

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

        cv2.imshow("MAR Test", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_demo()