import os
print(f"Key: {os.environ.get('GEMINI_API_KEY', 'NOT SET')[:40]}...")
