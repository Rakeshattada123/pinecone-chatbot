# main.py

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from pinecone import Pinecone

# --- THIS IS THE FIX: Import CORSMiddleware ---
from fastapi.middleware.cors import CORSMiddleware

from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding

# Load Environment Variables
load_dotenv()

# Global State
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... (Your existing lifespan code, no changes needed here)
    print("--- Server Starting Up ---")
    try:
        print("1. Configuring LlamaIndex settings...")
        Settings.llm = Gemini(model_name="models/gemini-1.5-flash", api_key=os.getenv("GOOGLE_API_KEY"))
        Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001", api_key=os.getenv("GOOGLE_API_KEY"))
        
        print("2. Initializing Pinecone connection...")
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index_name = "gemini-chatbot"
        
        if index_name not in pc.list_indexes().names():
            raise RuntimeError(f"Pinecone index '{index_name}' not found. Please run setup_index.py.")
            
        pinecone_index = pc.Index(index_name)

        print("3. Loading vector store and index...")
        vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

        print("4. Creating chat engine...")
        app_state["chat_engine"] = index.as_chat_engine(chat_mode="context", llm=Settings.llm, verbose=False)
        print("✅ Startup complete.")
    
    except Exception as e:
        print(f"❌ An error occurred during startup: {e}")
        raise RuntimeError(f"Server startup failed: {e}")

    yield
    
    print("--- Server Shutting Down ---")
    app_state.clear()


# Initialize FastAPI App
app = FastAPI(
    title="RAG Chatbot API",
    lifespan=lifespan
)


# --- Add CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Pydantic Models and the rest of your API endpoints...
# (No changes needed below this line)
class QueryRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str

@app.post("/chat", response_model=ChatResponse)
async def chat_with_bot(request: Request, query_request: QueryRequest):
    if "chat_engine" not in app_state:
        raise HTTPException(status_code=503, detail="Chat engine is not available.")
    if not query_request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        chat_engine = app_state["chat_engine"]
        response = await chat_engine.achat(query_request.query)
        if not response or not response.response:
             raise HTTPException(status_code=500, detail="Failed to get a valid response.")
        return ChatResponse(answer=response.response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Chatbot API is running and ready for frontend connections."}