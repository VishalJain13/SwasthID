import os
import google.generativeai as genai

# ----------------------------------
# Load Gemini API Key
# ----------------------------------
# Try strictly loading from parent .env if missing
if not os.getenv("GEMINI_API_KEY"):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini (Soft fail if missing)
model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-flash-latest")
    except Exception as e:
        print(f"⚠️ Gemini Config Error: {e}")
else:
    print("⚠️ Warning: GEMINI_API_KEY not found in rag.py. AI features disabled.")

# ----------------------------------
# Swasth AI Core Function
# ----------------------------------
def swasth_ai_answer(context: str, question: str, image_data: bytes = None) -> str:
    prompt = f"""
You are Swasth AI, a public health assistant for India.

RULES:
1. Answer ONLY health, disease, hygiene, nutrition, prevention, medical awareness, or prescription explanation questions.
2. If the question is NOT health-related, reply exactly:
   "I can only assist with health-related questions."
3. You MAY use general medical knowledge for awareness.
4. If patient-specific data is available in context, use it.
5. If an image is provided (e.g., prescription, report, symptoms), analyze it carefully.
6. DO NOT prescribe medicines or dosages.
7. DO NOT make final diagnoses.
8. Keep answers simple, safe, and understandable for the public.

CONTEXT:
{context}

QUESTION:
{question}
"""

    if not model:
        return "Swasth AI is unavailable (API Key missing)."

    try:
        content = [prompt]
        if image_data:
            import PIL.Image
            import io
            image = PIL.Image.open(io.BytesIO(image_data))
            content.append(image)
            
        response = model.generate_content(content)
        return response.text.strip()
    except Exception as e:
        return f"Error: {e}"
