import os
import io
import time
import json
from twelvelabs import TwelveLabs
from twelvelabs.types import ResponseFormat


def analyze_video_from_ram(video_bytes: bytes, timeout_seconds: int = 300):
    api_key = os.getenv("TL_API_KEY")
    tl_id = os.getenv("TL_ID")
    #if not api_key:
    #    raise RuntimeError("TL_API_KEY is not set in the environment")

    client = TwelveLabs(api_key=api_key)

    # 1. Wrap the raw bytes in a file-like object
    video_stream = io.BytesIO(video_bytes)
    # Important: Give it a name so the SDK/API knows the file extension
    video_stream.name = "recording.mp4"
    # Ensure the stream is at the start
    #video_stream.seek(0)

    # 2. Create an Index (consider reusing an existing index in production)
    index = client.indexes.create(
        index_name="RAM-Debug-Index",
        models=[{"model_name": "pegasus1.2", "model_options": ["visual"]}]
    )

    print("Uploading recording from RAM...")

    try:
        # 3. Upload directly from the BytesIO stream
        asset = client.assets.create(
            method="direct",
            file=video_stream  # The SDK reads from RAM here
        )

        # 4. Indexing & Polling with timeout and backoff
        indexed_asset = client.indexes.indexed_assets.create(
            index_id=tl_id,
            asset_id=asset.id
        )

        start_time = time.time()
        sleep_seconds = 1
        while True:
            status_check = client.indexes.indexed_assets.retrieve(
                index_id=tl_id,
                indexed_asset_id=indexed_asset.id
            )
            if getattr(status_check, "status", None) == "ready":
                break
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"Indexing timed out after {timeout_seconds} seconds")
            time.sleep(sleep_seconds)
            sleep_seconds = min(sleep_seconds * 2, 10)

        # 5. Analysis
        analysis = client.analyze(
            video_id=indexed_asset.id,
            prompt=
            """
            Your purpose is to be an observer and provide context based on a video you are given.
            Give a detailed summary of the video content and and explain in a step by step process what is happening. 
            Please also note that the cursor appears as a white triangle, and when the user left clicks it flashes green and when the user right clicks it flashes red however do not mention the cursor colors in the summary.
            This summary should also include any cursor/keyboard movement that occurs and the effects of such cursor/keyboard movement, please be precise as to what happens when the user left or right clicks.
            Do NOT mention the mouse color changing at all, only use the information about the cursor changing color as information for yourself.
            Also, do NOT make any assumptions about anything not clearly shown in the video, no assumptions should be made about anything. 
            """,
            response_format=ResponseFormat(
                json_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "code_fix": {"type": "string"}
                    },
                },
            ),
        )

        analysis = json.loads(analysis.data) if analysis.data else {}
        analysis = analysis.get('summary')
        return analysis
    finally:
        try:
            video_stream.close()
        except Exception:
            pass

def find_index_id():
    client = TwelveLabs(api_key='tlk_31BEGBV0ACAK722RC4Y5R35MM3D5')
    indexes = client.indexes.list()
    # List all indexes and find the one named "Debug-Analysis-Index"
    for index in indexes:
        print(f"Name: {index.index_name}, ID: {index.id}")
    return None

def main():
    # Example usage
    with open("VideoTests/Capybara_test_score400.mp4", "rb") as f:
        video_data = f.read()
    
    result = analyze_video_from_ram(video_data)
    print("Analysis Result:", result)
    return result

# main()
#find_index_id()