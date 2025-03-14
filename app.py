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

def display_pdf(uploaded_file):
    """Provide a download button for the uploaded PDF."""
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        b64 = base64.b64encode(bytes_data).decode("utf-8")
        href = f'<a href="data:application/pdf;base64,{b64}" download="{uploaded_file.name}">📥 Download PDF</a>'
        st.markdown(href, unsafe_allow_html=True)

def load_page():
    """Load the Streamlit page with enhanced UI."""
    st.set_page_config(layout="wide", page_title="LLM x RAG", page_icon="📄")
    st.title("📂 RAG - Support Layanan Sound System & Multimedia")
    with st.sidebar:
        st.subheader("Unggah Dokumen")
        uploaded_pdf = st.file_uploader("📂 Upload PDF", type=["pdf"], key="pdf")
        uploaded_excel = st.file_uploader("📊 Unggah File Excel", type=["xlsx"])
    
    col1, col2 = st.columns([1, 2])
    return col1, col2, uploaded_pdf, uploaded_excel

# Initialize Streamlit page
col1, col2, uploaded_pdf, uploaded_excel = load_page()

if uploaded_pdf:
    with col1:
        st.write("## 📄 Preview PDF")
        display_pdf(uploaded_pdf)
    
    with st.spinner("Mengekstrak teks dari PDF..."):
        documents = get_pdf_text(uploaded_file)
        st.session_state.pdf_data = create_texts_dataset(documents, file_name=uploaded_file.name)
        st.success("✅ PDF berhasil diproses!")
    
    col2.download_button(
        label="⬇️ Unduh PDF", 
        data=uploaded_pdf.getvalue(),
        file_name=uploaded_pdf.name,
        mime='application/pdf'
    )

# Initialize Streamlit Page
col1, col2, uploaded_pdf, uploaded_excel = load_page()

def process_pdf_and_merge():
    """Process PDF and merge with Excel if provided."""
    if uploaded_pdf is not None:
        if 'pdf_data' not in st.session_state:
            st.warning("❌ Silakan proses PDF terlebih dahulu!")
            return
        pdf_df = st.session_state.pdf_data
    
    if uploaded_excel is not None:
        with st.spinner("Memproses file Excel..."):
            try:
                excel_df = pd.read_excel(uploaded_excel, skiprows=3)
                excel_df.columns = [col.strip() for col in excel_df.columns]  # Clean up column names
                excel_df['TANGGAL'] = pd.to_datetime(excel_df['TANGGAL'], errors='coerce').dt.strftime('%d %B %Y')
                excel_df['NO'] = pd.to_numeric(excel_df['NO'], errors='coerce')
                
                # Get the last number in NO column to continue numbering correctly
                last_num = excel_df['NO'].max() if not excel_df.empty else 0
                
                if uploaded_pdf is not None:
                    df_pdf = st.session_state.pdf_data
                    df_merged = pd.concat([excel_df, df_merged], ignore_index=True)
                    st.session_state.merged_df = df_merged
                    
                    # Display merged dataframe
                    st.success("✅ Data berhasil diinput!")
                    st.dataframe(df_merged)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_merged.to_excel(writer, sheet_name="Sheet1", index=False)
                        writer.book.close()
                    
                    output.seek(0)
                    st.download_button(
                        "📥 Unduh Data yang Diperbarui",
                        data=output,
                        file_name="Merged_Layanan_SSC.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
    else:
        st.warning("Harap unggah PDF terlebih dahulu!")

# Handle Button Actions
if uploaded_pdf is not None and st.button("🔍 Tampilkan PDF"):
    with col2:
        display_pdf(uploaded_pdf)
    
if uploaded_pdf is not None and st.button("📋 Extract informasi dari PDF"):
    process_pdf_and_merge()
    
if uploaded_excel is not None and 'merged_df' in st.session_state:
    st.subheader("📝 Data yang Diperbarui")
    st.dataframe(st.session_state.merged_df)
    
# Add spacing for UI aesthetics
st.markdown("---")
st.write("🔔 **Petunjuk:** Unggah dokumen PDF atau Excel yang sesuai untuk ekstraksi data otomatis.")

