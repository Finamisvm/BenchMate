import requests
import time

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def generate(self, model: str, prompt: str, temperature: float = 0.0, max_tokens: int = 512, timeout: int = 120):
        """
        Call Ollama's /api/generate endpoint with streaming disabled.
        Returns (text, latency_ms).
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        t0 = time.perf_counter()
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            text = data.get("response", "")
        except Exception as e:
            text = f"__ERROR__: {e}"
        dt_ms = int((time.perf_counter() - t0) * 1000)
        return text, dt_ms
