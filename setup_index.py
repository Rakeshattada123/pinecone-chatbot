# setup_index.py

import os
from dotenv import load_dotenv
from pinecone import Pinecone, PodSpec

from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    Settings
)
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding

# --- 1. Load Environment Variables and API Keys ---
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")

if not all([GOOGLE_API_KEY, PINECONE_API_KEY, PINECONE_ENVIRONMENT]):
    raise ValueError("API keys and environment must be set in the .env file.")

# --- 2. Configure LlamaIndex Global Settings ---
# This ensures all components use the same models
print("Configuring LlamaIndex settings...")
llm = Gemini(
    model_name="models/gemini-1.5-flash", 
    api_key=GOOGLE_API_KEY
)

# The 'models/embedding-001' has a dimension of 768
embed_model = GeminiEmbedding(
    model_name="models/embedding-001", 
    api_key=GOOGLE_API_KEY
)

Settings.llm = llm
Settings.embed_model = embed_model
Settings.chunk_size = 1000
Settings.chunk_overlap = 50

# --- 3. Initialize Pinecone ---
print("Initializing Pinecone...")
pc = Pinecone(api_key=PINECONE_API_KEY)

index_name = "gemini-chatbot"
# The embedding dimension for "models/embedding-001" is 768
embedding_dimension = 768 

if index_name not in pc.list_indexes().names():
    print(f"Creating new Pinecone index: {index_name}")
    pc.create_index(
        name=index_name,
        dimension=embedding_dimension,
        metric="cosine",
        spec=PodSpec(environment=PINECONE_ENVIRONMENT)
    )
    print("Index created successfully.")
else:
    print(f"Pinecone index '{index_name}' already exists. Skipping creation.")

pinecone_index = pc.Index(index_name)

# --- 4. Load Documents and Build Index ---
pdf_path = "thebook.pdf"
if not os.path.exists(pdf_path):
    raise FileNotFoundError(f"The file '{pdf_path}' was not found. Please make sure it's in the same directory.")

print(f"Loading documents from '{pdf_path}'...")
try:
    documents = SimpleDirectoryReader(input_files=[pdf_path]).load_data()
    print(f"Loaded {len(documents)} document chunks.")
except Exception as e:
    print(f"Error loading the PDF file: {e}")
    exit()

# --- 5. Create Storage Context and Store in Pinecone ---
print("Creating storage context and vector store...")
vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

print("Creating index and storing embeddings in Pinecone... This may take a few moments.")
# This will use the global Settings.embed_model (GeminiEmbedding)
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
    show_progress=True
)

print("\n✅ Setup complete! Your PDF has been indexed and stored in Pinecone.")
print("You can now run the FastAPI application using: uvicorn main:app --reload")

