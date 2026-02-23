import streamlit as st
import pdfplumber
import pandas as pd
from google.oauth2 import service_account
import gspread
import re

# --- COLE AQUI O ID DA SUA PLANILHA ---
ID_PLANILHA_MASTER = "1XtIoPk-BL7egviMXJy-qrb0NB--EM7X-l-emusS1f24" 

st.set_page_config(page_title="Portal Cremilda | Extração", page_icon="🏫")
st.title("🏫 Motor de Extração - Urânia")

# --- FUNÇÃO DE EXTRAÇÃO CIRÚRGICA ---
def extrair_dados_urania(pdf_file, turno):
    dados = []
    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables: continue

            # 1. Identificar as Turmas da Página
            turmas = []
            # Tenta pegar do cabeçalho da primeira tabela (ex: Vespertino)
            if len(tables[0]) > 0:
                for cell in tables[0][0]:
                    if cell and "ANO" in str(cell).upper():
                        turmas.append(str(cell).replace('\n', ' ').strip().upper())
            
            # Se não achou na tabela (ex: Matutino), busca no texto da página
            if not turmas:
                texto = page.extract_text()
                encontradas = re.findall(r'\d[°º]\s*(?:ANO|ano)\s*[A-Z]', texto, re.IGNORECASE)
                for t in encontradas:
                    t_clean = t.replace('\n', ' ').strip().upper()
                    if t_clean not in turmas:
                        turmas.append(t_clean)

            # 2. Ler os Dias e Aulas
            # O Urânia gera até 5 tabelas por página (Segunda a Sexta)
            for idx_dia, table in enumerate(tables):
                if idx_dia >= 5: break 
                dia_nome = dias_semana[idx_dia]
                
                # Se for a primeira tabela e tiver cabeçalho, pulamos a primeira linha
                start_row = 1 if (idx_dia == 0 and len(table) > 0 and any("ANO" in str(c).upper() for c in table[0])) else 0

                aula_num = 1
                for row in table[start_row:]:
                    row_clean = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                    
                    # Ignorar linhas vazias
                    if not any("(" in cell for cell in row_clean):
                        continue

                    # A coluna 0 é o marcador de dia, as turmas começam no índice 1
                    for col_idx in range(1, len(row_clean)):
                        if col_idx - 1 < len(turmas):
                            turma_atual = turmas[col_idx - 1]
                            celula = row_clean[col_idx]

                            if "(" in celula and ")" in celula:
                                # Quebra "HISTORIA (Odineia)" em Disciplina e Professor
                                match = re.match(r'^(.*?)\s*\((.*?)\)$', celula)
                                if match:
                                    disciplina = match.group(1).strip()
                                    professor = match.group(2).strip().title()

                                    # ORDEM DAS COLUNAS: Turno | Professor | Dia | Horário | Turma | Disciplina | Sala
                                    dados.append([turno, professor, dia_nome, f"{aula_num}ª Aula", turma_atual, disciplina, "A Definir"])
                    aula_num += 1
    return dados

# --- INTERFACE ---
st.write("Faça o upload dos relatórios **Gerais** do Urânia para preencher o banco de dados perfeitamente.")
pdf_mat = st.file_uploader("PDF Matutino GERAL", type="pdf")
pdf_vesp = st.file_uploader("PDF Vespertino GERAL", type="pdf")

if st.button("🚀 PREENCHER PLANILHA MESTRA"):
    if not pdf_mat or not pdf_vesp:
        st.error("Por favor, insira os PDFs Gerais dos dois turnos.")
    else:
        with st.spinner("Lendo PDFs, fatiando tabelas e digitando na planilha..."):
            try:
                # 1. Conexão Google
                creds_dict = st.secrets["google_credentials"]
                creds = service_account.Credentials.from_service_account_info(
                    creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                )
                client = gspread.authorize(creds)
                
                # 2. Planilha e Aba
                planilha = client.open_by_key(ID_PLANILHA_MASTER)
                aba_bruta = planilha.worksheet("BASE_DADOS_BRUTA")
                
                # 3. Extração Fina
                dados_m = extrair_dados_urania(pdf_mat, "MATUTINO")
                dados_v = extrair_dados_urania(pdf_vesp, "VESPERTINO")
                todos_dados = dados_m + dados_v
                
                # 4. Injeção
                aba_bruta.clear()
                aba_bruta.append_row(["Turno", "Professor", "Dia", "Horário", "Turma", "Disciplina", "Sala"])
                
                if todos_dados:
                    aba_bruta.append_rows(todos_dados)
                
                st.success("✅ Extração Cirúrgica Concluída! Abra a sua planilha e veja as colunas preenchidas.")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao processar: {e}")
