import time
import threading
import numpy as np
import Quartz
from io import BytesIO
import imageio.v3 as iio
from pynput import mouse, keyboard

class QuartzVideoEngine:
    def __init__(self, fps: int = 10):
        self.fps = fps
        self.recording = False
        self.frames = []
        self.video_output = None
        self.stop_event = threading.Event()
        self.thread = None
        
        # Idle Detection
        self.last_activity = time.time()
        self.idle_threshold = 5 
        
        # Window Tracking
        self.target_window_id = None
        # We will set these after capturing the first frame
        self.fixed_width = 0
        self.fixed_height = 0

    def list_windows(self, app_name: str = None):
        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        
        results = []
        for win in window_list:
            owner = win.get('kCGWindowOwnerName', 'Unknown')
            name = win.get('kCGWindowName', '')
            win_id = win.get('kCGWindowNumber')
            bounds = win.get('kCGWindowBounds', {})
            width = bounds.get('Width', 0)
            height = bounds.get('Height', 0)
            
            if width < 50 or height < 50: continue
            if app_name and app_name.lower() not in owner.lower(): continue
                
            results.append({
                'id': win_id,
                'owner': owner,
                'name': name,
                'width': int(width),
                'height': int(height)
            })
        return results

    def _capture_window(self):
        if not self.target_window_id: return None

        image_ref = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            self.target_window_id,
            Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageNominalResolution
        )
        
        if not image_ref: return None

        width = Quartz.CGImageGetWidth(image_ref)
        height = Quartz.CGImageGetHeight(image_ref)
        pixel_data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image_ref))
        img_array = np.frombuffer(pixel_data, dtype=np.uint8)
        
        try:
            # Reshape to (Height, Width, 4) (BGRA)
            img = img_array.reshape((height, width, 4))
            
            # 1. Drop Alpha to get RGB
            img = img[:, :, :3]

            # 2. FORCE EVEN DIMENSIONS (Crucial Fix)
            # If height is 1095, we slice it to 1094.
            # If width is 1793, we slice to 1792.
            h_even = height - (height % 2)
            w_even = width - (width % 2)
            img = img[:h_even, :w_even, :]
            
            return img
        except ValueError:
            return None

    def _activity_callback(self, *args):
        self.last_activity = time.time()

    def start_recording(self, window_id: int):
        if self.recording: return "Already recording"
        
        self.target_window_id = window_id
        
        # Test capture to set dimensions
        first_frame = self._capture_window()
        if first_frame is None:
            return "Could not capture window. Is it minimized?"
            
        # Store the EVEN dimensions we just calculated
        self.fixed_height, self.fixed_width, _ = first_frame.shape
        print(f"[Engine] Locked to Window {window_id}. Enforcing Size: {self.fixed_width}x{self.fixed_height}")

        self.frames = []
        self.recording = True
        self.stop_event.clear()
        self.last_activity = time.time()
        
        self.mouse = mouse.Listener(on_move=self._activity_callback, on_click=self._activity_callback)
        self.key = keyboard.Listener(on_press=self._activity_callback)
        self.mouse.start()
        self.key.start()
        
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
        return "Started"

    def _record_loop(self):
        try:
            while not self.stop_event.is_set():
                start_time = time.time()
                
                frame = self._capture_window()
                
                # Only append if we successfully captured a frame of the EXACT right size
                if frame is not None:
                    h, w, _ = frame.shape
                    if h == self.fixed_height and w == self.fixed_width:
                        self.frames.append(frame)
                
                if time.time() - self.last_activity > self.idle_threshold:
                    print("\n[Engine] Idle detected. Stopping.")
                    break
                
                elapsed = time.time() - start_time
                time.sleep(max(0, (1.0/self.fps) - elapsed))
        finally:
            self._finalize()

    def _finalize(self):
        self.mouse.stop()
        self.key.stop()
        
        # Keep recording=True until we are DONE encoding
        if not self.frames:
            self.recording = False
            return

        print(f"[Engine] Encoding {len(self.frames)} frames... (Please Wait)")
        buffer = BytesIO()
        try:
            # macro_block_size=1 is no longer needed because we manually fixed the size
            iio.imwrite(buffer, self.frames, extension=".mp4", fps=self.fps, codec="libx264")
            buffer.seek(0)
            self.video_output = buffer.getvalue()
            buffer.close()
            print("[Engine] Encoding Complete.")
        except Exception as e:
            print(f"Encoding Error: {e}")
        
        self.frames.clear()
        self.recording = False # Now we are truly done

    def get_video_bytes(self):
        if self.video_output:
            data = self.video_output
            self.video_output = None
            return data
        return None

# Singleton
engine = QuartzVideoEngine()