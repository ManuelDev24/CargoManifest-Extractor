import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ANTIGRAVITY_API_KEY")

if not api_key:
    raise RuntimeError("ANTIGRAVITY_API_KEY no está configurada")

print("========================================")
print("ANTIGRAVITY API CONFIGURATION TEST")
print("========================================")
print("API key encontrada: OK")
print(f"Longitud de la API key: {len(api_key)}")
print("========================================")
