import uvicorn
import os
import sys

# Ensure backend dir is in path
sys.path.append(os.getcwd())

if __name__ == "__main__":
    try:
        print("Starting uvicorn server...")
        print("DEBUG: Current Environment Keys:")
        for key in os.environ.keys():
            if "FIREBASE" in key:
                print(f"  - Found Key with FIREBASE: '{key}'")
            else:
                # Print only first 3 chars to identifying keys without leaking secrets
                print(f"  - {key}")

        firebase_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if firebase_json:
            print(f"Restoring serviceAccountKey.json... (Length: {len(firebase_json)})")
            # Create file in absolute path /app/serviceAccountKey.json to be safe
            with open("/app/serviceAccountKey.json", "w") as f:
                f.write(firebase_json)
            print("Successfully wrote /app/serviceAccountKey.json")
        else:
            print("CRITICAL WARNING: FIREBASE_SERVICE_ACCOUNT_JSON environment variable is MISSING or EMPTY!")
            print("The app will crash when initializing Firebase.")

        port = int(os.environ.get("PORT", 8000))
        print(f"Starting uvicorn server on port {port}...")
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        print(f"Server crashed with error: {e}")
        import traceback
        traceback.print_exc()
