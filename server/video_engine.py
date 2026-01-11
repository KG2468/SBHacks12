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

    def _pil_to_tk_photo(self, pil_img):
        """Convert PIL Image to Tkinter PhotoImage without using ImageTk."""
        # Save to bytes as PNG
        buffer = BytesIO()
        pil_img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Use Tkinter's native PhotoImage with PNG data
        import base64
        png_data = base64.b64encode(buffer.getvalue()).decode('ascii')
        return tk.PhotoImage(data=png_data)

    def _capture_thumbnail_data(self, window_id):
        """Capture window and return PIL Image (not PhotoImage yet)."""
        try:
            image_ref = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull,
                Quartz.kCGWindowListOptionIncludingWindow,
                window_id,
                Quartz.kCGWindowImageBoundsIgnoreFraming
            )
            if not image_ref: 
                self._log(f"[DEBUG] CGWindowListCreateImage returned None for window {window_id}")
                return None

            width = Quartz.CGImageGetWidth(image_ref)
            height = Quartz.CGImageGetHeight(image_ref)
            self._log(f"[DEBUG] Captured window {window_id}: {width}x{height}")
            
            if width < 10 or height < 10:
                self._log(f"[DEBUG] Window {window_id} too small, skipping")
                return None

            # Use CGDataProvider to get raw bytes
            data_provider = Quartz.CGImageGetDataProvider(image_ref)
            pixel_data = Quartz.CGDataProviderCopyData(data_provider)
            
            if not pixel_data:
                self._log(f"[DEBUG] No pixel data for window {window_id}")
                return None

            # Create PIL Image directly from BGRA data
            raw_bytes = bytes(pixel_data)
            
            # Calculate expected size
            bpr = Quartz.CGImageGetBytesPerRow(image_ref)
            expected_size = height * bpr
            
            if len(raw_bytes) < expected_size:
                self._log(f"[DEBUG] Buffer too small: {len(raw_bytes)} < {expected_size}")
                return None

            # Create numpy array and handle stride
            buff = np.frombuffer(raw_bytes, dtype=np.uint8)
            buff = buff[:expected_size].reshape((height, bpr))
            
            # Extract only the image data (remove row padding)
            img_array = buff[:, :width * 4].reshape((height, width, 4))
            
            # BGRA -> RGB (macOS uses BGRA format)
            img_rgb = img_array[:, :, [2, 1, 0]]

            # Resize for thumbnail - return PIL Image, NOT PhotoImage
            pil_img = Image.fromarray(img_rgb)
            target_width = 280
            aspect_ratio = height / width
            target_height = int(target_width * aspect_ratio)
            if target_height > 200: 
                target_height = 200
                
            pil_img = pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            return pil_img  # Return PIL Image, not PhotoImage
            
        except Exception as e:
            self._log(f"[DEBUG] Thumbnail error for {window_id}: {e}")
            import traceback
            traceback.print_exc(file=sys.stderr)
            return None

    def get_windows(self):
        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        
        results = []
        for win in window_list:
            owner = win.get('kCGWindowOwnerName', 'Unknown')
            name = win.get('kCGWindowName', '')
            window_id = win.get('kCGWindowNumber')
            bounds = win.get('kCGWindowBounds', {})
            w = int(bounds.get('Width', 0))
            h = int(bounds.get('Height', 0))
            
            if w < 100 or h < 100: continue
            if "python" in owner.lower(): continue
            if owner in ["Screenshot", "Window Server", "Dock", "Control Center", "Overlay"]: continue
            
            display_name = name if name else owner

            results.append({
                'id': window_id,
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

        # MUST create Tk root FIRST before any PhotoImage
        self.root = tk.Tk()
        self.root.title("Select Window to Record")
        self.root.geometry("1000x700")
        self.root.configure(bg="#f0f0f0")
        self.root.eval('tk::PlaceWindow . center')
        
        # Force window to front and grab focus
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        self.root.focus_force()

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
            
            # Capture PIL image first
            pil_img = self._capture_thumbnail_data(win['id'])
            
            # Convert to PhotoImage AFTER Tk root exists using our workaround
            thumb = None
            if pil_img:
                thumb = self._pil_to_tk_photo(pil_img)
                self.images_cache.append(thumb)  # Keep reference to prevent garbage collection

            card = tk.Frame(scrollable_frame, bg="white", bd=1, relief="solid", padx=10, pady=10, cursor="hand2")
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            # Create click handler for this window
            def make_click_handler(window_id):
                return lambda e: self._on_click(window_id)
            
            click_handler = make_click_handler(win['id'])
            card.bind("<Button-1>", click_handler)

            if thumb:
                img_label = tk.Label(card, image=thumb, bg="white", cursor="hand2")
                img_label.pack(pady=(0, 10))
                img_label.bind("<Button-1>", click_handler)
            else:
                no_preview = tk.Label(card, text="[No Preview]", bg="#eee", height=8, width=20, cursor="hand2")
                no_preview.pack(pady=(0, 10))
                no_preview.bind("<Button-1>", click_handler)

            owner_label = tk.Label(card, text=win['owner'], font=("Helvetica", 11, "bold"), bg="white", cursor="hand2")
            owner_label.pack(anchor="w")
            owner_label.bind("<Button-1>", click_handler)
            
            subtext = win['name']
            if len(subtext) > 40: subtext = subtext[:37] + "..."
            name_label = tk.Label(card, text=subtext, font=("Helvetica", 10), bg="white", fg="#666", cursor="hand2")
            name_label.pack(anchor="w")
            name_label.bind("<Button-1>", click_handler)

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
                        
                        # 5. Threshold: If > 0.5% of pixels changed, it's activity
                        if change_ratio > 0.005: 
                            self._mark_activity()
                            idling = False
                    
                        self.prev_gray_frame = curr_gray
                    # ──────────────────────────────────────────────

                now = time.time()
                with self._activity_lock:
                    idle_time = now - self._last_activity_time
                
                if idle_time >= self.idle_seconds or len(self._frames) >= self.max_duration * self.fps:
                    if idling:
                        self._frames.clear()
                        continue
                    vid = self._frames
                    self._frames = []
                    vid = self._encode_to_ram(vid)
                    queue_lock.acquire()
                    video_queue.append(vid)
                    queue_lock.release()
                    idling = True

                process_time = time.time() - loop_start
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
        selector = WindowSelectorGUI()
        sid = selector.select()

        
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
