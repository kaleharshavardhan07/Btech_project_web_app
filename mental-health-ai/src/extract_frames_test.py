import cv2

video_path = "../data/videos/adhd/adhd_01.MOV"

cap = cv2.VideoCapture(video_path)

fps = int(cap.get(cv2.CAP_PROP_FPS))

frame_interval = fps   # 1 frame per second

frame_id = 0
saved_frames = 0

while True:

    ret, frame = cap.read()

    if not ret:
        break

    if frame_id % frame_interval == 0:
        cv2.imwrite(f"frame_{saved_frames}.jpg", frame)
        saved_frames += 1

    frame_id += 1

cap.release()

print("Frames extracted:", saved_frames)