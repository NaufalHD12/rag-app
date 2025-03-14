import streamlit as st
import pandas as pd
import os
import base64
import io
import tempfile
from functions import *

__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# Get API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def display_pdf(uploaded_file):
    """Display a PDF file with a more reliable method."""
    # Read file as bytes
    bytes_data = uploaded_file.getvalue()
    
    # Encode to base64
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    
    # Embed PDF viewer with iframe (can be more reliable in some browsers)
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def load_streamlit_page():
    """Load the Streamlit page with improved UI layout."""
    st.set_page_config(layout="wide", page_title="LLM x RAG", page_icon="📄")
    
    # Custom CSS for better UI
    st.markdown("""
        <style>
        .main {
            padding: 1rem 1rem;
        }
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            border-radius: 5px;
            padding: 0.5rem 1rem;
            font-weight: bold;
        }
        .css-1d391kg {
            padding-top: 3rem;
        }
        h1 {
            color: #1E3A8A;
        }
        h3 {
            color: #1E88E5;
            margin-top: 1rem;
        }
        .upload-section {
            background-color: #f8f9fa;
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("📂 RAG untuk Pendataan Support Layanan Sound System & Multimedia")
    st.markdown("Aplikasi ini membantu Anda mengekstrak informasi dari dokumen dan menyimpannya dalam format Excel.")
    
    st.markdown("---")
    
    return st

# Initialize session state variables if they don't exist
if 'vector_store' not in st.session_state:
    st.session_state.vector_store = None
    
if 'generated_data' not in st.session_state:
    st.session_state.generated_data = None
    
if 'merged_df' not in st.session_state:
    st.session_state.merged_df = None

# Initialize Streamlit page
st_page = load_streamlit_page()

# Create two columns for upload section
col1, col2 = st.columns([0.4, 0.6])

# Left column for uploads and controls
with col1:
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.subheader("📄 Unggah Dokumen")
    uploaded_pdf = st.file_uploader("Unggah Dokumen PDF:", type=["pdf"], help="Pilih file PDF yang ingin diproses")
    
    if uploaded_pdf is not None:
        st.success(f"✅ File berhasil diunggah: {uploaded_pdf.name}")
        
        if st.button("🔍 Ekstrak Informasi dari PDF", use_container_width=True):
            with st.spinner("Mengekstrak teks dari PDF..."):
                documents = get_pdf_text(uploaded_pdf)
                st.session_state.vector_store = create_vectorstore_from_texts(documents, file_name=uploaded_pdf.name)
                
                # Generate data after successful vector store creation
                with st.spinner("Menganalisis dokumen..."):
                    answer = query_document(
                        vectorstore=st.session_state.vector_store,
                        query="Berikan saya HARI (contoh: Senin), TANGGAL (contoh: 02 January 2025, nama bulan dalam bahasa Inggris), AGENDA (perihal kegiatan), LOKASI, REQUESTOR (lihat di yang menandatangani misal Section Head Safety, isikan Safety), LAYANAN (Sound System atau Sound System & Multimedia [contoh multimedia: proyektor, microphone, screen, dan lain-lain]), TYPE_ACARA (biarkan kosong), SITE (Bumi Patra, atau Kilang RU VI Balongan, atau Office RU VI Balongan, Pilih salah satu sesuaikan dengan lokasi), dan WORKING_HOUR (Yes atau No)."
                    )
                    st.session_state.generated_data = answer
                    
                    if not answer.empty:
                        st.success("✅ Data berhasil diekstrak!")
                    else:
                        st.error("❌ Gagal mengekstrak data. Silakan coba lagi.")
    
    st.markdown('<hr>', unsafe_allow_html=True)
    
    st.subheader("📊 Unggah File Excel")
    uploaded_excel = st.file_uploader("Unggah File Data Excel:", type=["xlsx"], 
                                      help="Pilih file Excel yang akan digabungkan dengan data hasil ekstraksi")
    
    if uploaded_excel is not None:
        st.success(f"✅ File Excel berhasil diunggah: {uploaded_excel.name}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Right column for PDF preview
with col2:
    # Show PDF preview only if uploaded
    if uploaded_pdf is not None:
        st.subheader("📑 Pratinjau PDF")
        display_pdf(uploaded_pdf)

# Display extracted data from PDF in full width
if st.session_state.generated_data is not None and not st.session_state.generated_data.empty:
    st.subheader("📋 Data Hasil Ekstraksi")
    st.dataframe(st.session_state.generated_data, use_container_width=True)
    
    # Process Excel file and show merge button only if both PDF data and Excel exist
    if uploaded_excel is not None:
        if st.button("🔄 Gabungkan Data", use_container_width=True):
            with st.spinner("Memproses file Excel..."):
                try:
                    excel_df = pd.read_excel(uploaded_excel, skiprows=3)
                    
                    # Correct column names
                    correct_columns = ["NO", "HARI", "TANGGAL", "AGENDA", "LOKASI", 
                                     "REQUESTOR", "LAYANAN", "TYPE_ACARA", "SITE", "WORKING_HOUR"]
                    
                    # Rename existing columns if necessary
                    if len(excel_df.columns) == len(correct_columns):
                        excel_df.columns = correct_columns
                    
                    # Format date column
                    excel_df["TANGGAL"] = pd.to_datetime(excel_df['TANGGAL'], errors='coerce').dt.strftime('%d %B %Y')
                    
                    # Convert NO to numeric and find the last number
                    excel_df["NO"] = pd.to_numeric(excel_df["NO"], errors="coerce")
                    last_no = excel_df["NO"].dropna().max() or 0
                    
                    # Add new data with incremented NO
                    generated_df = st.session_state.generated_data.copy()
                    generated_df.insert(0, "NO", range(int(last_no) + 1, int(last_no) + 1 + len(generated_df)))
                    
                    # Merge data
                    merged_df = pd.concat([excel_df, generated_df], ignore_index=True)
                    st.session_state.merged_df = merged_df
                    
                    st.success("✅ Data berhasil digabungkan!")
                except Exception as e:
                    st.error(f"❌ Terjadi kesalahan: {str(e)}")

# Show merged data in full width if available
if st.session_state.merged_df is not None:
    st.subheader("🔄 Data Gabungan")
    st.dataframe(st.session_state.merged_df, use_container_width=True, height=400)
    
    # Create Excel file for download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        st.session_state.merged_df.to_excel(writer, sheet_name="Sheet1", startrow=3, index=False)
        workbook = writer.book
        worksheet = writer.sheets["Sheet1"]
        
        # Set column widths
        column_widths = {"NO": 5, "HARI": 10, "TANGGAL": 15, "AGENDA": 50, "LOKASI": 25, 
                        "REQUESTOR": 20, "LAYANAN": 20, "TYPE_ACARA": 20, "SITE": 15, "WORKING_HOUR": 15}
        
        for col_num, (col_name, width) in enumerate(column_widths.items()):
            worksheet.set_column(col_num, col_num, width)
        
        # Add title formatting
        title_format = workbook.add_format({
            'bold': True, 
            'align': 'center', 
            'valign': 'vcenter', 
            'font_size': 14
        })
        
        # Add title
        worksheet.merge_range(1, 0, 1, len(st.session_state.merged_df.columns) - 1, 
                            "SUPPORT LAYANAN SOUND SYSTEM & MULTIMEDIA SSC ICT RU VI BALONGAN", title_format)
    
    output.seek(0)
    
    # Download button
    st.download_button(
        label="📥 Unduh Excel Hasil Gabungan",
        data=output,
        file_name="Support Sound Multimedia.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )