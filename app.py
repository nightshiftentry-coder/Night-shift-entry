import streamlit as st
import easyocr
import pandas as pd
from PIL import Image
import numpy as np
import re
import io

st.set_page_config(page_title="12 AM DCS Midnight Logger", layout="wide")

@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr_reader()

st.title("⚡ 12 AM DCS Midnight Data Logger")
st.caption("Upload DCS screen photos to auto-detect readings, verify/edit values, and export to Excel.")

# File Uploader
uploaded_files = st.file_uploader(
    "Upload DCS Photos (Select one or multiple images)",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

def parse_dcs_image(img_np):
    """Runs OCR and extracts Unit and key numeric parameters."""
    results = reader.readtext(img_np, detail=0)
    full_text = " ".join(results).upper()
    
    # 1. Detect Unit
    unit = "Unknown"
    if re.search(r'\b(UNIT[\s\-_]*1|U[\s\-_]*1|U#1)\b', full_text):
        unit = "Unit 1"
    elif re.search(r'\b(UNIT[\s\-_]*2|U[\s\-_]*2|U#2)\b', full_text):
        unit = "Unit 2"
    elif re.search(r'\b(UNIT[\s\-_]*3|U[\s\-_]*3|U#3)\b', full_text):
        unit = "Unit 3"
        
    extracted = {
        "Unit Detected": unit,
        "Raw Text": full_text
    }
    
    # 2. Key Parameter Extraction (Pattern matching)
    hotwell = re.search(r'HOTWELL.*?([0-9]+\.?[0-9]*)', full_text)
    if hotwell:
        extracted["Hotwell Integrator"] = hotwell.group(1)
        
    platen = re.search(r'PLATEN.*?([0-9]+\.?[0-9]*)', full_text)
    if platen:
        extracted["Platen SH Temp"] = platen.group(1)
        
    spiral = re.search(r'SPIRAL.*?([0-9]+\.?[0-9]*)', full_text)
    if spiral:
        extracted["Spiral Wall Temp"] = spiral.group(1)
        
    rh_temp = re.search(r'RH.*?([0-9]+\.?[0-9]*)', full_text)
    if rh_temp:
        extracted["RH Metal Temp"] = rh_temp.group(1)
        
    h2_press = re.search(r'H2.*?([0-9]+\.?[0-9]*)', full_text)
    if h2_press:
        extracted["H2 Pressure"] = h2_press.group(1)

    return extracted

# Data store initialization
if "log_entries" not in st.session_state:
    st.session_state.log_entries = []

if uploaded_files:
    if st.button("🚀 Process Uploaded Images", type="primary"):
        st.session_state.log_entries = []
        for file in uploaded_files:
            img = Image.open(file).convert('RGB')
            img_np = np.array(img)
            
            with st.spinner(f"Reading {file.name}..."):
                data = parse_dcs_image(img_np)
                st.session_state.log_entries.append({
                    "Filename": file.name,
                    "Unit": data.get("Unit Detected", "Unknown"),
                    "Hotwell Integrator": data.get("Hotwell Integrator", ""),
                    "Platen SH Temp": data.get("Platen SH Temp", ""),
                    "Spiral Wall Temp": data.get("Spiral Wall Temp", ""),
                    "RH Metal Temp": data.get("RH Metal Temp", ""),
                    "H2 Pressure": data.get("H2 Pressure", ""),
                    "Image Object": img
                })

# Verification and Rectification Interface
if st.session_state.log_entries:
    st.subheader("🔍 Review & Rectify Readings")
    st.info("Double-check detected readings against the image. Edit any incorrect values directly in the fields below.")
    
    updated_records = []
    
    for idx, entry in enumerate(st.session_state.log_entries):
        with st.expander(f"📷 {entry['Filename']} — ({entry['Unit']})", expanded=True):
            col_img, col_form = st.columns([1, 1.2])
            
            with col_img:
                st.image(entry["Image Object"], caption=entry["Filename"], use_container_width=True)
                
            with col_form:
                unit_val = st.selectbox(
                    f"Unit Assigned (#{idx+1})",
                    ["Unit 1", "Unit 2", "Unit 3", "Common / Offsite", "Unknown"],
                    index=["Unit 1", "Unit 2", "Unit 3", "Common / Offsite", "Unknown"].index(entry["Unit"])
                )
                
                c1, c2 = st.columns(2)
                with c1:
                    hw_val = st.text_input(f"Hotwell Integrator (#{idx+1})", value=entry["Hotwell Integrator"])
                    platen_val = st.text_input(f"Platen SH Temp (#{idx+1})", value=entry["Platen SH Temp"])
                    spiral_val = st.text_input(f"Spiral Wall Temp (#{idx+1})", value=entry["Spiral Wall Temp"])
                with c2:
                    rh_val = st.text_input(f"RH Metal Temp (#{idx+1})", value=entry["RH Metal Temp"])
                    h2_val = st.text_input(f"H2 Pressure (#{idx+1})", value=entry["H2 Pressure"])
                    
                updated_records.append({
                    "Filename": entry["Filename"],
                    "Unit": unit_val,
                    "Hotwell Integrator": hw_val,
                    "Platen SH Temp": platen_val,
                    "Spiral Wall Temp": spiral_val,
                    "RH Metal Temp": rh_val,
                    "H2 Pressure": h2_val
                })

    # Summary Data Table
    st.divider()
    st.subheader("📊 Final Verified Data")
    df_result = pd.DataFrame(updated_records)
    st.dataframe(df_result.drop(columns=["Filename"]), use_container_width=True)

    # Excel Download Export
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_result.to_excel(writer, index=False, sheet_name="Midnight_DCS_Log")
    
    st.download_button(
        label="📥 Download Verified Excel File",
        data=buffer.getvalue(),
        file_name="Midnight_DCS_Verified_Log.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
