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
from PIL import Image, ImageTk, ImageDraw

# Media/Input Dependencies
import imageio.v3 as iio
from pynput import keyboard, mouse
from pynput.mouse import Controller as MouseController

# ─────────────────────────────────────────────────────────
# 1. THE VISUAL WINDOW SELECTOR (GUI)
# ─────────────────────────────────────────────────────────
class WindowSelectorGUI:
    def __init__(self):
        self.selected_id = None
        self.root = None
        self.images_cache = []

    def _log(self, msg):
        """Print to stderr so we don't pollute stdout (used for ID return)."""
        print(msg, file=sys.stderr)

    def _capture_thumbnail(self, window_id):
        try:
            image_ref = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull,
                Quartz.kCGWindowListOptionIncludingWindow,
                window_id,
                Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageNominalResolution
            )
            if not image_ref: return None

            width = Quartz.CGImageGetWidth(image_ref)
            height = Quartz.CGImageGetHeight(image_ref)
            bpr = Quartz.CGImageGetBytesPerRow(image_ref)

            pixel_data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image_ref))
            buff = np.frombuffer(pixel_data, dtype=np.uint8)
            
            # Handle Stride/Padding
            expected_len = height * bpr
            buff = buff[:expected_len].reshape((height, bpr))
            buff = buff[:, :width * 4] # Crop padding
            
            # BGRA -> RGB
            img_array = buff.reshape((height, width, 4))
            img_rgb = img_array[:, :, [2, 1, 0]] 

            # Resize
            pil_img = Image.fromarray(img_rgb)
            target_width = 280
            aspect_ratio = height / width
            target_height = int(target_width * aspect_ratio)
            if target_height > 200: target_height = 200
                
            pil_img = pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(pil_img)
        except Exception:
            return None

    def get_windows(self):
        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        
        results = []
        for win in window_list:
            owner = win.get('kCGWindowOwnerName', 'Unknown')
            name = win.get('kCGWindowName', '')
            win_id = win.get('kCGWindowNumber')
            bounds = win.get('kCGWindowBounds', {})
            w = int(bounds.get('Width', 0))
            h = int(bounds.get('Height', 0))
            
            if w < 100 or h < 100: continue
            if "python" in owner.lower(): continue
            if owner in ["Screenshot", "Window Server", "Dock", "Control Center", "Overlay"]: continue
            
            display_name = name if name else owner

            results.append({
                'id': win_id,
                'owner': owner,
                'name': display_name,
                'dims': (w, h),
                'size_str': f"{w}x{h}"
            })
        return results

    def select(self):
        self._log("[GUI] Scanning windows...")
        windows = self.get_windows()
        
        if not windows:
            self._log("[GUI] No windows found.")
            return None

        self.root = tk.Tk()
        self.root.title("Select Window to Record")
        self.root.geometry("1000x700")
        self.root.configure(bg="#f0f0f0")
        self.root.eval('tk::PlaceWindow . center')

        # Header
        tk.Label(self.root, text="Select Screen to Record", font=("Helvetica", 18, "bold"), bg="#f0f0f0", pady=15).pack()

        # Scroll Area
        container = Frame(self.root, bg="#f0f0f0")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        canvas = Canvas(container, bg="#f0f0f0", highlightthickness=0)
        scrollbar = Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = Frame(canvas, bg="#f0f0f0")

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Grid
        COLUMNS = 3
        for i, win in enumerate(windows):
            row, col = divmod(i, COLUMNS)
            
            thumb = self._capture_thumbnail(win['id'])
            if thumb: self.images_cache.append(thumb)

            card = tk.Frame(scrollable_frame, bg="white", bd=1, relief="solid", padx=10, pady=10)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            select_fn = lambda w=win: self._on_click(w['id'])
            card.bind("<Button-1>", lambda e, c=select_fn: c())

            if thumb:
                l = tk.Label(card, image=thumb, bg="white", cursor="hand2")
                l.pack(pady=(0, 10))
                l.bind("<Button-1>", lambda e, c=select_fn: c())
            else:
                tk.Label(card, text="[No Preview]", bg="#eee", height=8, width=20).pack(pady=(0, 10))

            tk.Label(card, text=win['owner'], font=("Helvetica", 11, "bold"), bg="white").pack(anchor="w")
            
            subtext = win['name']
            if len(subtext) > 40: subtext = subtext[:37] + "..."
            tk.Label(card, text=subtext, font=("Helvetica", 10), bg="white", fg="#666").pack(anchor="w")

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta)), "units"))

        self.root.mainloop()
        return self.selected_id

    def _on_click(self, window_id):
        self.selected_id = window_id
        self.root.destroy()


# ─────────────────────────────────────────────────────────
# 2. THE RECORDER (Quartz Engine)
# ─────────────────────────────────────────────────────────
class IdleScreenRecorder:
    def __init__(self, idle_seconds=5, max_duration=300, fps=10):
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
        
        self._frames = []
        self._video_buffer = None
        self._recording_duration = 0.0
        self._stopped_reason = None
        self.target_window_id = None

    def _mark_activity(self):
        """Updates the timer when KEYBOARD activity happens."""
        with self._activity_lock:
            self._last_activity_time = time.time()

    def _on_mouse_click(self, x, y, button, pressed):
        """Changes cursor color but DOES NOT reset idle timer."""
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

    def record_until_idle(self):
        # 1. TRIGGER THE GUI HERE
        print("[Recorder] Launching GUI Selector...")
        try:
            # This calls THIS file again with the flag to open the GUI
            cmd = [sys.executable, os.path.abspath(__file__), "--select-window"]
            result = subprocess.check_output(cmd, stderr=sys.stderr).decode().strip()
            
            if not result or "None" in result:
                print("[Recorder] No selection made.")
                return

            self.target_window_id = int(result)
            print(f"[Recorder] Locked to Window ID {self.target_window_id}")

        except subprocess.CalledProcessError as e:
            print(f"[Recorder] GUI Process failed: {e}")
            return
        except ValueError:
            print(f"[Recorder] Invalid ID returned: {result}")
            return

        # 2. START RECORDING
        self._frames = []
        self._video_buffer = None
        self._mark_activity()
        self._start_listeners()
        
        start_time = time.time()
        print(f"[Recorder] Recording... (Stop by not typing for {self.idle_seconds}s)")

        try:
            while True:
                loop_start = time.time()

                frame = self._capture_frame()
                if frame is not None:
                    self._frames.append(frame)

                now = time.time()
                with self._activity_lock:
                    idle_time = now - self._last_activity_time
                
                if idle_time >= self.idle_seconds:
                    self._stopped_reason = "idle"
                    print("[Recorder] Keyboard idle detected. Stopping.")
                    break

                if (now - start_time) >= self.max_duration:
                    self._stopped_reason = "max_duration"
                    break

                process_time = time.time() - loop_start
                sleep_time = max(0, (1.0 / self.fps) - process_time)
                time.sleep(sleep_time)
        finally:
            self._stop_listeners()

        self._recording_duration = round(time.time() - start_time, 2)
        self._encode_to_ram()

    def _encode_to_ram(self):
        if not self._frames: return
        print(f"[Recorder] Encoding {len(self._frames)} frames...")
        buffer = BytesIO()
        try:
            iio.imwrite(buffer, self._frames, extension=".mp4", fps=self.fps, codec="libx264", format_hint=".mp4")
            buffer.seek(0)
            self._video_buffer = buffer
            print("[Recorder] Encoding Complete.")
        except Exception as e:
            print(f"[Recorder] Encoding Error: {e}")
        self._frames.clear()

    def get_video_bytes(self):
        return self._video_buffer.getvalue() if self._video_buffer else b""

    def delete_video(self):
        if self._video_buffer:
            self._video_buffer.close()
            self._video_buffer = None

    def get_metadata(self):
        return {
            "duration_seconds": self._recording_duration,
            "idle_seconds": self.idle_seconds,
            "stopped_reason": self._stopped_reason,
        }

# ─────────────────────────────────────────────────────────
# 3. THE ENGINE (Manager)
# ─────────────────────────────────────────────────────────
class VideoEngine:
    def __init__(self):
        self.recorder = IdleScreenRecorder()
        self.is_recording = False
        self.video_ready = False
        self.status_message = "Idle"

    def start_recording_session(self):
        if self.is_recording: return "Error: Already recording."
        self.is_recording = True
        self.video_ready = False
        self.status_message = "Selecting Window..."
        threading.Thread(target=self._recording_worker, daemon=True).start()
        return "Selector launched on server."

    def _recording_worker(self):
        try:
            self.recorder.record_until_idle()
            if self.recorder._video_buffer:
                self.video_ready = True
                self.status_message = "Video Captured. Ready for retrieval."
            else:
                self.status_message = "Recording cancelled or failed."
        except Exception as e:
            self.status_message = f"Error: {e}"
        finally:
            self.is_recording = False

    def get_video_data(self):
        if not self.video_ready: return None, "No video ready."
        data = self.recorder.get_video_bytes()
        self.recorder.delete_video()
        self.video_ready = False
        self.status_message = "Idle"
        return data, "Success"

engine = VideoEngine()

# ─────────────────────────────────────────────────────────
# 4. SUBPROCESS ENTRY POINT (Required for GUI)
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--select-window" in sys.argv:
        try:
            selector = WindowSelectorGUI()
            sid = selector.select()
            if sid:
                print(sid)
            else:
                print("None")
        except KeyboardInterrupt:
            print("None")