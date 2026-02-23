import streamlit as st
import pdfplumber
import pandas as pd
from google.oauth2 import service_account
import gspread

# --- COLE AQUI O ID DA SUA PLANILHA ---
ID_PLANILHA_MASTER = "1D1o5_DAN8A3wDIPd_ffPjIMFDr4q3o71" 

st.set_page_config(page_title="Portal Cremilda", page_icon="🏫")
st.title("🏫 Portal de Horários - Escola Cremilda")

# --- FUNÇÃO DE EXTRAÇÃO ---
def extrair_dados(pdf_file, turno):
    dados_extraidos = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                linhas = text.split('\n')
                for linha in linhas:
                    # Filtro básico (será refinado depois com base no PDF real)
                    if "Aula" in linha or "º" in linha:
                        dados_extraidos.append([turno, linha, "", "", "", "", ""])
    return dados_extraidos

# --- INTERFACE ---
st.write("Faça o upload dos PDFs gerados pelo Urânia para atualizar a base de dados.")
pdf_mat = st.file_uploader("PDF Matutino", type="pdf")
pdf_vesp = st.file_uploader("PDF Vespertino", type="pdf")

if st.button("🚀 ATUALIZAR BASE DE DADOS"):
    if not pdf_mat or not pdf_vesp:
        st.error("Por favor, insira os dois PDFs.")
    else:
        with st.spinner("O robô está digitando os dados na planilha..."):
            try:
                # 1. Conectar ao Google
                creds_dict = st.secrets["google_credentials"]
                creds = service_account.Credentials.from_service_account_info(
                    creds_dict, 
                    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                )
                client = gspread.authorize(creds)
                
                # 2. Abrir a Planilha e a Aba certa
                planilha = client.open_by_key(ID_PLANILHA_MASTER)
                aba_bruta = planilha.worksheet("BASE_DADOS_BRUTA")
                
                # 3. Ler PDFs
                dados_m = extrair_dados(pdf_mat, "MATUTINO")
                dados_v = extrair_dados(pdf_vesp, "VESPERTINO")
                todos_dados = dados_m + dados_v
                
                # 4. Limpar aba antiga e colocar dados novos
                aba_bruta.clear()
                # Recriar o cabeçalho
                aba_bruta.append_row(["Turno", "Professor", "Dia", "Horário", "Turma", "Disciplina", "Sala"])
                
                # Injetar as linhas
                if todos_dados:
                    aba_bruta.append_rows(todos_dados)
                
                st.success("✅ Base de dados atualizada! Pode abrir a sua planilha e gerar a grade.")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao escrever na planilha: {e}")
