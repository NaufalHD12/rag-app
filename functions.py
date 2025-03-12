from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.vectorstores import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

import os
import tempfile
import uuid
import pandas as pd
import re
import json
from dotenv import load_dotenv

__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')


# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def clean_filename(filename):
    # First, remove file extension if present
    name_without_ext = re.sub(r'\.[^.]+$', '', filename)
    
    # Remove the "(number)" pattern
    name_without_numbers = re.sub(r'\s\(\d+\)', '', name_without_ext)
    
    # Replace spaces, dots, and other non-allowed chars with underscores
    # Keep only alphanumeric, underscores, and hyphens
    clean_name = re.sub(r'[^\w\-]', '_', name_without_numbers)
    
    # Remove consecutive underscores
    clean_name = re.sub(r'_{2,}', '_', clean_name)
    
    # Ensure the name starts and ends with alphanumeric characters
    clean_name = re.sub(r'^[^a-zA-Z0-9]+', '', clean_name)  # Remove non-alphanumeric chars at start
    clean_name = re.sub(r'[^a-zA-Z0-9]+$', '', clean_name)  # Remove non-alphanumeric chars at end
    
    # Ensure the name is not too long (max 63 chars)
    if len(clean_name) > 63:
        clean_name = clean_name[:63]
        # Make sure it still ends with an alphanumeric character
        clean_name = re.sub(r'[^a-zA-Z0-9]+$', '', clean_name)
    
    # Make sure it's at least 3 characters long
    if len(clean_name) < 3:
        clean_name = clean_name + "doc"  # Add "doc" suffix if name is too short
    
    return clean_name

def get_pdf_text(uploaded_file): 
    try:
        input_file = uploaded_file.read()
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(input_file)
        temp_file.close()
        loader = PyPDFLoader(temp_file.name)
        documents = loader.load()
        return documents
    finally:
        os.unlink(temp_file.name)

def split_document(documents, chunk_size=1500, chunk_overlap=200):    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " "]
    )
    return text_splitter.split_documents(documents)

def get_embedding_function():
    return OpenAIEmbeddings(
        model="text-embedding-ada-002", 
        openai_api_key=OPENAI_API_KEY
    )

def create_vectorstore(chunks, embedding_function, file_name, vector_store_path="db"):
    ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.page_content)) for doc in chunks]
    unique_ids = set()
    unique_chunks = []
    for chunk, id in zip(chunks, ids):     
        if id not in unique_ids:       
            unique_ids.add(id)
            unique_chunks.append(chunk)        
    vectorstore = Chroma.from_documents(
        documents=unique_chunks, 
        collection_name=clean_filename(file_name),
        embedding=embedding_function, 
        ids=list(unique_ids), 
        persist_directory=vector_store_path
    )
    vectorstore.persist()
    return vectorstore

def create_vectorstore_from_texts(documents, file_name):
    docs = split_document(documents)
    embedding_function = get_embedding_function()
    vectorstore = create_vectorstore(docs, embedding_function, file_name)
    return vectorstore

def load_vectorstore(file_name, vectorstore_path="db"):
    embedding_function = get_embedding_function()
    return Chroma(
        persist_directory=vectorstore_path, 
        embedding_function=embedding_function, 
        collection_name=clean_filename(file_name)
    )

PROMPT_TEMPLATE = """
Anda adalah staf data entry yang ditugaskan untuk mengekstrak informasi dari dokumen surat. 
Jika agenda lebih dari sehari maka jumlah json dibuat sesuai dengan jumlah hari.
Gunakan potongan konteks yang diberikan di bawah ini untuk menjawab pertanyaan.
Berikan jawaban dalam format JSON dengan struktur berikut:

{{
    "HARI": "string",
    "TANGGAL": "date",
    "AGENDA": "string",
    "LOKASI": "string",
    "REQUESTOR": "string",
    "LAYANAN": "string",
    "TYPE_ACARA": "string",
    "SITE": "string",
    "WORKING_HOUR": "string"
}}

Konteks:
{context}

---

Jawablah pertanyaan berikut berdasarkan konteks di atas dalam format JSON:
{question}
"""

def format_docs(docs):
    """
    Format a list of Document objects into a single string.

    :param docs: A list of Document objects

    :return: A string containing the text of all the documents joined by two newlines
    """
    return "\n\n".join(doc.page_content for doc in docs)

def query_document(vectorstore, query):
    """
    Query a vector store with a question and return a structured response.

    :param vectorstore: A Chroma vector store object
    :param query: The question to ask the vector store

    :return: A pandas DataFrame with structured response
    """
    # Define expected columns to ensure consistent schema
    expected_columns = [
        "HARI", "TANGGAL", "AGENDA", "LOKASI", 
        "REQUESTOR", "LAYANAN", "TYPE_ACARA", "SITE", "WORKING_HOUR"
    ]

    llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)

    retriever = vectorstore.as_retriever(search_type="similarity")

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)

    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt_template
        | llm
    )

    response = rag_chain.invoke(query)

    # Extensive debugging
    print("=" * 50)
    print("DEBUG: Tipe Respons Mentah:", type(response))
    print("DEBUG: Konten Respons Mentah:", response)
    
    # Extract content robustly
    try:
        if hasattr(response, 'content'):
            raw_text = response.content
        elif isinstance(response, str):
            raw_text = response
        else:
            raw_text = str(response)
    except Exception as e:
        print(f"Error saat mengekstrak konten: {e}")
        return pd.DataFrame(columns=expected_columns)

    # Clean the text
    cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
    
    print("DEBUG: Teks yang Dibersihkan:", cleaned_text)
    print("=" * 50)

    # Parsing attempts
    try:
        # Try parsing as a JSON array
        if cleaned_text.startswith('[') and cleaned_text.endswith(']'):
            try:
                parsed_data = json.loads(cleaned_text)
                df = pd.DataFrame(parsed_data)
            except json.JSONDecodeError:
                print("Gagal parsing sebagai array JSON")
                df = pd.DataFrame()

        # Try parsing as a single JSON object
        elif cleaned_text.startswith('{') and cleaned_text.endswith('}'):
            try:
                parsed_data = json.loads(cleaned_text)
                df = pd.DataFrame([parsed_data])
            except json.JSONDecodeError:
                print("Gagal parsing sebagai objek JSON")
                df = pd.DataFrame()

        # Try extracting JSON objects
        else:
            # Use regex to find potential JSON objects
            json_objects = re.findall(r'\{[^{}]+\}', cleaned_text)
            results = []
            
            for obj in json_objects:
                try:
                    parsed_obj = json.loads(obj)
                    results.append(parsed_obj)
                except json.JSONDecodeError:
                    continue
            
            df = pd.DataFrame(results) if results else pd.DataFrame()

        # Enforce schema
        if df.empty:
            df = pd.DataFrame(columns=expected_columns)
        else:
            # Ensure all expected columns exist
            for col in expected_columns:
                if col not in df.columns:
                    df[col] = None

            # Reorder columns
            df = df.reindex(columns=expected_columns)

    except Exception as e:
        print(f"Error Parsing Akhir: {e}")
        df = pd.DataFrame(columns=expected_columns)

    return df