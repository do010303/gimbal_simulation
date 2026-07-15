#!/usr/bin/env python3
"""
Quick Auto-Exposure (AE) test for SIYI A8 Mini using GStreamer backend.
Usage:
  python3 test_ae.py
"""
import cv2
import numpy as np
import time

# GStreamer pipeline optimized for low latency and stability
# It drops frames automatically if the client is slow (sync=false, drop=true)
GST_PIPELINE = (
    "rtspsrc location=rtsp://192.168.168.16:8554/main.264 latency=100 protocols=tcp ! "
    "rtph264depay ! h264parse ! avdec_h264 ! "
    "videoconvert ! appsink drop=true max-buffers=1 sync=false"
)

print("[INFO] Opening RTSP stream via GStreamer...")
cap = cv2.VideoCapture(GST_PIPELINE, cv2.CAP_GSTREAMER)

if not cap.isOpened():
    print("[ERROR] Cannot open RTSP stream via GStreamer.")
    print("Please make sure the camera is pingable and no other clients are streaming.")
    exit(1)

print("[INFO] Stream opened successfully. Change lighting to test AE.")
print("[INFO] Press 'q' to quit.\n")

history = []
t0 = time.time()

while True:
    ret, frame = cap.read()
    if not ret or frame is None:
        # Avoid tight loop CPU burning if frame grab fails
        time.sleep(0.01)
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_b = float(np.mean(gray))
    elapsed = time.time() - t0
    history.append((elapsed, mean_b))

    # Draw HUD
    cv2.putText(frame, f"Mean Brightness: {mean_b:.1f}", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.putText(frame, f"Time: {elapsed:.1f}s", (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

    # AE verdict after some data
    if len(history) > 30:
        vals = [h[1] for h in history[-90:]]  # last ~3 seconds
        spread = max(vals) - min(vals)
        if spread > 30:
            verdict = "AE likely ACTIVE (brightness shifting)"
            color = (0, 255, 255)
        else:
            verdict = "AE stable or OFF"
            color = (0, 200, 0)
        cv2.putText(frame, verdict, (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    cv2.imshow("SIYI A8 - AE Test (GStreamer)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# Print summary
if len(history) > 10:
    vals = [h[1] for h in history]
    print(f"\n{'='*50}")
    print(f"  Total frames: {len(history)}")
    print(f"  Duration:     {history[-1][0]:.1f}s")
    print(f"  Brightness — min: {min(vals):.1f}  max: {max(vals):.1f}  range: {max(vals)-min(vals):.1f}")
    print(f"{'='*50}")
    if max(vals) - min(vals) > 40:
        print("  → Camera likely HAS Auto-Exposure (large brightness range detected)")
    else:
        print("  → Brightness stayed stable — AE may be OFF or lighting was constant")
