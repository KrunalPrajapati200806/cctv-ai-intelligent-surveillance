import cv2

print("Testing camera indexes...")

for index in range(10):
    cap = cv2.VideoCapture(index)

    if cap.isOpened():
        print(f"[OK] Camera index {index} opened")
        ret, frame = cap.read()

        if ret and frame is not None:
            print(f"     Frame received: {frame.shape}")
        else:
            print("     Camera opened but no frame received")

        cap.release()
    else:
        print(f"[NO] Camera index {index}")

print("Done.")
