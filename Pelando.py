from webdriver_manager.firefox import GeckoDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
import time
import traceback
import pandas as pd
import re
import requests
import os
import tempfile
from datetime import datetime
from PIL import Image
from io import BytesIO
import google.generativeai as genai
from fpdf import FPDF
from googleapiclient.discovery import build
import streamlit as st

# Campo de busca (input de texto)
busca = st.text_input("Está buscando qual produto?")
if isinstance(busca, tuple):
    busca = busca[0]

if st.button("Buscar", key="busca"):
    if busca:
        st.spinner(f"Buscando {busca}...")
        # Aqui você roda sua lógica de busca, exibe resultados, etc.
    else:
        st.warning("Por favor, digite algo para buscar.")


options = Options()
options.headless = True

service = Service(executable_path="/usr/bin/geckodriver")

#############################BLOCO PELANDO#################################################################################
@st.cache_data(show_spinner="Buscando ofertas no Pelando...")
def buscar_ofertas_pelando(busca):

    driver = webdriver.Firefox(service=service, options=options)

    url = f"https://www.pelando.com.br/busca/{busca.replace(' ', '-')}"
    driver.get(url)

    time.sleep(5)  # Aguarda carregamento JS

    cards = driver.find_elements(By.CSS_SELECTOR, "li > div._deal-card_1jdb6_25._default-deal-card_1mw5o_31")

    titulos = []
    precos = []
    links = []
    status_list = []

    for card in cards[:15]:
        try:
            titulo_elem = card.find_element(By.CSS_SELECTOR, "a._title_mszsg_31._default-deal-card-title_1mw5o_71")
            preco_elem = card.find_element(By.CSS_SELECTOR, "span._deal-card-stamp_15l5n_25")

            titulo = titulo_elem.text.strip()
            preco = preco_elem.text.strip().replace('\n', '')
            link = titulo_elem.get_attribute("href")

            try:
                status_elem = card.find_element(By.CSS_SELECTOR, "div._inactive-label_1glvo_38")
                status = status_elem.text.strip()
            except:
                status = "Ativa"

            titulos.append(titulo)
            precos.append(preco)
            links.append(link)
            status_list.append(status)

        except Exception as e:
            st.error(f"Erro ao extrair item: {e}")

    driver.quit()
    return titulos, precos, links, status_list

if busca:
    titulos, precos, links, status_list = buscar_ofertas_pelando(busca)

    # Checkbox para decidir se quer buscar ofertas relacionadas
    if st.button("Mostrar ofertas no Pelando", key="busca_pelando"):

        # Exibir resultados no Streamlit
        for i in range(len(titulos)):
            if status_list[i].lower() == "ativa":   
                st.markdown(f"##### {titulos[i]}")
                st.write(f"Preço: {precos[i]}")
                st.write(f"Status: {status_list[i]}")
                st.write(f"[Link da oferta]({links[i]})")

#######################################BLOCO TODAS AS OFERTAS#############################################################################################
@st.cache_data(show_spinner="Buscando produtos no Buscape...")
def buscar_buscape(busca):
    driver = webdriver.Firefox(service=service, options=options)

    url_buscape = f"https://www.buscape.com.br/search?q={busca.replace(' ', '%20')}&hitsPerPage=48&page=1&sortBy=price_asc"

    driver.get(url_buscape)
    time.sleep(5)  # Espera o carregamento via JavaScript

    cards = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='product-card']")

    titulos = []
    precos = []
    links = []
    lojas = []

    for card in cards[:15]:
        try:
            # Título do produto
            titulo_elem = card.find_element(By.CSS_SELECTOR, "h2[data-testid='product-card::name']")
            titulo = titulo_elem.text.strip()

            # Preço do produto
            preco_elem = card.find_element(By.CSS_SELECTOR, "p[data-testid='product-card::price']")
            preco = preco_elem.text.strip()

            # Link do produto
            link_elem = card.find_element(By.CSS_SELECTOR, "a[data-testid='product-card::card']")
            link = link_elem.get_attribute("href")

            # Nome da loja
            try:
                loja_elem = card.find_element(By.CSS_SELECTOR, "span.ProductCard_ProductCard_Link__vMbJq")
                loja = loja_elem.text.strip()
            except:
                loja = "Loja não encontrada"

            # Adiciona aos arrays
            titulos.append(titulo)
            precos.append(preco)
            links.append(link)
            lojas.append(loja)

        except Exception as e:
            print("Erro ao extrair item:", e)

    driver.quit()
    return titulos, precos, links, lojas

@st.cache_data(show_spinner="Gerando descrições dos produtos...")
def gerar_descricoes_formatadas(titulos):
    descricoes = []
    # Configurar a chave de API
    genai.configure(api_key="AIzaSyBqSIvFig8B5-2_WjRCVpNQ1twI3KeoRB4")

    # Instanciar o modelo
    model = genai.GenerativeModel("gemini-1.5-flash")

    for titulo in titulos:
        prompt = (
            f"""De acordo com o título abaixo, qual o nome do produto, a marca e as características técnicas principais?
    Use exclusivamente o título que estou enviando para responder.

    Modelo que você deve seguir:

    Produto: " "
    Marca: " "
    Descrição: " "

    Título: {titulo}
    """
        )
        response = model.generate_content(prompt)
        desc = response.text.strip()
        descricoes.append(desc)
    return descricoes


def preco_para_numero(preco_str):
    try:
        
        # Se vier como tupla, pega o primeiro elemento
        if isinstance(preco_str, tuple):
            preco_str = preco_str[0]

        preco_str = preco_str.replace('.', '').replace(',', '.')
        numeros = re.findall(r'\d+\.?\d*', preco_str)
        if numeros:
            return float(numeros[0])
        return float('inf')
    except Exception as e:
        print("ERRO dentro de preco_para_numero:", e)
        print("VALOR que causou erro:", preco_str, type(preco_str))
        raise e  # relevanta o erro para aparecer no Streamlit ou onde for


# Botão para exibir resultados ordenados por preço
if busca:
    titulos, precos, links, lojas = buscar_buscape(busca)
    descricoes_formatadas = gerar_descricoes_formatadas(titulos)


    # Montar lista completa e ordenar
    descricoes_completas = []
    for desc, preco, link, loja, titulo in zip(descricoes_formatadas, precos, links, lojas, titulos):
        preco_num = preco_para_numero(preco)
        descricoes_completas.append((desc, preco, preco_num, link, loja, titulo))
    
    # Ordena por preço numérico
    descricoes_completas.sort(key=lambda x: x[2])


    # Salva no session_state **depois** de criar a lista toda
    st.session_state['descricoes_formatadas'] = descricoes_completas
    
    if st.button("Exibir todos os resultados (ordenados por preço)", key="botao_pelando"):
        st.markdown("## Todos os resultados da busca:\n")
        #st.session_state['mostrar_resultados'] = True

    # Só exibe se o estado estiver marcado
    #if st.session_state.get('mostrar_resultados'):
    # Exibe os dados
        for desc, preco, _, link, loja, titulo in descricoes_completas:
            linhas = desc.splitlines()
            if len(linhas) >= 3:
                st.write(linhas[0])  # Produto
                st.write(linhas[1])  # Marca
                st.write(linhas[2])  # Descrição
            else:
                st.write(desc)
            st.write(f"Preço: {preco}")
            st.write(f"Loja: {loja}")
            st.write(f"[Link do produto]({link})")
            st.markdown("---")

#######################################BLOCO TOP 3 OFERTAS#############################################################################################

@st.cache_data(show_spinner="Selecionando os melhores produtos...")
def gerar_top3(descricoes_formatadas, precos):
    # Configurar a chave de API
    genai.configure(api_key="AIzaSyBqSIvFig8B5-2_WjRCVpNQ1twI3KeoRB4")

    # Instanciar o modelo
    model = genai.GenerativeModel("gemini-1.5-flash")

    time.sleep(60)  # Espera para não atingir as requisições por minuto
    # Junta os dados no formato desejado
    itens_formatados = []
    for i, (descricao, preco) in enumerate(zip(descricoes_formatadas, precos), start=1):
        item = f"{i}. {descricao}\nPreço: {preco}\n"
        itens_formatados.append(item)

    prompt_geral = (
        "Aqui está uma lista numerada de produtos com marca, descrição e preço:\n\n"
        + "\n".join(itens_formatados)
        + "\n\nPor favor, selecione os 3 melhores produtos em relação a custo-benefício, considerando marcas confiáveis e produtos que normalmente são bem avaliados. "
          "Responda **somente com os números e os nomes dos produtos escolhidos**, como no exemplo:\n"
          "1. Galaxy S22\n2. Moto G73\n3. Realme C55"
    )

    response = model.generate_content(prompt_geral)

    # Extrai os números da resposta
    numeros_escolhidos = re.findall(r"^\s*(\d+)\.", response.text, flags=re.MULTILINE)
    return [int(n) for n in numeros_escolhidos]


if busca:
    descricoes_formatadas = st.session_state.get('descricoes_formatadas', [])
    descricoes = [item[0] for item in descricoes_formatadas]  # pega só as descrições (string)
    precos = [item[1] for item in descricoes_formatadas]     # pega só os preços (string)

    # Chama a função com cache
    numeros_escolhidos = gerar_top3(descricoes, precos)
    st.session_state['numeros_escolhidos'] = numeros_escolhidos

    if numeros_escolhidos and descricoes_formatadas:
        st.markdown("## Top 3 produtos por custo x benefício\n")

        for i in numeros_escolhidos:
            if i-1 < len(descricoes_formatadas):
                desc, preco, _, link, loja, titulo = descricoes_formatadas[i-1]
                linhas = desc.splitlines()
                if len(linhas) >= 3:
                    st.write(linhas[0])
                    st.write(linhas[1])
                    st.write(linhas[2])
                else:
                    st.write(desc)
                st.write(f"Preço: {preco}")
                st.write(f"Link: [Clique aqui]({link})")
                st.write(f"Loja: {loja}")
                st.markdown("---")
    else:
        st.warning("Não foi possível gerar o top 3.")


#######################################BLOCO CRIADOR DE PDF#############################################################################################

# Configurações da API
API_KEY = 'AIzaSyDEjr0HgI8JIloqiGT5qivkSxjb0mzP5Pk'
CSE_ID = '3334b657e04a245e8'

@st.cache_data(show_spinner="Buscando imagem...")
def buscar_imagem_google(query):
    service = build("customsearch", "v1", developerKey=API_KEY)
    res = service.cse().list(q=query, cx=CSE_ID, searchType='image', num=1).execute()
    if 'items' in res:
        return res['items'][0]['link']
    else:
        return None

def gerar_pdf_item_escolhido(titulo, descricao, preco, emitido_em, numero_orcamento, valido_por, nome_contato, endereco):

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Adiciona imagem centralizada
    page_width = pdf.w
    image_width = 150
    x = (page_width - image_width) / 2
    pdf.image("GB Giba.png", x=x, y=10, w=image_width)
    pdf.ln(40)

    # Tabela com dados do contato e orçamento
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Informações do Orçamento", ln=True, align='L')
    pdf.set_font("Arial", size=11)

    largura_total = pdf.w - 20  # Considerando margens de 10mm de cada lado
    largura_campo = largura_total / 3
    altura = 10

    pdf.cell(largura_campo, altura, "Emitido em", border=1)
    pdf.cell(largura_campo, altura, "Número do orçamento", border=1)
    pdf.cell(largura_campo, altura, "Válido por", border=1, ln=True)

    pdf.cell(largura_campo, altura, emitido_em, border=1)
    pdf.cell(largura_campo, altura, numero_orcamento, border=1)
    pdf.cell(largura_campo, altura, f"{valido_por} dias", border=1, ln=True)


    pdf.ln(10)
    
    # Campos abaixo em linhas normais
    pdf.cell(40, altura, "Nome do contato", border=1)
    pdf.cell(0, altura, nome_contato, border=1, ln=True)

    pdf.cell(40, altura, "Endereço", border=1)
    pdf.cell(0, altura, endereco, border=1, ln=True)

    pdf.ln(10)

    # Título da seção de produto
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Orçamento para Material de Informática", ln=True, align='L')
    pdf.set_font("Arial", size=11)

    # Quebra de linha para espaçamento
    pdf.ln(5)

    # Busca imagem do produto
    imagem_url = buscar_imagem_google(titulo)
    
    # Captura a posição atual do cursor no PDF
    y_atual = pdf.get_y()
    
    if imagem_url:
        response = requests.get(imagem_url)
        if response.status_code == 200:
            try:
                # Verifica se é uma imagem válida
                img = Image.open(BytesIO(response.content))
                img_format = img.format.lower()  # 'jpeg', 'png', etc.
    
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{img_format}") as tmp_file:
                    img.save(tmp_file, format=img_format.upper())
                    tmp_path = tmp_file.name
    
                # Adiciona imagem no local certo (seguindo fluxo do conteúdo)
                pdf.image(tmp_path, x=10, y=y_atual, w=55)
    
                # Move cursor para abaixo da imagem
                altura_imagem = 50
                pdf.set_y(y_atual + altura_imagem + 5)
                pdf.ln(5)
    
                os.remove(tmp_path)
    
            except Exception as e:
                pdf.cell(200, 10, txt=f"Erro ao processar imagem: {e}", ln=True)
        else:
            pdf.cell(200, 10, txt="Imagem não disponível.", ln=True)
    else:
        pdf.cell(200, 10, txt="Imagem não encontrada.", ln=True)
    
    pdf.ln(10)
    pdf.cell(40, 10, "Descrição", border=1)
    pdf.multi_cell(0, 10, descricao, border=1)

    pdf.cell(40, 10, "Preço", border=1)
    pdf.cell(0, 10, preco, border=1, ln=True)

    pdf_output_str = pdf.output(dest='S').encode('latin1')
    return BytesIO(pdf_output_str)




# Preenche campos necessários para o documento
if busca:
    st.markdown("### Gerar orçamento em PDF")
    
    numeros_escolhidos = st.session_state.get('numeros_escolhidos', [])
    
    escolha_usuario = st.selectbox(
        "Item escolhido", 
        options=numeros_escolhidos,
        format_func=lambda i: descricoes_formatadas[i - 1][5].split('\n')[0] if i-1 < len(descricoes_formatadas) else f"Item {i}"
    )

    emitido_em = st.date_input("Emitido em", value=datetime.today())
    numero_orcamento = st.text_input("Número do orçamento")
    valido_por = st.number_input("Válido por (dias)", min_value=1, value=7)
    nome_contato = st.text_input("Nome do contato")
    endereco = st.text_input("Endereço")

    if st.button("Gerar PDF", key="botao_gerar_pdf"):
    # Verifica se todos os campos obrigatórios estão preenchidos
        if (
            escolha_usuario
            and numero_orcamento.strip()
            and nome_contato.strip()
            and endereco.strip()
            and valido_por > 0
            and (escolha_usuario - 1) < len(descricoes_formatadas)
        ):

            with st.spinner("Gerando PDF..."):
                try:
                    indice = escolha_usuario - 1
                    print(indice)

                    desc, preco, _, link, loja, titulo = descricoes_formatadas[escolha_usuario - 1]

                    # Converter preço string para número antes de passar para PDF
                    preco_num = preco_para_numero(preco)  # Função que já vimos para converter

                    pdf_buffer = gerar_pdf_item_escolhido(
                        titulo,
                        desc,
                        preco,
                        emitido_em.strftime("%d/%m/%Y"),
                        numero_orcamento,
                        valido_por,
                        nome_contato,
                        endereco
                    )

                    if pdf_buffer:
                        st.download_button(
                            label="📄 Baixar PDF",
                            data=pdf_buffer,
                            file_name="orcamento.pdf",
                            mime="application/pdf",
                            key="download_pdf"
                        )
                    else:
                        st.error("Erro ao gerar o PDF.")
                except Exception as e:
                    st.error(f"Ocorreu um erro: {e}")
        else:
            st.warning("Preencha todos os campos obrigatórios para gerar o PDF.")


