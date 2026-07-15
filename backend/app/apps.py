import threading
import asyncio
# pyrefly: ignore [missing-import]
from django.apps import AppConfig

class InquixConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        from app.services.embedding import ensure_models

        def run_ensure_models():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(ensure_models())
            except Exception as e:
                print(f"Warning: Could not verify Ollama models: {e}")

        threading.Thread(target=run_ensure_models, daemon=True).start()
