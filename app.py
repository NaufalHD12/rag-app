import streamlit as st
import pandas as pd
import os
import base64
import io
from functions import *

__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# Get API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def save_and_display_pdf(uploaded_file):
    """Save uploaded PDF and generate URL to view it."""
    file_path = f"./pdfs/{uploaded_file.name}"
    
    # Simpan file ke folder 'pdfs'
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Tampilkan link ke file
    st.markdown(f"[📄 View PDF](/{file_path})", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
if uploaded_file is not None:
    save_and_display_pdf(uploaded_file)


def load_streamlit_page():
    """Load the Streamlit page with improved UI layout."""
    st.set_page_config(layout="wide", page_title="LLM x RAG", page_icon="📄")
    st.title("📂 RAG untuk Pendataan Support Layanan Sound System & Multimedia")
    
    st.markdown("---")
    col1, col2 = st.columns([0.4, 0.6])
    
    with col1:
        st.subheader("Unggah Dokumen")
        uploaded_pdf = st.file_uploader("📄 Unggah Dokumen PDF:", type=["pdf"])
        uploaded_excel = st.file_uploader("📊 Unggah File Excel:", type=["xlsx"])
        
    return col1, col2, uploaded_pdf, uploaded_excel

# Initialize Streamlit page
col1, col2, uploaded_pdf, uploaded_excel = load_streamlit_page()

# Process PDF
if uploaded_pdf is not None:
    with col2:
        st.subheader("📑 Pratinjau PDF")
        save_and_display_pdf(uploaded_pdf)
    
    with st.spinner("Mengekstrak teks dari PDF..."):
        documents = get_pdf_text(uploaded_pdf)
        st.session_state.vector_store = create_vectorstore_from_texts(documents, file_name=uploaded_pdf.name)
        st.success("✅ PDF berhasil diproses!")

# Generate table from PDF response
if uploaded_pdf is not None and st.button("🔍 Extract informasi dari PDF"):
    with st.spinner("Generate data..."):
        answer = query_document(
            vectorstore=st.session_state.vector_store,
            query="Berikan saya HARI (contoh: Senin), TANGGAL (contoh: 02 January 2025, nama bulan dalam bahasa Inggris), AGENDA (perihal kegiatan), LOKASI, REQUESTOR (lihat di yang menandatangani misal Section Head Safety, isikan Safety), LAYANAN (Sound System atau Sound System & Multimedia [contoh multimedia: proyektor, microphone, screen, dan lain-lain]), TYPE_ACARA (biarkan kosong), SITE (Bumi Patra, atau Kilang RU VI Balongan, atau Office RU VI Balongan, Pilih salah satu sesuaikan dengan lokasi), dan WORKING_HOUR (Yes atau No)."
        )
        st.session_state.generated_data = pd.DataFrame(answer)
        st.success("✅ Berhasil generate data!")
        st.dataframe(st.session_state.generated_data)

# Process Excel file and merge data
if uploaded_excel is not None:
    with st.spinner("Memproses file Excel..."):
        excel_df = pd.read_excel(uploaded_excel, skiprows=3)
        excel_df.columns = {"NO": 5, "HARI": 10, "TANGGAL": 15, "AGENDA": 50, "LOKASI": 25, 
                           "REQUESTOR": 20, "LAYANAN": 25, "TYPE_ACARA": 20, "SITE": 15, "WORKING_HOUR": 15}
        excel_df["TANGGAL"] = pd.to_datetime(excel_df['TANGGAL'], errors='coerce').dt.strftime('%d %B %Y')
        excel_df["NO"] = pd.to_numeric(excel_df["NO"], errors="coerce")
        last_no = excel_df["NO"].dropna().max() or 0
    
    if "generated_data" in st.session_state:
        generated_df = st.session_state.generated_data.copy()
        generated_df.insert(0, "NO", range(int(last_no) + 1, int(last_no) + 1 + len(generated_df)))
        merged_df = pd.concat([excel_df, generated_df], ignore_index=True)
        st.session_state.merged_df = merged_df
        st.success("✅ Data berhasil diinput!")
        st.dataframe(merged_df)
    
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            merged_df.to_excel(writer, sheet_name="Sheet1", startrow=3, index=False)
            workbook = writer.book
            worksheet = writer.sheets["Sheet1"]
            column_widths = {"NO": 5, "HARI": 10, "TANGGAL": 15, "AGENDA": 30, "LOKASI": 25, "REQUESTOR": 20, "LAYANAN": 20, "TYPE_ACARA": 20, "SITE": 15, "WORKING_HOUR": 15}
            for col_num, (col_name, width) in enumerate(column_widths.items()):
                worksheet.set_column(col_num, col_num, width)
            title_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 14})
            worksheet.merge_range(1, 0, 1, len(merged_df.columns) - 1, "SUPPORT LAYANAN SOUND SYSTEM & MULTIMEDIA SSC ICT RU VI BALONGAN", title_format)
        output.seek(0)
    
        st.download_button(
            label="📥 Unduh Excel Baru",
            data=output,
            file_name="Support Sound Multimedia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )