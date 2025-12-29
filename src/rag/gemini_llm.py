import google.generativeai as genai
import os
from dotenv import load_dotenv

class GeminiLLM:
    def __init__(self, model_name="gemini-2.5-flash"):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt):
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating content with Gemini: {e}"

    def generate_from_image(self, prompt, image_path):
        """
        Supports analysis of images (diagrams, math, etc) with a prompt.
        """
        try:
            import PIL.Image
            img = PIL.Image.open(image_path)
            # Use 'gemini-1.5-flash' or 'gemini-1.5-pro' for vision
            response = self.model.generate_content([prompt, img])
            return response.text
        except Exception as e:
            return f"Error in Vision generation: {e}"

if __name__ == "__main__":
    # Test
    # llm = GeminiLLM()
    # print(llm.generate("Hello!"))
    pass
