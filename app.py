import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import os

# ==========================================
# 1. CONFIGURAÇÕES INICIAIS E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="Dashboard Escolar", layout="wide")

# Criar pasta para salvar os uploads (Mural e Avisos)
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Conexão com o banco de dados SQLite (cria o arquivo se não existir)
conn = sqlite3.connect('escola_dados.db', check_same_thread=False)
c = conn.cursor()

# Criação das tabelas para cruzar dados e evitar duplicidades
c.execute('''
    CREATE TABLE IF NOT EXISTS eventos_extras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_evento DATE,
        tipo TEXT,
        descricao TEXT,
        arquivo_path TEXT,
        UNIQUE(data_evento, descricao) -- Evita duplicar o mesmo evento na mesma data
    )
''')
c.execute('''
    CREATE TABLE IF NOT EXISTS avisos_gerais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_aviso DATE,
        titulo TEXT,
        texto TEXT,
        link TEXT,
        arquivo_path TEXT,
        UNIQUE(data_aviso, titulo)
    )
''')
conn.commit()

# Função auxiliar para salvar arquivos upados
def salvar_arquivo(uploaded_file, subpasta):
    if uploaded_file is not None:
        caminho_completo = os.path.join(UPLOAD_DIR, f"{subpasta}_{uploaded_file.name}")
        with open(caminho_completo, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return caminho_completo
    return None

# ==========================================
# 2. MENU LATERAL (NAVEGAÇÃO)
# ==========================================
st.sidebar.title("Navegação")
menu = st.sidebar.radio("Ir para:", 
    ["Diário de Bordo (Home)", "Uploads Urânia e Extras", "Avisos Gerais"]
)

# ==========================================
# 3. TELA: UPLOADS URÂNIA E EVENTOS EXTRAS
# ==========================================
if menu == "Uploads Urânia e Extras":
    st.header("Uploads de Horários e Eventos Extras")
    
    st.subheader("1. Arquivos do Urânia")
    col1, col2 = st.columns(2)
    with col1:
        urania_mat_geral = st.file_uploader("Urânia - Geral Matutino (PDF)", type=["pdf", "csv", "xlsx"])
        urania_mat_apa = st.file_uploader("Urânia - APA Matutino (PDF)", type=["pdf", "csv", "xlsx"])
    with col2:
        urania_vesp_geral = st.file_uploader("Urânia - Geral Vespertino (PDF)", type=["pdf", "csv", "xlsx"])
        urania_vesp_apa = st.file_uploader("Urânia - APA Vespertino (PDF)", type=["pdf", "csv", "xlsx"])
        
    st.write("---")
    
    st.subheader("2. Mural de Eventos Extras (Palestras, Aulas Extras)")
    with st.form("form_eventos_extras"):
        data_evento = st.date_input("Data do Evento")
        tipo_evento = st.selectbox("Tipo de Evento", ["Palestra", "Aula Extra", "Reunião de Pais", "Conselho de Classe", "Outros"])
        desc_evento = st.text_input("Descrição do Evento")
        arquivo_extra = st.file_uploader("Anexar Arquivo (PDF/Imagem)", type=["pdf", "png", "jpg", "jpeg"])
        
        submit_evento = st.form_submit_button("Registrar Evento no Mural")
        
        if submit_evento:
            caminho_arquivo = salvar_arquivo(arquivo_extra, "evento")
            try:
                c.execute("INSERT INTO eventos_extras (data_evento, tipo, descricao, arquivo_path) VALUES (?, ?, ?, ?)",
                          (data_evento, tipo_evento, desc_evento, caminho_arquivo))
                conn.commit()
                st.success("Evento registrado com sucesso no Mural!")
            except sqlite3.IntegrityError:
                st.warning("Este evento já está registrado nesta data (Duplicidade evitada).")

# ==========================================
# 4. TELA: AVISOS GERAIS (DASHBOARD EXTRA)
# ==========================================
elif menu == "Avisos Gerais":
    st.header("Mural de Avisos Gerais")
    
    # Formulário para cadastrar novos avisos
    with st.expander("➕ Adicionar Novo Aviso", expanded=False):
        with st.form("form_avisos"):
            data_aviso = st.date_input("Data de Referência/Prazo do Aviso")
            titulo_aviso = st.text_input("Título do Aviso")
            texto_aviso = st.text_area("Descrição / Informações")
            link_aviso = st.text_input("Link de Apoio (opcional)")
            arquivo_aviso = st.file_uploader("Anexar Arquivo (PDF, Imagens)", type=["pdf", "png", "jpg", "jpeg"])
            
            submit_aviso = st.form_submit_button("Publicar Aviso")
            
            if submit_aviso:
                caminho_arq = salvar_arquivo(arquivo_aviso, "aviso")
                try:
                    c.execute("INSERT INTO avisos_gerais (data_aviso, titulo, texto, link, arquivo_path) VALUES (?, ?, ?, ?, ?)",
                              (data_aviso, titulo_aviso, texto_aviso, link_aviso, caminho_arq))
                    conn.commit()
                    st.success("Aviso publicado com sucesso!")
                except sqlite3.IntegrityError:
                    st.warning("Um aviso com este título já existe para esta data.")
    
    st.write("---")
    
    # Exibição dos Avisos Filtrados por Data
    st.subheader("Consultar Avisos")
    df_avisos = pd.read_sql_query("SELECT * FROM avisos_gerais ORDER BY data_aviso DESC", conn)
    
    if not df_avisos.empty:
        # Pega as datas únicas para o Selectbox (setinhas de seleção)
        datas_disponiveis = df_avisos['data_aviso'].unique()
        data_selecionada = st.selectbox("Selecione a Data do Aviso:", datas_disponiveis)
        
        # Filtra os avisos pela data selecionada
        avisos_filtrados = df_avisos[df_avisos['data_aviso'] == data_selecionada]
        
        for index, row in avisos_filtrados.iterrows():
            with st.expander(f"📌 {row['titulo']}"):
                st.write(f"**Detalhes:** {row['texto']}")
                if row['link']:
                    st.markdown(f"[🔗 Link de Acesso]({row['link']})")
                if row['arquivo_path']:
                    st.write(f"📁 Arquivo anexado: `{os.path.basename(row['arquivo_path'])}`")
                    # Em um app real, aqui você usaria st.download_button para o arquivo
    else:
        st.info("Nenhum aviso registrado ainda.")

# ==========================================
# 5. TELA: DIÁRIO DE BORDO (CONTAGEM REGRESSIVA)
# ==========================================
elif menu == "Diário de Bordo (Home)":
    st.header("Diário de Bordo")
    st.write("Acompanhe aqui os prazos, termos obrigatórios e contagens regressivas para os próximos eventos e avisos.")
    
    hoje = date.today()
    
    # Buscar Eventos e Avisos futuros
    df_eventos = pd.read_sql_query(f"SELECT data_evento, tipo, descricao FROM eventos_extras WHERE data_evento >= '{hoje}'", conn)
    df_avisos_futuros = pd.read_sql_query(f"SELECT data_aviso, titulo, texto FROM avisos_gerais WHERE data_aviso >= '{hoje}'", conn)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⏳ Contagem Regressiva - Eventos")
        if not df_eventos.empty:
            for index, row in df_eventos.iterrows():
                data_ev = datetime.strptime(row['data_evento'], '%Y-%m-%d').date()
                dias_faltando = (data_ev - hoje).days
                
                if dias_faltando == 0:
                    cor = "red"
                    texto_dias = "É HOJE!"
                elif dias_faltando <= 3:
                    cor = "orange"
                    texto_dias = f"Faltam {dias_faltando} dias!"
                else:
                    cor = "green"
                    texto_dias = f"Faltam {dias_faltando} dias"
                    
                st.markdown(f"<h4 style='color: {cor};'>{texto_dias}</h4>", unsafe_allow_html=True)
                st.write(f"**{row['tipo']}**: {row['descricao']} ({data_ev.strftime('%d/%m/%Y')})")
                st.write("---")
        else:
            st.info("Nenhum evento futuro programado.")

    with col2:
        st.subheader("⏳ Contagem Regressiva - Termos e Avisos")
        if not df_avisos_futuros.empty:
            for index, row in df_avisos_futuros.iterrows():
                data_av = datetime.strptime(row['data_aviso'], '%Y-%m-%d').date()
                dias_faltando = (data_av - hoje).days
                
                texto_dias = "PRAZO HOJE!" if dias_faltando == 0 else f"Vence em {dias_faltando} dias"
                st.error(f"**{texto_dias}** - {row['titulo']}")
                st.caption(f"Prazo: {data_av.strftime('%d/%m/%Y')}")
        else:
            st.success("Tudo em dia! Nenhum aviso pendente.")
