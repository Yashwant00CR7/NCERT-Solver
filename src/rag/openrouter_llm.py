import os
import requests
import json

class OpenRouterLLM:
    def __init__(self, model_name="qwen/qwen3-4b:free", api_key=None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not self.api_key:
            print("Warning: OPENROUTER_API_KEY is not set.")

    def generate(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "NCERT Solver",
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            # "provider": { "ignore": ["Venice"] } # Optional: ignore specific providers if they are problematic
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            # OpenRouter standard OpenAI-compatible response format
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                return f"Error: Unexpected response format from OpenRouter: {result}"
        except Exception as e:
            # Basic error handling
            # If response has detailed error message, try to extract it
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response is not None:
                     error_msg += f" Response: {e.response.text}"
            except:
                pass
            raise RuntimeError(f"OpenRouter failure: {error_msg}")

if __name__ == "__main__":
    # Test
    # llm = OpenRouterLLM()
    # print(llm.generate("Hello!"))
    pass
