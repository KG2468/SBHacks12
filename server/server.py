from mcp.server.fastmcp import FastMCP
from video_engine import engine

# Define the server
mcp = FastMCP("Visual Debugger")

@mcp.tool()
def check_status() -> str:
    """
    Displays whether there is new visual debugging data available.
    """
    
    


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