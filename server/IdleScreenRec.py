"""
Screen Recorder with Idle Detection
- Records screen until inactivity
- Stores MP4 video fully in RAM
- Exposes methods to retrieve or delete video bytes
"""

import time
import threading
from typing import Optional

import numpy as np
import mss
from pynput import mouse, keyboard
import imageio.v3 as iio
from io import BytesIO


# ─────────────────────────────────────────────────────────────
# Recorder Controller
# ─────────────────────────────────────────────────────────────

class IdleScreenRecorder:
    def __init__(
        self,
        idle_seconds: int = 10,
        check_interval: int = 2,
        max_duration: int = 300,
        fps: int = 10,
    ):
        self.idle_seconds = idle_seconds
        self.check_interval = check_interval
        self.max_duration = max_duration
        self.fps = fps

        self._last_activity_time = time.time()
        self._activity_lock = threading.Lock()

        self._frames = []
        self._video_buffer: Optional[BytesIO] = None
        self._recording_duration = 0.0
        self._stopped_reason = None

    # ─────────────────────────────────────────────────────────
    # Activity Tracking
    # ─────────────────────────────────────────────────────────

    def _mark_activity(self) -> None:
        with self._activity_lock:
            self._last_activity_time = time.time()

    def _start_input_listeners(self) -> None:
        mouse.Listener(
            on_move=lambda *a: self._mark_activity(),
            on_click=lambda *a: self._mark_activity(),
            on_scroll=lambda *a: self._mark_activity(),
        ).start()

        keyboard.Listener(
            on_press=lambda *a: self._mark_activity(),
        ).start()

    # ─────────────────────────────────────────────────────────
    # Recording Logic
    # ─────────────────────────────────────────────────────────

    def record_until_idle(self) -> None:
        self._start_input_listeners()

        sct = mss.mss()
        monitor = sct.monitors[1]

        prev_gray = None
        start_time = time.time()

        while True:
            frame = np.array(sct.grab(monitor))
            frame_rgb = frame[..., :3]  # drop alpha
            self._frames.append(frame_rgb)

            gray = frame_rgb.mean(axis=2)

            if prev_gray is not None:
                diff = np.abs(gray - prev_gray)
                if (diff > 5).mean() > 0.01:
                    self._mark_activity()

            prev_gray = gray

            with self._activity_lock:
                idle_time = time.time() - self._last_activity_time

            elapsed = time.time() - start_time

            if idle_time >= self.idle_seconds:
                self._stopped_reason = "idle"
                break

            if elapsed >= self.max_duration:
                self._stopped_reason = "max_duration"
                break

            time.sleep(self.check_interval)

        self._recording_duration = round(time.time() - start_time, 2)
        self._encode_video_to_memory()

    # ─────────────────────────────────────────────────────────
    # Video Encoding (RAM-only)
    # ─────────────────────────────────────────────────────────

    def _encode_video_to_memory(self) -> None:
        buffer = BytesIO()
        iio.imwrite(
            buffer,
            self._frames,
            format="mp4",
            fps=self.fps,
            codec="h264",
        )
        buffer.seek(0)
        self._video_buffer = buffer
        self._frames.clear()  # free raw frames immediately

    # ─────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────

    def get_video_bytes(self) -> bytes:
        """
        Returns the MP4 video as raw bytes.
        """
        if self._video_buffer is None:
            raise RuntimeError("No video available.")
        return self._video_buffer.getvalue()

    def delete_video(self) -> None:
        """
        Deletes the video from memory.
        """
        if self._video_buffer is not None:
            self._video_buffer.close()
            self._video_buffer = None

    def get_metadata(self) -> dict:
        """
        Returns recording metadata.
        """
        return {
            "duration_seconds": self._recording_duration,
            "idle_seconds": self.idle_seconds,
            "stopped_reason": self._stopped_reason,
        }
