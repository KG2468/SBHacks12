import time
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add the server directory to Python path for imports when run from workspace root
_server_dir = os.path.dirname(os.path.abspath(__file__))
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

from mcp.server.fastmcp import FastMCP
from video_engine import VideoEngine
from twelvelabserver import analyze_video_from_ram
import threading

# Define the server
mcp = FastMCP("Visual Debugger")
status = False
status_lock = threading.Lock()

analysis_queue = []
analysis_lock = threading.Lock()

@mcp.tool()
def get_visual_debug_data() -> str:
    """
    Gets the latest visual debugging data from screen recordings.
    Call this tool when you need to understand what the user is seeing on their screen
    or to get context about recent user interactions.
    """
    with analysis_lock:
        if len(analysis_queue) == 0:
            return "No visual debugging data available. The user hasn't recorded any interactions yet."
        else:
            out = "Visual Debugging Data:\n\n"
            for i, item in enumerate(analysis_queue, 1):
                out += f"=== Interaction Session {i} ===\n"
                out += item + "\n\n"
            analysis_queue.clear()
            with status_lock:
                global status
                status = False
            return out


@mcp.tool()
def check_visual_debug_status() -> str:
    """
    Checks if new visual debugging data is available from screen recordings.
    Call this to see if the user has recorded new interactions that can be analyzed.
    """
    with status_lock:
        if status:
            return "New visual debugging data is available. Use get_visual_debug_data to retrieve it."
        return "No new visual debugging data available."

        
def async_main() -> None:
    """
    Asynchronously updates the analysis queue with new data.
    """
    engine = VideoEngine()
    while True:
        if engine.check_video():
            print("[Engine] Video ready for processing.")
            video_bytes = engine.get_video()
            # Here you would process the video bytes as needed
            # For this example, we just print the size
            analysis_result = analyze_video_from_ram(video_bytes)
            with analysis_lock:
                print("[Engine] Analysis complete, updating queue.")
                analysis_queue.append(analysis_result)
            with status_lock:
                global status
                status = True
        time.sleep(1)

if __name__ == "__main__":
    # Runs on stdio by default, perfect for local MCP integration
    threading.Thread(target=async_main, daemon=True).start()
    mcp.run()