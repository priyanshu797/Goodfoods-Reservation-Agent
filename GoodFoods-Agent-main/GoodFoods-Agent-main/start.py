import subprocess
import threading
import time
import webbrowser
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def check_env():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        print("=" * 60)
        print("ERROR: GROQ_API_KEY not found in .env file.")
        print("  Add:  GROQ_API_KEY=your_key_here")
        print("  Get a free key: https://console.groq.com")
        print("=" * 60)
        sys.exit(1)
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    print(f"✓ GROQ_API_KEY found")
    print(f"✓ Groq model: {groq_model}")


def start_flask_server():
    """Start Flask backend from project root."""
    flask_app = os.path.join(PROJECT_ROOT, "data", "service_api.py")
    try:
        print("Starting Flask server on http://localhost:8000 ...")
        subprocess.Popen(
            [sys.executable, flask_app],
            cwd=PROJECT_ROOT,
        )
    except Exception as e:
        print(f"Error starting Flask server: {e}")


def start_streamlit_app():
    """Start Streamlit frontend (blocking)."""
    app_path = os.path.join(PROJECT_ROOT, "app_goodfoods.py")
    try:
        print("Starting Streamlit app...")
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", app_path],
            cwd=PROJECT_ROOT,
        )
    except Exception as e:
        print(f"Error starting Streamlit app: {e}")


def wait_for_server(max_retries=15, delay=1.0):
    import requests
    for attempt in range(1, max_retries + 1):
        try:
            requests.get("http://localhost:8000/", timeout=2)
            print(f"✓ Flask server is running (attempt {attempt}/{max_retries})")
            return True
        except Exception:
            print(f"  Waiting for server... ({attempt}/{max_retries})")
            time.sleep(delay)
    print("⚠  Warning: Server did not start in time. Check data/service_api.py manually.")
    return False

if __name__ == "__main__":
    print("   GoodFoods Reservation Assistant")
    print("   Powered by Groq LLM + Flask + Streamlit")
    print(f"   Project root: {PROJECT_ROOT}")

    check_env()
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()
    wait_for_server(max_retries=15, delay=1.0)

    print("\nLaunching Streamlit UI at http://localhost:8501")
    print("Press Ctrl+C to stop.\n")
    start_streamlit_app()