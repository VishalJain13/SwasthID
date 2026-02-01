#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Update package lists and install Tesseract OCR
# Note: This runs in the build environment. 
# If Render requires sudo, it might fail, but this is the standard non-Docker approach.
apt-get update && apt-get install -y tesseract-ocr libtesseract-dev
