import streamlit as st
import pdfplumber
from google.oauth2 import service_account
import gspread
import re
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURAÇÃO DE ACESSO
# ==============================================================================
ID_PLANILHA_MASTER = "1XtIoPk-BL7egviMXJy-qrb0NB--EM7X-l-emusS1f24"

st.set_page_config(page_title="Gestor de Vigência", page_icon="🏫", layout="wide")
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
        .stButton>button { background-color: #2563eb; color: white; border-radius: 8px; font-weight: 700; width: 100%; padding: 0.8rem; font-size: 1.1rem;}
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>🏫 Motor de Vigência - Cremilda</h1>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Cálculo Automático de Início e Término de Horários</div>", unsafe_allow_html=True)

# ==============================================================================
# LÓGICA DE DATAS (O CÉREBRO)
# ==============================================================================
def calcular_sugestao_datas(nome_arquivo):
    matches = re.findall(r'(?<!\d)(\d{2})[\s\-\.]+(\d{2})(?!\d)', nome_arquivo)
    hoje = datetime.now()
    for match in matches:
        dia_str, mes_str = match
        ano = hoje.year
        try:
            dc = datetime.strptime(f"{dia_str}/{mes_str}/{ano}", "%d/%m/%Y")
            dias_para_segunda = (7 - dc.weekday()) % 7
            if dias_para_segunda == 0: dias_para_segunda = 7 
            return (dc + timedelta(days=dias_para_segunda)).date()
        except: continue
    return (hoje + timedelta(days=(7 - hoje.weekday())) % 7).date()

def calcular_sexta_anterior(data_inicio):
    """Pega a data de início (Segunda) e volta para a Sexta-feira anterior (-3 dias)"""
    return data_inicio - timedelta(days=3)

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
        if "LETR" in disc_up: nome_final = "2º ANO D (Let)"
        elif "APROF" in disc_up: nome_final = "2º ANO D (Aprof)"
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
                                    
                                    dados.append([turno, prof, dia_nome, f"{aula_num}ª Aula", turma_atual, disc, f"S{sala}", pav, duracao, data_inicio_str, "Em Aberto", f"V{num_versao}"])
                    aula_num += 1
    return dados

# ==============================================================================
# COMUNICAÇÃO GOOGLE SHEETS
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
        if nome.startswith("HV"): abas_historico.append(nome)
        elif nome == "BASE_DADOS_BRUTA":
            dados = aba.get_all_values()
            for linha in dados[1:]:
                if len(linha) >= 12:
                    turno = str(linha[0]).upper()
                    versao_num = int(re.sub(r'\D', '', str(linha[11])) or 1)
                    if turno == "MATUTINO": estado["mat"] = {"versao": versao_num, "inicio": linha[9]}
                    elif turno == "VESPERTINO": estado["vesp"] = {"versao": versao_num, "inicio": linha[9]}
    return estado, sorted(abas_historico)

try: estado_atual, abas_historico = obter_estado_sistema()
except: estado_atual = {"mat": {"versao": 1, "inicio": "-"}, "vesp": {"versao": 1, "inicio": "-"}}; abas_historico = []

with st.expander("🗑️ Lixeira: Apagar Históricos Antigos", expanded=False):
    abas_para_apagar = st.multiselect("Selecione as versões:", abas_historico)
    if st.button("Apagar Selecionadas"):
        client = get_client(); plan = client.open_by_key(ID_PLANILHA_MASTER)
        for nome_aba in abas_para_apagar:
            try: plan.del_worksheet(plan.worksheet(nome_aba))
            except: pass
        st.cache_data.clear(); st.rerun()

st.markdown("<div class='mode-box'>", unsafe_allow_html=True)
modo_operacao = st.radio("👉 Selecione o Modo:", options=["🧪 MODO TESTE (Apenas visualização. Não avança versão nem cria histórico)", "📌 MODO VÁLIDO (Arquiva o antigo calculando a data de fim, e avança a versão)"], index=0)
st.markdown("</div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1: 
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<h4>☀️ Matutino (Atual: V{estado_atual['mat']['versao']})</h4>", unsafe_allow_html=True)
    pdf_mat = st.file_uploader("PDF Matutino:", type="pdf", key="up_mat")
    sug_m = calcular_sugestao_datas(pdf_mat.name) if pdf_mat else datetime.today().date()
    data_mat = st.date_input("📅 Início da Vigência (Mat):", value=sug_m, format="DD/MM/YYYY", key="dm")
    st.markdown("</div>", unsafe_allow_html=True)

with col2: 
    st.markdown("<div class='card card-orange'>", unsafe_allow_html=True)
    st.markdown(f"<h4>🌇 Vespertino (Atual: V{estado_atual['vesp']['versao']})</h4>", unsafe_allow_html=True)
    pdf_vesp = st.file_uploader("PDF Vespertino:", type="pdf", key="up_vesp")
    sug_v = calcular_sugestao_datas(pdf_vesp.name) if pdf_vesp else datetime.today().date()
    data_vesp = st.date_input("📅 Início da Vigência (Vesp):", value=sug_v, format="DD/MM/YYYY", key="dv")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='danger-zone'>", unsafe_allow_html=True)
resetar = st.checkbox("⚠️ MODO VIRADA DE ANO: Apagar a Base Bruta inteira (e todos os históricos).")
st.markdown("</div>", unsafe_allow_html=True)

if st.button("🚀 INJETAR DADOS"):
    if not pdf_mat and not pdf_vesp and not resetar: st.warning("Selecione um PDF.")
    else:
        is_valido = "VÁLIDO" in modo_operacao
        str_data_mat = data_mat.strftime("%d/%m/%Y")
        str_data_vesp = data_vesp.strftime("%d/%m/%Y")

        with st.spinner("Modificando a base..."):
            try:
                client = get_client(); plan = client.open_by_key(ID_PLANILHA_MASTER)
                
                if resetar:
                    for a in plan.worksheets():
                        if str(a.title).startswith("HV") or str(a.title) == "BASE_DADOS_BRUTA":
                            try: plan.del_worksheet(a)
                            except: pass
                    aba_bruta = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=12)
                    dados_antigos = []; v_mat_nova = 1; v_vesp_nova = 1
                else:
                    try: aba_bruta = plan.worksheet("BASE_DADOS_BRUTA"); dados_antigos = aba_bruta.get_all_values()
                    except: aba_bruta = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=12); dados_antigos = []

                    if is_valido:
                        v_mat_nova = estado_atual['mat']['versao'] + 1 if pdf_mat else estado_atual['mat']['versao']
                        v_vesp_nova = estado_atual['vesp']['versao'] + 1 if pdf_vesp else estado_atual['vesp']['versao']
                    else:
                        v_mat_nova = estado_atual['mat']['versao']; v_vesp_nova = estado_atual['vesp']['versao']
                    
                    if v_mat_nova == 0: v_mat_nova = 1
                    if v_vesp_nova == 0: v_vesp_nova = 1

                    # O GRANDE TRUQUE: Calcular a data final e dar nome limpo à aba!
                    if is_valido and len(dados_antigos) > 1:
                        fim_mat_str = calcular_sexta_anterior(data_mat).strftime("%d/%m/%Y") if pdf_mat else ""
                        fim_vesp_str = calcular_sexta_anterior(data_vesp).strftime("%d/%m/%Y") if pdf_vesp else ""
                        
                        # Atualiza a coluna "Fim" (índice 10) do horário antigo!
                        for idx, linha in enumerate(dados_antigos[1:]):
                            while len(linha) < 12: linha.append("")
                            t = str(linha[0]).upper()
                            if t == "MATUTINO" and pdf_mat and not linha[10] and linha[9] != "--/--/----": linha[10] = fim_mat_str
                            if t == "VESPERTINO" and pdf_vesp and not linha[10] and linha[9] != "--/--/----": linha[10] = fim_vesp_str
                            dados_antigos[idx+1] = linha

                        data_nome_aba = (fim_mat_str or fim_vesp_str).replace("/", "-")[:5] # Pega dia-mes
                        nome_snap = f"HV: Encerrado em {data_nome_aba}"
                        
                        aba_bruta.update_title(nome_snap)
                        aba_bruta.update(range_name='A1', values=dados_antigos) # Salva com o fim preenchido
                        aba_bruta = plan.add_worksheet(title="BASE_DADOS_BRUTA", rows=3000, cols=12)

                dados_preservados = []
                if len(dados_antigos) > 1:
                    for linha in dados_antigos[1:]: 
                        while len(linha) < 12: linha.append("")
                        t = str(linha[0]).upper()
                        if t == "MATUTINO" and not pdf_mat: dados_preservados.append(linha)
                        if t == "VESPERTINO" and not pdf_vesp: dados_preservados.append(linha)

                dados_novos_mat = extrair_dados_pdf(pdf_mat, "MATUTINO", str_data_mat, v_mat_nova) if pdf_mat else []
                dados_novos_vesp = extrair_dados_pdf(pdf_vesp, "VESPERTINO", str_data_vesp, v_vesp_nova) if pdf_vesp else []

                cabecalho = ["Turno", "Professor", "Dia", "Horário", "Turma", "Disciplina", "Sala", "Pavilhao", "Duracao", "Inicio_Vigencia", "Fim", "Versao_Turno"]
                dados_finais = [cabecalho] + dados_preservados + dados_novos_mat + dados_novos_vesp
                
                aba_bruta.clear()
                aba_bruta.update(range_name='A1', values=dados_finais)
                
                st.cache_data.clear()
                if is_valido: st.success("✅ INJEÇÃO OFICIAL! Fim calculado e aba limpa gerada.")
                else: st.info("🧪 TESTE CONCLUÍDO!")
            except Exception as e: st.error(f"Erro Crítico: {e}")
