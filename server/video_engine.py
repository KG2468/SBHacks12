import time
import threading
import numpy as np
import mss
from io import BytesIO
from typing import Optional

# Dependencies: pip install imageio[ffmpeg] pynput mss numpy
import imageio.v3 as iio
from pynput import mouse, keyboard

# ─────────────────────────────────────────────────────────
# 1. THE RECORDER (The Eyes)
# ─────────────────────────────────────────────────────────
class IdleScreenRecorder:
    def __init__(
        self,
        idle_seconds: int = 5,    # Stop recording after 5s of no mouse/key activity
        max_duration: int = 300,  # Safety limit (5 mins)
        fps: int = 10,
    ):
        self.idle_seconds = idle_seconds
        self.max_duration = max_duration
        self.fps = fps

        self._last_activity_time = time.time()
        self._activity_lock = threading.Lock()
        
        # Input Listeners
        self._mouse_listener = None
        self._key_listener = None

        # Data Storage
        self._frames = []
        self._video_buffer: Optional[BytesIO] = None
        self._recording_duration = 0.0
        self._stopped_reason = None

    def _mark_activity(self) -> None:
        """Resets the idle timer."""
        with self._activity_lock:
            self._last_activity_time = time.time()

    def _start_listeners(self) -> None:
        """Starts background threads to detect mouse/keyboard usage."""
        # Note: On macOS, this requires "Accessibility" permissions in System Settings
        self._mouse_listener = mouse.Listener(
            on_move=lambda *a: self._mark_activity(),
            on_click=lambda *a: self._mark_activity(),
            on_scroll=lambda *a: self._mark_activity()
        )
        self._key_listener = keyboard.Listener(
            on_press=lambda *a: self._mark_activity()
        )
        self._mouse_listener.start()
        self._key_listener.start()

    def _stop_listeners(self) -> None:
        if self._mouse_listener: self._mouse_listener.stop()
        if self._key_listener: self._key_listener.stop()

    def record_until_idle(self) -> None:
        """
        BLOCKING FUNCTION.
        Records the screen until the user stops interacting for `idle_seconds`.
        """
        # Reset
        self._frames = []
        self._video_buffer = None
        self._mark_activity()
        self._start_listeners()

        with mss.mss() as sct:
            # Monitor [1] is usually the primary screen
            monitor = sct.monitors[1]
            start_time = time.time()
            
            print(f"[Recorder] Started. Waiting for {self.idle_seconds}s of silence...")

            try:
                while True:
                    loop_start = time.time()

                    # 1. Capture Frame (MSS gives BGRA)
                    frame_bgra = np.array(sct.grab(monitor))
                    
                    # 2. Convert BGRA -> RGB (Drop Alpha, Flip Blue/Red)
                    frame_rgb = np.flip(frame_bgra[:, :, :3], 2)
                    self._frames.append(frame_rgb)

                    # 3. Check Time limits
                    now = time.time()
                    with self._activity_lock:
                        idle_time = now - self._last_activity_time
                    
                    if idle_time >= self.idle_seconds:
                        self._stopped_reason = "idle"
                        print("[Recorder] Idle detected. Stopping.")
                        break

                    if (now - start_time) >= self.max_duration:
                        self._stopped_reason = "max_duration"
                        print("[Recorder] Max duration reached. Stopping.")
                        break

                    # 4. FPS Control
                    process_time = time.time() - loop_start
                    sleep_time = max(0, (1.0 / self.fps) - process_time)
                    time.sleep(sleep_time)

            finally:
                self._stop_listeners()

        self._recording_duration = round(time.time() - start_time, 2)
        self._encode_to_ram()

    def _encode_to_ram(self) -> None:
        """Compresses raw frames into MP4 format in memory."""
        if not self._frames: return
        
        print(f"[Recorder] Encoding {len(self._frames)} frames...")
        buffer = BytesIO()
        iio.imwrite(
            buffer,
            self._frames,
            extension=".mp4",
            fps=self.fps,
            codec="libx264",
            format_hint=".mp4"
        )
        buffer.seek(0)
        self._video_buffer = buffer
        self._frames.clear() # Free raw memory

    def get_video_bytes(self) -> bytes:
        if self._video_buffer is None:
            return b""
        return self._video_buffer.getvalue()

    def delete_video(self) -> None:
        if self._video_buffer:
            self._video_buffer.close()
            self._video_buffer = None

    # --- THIS WAS MISSING ---
    def get_metadata(self) -> dict:
        return {
            "duration_seconds": self._recording_duration,
            "idle_seconds": self.idle_seconds,
            "stopped_reason": self._stopped_reason,
        }

# ─────────────────────────────────────────────────────────
# 2. THE ENGINE (The Manager)
# ─────────────────────────────────────────────────────────
class VideoEngine:
    def __init__(self):
        self.recorder = IdleScreenRecorder()
        
        # State Flags
        self.is_recording = False
        self.video_ready = False
        self.status_message = "Idle"

    def start_recording_session(self):
        """Starts the recorder in a background thread."""
        if self.is_recording:
            return "Error: Already recording."
        
        self.is_recording = True
        self.video_ready = False
        self.status_message = "Recording (Watching for activity)..."
        
        # Start the worker thread
        threading.Thread(target=self._recording_worker, daemon=True).start()
        return "Recording started."

    def _recording_worker(self):
        try:
            # Blocks here until user stops moving mouse
            self.recorder.record_until_idle()
            
            # When done:
            self.video_ready = True
            self.status_message = "Video Captured. Ready for retrieval."
        except Exception as e:
            self.status_message = f"Error: {e}"
        finally:
            self.is_recording = False

    def get_video_data(self):
        """
        Returns the video bytes if ready, and clears the memory.
        Returns: (bytes, status_message)
        """
        if not self.video_ready:
            return None, "No video ready."
        
        data = self.recorder.get_video_bytes()
        
        # Cleanup immediately after retrieval
        self.recorder.delete_video() 
        self.video_ready = False
        self.status_message = "Idle"
        
        return data, "Success"

# Singleton Instance
engine = VideoEngine()