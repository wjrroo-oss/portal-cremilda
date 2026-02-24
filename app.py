import streamlit as st
import pdfplumber
import pandas as pd
from google.oauth2 import service_account
import gspread
import re
from datetime import datetime

# --- CONFIGURAÇÃO DA PLANILHA ---
ID_PLANILHA_MASTER = "1XtIoPk-BL7egviMXJy-qrb0NB--EM7X-l-emusS1f24" 

# --- INJEÇÃO DE CSS MODERNO (DESIGN JAMSTACK) ---
st.set_page_config(page_title="Portal Cremilda", page_icon="🏫", layout="centered")
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
        h1 { color: #1e293b; font-weight: 800; text-align: center; }
        .stButton>button { background-color: #2563eb; color: white; border-radius: 8px; font-weight: 600; width: 100%; padding: 0.75rem; border: none; transition: all 0.3s ease; }
        .stButton>button:hover { background-color: #1d4ed8; transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        div[data-baseweb="fileUploader"] { background-color: white; border-radius: 12px; border: 2px dashed #cbd5e1; padding: 1rem; }
        .stTextInput>div>div>input { border-radius: 8px; border: 1px solid #cbd5e1; }
    </style>
""", unsafe_allow_html=True)

st.title("🏫 Portal de Alocação - Cremilda")
st.markdown("<p style='text-align: center; color: #64748b; margin-bottom: 2rem;'>Módulo de Extração Urânia e Arquivamento de Base</p>", unsafe_allow_html=True)

# --- DICIONÁRIO DE SALAS E PAVILHÕES (BASEADO NOS SEUS PRINTS) ---
def mapear_sala_pavilhao(turma, turno):
    t = turma.upper().replace(" ", "").replace("º", "").replace("°", "").replace("ANO", "")
    if turno == "MATUTINO":
        mapa = {
            '6A': ('13', 'P1E2'), '6B': ('14', 'P1E2'), '7A': ('15', 'P1E2'), '7B': ('16', 'P1E2'),
            '8A': ('17', 'P1E2'), '8B': ('18', 'P1E2'), '9A': ('19', 'P1E2'), '9B': ('06', 'P1E2'),
            '1A': ('01', 'P1E2'), '1B': ('20', 'P1E2'), '1C': ('04', 'P1E2'), '1D': ('05', 'P1E2'),
            '2A': ('21', 'P1E2'), '2B': ('22', 'P1E2'), '2C': ('23', 'P1E2'), '2D': ('24', 'P1E2'),
            '3A': ('08', 'P1E2'), '3B': ('09', 'P1E2'), '3C': ('10', 'P1E2'), '3D': ('11', 'P1E2'), '3E': ('12', 'P1E2')
        }
    else:
        mapa = {
            '6C': ('13', 'P2'), '6D': ('14', 'P2'), '6E': ('15', 'P2'), '6F': ('16', 'P2'), '6G': ('17', 'P2'),
            '7C': ('19', 'P2'), '7D': ('18', 'P2'), '7E': ('20', 'P2'), '7F': ('21', 'P2'),
            '8C': ('01', 'P2'), '8D': ('04', 'P2'), '8E': ('22', 'P2'), '8F': ('23', 'P2'), '8G': ('24', 'P2'),
            '9C': ('05', 'P1'), '9D': ('08', 'P1'), '9E': ('09', 'P1'), '9F': ('06', 'P1'),
            '1E': ('10', 'P1'), '1F': ('11', 'P1'), '2E': ('12', 'P1')
        }
    return mapa.get(t, ('00', 'P?'))

def extrair_dados_urania(pdf_file, turno):
    dados = []
    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables: continue
            turmas = []
            if len(tables[0]) > 0:
                for cell in tables[0][0]:
                    if cell and "ANO" in str(cell).upper():
                        turmas.append(str(cell).replace('\n', ' ').strip().upper())
            if not turmas:
                texto = page.extract_text()
                encontradas = re.findall(r'\d[°º]\s*(?:ANO|ano)\s*[A-Z]?', texto, re.IGNORECASE)
                for t in encontradas:
                    t_clean = t.replace('\n', ' ').strip().upper()
                    if t_clean not in turmas: turmas.append(t_clean)

            for idx_dia, table in enumerate(tables):
                if idx_dia >= 5: break 
                dia_nome = dias_semana[idx_dia]
                start_row = 1 if (idx_dia == 0 and len(table) > 0 and any("ANO" in str(c).upper() for c in table[0])) else 0
                aula_num = 1
                for row in table[start_row:]:
                    row_clean = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                    if not any("(" in cell for cell in row_clean): continue
                    for col_idx in range(1, len(row_clean)):
                        if col_idx - 1 < len(turmas):
                            turma_atual = turmas[col_idx - 1]
                            celula = row_clean[col_idx]
                            if "(" in celula and ")" in celula:
                                match = re.match(r'^(.*?)\s*\((.*?)\)$', celula)
                                if match:
                                    disciplina = match.group(1).strip()
                                    professor = match.group(2).strip().title()
                                    sala, pavilhao = mapear_sala_pavilhao(turma_atual, turno)
                                    dados.append([turno, professor, dia_nome, f"{aula_num}ª Aula", turma_atual, disciplina, f"S{sala}", pavilhao])
                    aula_num += 1
    return dados

# --- INTERFACE E LÓGICA DE ARQUIVAMENTO ---
data_vigencia = st.text_input("📅 Início da Vigência deste Horário", placeholder="Ex: 09/03 a 13/03")
col1, col2 = st.columns(2)
with col1: pdf_mat = st.file_uploader("PDF Matutino GERAL", type="pdf")
with col2: pdf_vesp = st.file_uploader("PDF Vespertino GERAL", type="pdf")

if st.button("🚀 INICIAR NOVA VIGÊNCIA E ATUALIZAR BASE"):
    if not data_vigencia or not pdf_mat or not pdf_vesp:
        st.warning("⚠️ Preencha a data de vigência e anexe os dois PDFs.")
    else:
        with st.spinner("Arquivando base antiga e gerando nova..."):
            try:
                creds_dict = st.secrets["google_credentials"]
                creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
                client = gspread.authorize(creds)
                planilha = client.open_by_key(ID_PLANILHA_MASTER)
                aba_bruta = planilha.worksheet("BASE_DADOS_BRUTA")
                
                # 1. MECANISMO DE SEGURANÇA E ARQUIVAMENTO
                dados_antigos = aba_bruta.get_all_values()
                if len(dados_antigos) > 1:
                    data_hoje = datetime.now().strftime("%d-%m-%Y_%H-%M")
                    nome_aba_bkp = f"BKP_Vigencia_Anterior_{data_hoje}"
                    aba_bkp = planilha.add_worksheet(title=nome_aba_bkp, rows=len(dados_antigos)+10, cols=10)
                    aba_bkp.update(range_name='A1', values=dados_antigos)
                
                # 2. EXTRAÇÃO E PREENCHIMENTO NOVO
                dados_m = extrair_dados_urania(pdf_mat, "MATUTINO")
                dados_v = extrair_dados_urania(pdf_vesp, "VESPERTINO")
                todos_dados = dados_m + dados_v
                
                aba_bruta.clear()
                aba_bruta.append_row(["Turno", "Professor", "Dia", "Horário", "Turma", "Disciplina", "Sala", "Pavilhao", f"Vigência: {data_vigencia}"])
                if todos_dados:
                    aba_bruta.append_rows(todos_dados)
                
                st.success(f"✅ Sucesso! A base antiga foi salva na aba oculta e a vigência '{data_vigencia}' já está ativa!")
                st.balloons()
            except Exception as e:
                st.error(f"Erro: {e}")
