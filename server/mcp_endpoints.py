import os
import time
import threading
import cv2
import numpy as np
import mss
from enum import Enum
from mcp.server.fastmcp import FastMCP
from twelvelabs import TwelveLabs

# Initialize MCP
mcp = FastMCP("Visual Debugger Agent")

# Initialize TwelveLabs
client = TwelveLabs(api_key=os.getenv("TL_API_KEY"))

# --- 1. STATE & RECORDER LOGIC ---
class JobStatus(Enum):
    IDLE = "IDLE"
    RECORDING = "RECORDING"    # New Status!
    UPLOADING = "UPLOADING"
    INDEXING = "INDEXING"
    READY = "READY"

class State:
    def __init__(self):
        self.status = JobStatus.IDLE
        self.video_path = "recording.mp4"
        self.stop_recording_event = threading.Event()
        self.recording_thread = None
        self.analysis_result = None

state = State()

def _record_screen():
    """Background thread that captures screen to MP4"""
    with mss.mss() as sct:
        # Monitor 1 (Primary screen). Adjust if simulator is on a different screen.
        monitor = sct.monitors[1]
        
        # Setup Video Writer (XVID is widely supported)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = 10.0
        width, height = monitor["width"], monitor["height"]
        out = cv2.VideoWriter(state.video_path, fourcc, fps, (width, height))
        
        print("[Server] Recording started...")
        while not state.stop_recording_event.is_set():
            img = np.array(sct.grab(monitor))
            # Convert BGRA to BGR (required for OpenCV)
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            out.write(frame)
            time.sleep(1/fps)
            
        out.release()
        print(f"[Server] Recording saved to {state.video_path}")

def _upload_and_analyze():
    """Helper to handle the TwelveLabs upload flow"""
    print(f"[Server] Uploading {state.video_path}...")
    
    # 1. Create Index & Task
    index = client.index.create(
        name=f"Debug Session {int(time.time())}",
        engines=[{"name": "marengo2.6", "options": ["visual", "text_in_video"]}]
    )
    task = client.task.create(index_id=index.id, file=state.video_path)
    
    # 2. Wait for Indexing
    print(f"[Server] Waiting for indexing (Task ID: {task.id})...")
    
    # Simple polling loop (blocking for simplicity in this demo)
    while True:
        task_status = client.task.retrieve(task.id)
        if task_status.status == "ready":
            break
        if task_status.status == "failed":
            state.status = JobStatus.IDLE
            return "Analysis Failed"
        time.sleep(2)

    # 3. Generate Analysis
    print("[Server] generating analysis...")
    res = client.generate.text(
        video_id=task_status.video_id,
        prompt="Analyze the screen recording. Identify any error messages, UI glitches, or unexpected behaviors. Provide a code fix if an error is visible."
    )
    
    state.analysis_result = res.data
    state.status = JobStatus.READY


# --- TOOL 1: START RECORDING ---
@mcp.tool()
def start_recording() -> str:
    """
    Tells the server to start recording the screen immediately.
    Use this before you begin an action in the simulator.
    """
    if state.status != JobStatus.IDLE:
        return "Error: Server is busy (either recording or analyzing already)."

    state.status = JobStatus.RECORDING
    state.stop_recording_event.clear()
    
    # Start recording in a separate thread so we don't block the agent
    state.recording_thread = threading.Thread(target=_record_screen)
    state.recording_thread.start()
    
    return "Recording started. I am now watching your screen."


# --- TOOL 2: STOP AND ANALYZE ---
@mcp.tool()
def stop_and_analyze() -> str:
    """
    Stops the recording, uploads it to TwelveLabs, and waits for the result.
    This might take 30-60 seconds depending on video length.
    """
    if state.status != JobStatus.RECORDING:
        return "Error: I am not currently recording."

    # 1. Stop the recording
    state.stop_recording_event.set()
    state.recording_thread.join() # Wait for file to save
    state.status = JobStatus.UPLOADING
    
    # 2. Trigger analysis (We do this blocking here so the Agent gets the result in one go)
    # Note: For very long videos, you might want to separate this into 'stop' and 'check_status'
    # but for short debug clips, blocking is fine.
    _upload_and_analyze()
    
    result = state.analysis_result
    
    # Reset for next time
    state.status = JobStatus.IDLE
    
    return f"Recording finished and analyzed.\n\nANALYSIS:\n{result}"

if __name__ == "__main__":
    mcp.run()