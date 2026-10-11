# import cv2

# cap = cv2.VideoCapture(0)

# if not cap.isOpened():
#     print("ERROR: Could not open camera")
#     raise SystemExit(1)

# print("Camera opened successfully.")
# print("Press Q to quit.")

# while True:
#     ret, frame = cap.read()

#     if not ret:
#         print("ERROR: Could not read frame")
#         break

#     cv2.imshow("CAM01 Test", frame)

#     if cv2.waitKey(1) & 0xFF == ord("q"):
#         break

# cap.release()
# cv2.destroyAllWindows()




import cv2


def main():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Could not open camera")
        return 1

    print("Camera opened successfully.")
    print("Press Q to quit.")

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("ERROR: Could not read frame")
                return 1

            cv2.imshow("CAM01 Test", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
