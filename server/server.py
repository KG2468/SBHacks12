from mcp.server.fastmcp import FastMCP
from video_engine import engine

# Define the server
mcp = FastMCP("Visual Debugger")

@mcp.tool()
def check_status() -> str:
    """
    Checks the status of the debugging session.
    
    - If the system is IDLE, this automatically starts the Screen Recorder.
    - If the system is BUSY, it returns the current progress.
    - If the system is READY, it tells you to call 'get_debugged_code'.
    """
    
    # 1. If we have a result, tell the agent
    if engine.analysis_ready:
        return "YES. The analysis is finished. Call 'get_debugged_code' to retrieve the fix."

    # 2. If we are already working, report status
    if engine.is_running:
        return f"WAIT. {engine.status_message}"

    # 3. If idle, start the process automatically
    engine.trigger_session()
    return "STARTED. I have begun watching the screen for activity. Check back in a moment."


@mcp.tool()
def get_debugged_code() -> str:
    """
    Retrieves the final code fix from the analyzed video.
    This consumes the result and resets the recorder for the next session.
    """
    result = engine.get_result()
    
    if result is None:
        return "ERROR: No code is ready yet. Please call 'check_status' first."
        
    return f"--- DEBUGGED CODE ---\n\n{result}"

if __name__ == "__main__":
    # Runs on stdio by default, perfect for local MCP integration
    mcp.run()