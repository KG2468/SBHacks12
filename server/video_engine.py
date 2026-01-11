import time
import threading
import numpy as np
import Quartz
from io import BytesIO
from typing import Optional
import sys
import os
import subprocess

# GUI Dependencies
import tkinter as tk
from tkinter import Canvas, Frame, Scrollbar
from PIL import Image, ImageDraw

# Media/Input Dependencies
import imageio.v3 as iio
from pynput import keyboard, mouse
from pynput.mouse import Controller as MouseController
from screenmanager.screenmanager import pick_window


# ─────────────────────────────────────────────────────────
# 2. THE RECORDER (Quartz Engine)
# ─────────────────────────────────────────────────────────
class IdleScreenRecorder:
    def __init__(self, idle_seconds=5, max_duration=300, fps=10, target_window_id=None):
        self.idle_seconds = idle_seconds
        self.max_duration = max_duration
        self.fps = fps
        self._last_activity_time = time.time()
        self._activity_lock = threading.Lock()
        
        # Tools for cursor visualization
        self.mouse_controller = MouseController()
        # Default cursor color
        self.cursor_color = "white"

        self._key_listener = None
        self._mouse_listener = None
        
        # Visual Activity Tracking
        self.prev_gray_frame = None
        
        self._frames = []
        self._video_buffer = None
        self._recording_duration = 0.0
        self._stopped_reason = None
        self.target_window_id = target_window_id

    def _mark_activity(self):
        """Updates the timer when activity happens."""
        with self._activity_lock:
            self._last_activity_time = time.time()

    def _on_mouse_click(self, x, y, button, pressed):
        """Changes cursor color."""
        if not pressed:
            self.cursor_color = "white"
        else:
            if button == mouse.Button.left:
                self.cursor_color = "#00FF00" # Green
            elif button == mouse.Button.right:
                self.cursor_color = "#FF0000" # Red
            else:
                self.cursor_color = "blue"

    def _start_listeners(self):
        # 1. Keyboard: Resets idle timer
        self._key_listener = keyboard.Listener(on_press=lambda *a: self._mark_activity())
        self._key_listener.start()

        # 2. Mouse: Only updates color (no idle reset)
        self._mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self._mouse_listener.start()

    def _stop_listeners(self):
        if self._key_listener: self._key_listener.stop()
        if self._mouse_listener: self._mouse_listener.stop()

    def _draw_cursor_on_frame(self, img_rgb, width, height):
        try:
            # 1. Get Window Position
            win_info_list = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionIncludingWindow, self.target_window_id)
            if not win_info_list: return img_rgb
            bounds = win_info_list[0].get('kCGWindowBounds', {})
            win_x = bounds.get('X', 0)
            win_y = bounds.get('Y', 0)

            # 2. Get Mouse Position
            gx, gy = self.mouse_controller.position
            rx = int(gx - win_x)
            ry = int(gy - win_y)

            # 3. Draw Triangle if inside
            if 0 <= rx < width and 0 <= ry < height:
                pil_img = Image.fromarray(img_rgb)
                draw = ImageDraw.Draw(pil_img)
                
                # Triangle Geometry
                triangle_points = [
                    (rx, ry),           # Top
                    (rx - 8, ry + 18),  # Bottom Left
                    (rx + 8, ry + 18)   # Bottom Right
                ]
                
                # Fill based on click state
                draw.polygon(triangle_points, fill=self.cursor_color, outline='black')
                
                return np.array(pil_img)

        except Exception as e:
            # Don't crash on drawing errors
            pass
            
        return img_rgb

    def _capture_frame(self):
        if not self.target_window_id: return None
        image_ref = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            self.target_window_id,
            Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageNominalResolution
        )
        if not image_ref: return None

        w = Quartz.CGImageGetWidth(image_ref)
        h = Quartz.CGImageGetHeight(image_ref)
        bpr = Quartz.CGImageGetBytesPerRow(image_ref)
        
        pixel_data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image_ref))
        buff = np.frombuffer(pixel_data, dtype=np.uint8)
        
        expected_len = h * bpr
        buff = buff[:expected_len].reshape((h, bpr))
        buff = buff[:, :w*4] 
        
        img = buff.reshape((h, w, 4))
        img = img[:, :, :3] # Drop Alpha
        img_rgb = img[:, :, [2, 1, 0]] # BGRA -> RGB

        img_with_cursor = self._draw_cursor_on_frame(img_rgb, w, h)

        h_even = h - (h % 2)
        w_even = w - (w % 2)
        return img_with_cursor[:h_even, :w_even, :]

    def record_until_idle(self, video_queue, queue_lock) -> None:
        # # 1. TRIGGER THE GUI HERE
        # print("[Recorder] Launching GUI Selector...")
        # try:
        #     # This calls THIS file again with the flag to open the GUI
        #     # cmd = [sys.executable, os.path.abspath(__file__), "--select-window"]
        #     # result = subprocess.check_output(cmd, stderr=sys.stderr).decode().strip()
            
        #     # if not result or "None" in result:
        #     #     print("[Recorder] No selection made.")
        #     #     return
            
        #     print(f"[Recorder] Locked to Window ID {self.target_window_id}")

        # except subprocess.CalledProcessError as e:
        #     print(f"[Recorder] GUI Process failed: {e}")
        #     return
        # except ValueError:
        #     print(f"[Recorder] Invalid ID returned: {sid}")
        #     return
        # except Exception as e:
        #     print(f"[Recorder] GUI Selector Error: {e}")
        #     return

        # 2. START RECORDING
        self._frames = []
        self._video_buffer = None
        self._mark_activity()
        # self._start_listeners()
        
        # Reset visual tracker
        self.prev_gray_frame = None
        idling = True
        
        print(f"[Recorder] Recording... (Stop by not acting for {self.idle_seconds}s)")

        try:
            while True:
                loop_start = time.time()
                # print(loop_start)

                frame = self._capture_frame()
                if frame is not None:
                    self._frames.append(frame)

                    # ──────────────────────────────────────────────
                    # VISUAL ACTIVITY DETECTION (SCROLLING CHECK)
                    # ──────────────────────────────────────────────
                    # 1. Convert to grayscale (mean of RGB) to simplify
                    

                    if len(self._frames)%self.fps == 0:
                        curr_gray = frame.mean(axis=2)
                        if self.prev_gray_frame is None:
                            self.prev_gray_frame = curr_gray
                            continue
            
                        # 2. Calculate pixel difference
                        diff = np.abs(curr_gray - self.prev_gray_frame)
                        
                        # 3. Check for meaningful change (>15 value shift)
                        # This ignores tiny compression noise
                        changed_mask = diff > 15
                        
                        # 4. Calculate Ratio (0.0 to 1.0)
                        change_ratio = np.mean(changed_mask)
                        print(change_ratio)
                        
                        # 5. Threshold: If > 0.35% of pixels changed, it's activity
                        if change_ratio > 0.0035: 
                            self._mark_activity()
                            idling = False
                    
                        self.prev_gray_frame = curr_gray
                    # ──────────────────────────────────────────────

                now = time.time()
                with self._activity_lock:
                    idle_time = (now - self._last_activity_time)# / 1000
                
                if idle_time >= self.idle_seconds or len(self._frames) >= self.max_duration * self.fps:
                    if idling:
                        self._frames.clear()
                        self._mark_activity()
                        continue
                    vid = self._frames
                    self._frames = []
                    vid = self._encode_to_ram(vid)
                    queue_lock.acquire()
                    video_queue.append(vid)
                    print(len(video_queue))
                    queue_lock.release()
                    idling = True

                process_time = (time.time() - loop_start)
                
                sleep_time = max(0, (1.0 / self.fps) - process_time)
                time.sleep(sleep_time)
        # finally:
        #     self._stop_listeners()
        except Exception as e:
            print(f"[Recorder] Recording Error: {e}")


    def _encode_to_ram(self, frames):
        if not frames: return
        print(f"[Recorder] Encoding {len(frames)} frames...")
        buffer = BytesIO()
        try:
            iio.imwrite(buffer, frames, extension=".mp4", fps=self.fps, codec="libx264", format_hint=".mp4")
            buffer.seek(0)
            return buffer.getvalue()
        except Exception as e:
            print(f"[Recorder] Encoding Error: {e}")


# ─────────────────────────────────────────────────────────
# 3. THE ENGINE (Manager)
# ─────────────────────────────────────────────────────────
class VideoEngine:
    def __init__(self):
        # selector = WindowSelectorGUI()
        # sid = selector.select()
        # sid = select_window()
        # print(pwc.checkPermissions())

        sid = pick_window()['windowID']
        # print(sid)



        
        self.recorder = IdleScreenRecorder(target_window_id=sid)

        self.video_queue = []
        self.video_queue_lock = threading.Lock()
        print(sid)
        self.recording_thread = self.start_recording_session()
        
        # time.sleep(30)  # Give some time to initialize


    def start_recording_session(self):
        thread = threading.Thread(target=self._recording_worker, daemon=True)
        thread.start()
        return thread

    def _recording_worker(self):
        try:
            self.recorder.record_until_idle(self.video_queue, self.video_queue_lock)
        except Exception as e:
            self.status_message = f"Error: {e}"

    def get_video_data(self):
        if not self.video_ready: return None, "No video ready."
        data = self.recorder.get_video_bytes()
        self.recorder.delete_video()
        self.video_ready = False
        self.status_message = "Idle"
        return data, "Success"
    
    def check_video(self):
        return len(self.video_queue) > 0
    
    def get_video(self):
        self.video_queue_lock.acquire()
        if self.video_queue:
            video_data = self.video_queue.pop(0)
            self.video_queue_lock.release()
            return video_data
        self.video_queue_lock.release()
        return None


# engine = VideoEngine()



# # ─────────────────────────────────────────────────────────
# # 4. SUBPROCESS ENTRY POINT (Required for GUI)
# # ─────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     if "--select-window" in sys.argv:
#         try:
#             selector = WindowSelectorGUI()
#             sid = selector.select()
#             if sid:
#                 print(sid)
#             else:
#                 print("None")
#         except KeyboardInterrupt:
#             print("None")
