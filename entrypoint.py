import uvicorn
import os
import sys

# Ensure backend dir is in path
sys.path.append(os.getcwd())

if __name__ == "__main__":
    try:
        print("Starting uvicorn server...")
        if os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
            print("Restoring serviceAccountKey.json from environment variable...")
            with open("serviceAccountKey.json", "w") as f:
                f.write(os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"))

        port = int(os.environ.get("PORT", 8000))
        print(f"Starting uvicorn server on port {port}...")
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        print(f"Server crashed with error: {e}")
        import traceback
        traceback.print_exc()
