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
# DESIGN E LAYOUT (CSS INJETADO - JAMSTACK UX)
# ==============================================================================
st.set_page_config(page_title="Portal Cremilda", page_icon="🏫", layout="wide")
st.markdown("""
    <style>
        /* Reset e Fontes */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        .stApp { background-color: #f1f5f9; font-family: 'Inter', sans-serif; }
        
        /* Centralização Perfeita e Espaçamento */
        .block-container { max-width: 900px; padding-top: 3rem; padding-bottom: 3rem; }
        
        /* Estilos de Texto */
        h1 { color: #0f172a; font-weight: 800; text-align: center; font-size: 2.5rem; margin-bottom: 0.5rem;}
        h3 { color: #334155; font-weight: 600; font-size: 1.2rem; }
        .subtitle { text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 2rem; }
        
        /* Cards e Boxes */
        .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px -3px rgba(0,0,0,0.05); margin-bottom: 20px; border-top: 4px solid #3b82f6;}
        .card-orange { border-top-color: #f59e0b; }
        .date-box { background-color: #f8fafc; padding: 15px; border-radius: 8px; border-left: 4px solid #10b981; margin-bottom: 15px; }
        .danger-zone { border: 1px solid #fecaca; padding: 20px; border-radius: 10px; background-color: #fef2f2; margin-top: 30px;}
        
        /* Botões Padrão App */
        .stButton>button { background-color: #2563eb; color: white; border-radius: 8px; font-weight: 700; width: 100%; padding: 0.8rem; border: none; transition: all 0.3s; font-size: 1.1rem;}
        .stButton>button:hover { background-color: #1d4ed8; transform: translateY(-2px); box-shadow: 0 4px 6px rgba(37,99,235,0.2); }
        
        /* Ajuste nativo do Streamlit */
        div[data-testid="stFileUploader"] { padding: 1.5rem; background-color: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>🏫 Portal de Alocação</h1>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Módulo de Extração Inteligente Urânia → Sheets</div>", unsafe_allow_html=True)

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

def formatar_nome_turma(turma_suja, disciplina):
    t_limpa = turma_suja.upper().replace(" ", "").replace("º", "").replace("°", "").replace("ANO", "")
    serie_match = re.search(r'\d', t_limpa)
    letra_match = re.search(r'[A-Z]$', t_limpa)
    
    nome_final = turma_suja
    if serie_match and letra_match:
        nome_final = f"{serie_match.group(0)}º ANO {letra_match.group(0)}"
    
    # A BALA DE PRATA PARA O 2º ANO D (Salva na base bruta já mastigado!)
    if nome_final == "2º ANO D":
        disc_up = str(disciplina).upper()
        if "LETRAMENTO" in disc_up:
            nome_final = "2º ANO D (Let)"
        elif "APROFUNDAMENTO" in disc_up:
            nome_final = "2º ANO D (Aprof)"
            
    return nome_final

def extrair_dados(pdf_file, turno, data_inicio, num_versao):
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
                            celula = row_clean[col_idx]
                            if "(" in celula and ")" in celula:
                                match = re.match(r'^(.*?)\s*\((.*?)\)$', celula)
                                if match:
                                    disc = match.group(1).strip()
                                    prof = match.group(2).strip().title()
                                    
                                    # Passa a disciplina para formar o nome final do 2º ANO D
                                    turma_atual = formatar_nome_turma(turmas[col_idx - 1], disc)
                                    sala, pav = mapear_sala_pavilhao(turma_atual, turno)
                                    
                                    duracao = "0:50" if aula_num in [1, 3] else "0:45"
                                    
                                    # Colunas: 0:Turno | 1:Prof | 2:Dia | 3:Aula | 4:Turma | 5:Disc | 6:Sala | 7:Pav | 8:Dur | 9:Inicio | 10:Fim | 11:Versao
                                    dados.append([turno, prof, dia_nome, f"{aula_num}ª Aula", turma_atual, disc, f"S{sala}", pav, duracao, data_inicio, "Em Aberto", f"V{num_versao}"])
                    aula_num += 1
    return dados

# ==============================================================================
# COMUNICAÇÃO COM O GOOGLE SHEETS
# ==============================================================================
@st.cache_data(ttl=60)
def obter_info_planilha():
    try:
        creds = service_account.Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        planilha = client.open_by_key(ID_PLANILHA_MASTER)
        
        # Puxa a base bruta atual para descobrir como estão os turnos
        try:
            aba_bruta = planilha.worksheet("BASE_DADOS_BRUTA")
            dados_atuais = aba_bruta.get_all_values()
        except:
            dados_atuais = []

        abas = planilha.worksheets()
        num_historicos = sum(1 for a in abas if str(a.title).startswith("HV"))
        
        return planilha, num_historicos, dados_atuais
    except Exception as e:
        return None, 0, []

planilha, num_historicos, dados_atuais = obter_info_planilha()
versao_global = num_historicos + 1

# ==============================================================================
# INTERFACE GRÁFICA (VIGÊNCIA INDEPENDENTE)
# ==============================================================================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("<h3>📝 Atualização por Turno (Vigência Independente)</h3>", unsafe_allow_html=True)
st.write("Anexe apenas o PDF do turno que sofreu alteração. Se enviar os dois, ambos serão atualizados.")

col1, col2 = st.columns(2)
with col1: 
    st.markdown("**Turno Matutino**")
    pdf_mat = st.file_uploader("PDF Matutino GERAL", type="pdf")
    data_mat = st.text_input("Data de Início (Matutino):", value="--/--/2026", key="dm")

with col2: 
    st.markdown("**Turno Vespertino**")
    pdf_vesp = st.file_uploader("PDF Vespertino GERAL", type="pdf")
    data_vesp = st.text_input("Data de Início (Vespertino):", value="--/--/2026", key="dv")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='danger-zone'>", unsafe_allow_html=True)
st.markdown("<h3 style='color: #b91c1c;'>⚠️ Opções Avançadas</h3>", unsafe_allow_html=True)
arquivar = st.checkbox("Arquivar horário antigo (Recomendado se a mudança for grande)")
resetar = st.checkbox("MODO VIRADA DE ANO: Apagar tudo e reiniciar na Versão 1.")
st.markdown("</div>", unsafe_allow_html=True)

if st.button(f"🚀 INJETAR DADOS NO SISTEMA"):
    if not pdf_mat and not pdf_vesp:
        st.warning("⚠️ Precisa de anexar pelo menos um ficheiro PDF.")
    else:
        with st.spinner("Processando Inteligência de Turnos..."):
            try:
                creds = service_account.Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=["https://www.googleapis.com/auth/spreadsheets"])
                client = gspread.authorize(creds)
                plan = client.open_by_key(ID_PLANILHA_MASTER)
                
                # 1. Reset Global (Virada de ano)
                if resetar:
                    for a in plan.worksheets():
                        if str(a.title).startswith("HV") or str(a.title) == "BASE_DADOS_BRUTA":
                            try: plan.del_worksheet(a)
                            except: pass
                    versao_global = 1
                    aba_bruta = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=12)
                    dados_antigos = []
                else:
                    aba_bruta = plan.worksheet("BASE_DADOS_BRUTA")
                    dados_antigos = aba_bruta.get_all_values()
                    
                    # 2. Lógica de Arquivamento (Guarda um snapshot do que estava lá)
                    if arquivar and len(dados_antigos) > 1:
                        nome_historico = f"HV{versao_global}_{datetime.now().strftime('%d-%m-%H%M')}"
                        aba_bruta.update_title(nome_historico) 
                        aba_bruta = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=12)
                        versao_global += 1

                # 3. Separa os dados antigos que NÃO foram atualizados
                dados_preservados = []
                if len(dados_antigos) > 1:
                    for linha in dados_antigos[1:]: # Ignora cabeçalho
                        turno = linha[0].upper()
                        # Se subiu o Matutino, apaga o Matutino velho. Mas preserva o Vespertino (se não subiu Vesp novo).
                        if turno == "MATUTINO" and not pdf_mat:
                            dados_preservados.append(linha)
                        if turno == "VESPERTINO" and not pdf_vesp:
                            dados_preservados.append(linha)

                # 4. Extrai os Dados Novos (Com a Versão Global sendo usada como ID do Lote)
                dados_novos_mat = extrair_dados(pdf_mat, "MATUTINO", data_mat, versao_global) if pdf_mat else []
                dados_novos_vesp = extrair_dados(pdf_vesp, "VESPERTINO", data_vesp, versao_global) if pdf_vesp else []

                # 5. Junta tudo (O Frankenstein Perfeito)
                cabecalho = ["Turno", "Professor", "Dia", "Horário", "Turma", "Disciplina", "Sala", "Pavilhao", "Duracao", "Inicio_Vigencia", "Fim", "Versao_Turno"]
                dados_finais = [cabecalho] + dados_preservados + dados_novos_mat + dados_novos_vesp
                
                # 6. Limpa e Atualiza
                aba_bruta.clear()
                aba_bruta.update(range_name='A1', values=dados_finais)
                
                st.success("✅ Extração Impecável! Turnos atualizados de forma independente.")
                st.balloons()
            except Exception as e:
                st.error(f"Erro Crítico: {e}")
