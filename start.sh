#!/bin/sh
echo "Starting app on port $PORT"
uvicorn app.main:app --host 0.0.0.0 --port $PORT
