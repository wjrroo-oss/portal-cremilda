import streamlit as st
import pdfplumber
import pandas as pd
from google.oauth2 import service_account
import gspread
import re
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
ID_PLANILHA_MASTER = "1XtIoPk-BL7egviMXJy-qrb0NB--EM7X-l-emusS1f24" 

st.set_page_config(page_title="Portal Cremilda", page_icon="🏫", layout="centered")
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
        h1 { color: #1e293b; font-weight: 800; text-align: center; }
        .stButton>button { background-color: #2563eb; color: white; border-radius: 8px; font-weight: 600; width: 100%; padding: 0.75rem; border: none; }
        .stButton>button:hover { background-color: #1d4ed8; transform: translateY(-2px); }
        .date-box { background-color: #e2e8f0; padding: 20px; border-radius: 12px; margin-bottom: 20px; border-left: 5px solid #2563eb; }
        .info-criacao { font-size: 0.85rem; color: #475569; margin-bottom: 10px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

st.title("🏫 Portal de Alocação - Cremilda")
st.markdown("<p style='text-align: center; color: #64748b;'>Módulo de Extração, Vigência e Histórico</p>", unsafe_allow_html=True)

def mapear_sala_pavilhao(turma, turno):
    t = turma.upper().replace(" ", "").replace("º", "").replace("°", "").replace("ANO", "")
    if turno == "MATUTINO":
        mapa = {'6A': ('13', 'P1E2'), '6B': ('14', 'P1E2'), '7A': ('15', 'P1E2'), '7B': ('16', 'P1E2'), '8A': ('17', 'P1E2'), '8B': ('18', 'P1E2'), '9A': ('19', 'P1E2'), '9B': ('06', 'P1E2'), '1A': ('01', 'P1E2'), '1B': ('20', 'P1E2'), '1C': ('04', 'P1E2'), '1D': ('05', 'P1E2'), '2A': ('21', 'P1E2'), '2B': ('22', 'P1E2'), '2C': ('23', 'P1E2'), '2D': ('24', 'P1E2'), '3A': ('08', 'P1E2'), '3B': ('09', 'P1E2'), '3C': ('10', 'P1E2'), '3D': ('11', 'P1E2'), '3E': ('12', 'P1E2')}
    else:
        mapa = {'6C': ('13', 'P2'), '6D': ('14', 'P2'), '6E': ('15', 'P2'), '6F': ('16', 'P2'), '6G': ('17', 'P2'), '7C': ('19', 'P2'), '7D': ('18', 'P2'), '7E': ('20', 'P2'), '7F': ('21', 'P2'), '8C': ('01', 'P2'), '8D': ('04', 'P2'), '8E': ('22', 'P2'), '8F': ('23', 'P2'), '8G': ('24', 'P2'), '9C': ('05', 'P1'), '9D': ('08', 'P1'), '9E': ('09', 'P1'), '9F': ('06', 'P1'), '1E': ('10', 'P1'), '1F': ('11', 'P1'), '2E': ('12', 'P1')}
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
                    if cell and "ANO" in str(cell).upper(): turmas.append(str(cell).replace('\n', ' ').strip().upper())
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

def calcular_datas_inteligentes(nome_arquivo):
    match = re.search(r'(\d{2})\s+(\d{2})', nome_arquivo)
    if match:
        ano_atual = datetime.now().year
        data_criacao_str = f"{match.group(1)}/{match.group(2)}/{ano_atual}"
        try:
            data_criacao = datetime.strptime(data_criacao_str, "%d/%m/%Y")
            dias_para_segunda = (0 - data_criacao.weekday()) % 7
            if dias_para_segunda == 0: dias_para_segunda = 7 
            
            data_nova_vigencia = data_criacao + timedelta(days=dias_para_segunda)
            data_fim_velha = data_nova_vigencia - timedelta(days=3) 
            
            return data_criacao_str, data_nova_vigencia.strftime("%d/%m/%Y"), data_fim_velha.strftime("%d/%m/%Y")
        except: pass
    return "Não identificada", "", ""

col1, col2 = st.columns(2)
with col1: pdf_mat = st.file_uploader("PDF Matutino GERAL", type="pdf")
with col2: pdf_vesp = st.file_uploader("PDF Vespertino GERAL", type="pdf")

data_criacao = "Aguardando PDF..."
data_sugerida_nova = ""
data_sugerida_velha = ""

if pdf_mat: 
    data_criacao, data_sugerida_nova, data_sugerida_velha = calcular_datas_inteligentes(pdf_mat.name)

st.markdown("<div class='date-box'>", unsafe_allow_html=True)
st.markdown("### 📅 Validação de Vigência")
st.markdown(f"<div class='info-criacao'>🕒 Data de criação identificada no Urânia: {data_criacao}</div>", unsafe_allow_html=True)

col_dt1, col_dt2 = st.columns(2)
with col_dt1:
    data_fim_velha = st.text_input("Encerramento do Horário Atual (Sexta-feira):", value=data_sugerida_velha, placeholder="Ex: 30/01/2026")
with col_dt2:
    data_inicio_nova = st.text_input("Início da Nova Vigência (Segunda-feira):", value=data_sugerida_nova, placeholder="Ex: 02/02/2026")
st.markdown("</div>", unsafe_allow_html=True)

if st.button("🚀 ARQUIVAR ANTIGO E ATIVAR NOVO HORÁRIO"):
    if not data_inicio_nova or not pdf_mat or not pdf_vesp:
        st.warning("⚠️ Preencha as datas e anexe os dois PDFs.")
    else:
        with st.spinner("Arquivando histórico e gerando nova base oficial..."):
            try:
                creds_dict = st.secrets["google_credentials"]
                creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
                client = gspread.authorize(creds)
                planilha = client.open_by_key(ID_PLANILHA_MASTER)
                
                # --- ARQUIVAMENTO BLINDADO ---
                try:
                    aba_bruta = planilha.worksheet("BASE_DADOS_BRUTA")
                    dados_antigos = aba_bruta.get_all_values()
                    if len(dados_antigos) > 1:
                        # Pega as datas diretamente das células fixas (I1 e J1) para não dar erro
                        inicio_antigo = aba_bruta.acell('I1').value or "Antigo"
                        inicio_limpo = inicio_antigo.replace('INÍCIO: ', '').replace('/', '-')
                        fim_limpo = data_fim_velha.replace('/', '-')
                        
                        aba_bruta.update_acell('J1', f"FIM: {data_fim_velha}")
                        nome_historico = f"HISTORICO_{inicio_limpo}_a_{fim_limpo}"
                        aba_bruta.update_title(nome_historico[:90]) 
                    else:
                        aba_bruta.update_title("BKP_VAZIO")
                except gspread.exceptions.WorksheetNotFound:
                    pass # Se não existir, apenas segue em frente

                # --- NOVA BASE COM DATAS EXATAS NAS CÉLULAS I1 E J1 ---
                nova_aba_bruta = planilha.add_worksheet(title="BASE_DADOS_BRUTA", rows=1000, cols=15)
                dados_m = extrair_dados_urania(pdf_mat, "MATUTINO")
                dados_v = extrair_dados_urania(pdf_vesp, "VESPERTINO")
                todos_dados = dados_m + dados_v
                
                cabecalho = ["Turno", "Professor", "Dia", "Horário", "Turma", "Disciplina", "Sala", "Pavilhao"]
                nova_aba_bruta.append_row(cabecalho)
                if todos_dados: nova_aba_bruta.append_rows(todos_dados)
                
                # Cravando as datas nos lugares corretos para o Apps Script ler
                nova_aba_bruta.update_acell('I1', f"{data_inicio_nova}")
                nova_aba_bruta.update_acell('J1', "Em Aberto")
                
                try: planilha.del_worksheet(planilha.worksheet("BKP_VAZIO"))
                except: pass
                
                st.success(f"✅ Base criada com sucesso! Vespertino e Matutino processados.")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao processar: {e}")

