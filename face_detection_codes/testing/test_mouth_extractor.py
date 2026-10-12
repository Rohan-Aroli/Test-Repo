import cv2

from detection.face_detection import FaceDetector
from detection.mouth_landmark_extractor import MouthLandmarkExtractor

def run_demo():
    cap = cv2.VideoCapture(0)

    detector = FaceDetector()
    extractor = MouthLandmarkExtractor()

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

            # Draw face box
            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            # Draw mouth landmarks
            for px, py in mouth_points:

                cv2.circle(
                    frame,
                    (px, py),
                    4,
                    (0, 0, 255),
                    -1
                )

        cv2.imshow("Mouth Landmark Test", frame)

        key = cv2.waitKey(1)

        if key == 27:  # ESC
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_demo()