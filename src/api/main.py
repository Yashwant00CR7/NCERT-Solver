from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from src.rag.rag_pipeline import RAGPipeline
from src.ingestion.ingest_books import DataIngestor
import os
import shutil
import json

app = FastAPI(title="NCERT Solver API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Pipeline (Note: This might be heavy for startup)
pipeline = RAGPipeline()
ingestor = DataIngestor()

class QueryRequest(BaseModel):
    query: str
    grade: Optional[str] = None
    subject: Optional[str] = None
    filename: Optional[str] = None
    conversation_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    query: str
    answer: str
    rating: int  # 1 for good, 0 for bad
    comments: Optional[str] = None

class MissionRequest(BaseModel):
    displayName: str
    readiness: float
    subjects_mastery: dict
    recent_activity: List[dict]
    persona: str

@app.get("/")
async def root():
    return {"message": "NCERT Solver API is running"}

@app.post("/chat")
async def chat(request: QueryRequest):
    try:
        response = pipeline.generate_response(
            query=request.query,
            grade=request.grade,
            subject=request.subject,
            filename=request.filename
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    grade: str = Form(...),
    subject: str = Form(...)
):
    # Save file to data/raw
    save_dir = os.path.join("data/raw", grade, subject)
    os.makedirs(save_dir, exist_ok=True)
    
    file_path = os.path.join(save_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Trigger ingestion
    try:
        ingestor.ingest_file(file_path)
        return {"status": "success", "message": f"File {file.filename} uploaded and indexed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    # Log feedback to a file or database
    feedback_path = "data/feedback.jsonl"
    with open(feedback_path, "a", encoding="utf-8") as f:
        f.write(request.json() + "\n")
    return {"status": "success"}

@app.get("/library")
async def get_library():
    """
    Returns a list of all processed chapters/books using their PDF filenames as titles.
    """
    processed_dir = "data/processed"
    if not os.path.exists(processed_dir):
        return {"subjects": []}
    
    library = {}
    
    for filename in os.listdir(processed_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(processed_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                metadata = data.get("metadata", {})
                subject = metadata.get("subject", "General")
                grade = metadata.get("grade", "10")
                filename_base = metadata.get("filename", filename)

                # Rename Social Science subjects to specific disciplines
                if "jess1" in filename_base or subject == "Social1":
                    subject = "Geography"
                elif "jess2" in filename_base or "Social-Economics" in subject:
                    subject = "Economics"
                elif "jess4" in filename_base or "Social-Politics" in subject:
                    subject = "Politics"
                elif "jess3" in filename_base:
                    subject = "History"
                
                # Use the original PDF filename from metadata as the title
                title = metadata.get("filename", filename)

                if subject not in library:
                    library[subject] = []
                
                library[subject].append({
                    "id": filename,
                    "title": title,
                    "grade": grade,
                    "filename": metadata.get("filename")
                })
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                
    formatted_library = []
    for subject, chapters in library.items():
        formatted_library.append({
            "subject": subject,
            "chapters": chapters
        })
        
    return {"subjects": formatted_library}

@app.post("/assessment")
async def generate_assessment(request: QueryRequest):
    """
    Generates flashcards and quizzes based on a topic or subject context.
    """
    try:
        # 1. Determine Namespace for retrieval
        namespace = None
        if request.subject and request.grade:
            namespace = f"{request.subject}_{request.grade}".replace(" ", "_")
        
        # 2. Retrieve context
        filters = {"filename": request.filename} if request.filename else None
        docs = pipeline.vector_store.search(request.query, namespace=namespace, k=8, filter=filters)
        
        if not docs:
            # Fallback: if no specific query matches, just get general subject context
            docs = pipeline.vector_store.search(request.subject or "NCERT", namespace=namespace, k=8, filter=filters)
            
        if not docs:
            raise HTTPException(status_code=404, detail="No content found to generate assessment.")
            
        context = "\n---\n".join([doc.page_content for doc in docs])
        
        # 3. Generate structured assessment
        prompt = f"""You are an educational assessment expert for NCERT curriculum. 
Using the context below, generate high-quality study materials for a student.

Context:
{context}

Output strictly in JSON format with the following structure:
{{
  "topic": "The main topic name",
  "flashcards": [
    {{"q": "Question/Term", "a": "Concise answer/definition"}},
    ... (at least 4)
  ],
  "quiz": [
    {{
      "q": "Multiple choice question",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": "Exact string of the correct option"
    }},
    ... (at least 3)
  ]
}}

Ensure questions are diverse and cover key concepts from the context.
"""
        raw_response = pipeline.generate_text(prompt)
        
        # Robust JSON extraction
        import re
        try:
            # Match the first outer-most JSON object
            # This regex looks for { ... } including nested braces
            # Because simple matching is hard with nested structures, we'll try a simpler approach first:
            # Find the first '{' and the last '}'
            start_idx = raw_response.find('{')
            end_idx = raw_response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                clean_json = raw_response[start_idx : end_idx + 1]
                return json.loads(clean_json)
            else:
                raise ValueError("No JSON object found in response")
        except json.JSONDecodeError:
            # Attempt to fix common JSON errors (like trailing commas) could go here
            # For now, let's retry logging and fall through
            print(f"JSON Parsing Failed. Raw output:\n{raw_response}")
            raise
    except Exception as e:
        print(f"Assessment generation error: {e}")
        # Return a fallback structure if parsing fails
        return {
            "topic": request.subject or "Study Session",
            "flashcards": [
                {"q": "Error generating flashcards", "a": "Please try a more specific topic."}
            ],
            "quiz": []
        }
@app.post("/mission")
async def generate_mission(request: MissionRequest):
    """
    Analyzes student data via LLM to generate a personalized daily mission.
    """
    try:
        # Construct the context for the LLM
        stats_context = f"""
        Student: {request.displayName}
        Persona: {request.persona}
        Current Readiness: {request.readiness}%
        Subject Mastery: {json.dumps(request.subjects_mastery)}
        Recent Activity: {json.dumps(request.recent_activity[:3])}
        """

        prompt = f"""You are an expert academic coach. Based on the student stats below, generate ONE high-impact 'Daily Mission' to help them improve.
        
        {stats_context}
        
        Requirements:
        1. Be specific (mention a subject or concept based on their low mastery).
        2. Be encouraging but direct.
        3. Output strictly in JSON format:
        {{
          "mission_title": "Short catchy title",
          "description": "Specific action to take",
          "target_subject": "Science/Math/etc",
          "reward_points": 50
        }}
        """
        
        raw_response = pipeline.generate_text(prompt)
        
        # Clean response
        clean_json = raw_response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
            
        return json.loads(clean_json)
    except Exception as e:
        print(f"Mission generation error: {e}")
        return {
            "mission_title": "Concept Deep Dive",
            "description": "Re-examine your last studied chapter to solidify understanding.",
            "target_subject": "General",
            "reward_points": 20
        }

@app.post("/mindmap")
async def generate_mindmap(request: QueryRequest):
    """
    Generates a Mermaid.js mindmap script based on a topic or chapter context.
    """
    try:
        # 1. Determine Namespace
        namespace = None
        if request.subject and request.grade:
            namespace = f"{request.subject}_{request.grade}".replace(" ", "_")
        
        # 2. Retrieve context for the mindmap
        filters = {"filename": request.filename} if request.filename else None
        docs = pipeline.vector_store.search(request.query, namespace=namespace, k=10, filter=filters)
        
        if not docs:
            docs = pipeline.vector_store.search(request.subject or "NCERT", namespace=namespace, k=10, filter=filters)
            
        if not docs:
            raise HTTPException(status_code=404, detail="No content found to generate mindmap.")
            
        context = "\n---\n".join([doc.page_content for doc in docs])
        
        # 3. Generate structured mindmap script
        # Simplified prompt for smaller models
        prompt = f"""Create a Mermaid.js mindmap for: {request.query}.
        
        Rules:
        1. Start strictly with 'mindmap'.
        2. Next line must be '  root(({request.query}))'.
        3. Use indentation for branches.
        4. No descriptions with colons (:), just short distinctive concepts.
        5. Output ONLY the code.

        Context to use:
        {context[:500]}...
        """
        mindmap_script = pipeline.generate_text(prompt)
        
        # Clean response
        import re
        raw_text = mindmap_script.strip()
        
        # 1. Extract code block if present
        code_block_pattern = r"```(?:mermaid)?(.*?)```"
        match = re.search(code_block_pattern, raw_text, re.DOTALL)
        if match:
            raw_text = match.group(1).strip()
        
        # 2. Check if valid mermaid
        if raw_text.startswith("mindmap"):
            clean_script = raw_text
        else:
            # FALLBACK: Convert structured text/outline to Mindmap
            lines = raw_text.split('\n')
            
            # Remove empty lines
            lines = [l for l in lines if l.strip()]
            
            clean_lines = ["mindmap"]
            # Root node
            clean_lines.append(f'  root(("{request.query}"))')
            
            for line in lines:
                stripped = line.lstrip()
                if not stripped: continue
                    
                # Calculate indent level (2 spaces = 1 level approx)
                indent_len = len(line) - len(stripped)
                level = (indent_len // 2) + 2 # Base indent is 2
                
                # Sanitize content
                # 1. Remove bullets
                content = re.sub(r"^[-*•0-9.]+\s*", "", stripped)
                # 2. Escape quotes and parens which break mermaid
                content = content.replace('"', "'").replace("(", "[").replace(")", "]")
                # 3. Limit length
                if len(content) > 50: content = content[:47] + "..."
                
                if not content: continue
                
                # Mermaid needs at least 2 spaces indent
                indent_str = " " * max(4, level * 2) 
                clean_lines.append(f"{indent_str}{content}")
                
            clean_script = "\n".join(clean_lines)
            
        return {"mindmap": clean_script}
    except Exception as e:
        print(f"MindMap generation error: {e}")
        return {"mindmap": f"mindmap\n  root((Error))\n    Failed to generate\n    {str(e)[:50]}"}

@app.post("/visual-solve")
async def visual_solve(
    file: UploadFile = File(...),
    grade: Optional[str] = Form(None),
    subject: Optional[str] = Form(None)
):
    """
    Analyzes an image (problem/diagram) and provides a solution using Vision LLM and RAG.
    """
    try:
        # 1. Save temp image
        temp_dir = "data/temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Extract context using Vision (Gemini)
        # Try to find Gemini in the pipeline
        gemini = next((llm for llm in pipeline.llms if "GeminiLLM" in str(type(llm))), None)
        
        if not gemini:
            # Fallback to OCR if Gemini Vision is not configured
            from src.ocr.ocr_engine import OCREngine
            ocr = OCREngine()
            extracted_text = ocr.extract_text_from_image(file_path)
            query = extracted_text
            vision_analysis = "Self-extracted text via OCR."
        else:
            # Step A: Get a descriptive analysis/extraction from Gemini Vision
            vision_prompt = """You are an NCERT AI assistant. 
            Analyze this image from a textbook or student notebook. 
            1. Extract any text or math problems.
            2. Describe any diagrams or graphs.
            3. Formulate a search query to find this topic in NCERT textbooks.
            
            Output in JSON format:
            {
              "extracted_query": "The text/problem found",
              "visual_description": "Description of diagrams",
              "search_query": "Key terms for RAG search"
            }
            """
            analysis_json = gemini.generate_from_image(vision_prompt, file_path)
            
            # Simple cleaning for JSON
            try:
                clean_json = analysis_json.strip()
                if clean_json.startswith("```json"): clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif clean_json.startswith("```"): clean_json = clean_json.split("```")[1].split("```")[0].strip()
                analysis = json.loads(clean_json)
                query = analysis.get("search_query", analysis.get("extracted_query", ""))
                vision_analysis = analysis.get("visual_description", "")
            except:
                query = "Problem from image"
                vision_analysis = analysis_json

        # 3. Perform RAG with the extracted query
        namespace = f"{subject}_{grade}".replace(" ", "_") if subject and grade else None
        docs = pipeline.vector_store.search(query, namespace=namespace, k=3)
        context = "\n---\n".join([doc.page_content for doc in docs]) if docs else "No direct text context found."

        # 4. Generate Final Solution
        final_prompt = f"""You are an elite NCERT tutor. 
        Solve the student's problem based on the visual input and retrieved textbook context.
        
        Visual Description: {vision_analysis}
        NCERT Context: {context}
        Extracted Problem: {query}
        
        Provide a detailed, step-by-step solution. If it's a diagram, explain its components based on NCERT syllabus.
        """
        
        solution = pipeline.generate_text(final_prompt)
        
        # Cleanup
        os.remove(file_path)
        
        return {
            "solution": solution,
            "query": query,
            "citations": [
                {"source": doc.metadata.get("filename"), "page": doc.metadata.get("page")} 
                for doc in docs
            ] if docs else []
        }
    except Exception as e:
        print(f"Visual solve error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
