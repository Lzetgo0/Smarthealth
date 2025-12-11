import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import os

# ---------------------------
# GEMINI API KEY (in-code)
# ---------------------------
# NOTE: Anda meminta API key dimasukkan ke kode utama. Ini bekerja, tetapi
# menyimpan kunci sensitif langsung di kode bukan praktik terbaik.
# Jika memungkinkan, pindahkan kembali ke .streamlit/secrets.toml atau variable environment.
GEMINI_API_KEY = "AIzaSyC94X_bwRT3zVpEpQgbbnBbHmKvJ5cJdT4"

# ============= ChatbotService (digabung dari chatbot.py) =============
try:
    import google.generativeai as genai
except Exception:
    genai = None

class ChatbotService:
    def __init__(self, api_key=None):
        # Prefer explicit argument, fallback to in-file GEMINI_API_KEY, then st.secrets if present
        self.api_key = api_key or GEMINI_API_KEY
        try:
            # allow overriding from streamlit secrets if set (still not required)
            if not self.api_key:
                self.api_key = st.secrets.get("GEMINI_API_KEY", None)
        except Exception:
            pass

        if not self.api_key:
            print("Gemini API key not configured. Set GEMINI_API_KEY in code, env, or st.secrets.")

        # configure client if library available
        if genai and self.api_key:
            try:
                # some versions require genai.configure, others do not — ignore errors
                genai.configure(api_key=self.api_key)
            except Exception as e:
                print("Failed to configure Gemini client (or configure not required):", e)

        # system instruction to keep responses safe
        self.system_prompt = (
            "You are a helpful home health assistant. Provide first-aid steps and safe advice. "
            "Do NOT give medical diagnoses or prescribe medications. For emergencies, instruct to call local emergency services."
        )

    def ask(self, user_text, context=None, model="gemini-2.5-flash"):
        if not self.api_key or not genai:
            return "Chatbot API key or Gemini client not configured. Please set GEMINI_API_KEY in the code or install google-generativeai."

        context_text = ""
        if context:
            # context: dict with temp, hum, gas, ai, ts, device
            ctx_parts = []
            for k in ("ts","device","ai","temp","hum","gas"):
                if k in context and context[k] is not None:
                    ctx_parts.append(f"{k}: {context[k]}")
            context_text = "\n".join(ctx_parts)

        prompt = f"{context_text}\n\nUser: {user_text}"

        messages = [
            {"author": "system", "content": self.system_prompt},
            {"author": "user", "content": prompt}
        ]

        try:
            # Prepare common kwargs
            call_kwargs = dict(model=model, messages=messages, max_output_tokens=350, temperature=0.2)

            # Try multiple call shapes for compatibility across genai versions
            resp = None
            if hasattr(genai, "chat") and hasattr(genai.chat, "create"):
                resp = genai.chat.create(**call_kwargs)
            elif hasattr(genai, "ChatCompletion") and hasattr(genai.ChatCompletion, "create"):
                resp = genai.ChatCompletion.create(**call_kwargs)
            elif hasattr(genai, "models") and hasattr(genai.models, "generate"):
                try:
                    resp = genai.models.generate(**call_kwargs)
                except Exception:
                    resp = genai.models.generate(model=model, prompt=prompt, max_output_tokens=350, temperature=0.2)
            elif hasattr(genai, "generate"):
                try:
                    resp = genai.generate(**call_kwargs)
                except Exception:
                    resp = genai.generate(model=model, prompt=prompt, max_output_tokens=350, temperature=0.2)
            else:
                raise RuntimeError("Installed google.generativeai package doesn't expose a known chat/generate API. Try upgrading with: pip install --upgrade google-generativeai")

            # robust extraction of text from possible response shapes
            text = ""
            try:
                # primary common shape: resp.candidates[0].content[0].text
                text = resp.candidates[0].content[0].text
            except Exception:
                try:
                    text = getattr(resp, "output_text", "") or getattr(resp, "result", "")
                except Exception:
                    text = str(resp)

            return (text or "").strip()
        except Exception as e:
            print("Chatbot (Gemini) error:", e)
            return f"Chatbot error: {e}"

# ============= PAGE CONFIG =============
st.set_page_config(
    page_title="Smart Health Ecosystem",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============= MODERN 2025 CUSTOM CSS - DARK THEME WITH TOSCA ACCENT =============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700;800&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0f1f1e 0%, #132523 25%, #0a1918 50%, #132523 75%, #0f1f1e 100%);
        background-attachment: fixed;
        overflow-x: hidden;
    }
    
    .main .block-container {
        padding: 2.5rem 3rem;
        max-width: 100%;
    }
    
    [data-testid="stSidebar"] {
        display: none;
    }
    
    .sidebar-title {
        text-align: center;
        background: linear-gradient(120deg, #1db8a0 0%, #26d0ce 50%, #2dd9ce 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2.2rem;
        font-weight: 800;
        margin: 2rem 0 1rem 0;
        letter-spacing: -0.5px;
    }
    
    .dashboard-title {
        background: linear-gradient(120deg, #1db8a0 0%, #26d0ce 40%, #2dd9ce 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2.8rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        letter-spacing: -0.5px;
        text-align: center;
    }
    
    .dashboard-subtitle {
        background: linear-gradient(90deg, #1db8a0 0%, #26d0ce 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-family: 'Poppins', sans-serif;
        font-size: 1.1rem;
        font-weight: 500;
        margin-bottom: 2.5rem;
        letter-spacing: 0.5px;
        text-align: center;
    }
    
    .section-header {
        background: linear-gradient(90deg, rgba(29, 184, 160, 0.15) 0%, rgba(38, 208, 206, 0.1) 100%);
        border-left: 4px solid #1db8a0;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin: 2.5rem 0 1.5rem 0;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        color: #2dd9ce;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        box-shadow: 0 4px 20px rgba(29, 184, 160, 0.15);
        border: 1px solid rgba(29, 184, 160, 0.3);
    }
    
    .modern-card {
        background: linear-gradient(135deg, rgba(25, 35, 33, 0.95) 0%, rgba(15, 31, 30, 0.98) 100%);
        border-radius: 20px;
        padding: 1.8rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        border: 2px solid rgba(29, 184, 160, 0.25);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    
    .modern-card::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 100%;
        height: 100%;
        background: radial-gradient(circle, rgba(29, 184, 160, 0.05) 0%, transparent 70%);
        transition: all 0.6s ease;
    }
    
    .modern-card:hover {
        transform: translateY(-8px);
        box-shadow: 0 20px 60px rgba(29, 184, 160, 0.2);
        border-color: rgba(29, 184, 160, 0.4);
        background: linear-gradient(135deg, rgba(35, 45, 43, 0.96) 0%, rgba(25, 41, 40, 0.99) 100%);
    }
    
    .metric-card-modern {
        background: linear-gradient(135deg, rgba(25, 35, 33, 0.9) 0%, rgba(15, 31, 30, 0.95) 100%);
        border-radius: 18px;
        padding: 1.6rem;
        text-align: center;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        border: 2px solid rgba(29, 184, 160, 0.3);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    
    .metric-card-modern::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(45, 217, 206, 0.2), transparent);
        transition: left 0.6s;
    }
    
    .metric-card-modern:hover::before {
        left: 100%;
    }
    
    .metric-card-modern:hover {
        transform: translateY(-10px) scale(1.05);
        box-shadow: 0 12px 40px rgba(29, 184, 160, 0.25);
        border-color: rgba(29, 184, 160, 0.5);
    }
    
    .metric-value-modern {
        font-family: 'Poppins', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
        color: #2dd9ce;
        margin: 0.8rem 0;
        position: relative;
        z-index: 1;
    }
    
    .metric-label-modern {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.85rem;
        color: #1db8a0;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-weight: 700;
        position: relative;
        z-index: 1;
    }
    
    .control-panel-glass {
        background: linear-gradient(135deg, rgba(25, 35, 33, 0.95) 0%, rgba(15, 31, 30, 0.98) 100%);
        border-radius: 22px;
        padding: 1.8rem;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
        border: 2px solid rgba(29, 184, 160, 0.25);
        margin-bottom: 1.5rem;
        transition: all 0.4s ease;
        height: 100%;
    }
    
    .control-panel-glass:hover {
        box-shadow: 0 15px 50px rgba(29, 184, 160, 0.25);
        border-color: rgba(29, 184, 160, 0.4);
        transform: translateY(-4px);
    }
    
    .control-section-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.2rem;
        font-weight: 700;
        color: #2dd9ce;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.7rem;
        padding-bottom: 0.8rem;
        border-bottom: 2px solid rgba(29, 184, 160, 0.3);
    }
    
    .stTextInput input, .stTextArea textarea, .stDateInput input, .stTimeInput input, .stNumberInput input, .stSelectbox select {
        background: rgba(15, 31, 30, 0.8) !important;
        border: 2px solid rgba(29, 184, 160, 0.4) !important;
        border-radius: 12px !important;
        padding: 0.75rem 1rem !important;
        color: #2dd9ce !important;
        font-size: 0.95rem !important;
        transition: all 0.3s ease !important;
        font-weight: 600 !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: rgba(45, 217, 206, 0.5) !important;
    }
    
    .stTextInput input:focus, .stTextArea textarea:focus, .stDateInput input:focus, .stTimeInput input:focus, .stNumberInput input:focus, .stSelectbox select:focus {
        border-color: #26d0ce !important;
        box-shadow: 0 0 0 3px rgba(29, 184, 160, 0.3), inset 0 0 0 1px rgba(29, 184, 160, 0.2) !important;
        background: rgba(25, 35, 33, 0.9) !important;
        outline: none !important;
    }
    
    label {
        color: #26d0ce !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.5px !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #1db8a0 0%, #26d0ce 50%, #2dd9ce 100%) !important;
        color: #0f1f1e !important;
        border: none !important;
        border-radius: 14px !important;
        padding: 0.85rem 1.8rem !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 6px 20px rgba(29, 184, 160, 0.3) !important;
        width: 100% !important;
        letter-spacing: 0.8px !important;
        text-transform: uppercase !important;
        font-family: 'Space Grotesk', sans-serif !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-3px) scale(1.02) !important;
        box-shadow: 0 10px 30px rgba(29, 184, 160, 0.5) !important;
        background: linear-gradient(135deg, #15a894 0%, #1db8a0 50%, #26d0ce 100%) !important;
    }
    
    .stButton > button:active {
        transform: translateY(-1px) !important;
    }
    
    .status-badge {
        display: inline-block;
        padding: 0.6rem 1.4rem;
        border-radius: 25px;
        font-weight: 700;
        font-size: 0.85rem;
        box-shadow: 0 4px 15px rgba(29, 184, 160, 0.3);
        border: 1px solid rgba(45, 217, 206, 0.3);
        font-family: 'Poppins', sans-serif;
    }
    
    .status-normal {
        background: linear-gradient(135deg, #1db8a0 0%, #26d0ce 100%);
        color: #0f1f1e;
    }
    
    .status-warning {
        background: linear-gradient(135deg, #ff9800 0%, #ffb74d 100%);
        color: #0f1f1e;
    }
    
    .status-danger {
        background: linear-gradient(135deg, #f44336 0%, #e57373 100%);
        color: white;
    }
    
    .info-card-modern {
        background: linear-gradient(135deg, rgba(25, 35, 33, 0.9) 0%, rgba(15, 31, 30, 0.95) 100%);
        border-left: 4px solid #1db8a0;
        padding: 1.2rem 1.5rem;
        border-radius: 14px;
        margin: 1rem 0;
        color: #2dd9ce;
        font-size: 0.95rem;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
        border: 1px solid rgba(29, 184, 160, 0.25);
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
    }
    
    .info-card-modern:hover {
        transform: translateX(6px);
        box-shadow: 0 6px 20px rgba(29, 184, 160, 0.25);
        border-color: rgba(29, 184, 160, 0.4);
    }
    
    .system-info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.8rem 0;
        border-bottom: 1px solid rgba(29, 184, 160, 0.2);
        transition: all 0.3s ease;
    }
    
    .system-info-row:hover {
        background: rgba(29, 184, 160, 0.08);
        padding-left: 0.5rem;
        border-radius: 8px;
    }
    
    .system-info-row:last-child {
        border-bottom: none;
    }
    
    .system-info-label {
        font-weight: 700;
        color: #1db8a0;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-family: 'Space Grotesk', sans-serif;
    }
    
    .system-info-value {
        color: #2dd9ce;
        font-size: 0.9rem;
        font-weight: 600;
        font-family: 'Poppins', sans-serif;
    }
    
    .footer-card {
        background: linear-gradient(135deg, rgba(25, 35, 33, 0.9) 0%, rgba(15, 31, 30, 0.95) 100%);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        border: 2px solid rgba(29, 184, 160, 0.25);
        margin-top: 3rem;
    }
    
    .stAlert {
        background: rgba(25, 35, 33, 0.9) !important;
        border: 2px solid rgba(29, 184, 160, 0.35) !important;
        border-radius: 12px !important;
        color: #2dd9ce !important;
        font-size: 0.95rem !important;
    }
    
    .stInfo {
        background: rgba(25, 35, 33, 0.9) !important;
        border: 2px solid rgba(29, 184, 160, 0.35) !important;
        border-left: 4px solid #1db8a0 !important;
        color: #2dd9ce !important;
        border-radius: 12px !important;
        font-size: 0.95rem !important;
    }
    
    .stWarning {
        background: rgba(255, 152, 0, 0.1) !important;
        border: 2px solid rgba(255, 152, 0, 0.3) !important;
        border-left: 4px solid #ff9800 !important;
        color: #ffb74d !important;
        border-radius: 12px !important;
        font-size: 0.95rem !important;
    }
    
    .stSuccess {
        background: rgba(25, 35, 33, 0.9) !important;
        border: 2px solid rgba(29, 184, 160, 0.35) !important;
        border-left: 4px solid #1db8a0 !important;
        color: #2dd9ce !important;
        border-radius: 12px !important;
        font-size: 0.95rem !important;
    }
    
    .stError {
        background: rgba(244, 67, 54, 0.1) !important;
        border: 2px solid rgba(244, 67, 54, 0.3) !important;
        border-left: 4px solid #f44336 !important;
        color: #ff7675 !important;
        border-radius: 12px !important;
        font-size: 0.95rem !important;
    }
    
    p, div, span, li {
        color: #2dd9ce;
        font-family: 'Inter', sans-serif;
    }
    
    strong {
        color: #2dd9ce;
        font-weight: 700;
        font-family: 'Poppins', sans-serif;
    }
    
    [data-testid="stDataFrame"] {
        background: rgba(25, 35, 33, 0.9);
        border-radius: 12px;
        border: 2px solid rgba(29, 184, 160, 0.25) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .dataframe {
        font-size: 0.9rem;
        border-radius: 12px;
        border: 2px solid rgba(29, 184, 160, 0.25) !important;
        background: rgba(25, 35, 33, 0.9) !important;
        color: #2dd9ce !important;
    }
    
    hr {
        margin: 2rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(29, 184, 160, 0.3), transparent);
    }
    
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(29, 184, 160, 0.05);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #1db8a0, #26d0ce);
        border-radius: 10px;
        border: 2px solid rgba(15, 31, 30, 0.8);
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #15a894, #1db8a0);
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* ============= GAUGE VISUALIZATION CONTAINER ============= */
    .gauge-viz-container {
        background: linear-gradient(135deg, rgba(20, 30, 28, 0.92) 0%, rgba(10, 25, 24, 0.95) 100%);
        border-radius: 24px;
        padding: 2rem;
        border: 2px solid rgba(29, 184, 160, 0.25);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        margin-bottom: 1.5rem;
    }
    
    /* ============= MODERN CIRCULAR GAUGE STYLES ============= */
    .gauge-circular-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1.2rem;
        padding: 1.5rem;
        background: rgba(15, 31, 30, 0.6);
        border-radius: 18px;
        border: 1px solid rgba(29, 184, 160, 0.2);
    }
    
    .gauge-circular-label {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.9rem;
        color: #1db8a0;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-weight: 700;
        text-align: center;
    }
    
    .gauge-circular-wrapper {
        position: relative;
        width: 180px;
        height: 180px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .gauge-circular-bg {
        position: absolute;
        width: 100%;
        height: 100%;
        border-radius: 50%;
        background: conic-gradient(from 180deg, #0a1918 0deg, #0a1918 360deg);
        box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.5);
    }
    
    .gauge-circular-fill {
        position: absolute;
        width: 100%;
        height: 100%;
        border-radius: 50%;
        background: conic-gradient(from 180deg, #1db8a0 var(--gauge-percent), #0a1918 var(--gauge-percent));
    }
    
    .gauge-circular-text {
        position: relative;
        z-index: 10;
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    
    .gauge-circular-value {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2.4rem;
        font-weight: 800;
        color: #2dd9ce;
        line-height: 1;
    }
    
    .gauge-circular-unit {
        font-family: 'Poppins', sans-serif;
        font-size: 0.8rem;
        color: #1db8a0;
        font-weight: 600;
        margin-top: 0.3rem;
        letter-spacing: 0.5px;
    }
    
    .gauge-stats-modern {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.8rem;
        width: 100%;
        margin-top: 0.5rem;
    }
    
    .gauge-stat-modern {
        background: rgba(29, 184, 160, 0.1);
        padding: 0.7rem 0.8rem;
        border-radius: 10px;
        text-align: center;
        border: 1px solid rgba(29, 184, 160, 0.2);
    }
    
    .gauge-stat-label-modern {
        font-family: 'Poppins', sans-serif;
        font-size: 0.7rem;
        color: #1db8a0;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.4px;
    }
    
    .gauge-stat-value-modern {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1rem;
        color: #2dd9ce;
        font-weight: 700;
        margin-top: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)

# ============= CONFIG & INIT =============
# Allow overriding broker/port from st.secrets if present
BROKER = st.secrets.get("MQTT_BROKER", "broker.emqx.io")
PORT = int(st.secrets.get("MQTT_PORT", 1883))
MODEL_PATH = "models/smarthealth_rf.pkl"
CSV_PATH = "data.csv"

# Non-blocking model check
if not os.path.exists(MODEL_PATH):
    st.warning(f"⚠️ Model tidak ditemukan di {MODEL_PATH}. Menjalankan mode terbatas (prediksi AI dinonaktifkan). Letakkan file .pkl di folder models/ untuk mengaktifkan prediksi.")
    MODEL_AVAILABLE = False
else:
    MODEL_AVAILABLE = True

# Initialize MQTT runner (tolerant to errors)
if "mqtt_runner" not in st.session_state:
    try:
        # Import here to allow app to start even if mqtt_client missing
        from mqtt_client import MQTTRunner
        model_arg = MODEL_PATH if MODEL_AVAILABLE else None
        st.session_state.mqtt_runner = MQTTRunner(BROKER, PORT, model_path=model_arg, csv_path=CSV_PATH)
        try:
            st.session_state.mqtt_runner.start()
        except Exception as e:
            print("Warning: mqtt_runner.start() raised:", e)
        time.sleep(0.5)
    except Exception as e:
        print("Failed to initialize MQTTRunner:", e)
        class _DummyMQTTRunner:
            def __init__(self, *args, **kwargs):
                self._latest = None
            def start(self): pass
            def get_latest_record(self):
                return {}
            def publish_obat(self, schedules):
                print("Dummy publish_obat called:", schedules)
        st.session_state.mqtt_runner = _DummyMQTTRunner()

# Ensure CSV exists
if not os.path.exists(CSV_PATH):
    try:
        pd.DataFrame(columns=["ts", "device", "temp", "hum", "gas", "ai"]).to_csv(CSV_PATH, index=False)
    except Exception as e:
        print("Warning: unable to create CSV file:", e)

# Initialize chatbot
if "chatbot" not in st.session_state:
    try:
        st.session_state.chatbot = ChatbotService(api_key=GEMINI_API_KEY)
    except Exception as e:
        print("Warning: ChatbotService init failed:", e)
        class _DummyChatbot:
            api_key = None
            def ask(self, text, context=None, model=None):
                return "Chatbot tidak tersedia."
        st.session_state.chatbot = _DummyChatbot()

# Initialize schedules
if "medicine_schedules" not in st.session_state:
    st.session_state.medicine_schedules = []

# Initialize auto-refresh session state
if "autorefresh_running" not in st.session_state:
    st.session_state.autorefresh_running = False

if "last_auto_refresh_time" not in st.session_state:
    st.session_state.last_auto_refresh_time = time.time()

# ============= LOAD DATA =============
expected_cols = ["ts", "device", "temp", "hum", "gas", "ai"]

def _safe_read_csv(path):
    try:
        df = pd.read_csv(path)
        # jika header tidak sesuai, coba baca tanpa header dan pasang header default
        if not set(expected_cols).issubset(df.columns):
            df2 = pd.read_csv(path, header=None)
            if df2.shape[1] >= len(expected_cols):
                df2 = df2.iloc[:, :len(expected_cols)]
                df2.columns = expected_cols
                return df2
            return pd.DataFrame(columns=expected_cols)
        return df
    except Exception as e:
        print("Warning reading CSV:", e)
        return pd.DataFrame(columns=expected_cols)

df = _safe_read_csv(CSV_PATH)
# pastikan kolom numerik ada dan bertipe numeric
for col in ("temp", "hum", "gas"):
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    else:
        df[col] = 0

# parse timestamp ke datetime jika memungkinkan
if "ts" in df.columns:
    try:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    except Exception:
        df["ts"] = df["ts"].astype(str)

# fallback: jika mqtt_runner belum punya latest, ambil dari CSV terakhir
last_record = st.session_state.mqtt_runner.get_latest_record() or {}
if not last_record and not df.empty:
    # ambil baris terakhir dengan fallback fields
    last_row = df.iloc[-1].to_dict()
    last_record = {
        "ts": last_row.get("ts", ""),
        "device": last_row.get("device", ""),
        "temp": float(last_row.get("temp") or 0),
        "hum": float(last_row.get("hum") or 0),
        "gas": float(last_row.get("gas") or 0),
        "ai": last_row.get("ai", "N/A")
    }

temp = float(last_record.get("temp", 0) or 0)
hum = float(last_record.get("hum", 0) or 0)
gas = float(last_record.get("gas", 0) or 0)
ai_status = last_record.get("ai", "N/A")

# ============= HEADER =============
st.markdown("<h1 class='dashboard-title'>🏥 Smart Health Ecosystem</h1>", unsafe_allow_html=True)
st.markdown("<p class='dashboard-subtitle'>Real-time Health Monitoring dengan AI & IoT Technology</p>", unsafe_allow_html=True)

# ============= MAIN LAYOUT - 75% / 25% =============
main_col, control_col = st.columns([3, 1])

# ========== LEFT SIDE: 75% MAIN CONTENT ==========
with main_col:
    st.markdown("<div class='section-header'>📊 Live Sensor Metrics</div>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class='metric-card-modern'>
            <div class='metric-label-modern'>🌡️ Temperature</div>
            <div class='metric-value-modern'>{temp:.1f}°C</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class='metric-card-modern'>
            <div class='metric-label-modern'>💧 Humidity</div>
            <div class='metric-value-modern'>{hum:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class='metric-card-modern'>
            <div class='metric-label-modern'>🌫️ Gas Level</div>
            <div class='metric-value-modern'>{gas:.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        status_class = "status-normal" if ai_status == "Normal" else "status-warning" if ai_status == "Warning" else "status-danger"
        st.markdown(f"""
        <div class='metric-card-modern'>
            <div class='metric-label-modern'>🤖 AI Status</div>
            <div class='metric-value-modern' style='font-size: 1.8rem;'><span class='{status_class} status-badge'>{ai_status}</span></div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<div class='section-header'>📈 Modern Sensor Visualization</div>", unsafe_allow_html=True)
    st.markdown("<div class='gauge-viz-container'>", unsafe_allow_html=True)
    
    col_gauge1, col_gauge2 = st.columns(2)
    
    # ===== MODERN CIRCULAR GAUGE TEMPERATURE =====
    with col_gauge1:
        temp_percent = min(100, max(0, (temp / 50) * 100))
        
        st.markdown(f"""
        <div class='gauge-circular-container'>
            <div class='gauge-circular-label'>🌡️ Temperature</div>
            <div class='gauge-circular-wrapper'>
                <div class='gauge-circular-bg'></div>
                <div class='gauge-circular-fill' style='--gauge-percent: {temp_percent}%'></div>
                <div class='gauge-circular-text'>
                    <div class='gauge-circular-value'>{temp:.1f}</div>
                    <div class='gauge-circular-unit'>°C</div>
                </div>
            </div>
            <div class='gauge-stats-modern'>
                <div class='gauge-stat-modern'>
                    <div class='gauge-stat-label-modern'>Min</div>
                    <div class='gauge-stat-value-modern'>{df['temp'].min() if not df.empty else 0:.1f}°C</div>
                </div>
                <div class='gauge-stat-modern'>
                    <div class='gauge-stat-label-modern'>Max</div>
                    <div class='gauge-stat-value-modern'>{df['temp'].max() if not df.empty else 0:.1f}°C</div>
                </div>
                <div class='gauge-stat-modern'>
                    <div class='gauge-stat-label-modern'>Avg</div>
                    <div class='gauge-stat-value-modern'>{df['temp'].mean() if not df.empty else 0:.1f}°C</div>
                </div>
                <div class='gauge-stat-modern'>
                    <div class='gauge-stat-label-modern'>Status</div>
                    <div class='gauge-stat-value-modern'>Optimal</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # ===== MODERN CIRCULAR GAUGE HUMIDITY & GAS =====
    with col_gauge2:
        col_hum, col_gas = st.columns(2)
        
        with col_hum:
            hum_percent = min(100, max(0, hum))
            
            st.markdown(f"""
            <div class='gauge-circular-container'>
                <div class='gauge-circular-label'>💧 Humidity</div>
                <div class='gauge-circular-wrapper'>
                    <div class='gauge-circular-bg'></div>
                    <div class='gauge-circular-fill' style='--gauge-percent: {hum_percent}%'></div>
                    <div class='gauge-circular-text'>
                        <div class='gauge-circular-value'>{hum:.1f}</div>
                        <div class='gauge-circular-unit'>%</div>
                    </div>
                </div>
                <div class='gauge-stats-modern'>
                    <div class='gauge-stat-modern'>
                        <div class='gauge-stat-label-modern'>Min</div>
                        <div class='gauge-stat-value-modern'>{df['hum'].min() if not df.empty else 0:.1f}%</div>
                    </div>
                    <div class='gauge-stat-modern'>
                        <div class='gauge-stat-label-modern'>Max</div>
                        <div class='gauge-stat-value-modern'>{df['hum'].max() if not df.empty else 0:.1f}%</div>
                    </div>
                    <div class='gauge-stat-modern'>
                        <div class='gauge-stat-label-modern'>Avg</div>
                        <div class='gauge-stat-value-modern'>{df['hum'].mean() if not df.empty else 0:.1f}%</div>
                    </div>
                    <div class='gauge-stat-modern'>
                        <div class='gauge-stat-label-modern'>Status</div>
                        <div class='gauge-stat-value-modern'>Good</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_gas:
            gas_percent = min(100, max(0, (gas / 1000) * 100))
            
            st.markdown(f"""
            <div class='gauge-circular-container'>
                <div class='gauge-circular-label'>🌫️ Gas Level</div>
                <div class='gauge-circular-wrapper'>
                    <div class='gauge-circular-bg'></div>
                    <div class='gauge-circular-fill' style='--gauge-percent: {gas_percent}%'></div>
                    <div class='gauge-circular-text'>
                        <div class='gauge-circular-value'>{gas:.0f}</div>
                        <div class='gauge-circular-unit'>ppm</div>
                    </div>
                </div>
                <div class='gauge-stats-modern'>
                    <div class='gauge-stat-modern'>
                        <div class='gauge-stat-label-modern'>Min</div>
                        <div class='gauge-stat-value-modern'>{df['gas'].min() if not df.empty else 0:.0f}</div>
                    </div>
                    <div class='gauge-stat-modern'>
                        <div class='gauge-stat-label-modern'>Max</div>
                        <div class='gauge-stat-value-modern'>{df['gas'].max() if not df.empty else 0:.0f}</div>
                    </div>
                    <div class='gauge-stat-modern'>
                        <div class='gauge-stat-label-modern'>Avg</div>
                        <div class='gauge-stat-value-modern'>{df['gas'].mean() if not df.empty else 0:.0f}</div>
                    </div>
                    <div class='gauge-stat-modern'>
                        <div class='gauge-stat-label-modern'>Status</div>
                        <div class='gauge-stat-value-modern'>Safe</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='section-header'>📉 Historical Trends</div>", unsafe_allow_html=True)
    st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
    
    if not df.empty:
        recent = df.tail(200).copy()
        
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=recent['ts'], y=recent['temp'], name='Temperature',
            line=dict(color='#ff6b6b', width=3), mode='lines',
            fill='tonexty', fillcolor='rgba(255, 107, 107, 0.1)',
            hovertemplate='<b>Temperature</b><br>%{y:.1f}°C<br>%{x}<extra></extra>'
        ))
        fig_trend.add_trace(go.Scatter(
            x=recent['ts'], y=recent['hum'], name='Humidity',
            line=dict(color='#1db8a0', width=3), mode='lines',
            fill='tonexty', fillcolor='rgba(29, 184, 160, 0.1)',
            hovertemplate='<b>Humidity</b><br>%{y:.1f}%<br>%{x}<extra></extra>'
        ))
        fig_trend.add_trace(go.Scatter(
            x=recent['ts'], y=recent['gas']/10, name='Gas (÷10)',
            line=dict(color='#2dd9ce', width=3), mode='lines',
            fill='tonexty', fillcolor='rgba(45, 217, 206, 0.1)',
            hovertemplate='<b>Gas Level</b><br>%{y:.1f} ppm<br>%{x}<extra></extra>'
        ))
        
        fig_trend.update_layout(
            hovermode='x unified',
            plot_bgcolor='rgba(15, 31, 30, 0.5)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor='rgba(29, 184, 160, 0.15)', color='#2dd9ce', title='Time', title_font=dict(size=12, color='#2dd9ce')),
            yaxis=dict(showgrid=True, gridcolor='rgba(29, 184, 160, 0.15)', color='#2dd9ce', title='Value', title_font=dict(size=12, color='#2dd9ce')),
            height=320,
            margin=dict(l=60, r=30, t=30, b=60),
            font={'family': 'Poppins', 'color': '#2dd9ce', 'size': 11},
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, 
                       bgcolor='rgba(25, 35, 33, 0.9)', bordercolor='rgba(29, 184, 160, 0.25)', borderwidth=2)
        )
        st.plotly_chart(fig_trend, use_container_width=True, config={'displayModeBar': True})
    else:
        st.info("📭 Menunggu data sensor...")
    
    st.markdown("</div>", unsafe_allow_html=True)

# ========== RIGHT SIDE: 25% CONTROL PANEL ==========
with control_col:
    # ===== AI ASSISTANT =====
    st.markdown("<div class='control-panel-glass'>", unsafe_allow_html=True)
    st.markdown("<div class='control-section-title'>🤖 AI Assistant</div>", unsafe_allow_html=True)
    
    if getattr(st.session_state.chatbot, "api_key", None) is None:
        st.warning("⚠️ API key belum dikonfigurasi", icon=False)
    
    user_input = st.text_area("Tanyakan kesehatan Anda:", height=100, key="chat_input", label_visibility="collapsed", placeholder="Ketik pertanyaan...")
    
    if st.button("💬 KIRIM", key="send_chat"):
        if user_input.strip():
            with st.spinner("🤔"):
                context = last_record
                reply = st.session_state.chatbot.ask(user_input, context=context)
                # tampilkan jawaban (dipotong agar tidak memanjang UI)
                display_text = reply if len(reply) <= 800 else reply[:800] + "..."
                st.markdown(f"<div class='info-card-modern'><strong>💡</strong> {display_text}</div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== MEDICINE SCHEDULER =====
    st.markdown("<div class='control-panel-glass'>", unsafe_allow_html=True)
    st.markdown("<div class='control-section-title'>💊 Medicine</div>", unsafe_allow_html=True)
    
    medicine_name = st.text_input("Obat", "", key="med_name", label_visibility="collapsed", placeholder="Nama...")
    start_date = st.date_input("Mulai", datetime.now(), key="start_date", label_visibility="collapsed")
    end_date = st.date_input("Selesai", datetime.now() + timedelta(days=7), key="end_date", label_visibility="collapsed")
    frequency = st.number_input("Frekuensi", min_value=1, max_value=6, value=2, key="freq", label_visibility="collapsed")
    
    times = []
    for i in range(frequency):
        time_input = st.time_input(f"T {i+1}", datetime.strptime(f"{8 + i*4}:00", "%H:%M").time(), key=f"time_{i}", label_visibility="collapsed")
        times.append(time_input)
    
    if st.button("➕ TAMBAH", key="add_schedule"):
        if start_date and end_date and times and medicine_name.strip():
            schedules = []
            current_date = start_date
            while current_date <= end_date:
                for t in times:
                    schedule_datetime = datetime.combine(current_date, t)
                    schedules.append(schedule_datetime.strftime("%Y-%m-%d %H:%M"))
                current_date += timedelta(days=1)
            
            st.session_state.medicine_schedules.extend([
                {"datetime": s, "medicine": medicine_name} for s in schedules
            ])
            
            st.session_state.mqtt_runner.publish_obat(schedules)
            st.success(f"✅ {len(schedules)} jadwal!")
        elif not medicine_name.strip():
            st.error("⚠️ Nama obat harus diisi!")
    
    if st.session_state.medicine_schedules:
        st.markdown("<p style='color: #26d0ce; font-size: 0.8rem; font-weight: 700; margin-bottom: 0.8rem;'>📅 Jadwal:</p>", unsafe_allow_html=True)
        schedule_df = pd.DataFrame(st.session_state.medicine_schedules)
        st.dataframe(schedule_df, use_container_width=True, hide_index=True, height=120)
        
        if st.button("🗑️ Hapus", key="clear_schedules"):
            st.session_state.medicine_schedules = []
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== SYSTEM CONTROL =====
    st.markdown("<div class='control-panel-glass'>", unsafe_allow_html=True)
    st.markdown("<div class='control-section-title'>⚙️ System</div>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class='system-info-row'>
        <span class='system-info-label'>Status</span>
        <span class='system-info-value'>🟢 Active</span>
    </div>
    <div class='system-info-row'>
        <span class='system-info-label'>Broker</span>
        <span class='system-info-value' style='font-size: 0.8rem;'>{BROKER[:20]}</span>
    </div>
    <div class='system-info-row'>
        <span class='system-info-label'>Port</span>
        <span class='system-info-value'>{PORT}</span>
    </div>
    <div class='system-info-row'>
        <span class='system-info-label'>Device</span>
        <span class='system-info-value'>{last_record.get('device', 'N/A')[:15]}</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)

        # ===== AUTO-REFRESH CONTROLS (MODERN & RESPONSIVE) =====
    st.markdown("<div style='margin-top:0.4rem; margin-bottom:0.6rem;'><strong style='color:#2dd9ce;'>🔄 Auto-Refresh</strong></div>", unsafe_allow_html=True)

    col_start, col_stop = st.columns(2)

    with col_start:
        if st.button("▶️ START", key="start_autorefresh", use_container_width=True):
            st.session_state.autorefresh_running = True
            st.session_state.last_auto_refresh_time = time.time()
            st.success("Auto-refresh diaktifkan")
            st.rerun()

    with col_stop:
        if st.button("⏹️ STOP", key="stop_autorefresh", use_container_width=True):
            st.session_state.autorefresh_running = False
            st.success("Auto-refresh dihentikan")
            st.rerun()

    # Force manual refresh
    if st.button("🔁 REFRESH SEKARANG", key="refresh_now", use_container_width=True):
        st.session_state.last_auto_refresh_time = time.time()
        st.rerun()

    # Status indicator
    status_text = "🟢 BERJALAN" if st.session_state.get("autorefresh_running", False) else "🔴 BERHENTI"
    status_color = "#1db8a0" if st.session_state.get("autorefresh_running", False) else "#f44336"
    st.markdown(f"""
    <div style='padding:0.8rem; border-radius:12px; background:rgba(29,184,160,0.1); margin:0.8rem 0; text-align:center;'>
        <strong style='color:{status_color}; font-size:1rem;'>Status: {status_text}</strong>
    </div>
    """, unsafe_allow_html=True)

    # Last refresh time
    last_refresh_display = datetime.fromtimestamp(st.session_state.get("last_auto_refresh_time", time.time())).strftime("%H:%M:%S")
    st.markdown(f"<small style='color:#26d0ce; display:block; text-align:center;'>Terakhir diupdate: {last_refresh_display}</small>", unsafe_allow_html=True)

    # Hapus semua selectbox interval karena sekarang tanpa batas waktu tetap
    # Kita akan refresh secepat mungkin (setiap ~2 detik)

# ============= AUTO-REFRESH LOOP (NON-BLOCKING, RESPONSIVE) =============
if st.session_state.get("autorefresh_running", False):
    # Update timestamp setiap kali rerun
    now = time.time()
    last_time = st.session_state.get("last_auto_refresh_time", now)

    # Refresh setiap ~2 detik (bisa diubah ke 1 atau 3 jika perlu)
    REFRESH_INTERVAL = 2  # detik

    if now - last_time >= REFRESH_INTERVAL:
        st.session_state.last_auto_refresh_time = now
        # Trigger rerun otomatis
        st.rerun()
# ============= FOOTER ============
st.markdown("<div class='footer-card'><p style='color: #2dd9ce; font-size: 0.85rem; margin: 0; font-weight: 700;'>✨ Smart Health Ecosystem © 2025 | So Cool ✨</p></div>", unsafe_allow_html=True)

time.sleep(0.1)


