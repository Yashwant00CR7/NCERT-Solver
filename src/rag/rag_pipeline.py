import os
import langdetect
from src.ingestion.vector_store import VectorStoreManager

class RAGPipeline:
    def __init__(self):
        self.vector_store = VectorStoreManager()
        
        # Priority: Ollama -> Gemini -> Local
        self.llms = []
        
        ollama_model = os.getenv("OLLAMA_MODEL")
        if ollama_model:
            from src.rag.ollama_llm import OllamaLLM
            self.llms.append(OllamaLLM(model_name=ollama_model))
            print(f"Ollama ({ollama_model}) added to pipeline.")

        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            from src.rag.gemini_llm import GeminiLLM
            self.llms.append(GeminiLLM())
            print("Gemini API added to pipeline.")

        # Always add local as ultra-fallback if nothing else works
        try:
            from src.rag.local_llm import LocalLLM
            self.llms.append(LocalLLM())
            print("Local LLM added as fallback.")
        except Exception as e:
            print(f"Could not initialize local LLM: {e}")
        
    def generate_text(self, prompt):
        """
        Helper to generate text using the available LLM chain with full fallback.
        """
        for llm in self.llms:
            try:
                response = llm.generate(prompt)
                print(f"Text generated using {llm.__class__.__name__}.")
                return response
            except Exception as e:
                print(f"Provider {llm.__class__.__name__} failed: {e}. Trying fallback...")
                continue
        return "I am sorry, but all my AI brains are currently offline."

    def generate_response(self, query, grade=None, subject=None, filename=None):
        """
        Full RAG flow: Retrieve -> Augment -> Generate
        """
        # 1. Detection & Filtering
        try:
            lang = langdetect.detect(query)
        except:
            lang = "en"
            
        filters = {}
        if filename:
            filters["filename"] = filename
        
        # 2. Retrieval
        print(f"Querying Knowledge Base: '{query}'...")
        subject_grade_namespace = None
        if subject and grade:
            subject_grade_namespace = f"{subject}_{grade}".replace(" ", "_")
        
        docs = self.vector_store.search(query, namespace=subject_grade_namespace, k=3, filter=filters if filters else None)
        print(f"Found {len(docs)} relevant context blocks.")
        
        if not docs:
            return {
                "answer": "I am sorry, but I don't have information about that in my NCERT knowledge base.",
                "citations": []
            }
            
        context = "\n---\n".join([doc.page_content for doc in docs])
        
        # 3. Augmentation (Prompt Engineering)
        prompt = self._build_prompt(query, context, lang)
        
        # 4. Generation
        print("Brain is thinking (Generating response)...")
        response_text = self.generate_text(prompt)
        print("Response generated.")
        
        # 5. Citations
        citations = []
        for doc in docs:
            citations.append({
                "source": doc.metadata.get("filename", "Unknown"),
                "page": doc.metadata.get("page", "?"),
                "grade": doc.metadata.get("grade", "?"),
                "subject": doc.metadata.get("subject", "?")
            })
            
        return {
            "answer": response_text,
            "citations": citations,
            "detected_language": lang
        }

    def _build_prompt(self, query, context, lang):
        # Map detected language codes to full names for better LLM instruction
        lang_map = {
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu",
            "kn": "Kannada",
            "ml": "Malayalam",
            "bn": "Bengali",
            "mr": "Marathi",
            "gu": "Gujarati",
            "pa": "Punjabi"
        }
        
        target_lang = lang_map.get(lang, "the same language as the question")
        
        return f"""You are an elite academic assistant specializing in the NCERT curriculum. 
Answer the student's question using ONLY the provided context. 

RULES:
1. Ground your answer strictly in the provided NCERT context.
2. Provide a clear, step-by-step explanation suitable for a student.
3. If the answer is not in the context, say "I don't have this specific information in the current NCERT context."
4. CRITICAL: You MUST respond in {target_lang}.

Context:
{context}

Question: {query}
Answer:"""

if __name__ == "__main__":
    # Example usage
    # pipeline = RAGPipeline()
    # print(pipeline.generate_response("What is the capital of India?"))
    pass
