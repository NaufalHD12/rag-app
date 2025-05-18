import streamlit as st
import pandas as pd
import os
import base64
import io
from functions import *
from datetime import datetime

# Set page config FIRST - before any other Streamlit commands
st.set_page_config(
    layout="wide", 
    page_title="Alat LLM - Pendataan Sound System", 
    page_icon="🎤",
    initial_sidebar_state="expanded"
)

# Get API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Custom CSS for better styling
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Apply custom CSS
local_css("style.css")

def display_pdf(uploaded_file):
    """Display a PDF file in an iframe with improved styling."""
    bytes_data = uploaded_file.getvalue()
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    pdf_display = f'''
    <div class="pdf-container">
        <iframe src="data:application/pdf;base64,{base64_pdf}" 
                width="100%" 
                height="600px" 
                type="application/pdf"
                style="border: 1px solid #e1e4e8; border-radius: 8px;">
        </iframe>
    </div>
    '''
    st.markdown(pdf_display, unsafe_allow_html=True)

def load_streamlit_page():
    """Load the Streamlit page with improved UI layout."""
    # Header with logo and title - modified for better alignment
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        # Add vertical padding to the logo to align with text
        st.markdown("""
        <style>
        .aligned-logo {
            padding-top: 50px;
        }
        </style>
        <div class="aligned-logo">
        """, unsafe_allow_html=True)
        st.image("Logo.png", width=100)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.title("📂 PDF Extraction dan Data Entry Automation")
        st.markdown("**Pendataan Support Layanan Sound System & Multimedia**")
    
    st.markdown("---")
    
    # Main content columns
    col1, col2 = st.columns([0.4, 0.6], gap="large")
    
    with col1:
        with st.container(border=True):
            st.subheader("📤 Unggah Dokumen", divider="blue")
            st.markdown("Silakan unggah dokumen PDF dan file Excel template yang akan diproses.")
            
            uploaded_pdf = st.file_uploader(
                "📄 Dokumen PDF", 
                type=["pdf"],
                help="Unggah dokumen PDF yang berisi informasi jadwal kegiatan"
            )
            
            uploaded_excel = st.file_uploader(
                "📊 Template Excel", 
                type=["xlsx"],
                help="Unggah file Excel template untuk data pendukung"
            )
            
            # Help section
            with st.expander("ℹ️ Petunjuk Penggunaan"):
                st.markdown("""
                1. Unggah dokumen PDF yang berisi informasi jadwal
                2. Unggah template Excel yang akan diisi
                3. Klik tombol 'Extract informasi dari PDF'
                4. Periksa data yang dihasilkan
                5. Unduh file Excel yang sudah digabungkan
                """)
        
    return col1, col2, uploaded_pdf, uploaded_excel

# Initialize Streamlit page
col1, col2, uploaded_pdf, uploaded_excel = load_streamlit_page()

# Process PDF
if uploaded_pdf is not None:
    with col2:
        with st.container(border=True):
            st.subheader("📑 Pratinjau Dokumen", divider="green")
            display_pdf(uploaded_pdf)
    
    with st.spinner("🔍 Mengekstrak teks dari PDF..."):
        try:
            documents = get_pdf_text(uploaded_pdf)
            st.session_state.vector_store = create_vectorstore_from_texts(
                documents, 
                file_name=uploaded_pdf.name
            )
            st.toast("✅ PDF berhasil diproses!", icon="✅")
        except Exception as e:
            st.error(f"Gagal memproses PDF: {str(e)}")

# Generate table from PDF response
if uploaded_pdf is not None:
    extract_button = st.button(
        "🔍 Extract informasi dari PDF",
        type="primary",
        help="Klik untuk mengekstrak informasi dari dokumen PDF",
        use_container_width=True
    )
    
    if extract_button:
        with st.spinner("🧠 Menganalisis dokumen dan menghasilkan data tabel..."):
            try:
                answer = query_document(
                    vectorstore=st.session_state.vector_store,
                    query="Berikan saya HARI (contoh: Senin), TANGGAL (contoh: 02 January 2025, nama bulan dalam bahasa Inggris), AGENDA (perihal kegiatan), LOKASI, REQUESTOR (lihat di yang menandatangani misal Section Head Safety, isikan Safety), LAYANAN (Sound System atau Sound System & Multimedia [contoh multimedia: proyektor, microphone, screen, dan lain-lain]), TYPE_ACARA (biarkan kosong), SITE (Bumi Patra, atau Kilang RU VI Balongan, atau Office RU VI Balongan, Pilih salah satu sesuaikan dengan lokasi), dan WORKING_HOUR (Yes atau No)."
                )
                st.session_state.generated_data = pd.DataFrame(answer)
                
                # Display success and data
                st.toast("✅ Data berhasil diekstrak!", icon="✅")
                with st.expander("📊 Data yang Diambil dari PDF", expanded=True):
                    st.dataframe(
                        st.session_state.generated_data,
                        use_container_width=True,
                        hide_index=True
                    )
            except Exception as e:
                st.error(f"Gagal mengekstrak data: {str(e)}")

# Process Excel file and merge data
if uploaded_excel is not None:
    with st.spinner("📊 Memproses file Excel..."):
        try:
            excel_df = pd.read_excel(uploaded_excel, skiprows=3)
            excel_df.columns = ["NO", "HARI", "TANGGAL", "AGENDA", "LOKASI", 
                               "REQUESTOR", "LAYANAN", "TYPE_ACARA", "SITE", "WORKING_HOUR"]
            
            # Clean and format data
            excel_df["TANGGAL"] = pd.to_datetime(excel_df['TANGGAL'], errors='coerce').dt.strftime('%d %B %Y')
            excel_df["NO"] = pd.to_numeric(excel_df["NO"], errors="coerce")
            last_no = excel_df["NO"].dropna().max() or 0
            
            if "generated_data" in st.session_state:
                generated_df = st.session_state.generated_data.copy()
                generated_df.insert(0, "NO", range(int(last_no) + 1, int(last_no) + 1 + len(generated_df)))
                merged_df = pd.concat([excel_df, generated_df], ignore_index=True)
                st.session_state.merged_df = merged_df
                
                # Display merged data
                st.toast("✅ Data berhasil digabungkan!", icon="✅")
                with st.expander("🧩 Data yang Sudah Digabung", expanded=True):
                    st.dataframe(
                        merged_df,
                        use_container_width=True,
                        hide_index=True
                    )
                
                # Prepare Excel download
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    merged_df.to_excel(writer, sheet_name="Sheet1", startrow=3, index=False)
                    workbook = writer.book
                    worksheet = writer.sheets["Sheet1"]
                    
                    # Format columns
                    column_widths = {
                        "NO": 5, "HARI": 10, "TANGGAL": 15, "AGENDA": 30, 
                        "LOKASI": 25, "REQUESTOR": 20, "LAYANAN": 20, 
                        "TYPE_ACARA": 20, "SITE": 15, "WORKING_HOUR": 15
                    }
                    
                    for col_num, (col_name, width) in enumerate(column_widths.items()):
                        worksheet.set_column(col_num, col_num, width)
                    
                    # Add title and formatting
                    title_format = workbook.add_format({
                        'bold': True, 
                        'align': 'center', 
                        'valign': 'vcenter', 
                        'font_size': 14,
                        'font_name': 'Arial'
                    })
                    
                    worksheet.merge_range(
                        1, 0, 1, len(merged_df.columns) - 1, 
                        "SUPPORT LAYANAN SOUND SYSTEM & MULTIMEDIA SSC ICT RU VI BALONGAN", 
                        title_format
                    )
                
                output.seek(0)
                
                # Download button with improved styling
                st.download_button(
                    label="📥 Unduh Excel yang Digabung",
                    data=output,
                    file_name=f"Support_Sound_Multimedia_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                    help="Klik untuk mengunduh file Excel yang sudah digabungkan"
                )
                
        except Exception as e:
            st.error(f"Gagal memproses file Excel: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #666; font-size: 0.9em;">
        <p>© 2025 AI Tools - Pendataan Sound System & Multimedia | Version 1.0</p>
    </div>
    """,
    unsafe_allow_html=True
)