import streamlit as st
import pdfplumber
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread

# IDs QUE VOCÊ PASSOU
ID_PASTA_2026 = "1R820oGrk43IDYS3GjE7K4Qe9Zs03Vq6A"
ID_PLANILHA_MASTER = "1g4Czl95Wfp3gw8moJ1GnPqd73XqhGxjJvj1vDc34fvY"

# Configuração da Página
st.set_page_config(page_title="Portal Cremilda", page_icon="🏫")
st.title("🏫 Portal de Horários - Escola Cremilda")

# --- FUNÇÃO DE EXTRAÇÃO (O Motor) ---
def extrair_dados(pdf_file, turno):
    dados_extraidos = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                linhas = text.split('\n')
                for linha in linhas:
                    # Lógica simplificada para encontrar Turma e Professor
                    if "Aula" in linha or "º" in linha:
                        dados_extraidos.append([turno, linha]) # Exemplo simplificado
    return dados_extraidos

# --- INTERFACE ---
nome_versao = st.text_input("Nome da Nova Versão", placeholder="Ex: Horario_Oficial_Marco")
pdf_mat = st.file_uploader("PDF Matutino Geral", type="pdf")
pdf_vesp = st.file_uploader("PDF Vespertino Geral", type="pdf")

if st.button("🚀 GERAR E ARQUIVAR NO DRIVE"):
    if not nome_versao or not pdf_mat or not pdf_vesp:
        st.error("Preencha todos os campos!")
    else:
        try:
            with st.spinner("Conectando ao Google Drive..."):
                # Carregar credenciais dos Secrets
                creds_dict = st.secrets["google_credentials"]
                creds = service_account.Credentials.from_service_account_info(creds_dict)
                
                service_drive = build('drive', 'v3', credentials=creds)
                client_sheets = gspread.authorize(creds)

                # 1. Criar Pasta da Versão
                folder_metadata = {
                    'name': nome_versao,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [ID_PASTA_2026]
                }
                nova_pasta = service_drive.files().create(body=folder_metadata, fields='id').execute()
                id_nova_pasta = nova_pasta.get('id')

                # 2. Clonar Planilha Master para a nova pasta
                copy_metadata = {
                    'name': f"Planilha_{nome_versao}",
                    'parents': [id_nova_pasta]
                }
                copia = service_drive.files().copy(fileId=ID_PLANILHA_MASTER, body=copy_metadata).execute()
                
                st.success(f"✅ Versão {nome_versao} criada com sucesso na pasta 2026!")
                st.balloons()
        except Exception as e:
            st.error(f"Erro técnico: {e}")
