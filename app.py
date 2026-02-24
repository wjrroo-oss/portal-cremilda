import streamlit as st
import pdfplumber
import pandas as pd
from google.oauth2 import service_account
import gspread
import re
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURAÇÃO DE ACESSO
# ==============================================================================
ID_PLANILHA_MASTER = "1XtIoPk-BL7egviMXJy-qrb0NB--EM7X-l-emusS1f24" 

# ==============================================================================
# DESIGN E LAYOUT (CSS INJETADO)
# ==============================================================================
st.set_page_config(page_title="Portal Cremilda", page_icon="🏫", layout="centered")
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
        h1 { color: #1e293b; font-weight: 800; text-align: center; }
        .stButton>button { background-color: #2563eb; color: white; border-radius: 8px; font-weight: 600; width: 100%; padding: 0.75rem; border: none; }
        .stButton>button:hover { background-color: #1d4ed8; transform: translateY(-2px); }
        .date-box { background-color: #e2e8f0; padding: 20px; border-radius: 12px; margin-bottom: 20px; border-left: 5px solid #2563eb; }
        .info-criacao { font-size: 0.85rem; color: #475569; margin-bottom: 10px; font-weight: 600; }
        .danger-zone { border: 1px solid #ef4444; padding: 15px; border-radius: 8px; background-color: #fef2f2; margin-top: 20px;}
    </style>
""", unsafe_allow_html=True)

st.title("🏫 Portal de Alocação - Cremilda")
st.markdown("<p style='text-align: center; color: #64748b;'>Módulo de Extração, Vigência e Versionamento</p>", unsafe_allow_html=True)

# ==============================================================================
# FUNÇÕES DE NEGÓCIO (MAPEAMENTO E CÁLCULO)
# ==============================================================================
def mapear_sala_pavilhao(turma, turno):
    t = turma.upper().replace(" ", "").replace("º", "").replace("°", "").replace("ANO", "")
    if turno == "MATUTINO":
        mapa = {'6A': ('13', 'P1E2'), '6B': ('14', 'P1E2'), '7A': ('15', 'P1E2'), '7B': ('16', 'P1E2'), '8A': ('17', 'P1E2'), '8B': ('18', 'P1E2'), '9A': ('19', 'P1E2'), '9B': ('06', 'P1E2'), '1A': ('01', 'P1E2'), '1B': ('20', 'P1E2'), '1C': ('04', 'P1E2'), '1D': ('05', 'P1E2'), '2A': ('21', 'P1E2'), '2B': ('22', 'P1E2'), '2C': ('23', 'P1E2'), '2D': ('24', 'P1E2'), '3A': ('08', 'P1E2'), '3B': ('09', 'P1E2'), '3C': ('10', 'P1E2'), '3D': ('11', 'P1E2'), '3E': ('12', 'P1E2')}
    else:
        mapa = {'6C': ('13', 'P2'), '6D': ('14', 'P2'), '6E': ('15', 'P2'), '6F': ('16', 'P2'), '6G': ('17', 'P2'), '7C': ('19', 'P2'), '7D': ('18', 'P2'), '7E': ('20', 'P2'), '7F': ('21', 'P2'), '8C': ('01', 'P2'), '8D': ('04', 'P2'), '8E': ('22', 'P2'), '8F': ('23', 'P2'), '8G': ('24', 'P2'), '9C': ('05', 'P1'), '9D': ('08', 'P1'), '9E': ('09', 'P1'), '9F': ('06', 'P1'), '1E': ('10', 'P1'), '1F': ('11', 'P1'), '2E': ('12', 'P1')}
    return mapa.get(t, ('00', 'P?'))

def formatar_nome_turma(turma_suja):
    # Transforma "9A" ou "9° Ano A" em "9º ANO A" perfeito
    t_limpa = turma_suja.upper().replace(" ", "").replace("º", "").replace("°", "").replace("ANO", "")
    serie_match = re.search(r'\d', t_limpa)
    letra_match = re.search(r'[A-Z]$', t_limpa)
    if serie_match and letra_match:
        return f"{serie_match.group(0)}º ANO {letra_match.group(0)}"
    return turma_suja

def extrair_dados(pdf_file, turno):
    dados = []
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables: continue
            turmas = []
            if len(tables[0]) > 0:
                for c in tables[0][0]:
                    if c and "ANO" in str(c).upper(): turmas.append(str(c).replace('\n', ' ').strip().upper())
            if not turmas:
                texto = page.extract_text()
                encontradas = re.findall(r'\d[°º]\s*(?:ANO|ano)\s*[A-Z]?', texto, re.IGNORECASE)
                for t in encontradas:
                    tc = t.replace('\n', ' ').strip().upper()
                    if tc not in turmas: turmas.append(tc)

            for idxd, table in enumerate(tables):
                if idxd >= 5: break 
                dia_nome = dias[idxd]
                start_row = 1 if (idxd == 0 and len(table) > 0 and any("ANO" in str(c).upper() for c in table[0])) else 0
                aula_num = 1
                for row in table[start_row:]:
                    row_clean = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
                    if not any("(" in c for c in row_clean): continue
                    for col_idx in range(1, len(row_clean)):
                        if col_idx - 1 < len(turmas):
                            turma_atual = formatar_nome_turma(turmas[col_idx - 1])
                            celula = row_clean[col_idx]
                            if "(" in celula and ")" in celula:
                                match = re.match(r'^(.*?)\s*\((.*?)\)$', celula)
                                if match:
                                    disc = match.group(1).strip()
                                    prof = match.group(2).strip().title()
                                    sala, pav = mapear_sala_pavilhao(turma_atual, turno)
                                    
                                    # Lógica exata de duração
                                    duracao = "0:45"
                                    if aula_num == 1: duracao = "0:50"
                                    if aula_num == 3: duracao = "0:50" 
                                    
                                    # Formato: Turno | Prof | Dia | Aula | Turma | Disc | Sala | Pav | Duracao
                                    dados.append([turno, prof, dia_nome, f"{aula_num}ª Aula", turma_atual, disc, f"S{sala}", pav, duracao])
                    aula_num += 1
    return dados

def calcular_datas(nome_arquivo):
    match = re.search(r'(\d{2})\s+(\d{2})', nome_arquivo)
    if match:
        ano = datetime.now().year
        dc_str = f"{match.group(1)}/{match.group(2)}/{ano}"
        try:
            dc = datetime.strptime(dc_str, "%d/%m/%Y")
            dias_seg = (0 - dc.weekday()) % 7
            if dias_seg == 0: dias_seg = 7 
            d_nova = dc + timedelta(days=dias_seg)
            d_velha = d_nova - timedelta(days=3) 
            return dc_str, d_nova.strftime("%d/%m/%Y"), d_velha.strftime("%d/%m/%Y")
        except: pass
    return "Não identificada", "", ""

# ==============================================================================
# COMUNICAÇÃO COM O GOOGLE SHEETS
# ==============================================================================
@st.cache_data(ttl=60)
def obter_info_planilha():
    try:
        creds = service_account.Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        planilha = client.open_by_key(ID_PLANILHA_MASTER)
        abas = planilha.worksheets()
        num_historicos = sum(1 for a in abas if str(a.title).startswith("HV"))
        return planilha, num_historicos
    except:
        return None, 0

planilha, num_historicos = obter_info_planilha()
versao_atual = num_historicos + 1
nova_versao_num = versao_atual + 1

# ==============================================================================
# FRONTEND E EXECUÇÃO
# ==============================================================================
col1, col2 = st.columns(2)
with col1: pdf_mat = st.file_uploader("PDF Matutino GERAL", type="pdf")
with col2: pdf_vesp = st.file_uploader("PDF Vespertino GERAL", type="pdf")

dc, d_nova, d_velha = calcular_datas(pdf_mat.name) if pdf_mat else ("Aguardando...", "", "")

st.markdown("<div class='date-box'>", unsafe_allow_html=True)
st.markdown(f"### ⚙️ O sistema está atualmente na **Versão {versao_atual}**")
st.markdown(f"<div class='info-criacao'>🕒 Data de criação no Urânia: {dc}</div>", unsafe_allow_html=True)

col_dt1, col_dt2 = st.columns(2)
with col_dt1:
    if versao_atual == 1:
        st.info("Primeiro horário do ano. Não há versão anterior para encerrar.")
        data_fim_velha = ""
    else:
        data_fim_velha = st.text_input(f"Encerramento da Versão {versao_atual} (Sexta):", value=d_velha)
with col_dt2:
    data_inicio_nova = st.text_input(f"Início da Versão {nova_versao_num} (Segunda):", value=d_nova)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='danger-zone'>", unsafe_allow_html=True)
resetar = st.checkbox("⚠️ MODO VIRADA DE ANO: Apagar todo o histórico e reiniciar na Versão 1.")
st.markdown("</div>", unsafe_allow_html=True)

if st.button(f"🚀 GERAR VERSÃO {1 if resetar else nova_versao_num} OFICIAL"):
    if not data_inicio_nova or not pdf_mat or not pdf_vesp:
        st.warning("⚠️ Preencha as datas e anexe os dois PDFs.")
    else:
        with st.spinner("Construindo a base de dados em bloco maciço..."):
            try:
                creds = service_account.Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=["https://www.googleapis.com/auth/spreadsheets"])
                client = gspread.authorize(creds)
                plan = client.open_by_key(ID_PLANILHA_MASTER)
                
                if resetar:
                    for a in plan.worksheets():
                        if str(a.title).startswith("HV") or str(a.title) == "BASE_DADOS_BRUTA":
                            try: plan.del_worksheet(a)
                            except: pass
                    nova_versao_num = 1
                else:
                    # ARQUIVAMENTO (Protegido contra Index Error)
                    try:
                        aba_bruta = plan.worksheet("BASE_DADOS_BRUTA")
                        dados_antigos = aba_bruta.get_all_values()
                        if len(dados_antigos) > 1:
                            while len(dados_antigos[0]) < 12: dados_antigos[0].append("")
                            dados_antigos[0][10] = data_fim_velha 
                            nome_historico = f"HV{versao_atual}_{data_fim_velha.replace('/', '-')}"
                            aba_bruta.update_title(nome_historico) 
                            aba_bruta.update(range_name='A1', values=dados_antigos)
                    except: pass

                # GERAÇÃO DA BASE NOVA VIGENTE
                nova_aba = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=15)
                pdf_mat.seek(0); pdf_vesp.seek(0)
                todos_dados = extrair_dados(pdf_mat, "MATUTINO") + extrair_dados(pdf_vesp, "VESPERTINO")
                
                # As colunas exatas que o Apps Script vai ler:
                # 0:Turno | 1:Prof | 2:Dia | 3:Aula | 4:Turma | 5:Disc | 6:Sala | 7:Pav | 8:Duracao | 9:Inicio | 10:Fim | 11:Versao
                cabecalho = ["Turno", "Professor", "Dia", "Horário", "Turma", "Disciplina", "Sala", "Pavilhao", "Duracao", data_inicio_nova, "Em Aberto", f"Versão {nova_versao_num}"]
                
                nova_aba.update(range_name='A1', values=[cabecalho] + todos_dados)
                
                st.success(f"✅ Sucesso absoluto! A Versão {nova_versao_num} foi gravada na folha de cálculo.")
                st.balloons()
            except Exception as e:
                st.error(f"Erro Crítico: {e}")
