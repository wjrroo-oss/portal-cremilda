import streamlit as st
import pdfplumber
from google.oauth2 import service_account
import gspread
import re
from datetime import datetime, timedelta, date

# ==============================================================================
# CONFIGURAÇÃO DE ACESSO
# ==============================================================================
ID_PLANILHA_MASTER = "1XtIoPk-BL7egviMXJy-qrb0NB--EM7X-l-emusS1f24"

# ==============================================================================
# DESIGN E LAYOUT (UI MODERNA)
# ==============================================================================
st.set_page_config(page_title="Portal Cremilda", page_icon="🏫", layout="wide")
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; font-family: 'Segoe UI', Tahoma, sans-serif; }
        .block-container { padding-top: 2rem; max-width: 1050px;}
        h1 { color: #0f172a; font-weight: 800; text-align: center; font-size: 2.2rem;}
        .subtitle { text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 2rem; }
        .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-top: 4px solid #3b82f6; margin-bottom: 20px;}
        .card-orange { border-top-color: #f59e0b; }
        .mode-box { background: #f0fdf4; border: 2px solid #22c55e; padding: 15px; border-radius: 10px; margin-bottom: 20px;}
        .danger-zone { border: 1px solid #fecaca; padding: 15px; border-radius: 8px; background-color: #fef2f2; margin-top: 10px;}
        .stButton>button { background-color: #2563eb; color: white; border-radius: 8px; font-weight: 700; width: 100%; padding: 0.8rem; font-size: 1.1rem; transition: 0.3s;}
        .stButton>button:hover { background-color: #1d4ed8; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>🏫 Gestor de Horários - Cremilda</h1>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Motor de Injeção com Calendário e Modos de Validação</div>", unsafe_allow_html=True)

# ==============================================================================
# FUNÇÕES DE NEGÓCIO E EXTRAÇÃO
# ==============================================================================
def calcular_sugestao_datas(nome_arquivo):
    """Lê a data do arquivo e converte para datetime.date para o Calendário do Streamlit"""
    # Regex melhorado para pegar "31 01", "31-01", etc.
    match = re.search(r'(?<!\d)(\d{2})[\s\-\.](\d{2})(?!\d)', nome_arquivo)
    hoje = datetime.now()
    if match:
        ano = hoje.year
        dc_str = f"{match.group(1)}/{match.group(2)}/{ano}"
        try:
            dc = datetime.strptime(dc_str, "%d/%m/%Y")
            dias_seg = (0 - dc.weekday()) % 7
            if dias_seg == 0: dias_seg = 7 # Pula para a próxima segunda
            d_nova = dc + timedelta(days=dias_seg)
            return d_nova.date()
        except: pass
    
    # Se falhar, sugere a próxima segunda-feira do dia de hoje
    prox_segunda = hoje + timedelta(days=(7 - hoje.weekday()))
    return prox_segunda.date()

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
    
    if nome_final == "2º ANO D":
        disc_up = str(disciplina).upper()
        if "LETRAMENTO" in disc_up:
            nome_final = "2º ANO D (Let)"
        elif "APROFUNDAMENTO" in disc_up:
            nome_final = "2º ANO D (Aprof)"
    return nome_final

def extrair_dados_pdf(pdf_file, turno, data_inicio_str, num_versao):
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
                                    turma_atual = formatar_nome_turma(turmas[col_idx - 1], disc)
                                    sala, pav = mapear_sala_pavilhao(turma_atual, turno)
                                    duracao = "0:50" if aula_num in [1, 3] else "0:45"
                                    
                                    # Colunas: 0:Turno | 1:Prof | 2:Dia | 3:Aula | 4:Turma | 5:Disc | 6:Sala | 7:Pav | 8:Dur | 9:Inicio | 10:Fim | 11:Versao
                                    dados.append([turno, prof, dia_nome, f"{aula_num}ª Aula", turma_atual, disc, f"S{sala}", pav, duracao, data_inicio_str, "Em Aberto", f"V{num_versao}"])
                    aula_num += 1
    return dados

# ==============================================================================
# LEITURA DO GOOGLE SHEETS
# ==============================================================================
def get_client():
    creds = service_account.Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds)

@st.cache_data(ttl=5) 
def obter_estado_sistema():
    client = get_client()
    planilha = client.open_by_key(ID_PLANILHA_MASTER)
    
    estado = {"mat": {"versao": 1, "inicio": "--/--/----"}, "vesp": {"versao": 1, "inicio": "--/--/----"}}
    abas_historico = []
    
    for aba in planilha.worksheets():
        nome = str(aba.title)
        if nome.startswith("HV"):
            abas_historico.append(nome)
        elif nome == "BASE_DADOS_BRUTA":
            dados = aba.get_all_values()
            for linha in dados[1:]:
                if len(linha) >= 12:
                    turno = str(linha[0]).upper()
                    versao_num = int(re.sub(r'\D', '', str(linha[11])) or 1)
                    if turno == "MATUTINO": estado["mat"] = {"versao": versao_num, "inicio": linha[9]}
                    elif turno == "VESPERTINO": estado["vesp"] = {"versao": versao_num, "inicio": linha[9]}
                    
    return estado, sorted(abas_historico)

try:
    estado_atual, abas_historico = obter_estado_sistema()
except:
    estado_atual = {"mat": {"versao": 1, "inicio": "-"}, "vesp": {"versao": 1, "inicio": "-"}}
    abas_historico = []

# ==============================================================================
# LIXEIRA: GESTÃO DO HISTÓRICO
# ==============================================================================
with st.expander("🗑️ Lixeira: Apagar Históricos Antigos ou Testes", expanded=False):
    st.write("Selecione as abas arquivadas que deseja excluir permanentemente do sistema.")
    if not abas_historico:
        st.info("Nenhuma aba de histórico encontrada.")
    else:
        abas_para_apagar = st.multiselect("Selecione as versões:", abas_historico)
        if st.button("Apagar Versões Selecionadas"):
            if abas_para_apagar:
                client = get_client()
                plan = client.open_by_key(ID_PLANILHA_MASTER)
                for nome_aba in abas_para_apagar:
                    try:
                        aba_del = plan.worksheet(nome_aba)
                        plan.del_worksheet(aba_del)
                    except: pass
                st.cache_data.clear()
                st.rerun()

# ==============================================================================
# SELETOR DE MODO DE OPERAÇÃO
# ==============================================================================
st.markdown("<div class='mode-box'>", unsafe_allow_html=True)
modo_operacao = st.radio(
    "👉 Selecione o Modo de Atualização:",
    options=["🧪 MODO TESTE: Substitui a grade atual para visualização, mas NÃO altera a versão nem cria backup.", 
             "📌 MODO VÁLIDO (OFICIAL): Atualiza a versão, cria backup do antigo e define este como o Horário Oficial."],
    index=0
)
st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# INJEÇÃO E CALENDÁRIO
# ==============================================================================
col1, col2 = st.columns(2)

with col1: 
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<h4>☀️ Matutino (Atual: V{estado_atual['mat']['versao']})</h4>", unsafe_allow_html=True)
    pdf_mat = st.file_uploader("PDF Matutino GERAL:", type="pdf", key="up_mat")
    
    # Calendário Inteligente do Streamlit
    sug_m = calcular_sugestao_datas(pdf_mat.name) if pdf_mat else datetime.today().date()
    data_mat = st.date_input("📅 Data de Início da Vigência:", value=sug_m, format="DD/MM/YYYY", key="dm")
    st.markdown("</div>", unsafe_allow_html=True)

with col2: 
    st.markdown("<div class='card card-orange'>", unsafe_allow_html=True)
    st.markdown(f"<h4>🌇 Vespertino (Atual: V{estado_atual['vesp']['versao']})</h4>", unsafe_allow_html=True)
    pdf_vesp = st.file_uploader("PDF Vespertino GERAL:", type="pdf", key="up_vesp")
    
    # Calendário Inteligente do Streamlit
    sug_v = calcular_sugestao_datas(pdf_vesp.name) if pdf_vesp else datetime.today().date()
    data_vesp = st.date_input("📅 Data de Início da Vigência:", value=sug_v, format="DD/MM/YYYY", key="dv")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='danger-zone'>", unsafe_allow_html=True)
resetar = st.checkbox("⚠️ MODO VIRADA DE ANO: Apagar a Base Bruta inteira (e todos os históricos) e recomeçar na Versão 1.")
st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# MOTOR BACKEND
# ==============================================================================
if st.button("🚀 INJETAR DADOS NA PLANILHA"):
    if not pdf_mat and not pdf_vesp and not resetar:
        st.warning("⚠️ Selecione pelo menos um PDF.")
    else:
        # Define as variáveis booleanas de modo
        is_valido = "OFICIAL" in modo_operacao
        
        # Converte as datas do calendário visual de volta para string para o Sheets
        str_data_mat = data_mat.strftime("%d/%m/%Y")
        str_data_vesp = data_vesp.strftime("%d/%m/%Y")

        with st.spinner("Modificando a base de dados no Google Sheets..."):
            try:
                client = get_client()
                plan = client.open_by_key(ID_PLANILHA_MASTER)
                
                # 1. MODO NUCLEAR
                if resetar:
                    for a in plan.worksheets():
                        if str(a.title).startswith("HV") or str(a.title) == "BASE_DADOS_BRUTA":
                            try: plan.del_worksheet(a)
                            except: pass
                    aba_bruta = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=12)
                    dados_antigos = []
                    v_mat_nova = 1
                    v_vesp_nova = 1
                
                # 2. ATUALIZAÇÃO PADRÃO
                else:
                    try:
                        aba_bruta = plan.worksheet("BASE_DADOS_BRUTA")
                        dados_antigos = aba_bruta.get_all_values()
                    except:
                        aba_bruta = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=12)
                        dados_antigos = []

                    # Lógica de Versão por Modo
                    if is_valido:
                        v_mat_nova = estado_atual['mat']['versao'] + 1 if pdf_mat else estado_atual['mat']['versao']
                        v_vesp_nova = estado_atual['vesp']['versao'] + 1 if pdf_vesp else estado_atual['vesp']['versao']
                    else:
                        v_mat_nova = estado_atual['mat']['versao']
                        v_vesp_nova = estado_atual['vesp']['versao']
                    
                    if v_mat_nova == 0: v_mat_nova = 1
                    if v_vesp_nova == 0: v_vesp_nova = 1

                    # Realiza o Backup Físico apenas se for MODO VÁLIDO
                    if is_valido and len(dados_antigos) > 1:
                        nome_snap = f"HV_Snapshot_{datetime.now().strftime('%d-%m-%H%M')}"
                        aba_bruta.update_title(nome_snap)
                        aba_bruta = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=12)

                # 3. Preservação Cruzada
                dados_preservados = []
                if len(dados_antigos) > 1:
                    for linha in dados_antigos[1:]: 
                        while len(linha) < 12: linha.append("")
                        turno = str(linha[0]).upper()
                        
                        if turno == "MATUTINO" and not pdf_mat: dados_preservados.append(linha)
                        if turno == "VESPERTINO" and not pdf_vesp: dados_preservados.append(linha)

                # 4. Extração (Passando a Data em String Formatada)
                dados_novos_mat = extrair_dados_pdf(pdf_mat, "MATUTINO", str_data_mat, v_mat_nova) if pdf_mat else []
                dados_novos_vesp = extrair_dados_pdf(pdf_vesp, "VESPERTINO", str_data_vesp, v_vesp_nova) if pdf_vesp else []

                # 5. Juntar e Injetar
                cabecalho = ["Turno", "Professor", "Dia", "Horário", "Turma", "Disciplina", "Sala", "Pavilhao", "Duracao", "Inicio_Vigencia", "Fim", "Versao_Turno"]
                dados_finais = [cabecalho] + dados_preservados + dados_novos_mat + dados_novos_vesp
                
                aba_bruta.clear()
                aba_bruta.update(range_name='A1', values=dados_finais)
                
                st.cache_data.clear()
                if is_valido:
                    st.success("✅ INJEÇÃO OFICIAL! Versão avançada e histórico salvo com sucesso.")
                    st.balloons()
                else:
                    st.info("🧪 TESTE CONCLUÍDO! Grade atualizada para testes. Nenhum histórico foi gerado.")
            except Exception as e:
                st.error(f"Erro Crítico: {e}")
