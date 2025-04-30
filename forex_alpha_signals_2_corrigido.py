# Forex Alpha Signals 2.0 - Sistema Integrado (corrigido)

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands # <<< ADICIONADO AQUI
from sklearn.tree import DecisionTreeClassifier
import requests
from datetime import datetime
import config # <<< ADICIONADO AQUI

# CONFIGURAÇÕES INICIAIS
st.set_page_config(page_title="Forex Alpha Signals 2.0", layout="wide")
st.title("📊 Forex Alpha Signals 2.0")

# Autenticação
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    senha = st.text_input("Digite a senha:", type="password")
    # Usa a senha do arquivo config.py
    if senha != config.SENHA_APP:
        st.stop()
    else:
        st.session_state.autenticado = True
        st.rerun()

# Telegram - Credenciais movidas para config.py
# TELEGRAM_TOKEN = "..."
# TELEGRAM_CHAT_ID = "..."

def enviar_telegram(mensagem):
    # Usa credenciais do config.py
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": config.TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        response = requests.post(url, data=data, timeout=10) # Adicionado timeout
        response.raise_for_status() # Levanta exceção para erros HTTP (4xx ou 5xx)
        print("Notificação Telegram enviada com sucesso.") # Adicionado feedback
    except requests.exceptions.RequestException as e:
        print(f"ALERTA: Falha ao enviar notificação para o Telegram: {e}")
    except Exception as e:
        print(f"ALERTA: Ocorreu um erro inesperado ao enviar notificação para o Telegram: {e}")

# Seleção de mercado e ativos
st.sidebar.header("Configurações de Análise") # <<< Adicionado Sidebar
mercado = st.sidebar.selectbox("Escolha o Mercado", ["Câmbio (Forex)", "Criptomoedas", "Ações", "Commodities"])

ativos = {
    "Câmbio (Forex)": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"],
    "Criptomoedas": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "Ações": ["AAPL", "MSFT", "AMZN", "PETR4.SA", "VALE3.SA"],
    "Commodities": ["GC=F", "CL=F", "SI=F"]
}

ativo = st.sidebar.selectbox("Selecione o Ativo", ativos[mercado])
timeframe = st.sidebar.selectbox("Intervalo de Tempo", ["15m", "30m", "1h", "4h", "1d", "1wk", "1mo"])

st.sidebar.header("Gerenciamento de Risco")
# Multiplicadores como desvio percentual (ex: 0.003 para 0.3%)
stop_dev = st.sidebar.number_input("Desvio Stop Loss (ex: 0.003 para 0.3%)", min_value=0.0001, max_value=0.1, value=0.003, step=0.0001, format="%.4f")
take_dev = st.sidebar.number_input("Desvio Take Profit (ex: 0.003 para 0.3%)", min_value=0.0001, max_value=0.1, value=0.003, step=0.0001, format="%.4f")

# Histórico
if "historico" not in st.session_state:
    st.session_state.historico = []

# Funções de análise
def obter_dados(ticker, tf):
    # Define o período com base no intervalo, respeitando limites do yfinance
    # Intervalos < 1h: max 7d (recomendado pela documentação yfinance para 1m)
    # Intervalos 1h, 4h: max 730d (usaremos 60d como antes)
    # Intervalos >= 1d: sem limite prático recente
    if tf in ["15m", "30m"]:
        periodo = "7d"  # Usar 7 dias para intervalos < 1h
    elif tf in ["1h", "4h"]:
        periodo = "60d" # Manter 60 dias para 1h e 4h
    elif tf == "1d":
        periodo = "1y" # 1 ano para diário
    elif tf == "1wk":
        periodo = "5y" # 5 anos para semanal
    elif tf == "1mo":
        periodo = "10y" # 10 anos para mensal
    else:
        periodo = "1mo" # Fallback, embora não deva acontecer com os TFs definidos

    intervalo = tf
    print(f"Baixando dados para {ticker} | Intervalo: {intervalo} | Período: {periodo}")
    try:
        df = yf.download(ticker, period=periodo, interval=intervalo, progress=False) # Desativar barra de progresso
        if df.empty:
            st.error(f"Erro: Nenhum dado retornado por yfinance para {ticker} com intervalo {tf} e período {periodo}.")
            return None

        df = df.dropna()
        if df.empty:
            st.error(f"Erro: Dados retornados, mas vazios após dropna para {ticker} com intervalo {tf}.")
            return None

        # Tenta converter fuso horário
        try:
            if isinstance(df.index, pd.DatetimeIndex):
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                df.index = df.index.tz_convert("America/Sao_Paulo")
            else:
                st.warning(f"Aviso: Índice não é do tipo DatetimeIndex para {ticker}. Conversão de fuso horário pulada.")
        except Exception as e:
            st.warning(f"Aviso: Falha ao converter fuso horário para {ticker}: {e}. Usando dados como estão.")

        print(f"Dados para {ticker} baixados e processados com sucesso.")
        return df

    except Exception as e:
        st.error(f"Erro GERAL ao baixar/processar dados de yfinance para {ticker} com intervalo {tf}: {e}")
        return None

def analisar(df, ativo):
    close = df["Close"].squeeze()
    # Calcular Indicadores
    df["EMA9"] = EMAIndicator(close, window=9).ema_indicator()
    df["EMA21"] = EMAIndicator(close, window=21).ema_indicator()
    df["MACD"] = MACD(close).macd()
    df["RSI"] = RSIIndicator(close).rsi()
    # Calcular Bandas de Bollinger
    bb = BollingerBands(close, window=20, window_dev=2)
    df["BB_High"] = bb.bollinger_hband()
    df["BB_Mid"] = bb.bollinger_mavg()
    df["BB_Low"] = bb.bollinger_lband()

    df = df.dropna() # Remover NaNs após calcular todos os indicadores

    if df.empty or df.shape[0] < 10:
        st.warning("Dados insuficientes para análise após cálculo de indicadores. Tente outro ativo ou intervalo.")
        return ""

    df["Alvo"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    # Remover a última linha para treino, pois seu alvo é NaN e não deve ser usado
    df_train = df.iloc[:-1].copy()
    df_train = df_train.dropna() # Garante que não há NaNs no treino

    if df_train.empty or df_train.shape[0] < 10:
        st.warning("Dados insuficientes para treinar o modelo após ajustes. Tente outro ativo ou intervalo.")
        return ""

    # Definir features (incluindo Bandas de Bollinger)
    features = ["EMA9", "EMA21", "MACD", "RSI", "BB_High", "BB_Mid", "BB_Low"]
    X_train = df_train[features]
    y_train = df_train["Alvo"]

    # Preparar dados da última linha para previsão
    X_predict = df[features].iloc[-1:]

    modelo = DecisionTreeClassifier(random_state=42) # Adicionar random_state para reprodutibilidade
    modelo.fit(X_train, y_train)
    previsao_ult = modelo.predict(X_predict)[0]

    ult = df.iloc[-1]
    tipo = "📈 Compra" if previsao_ult == 1 else "📉 Venda"
    entrada = ult["Close"]
    # Usa os desvios definidos na sidebar
    stop = entrada * (1 - stop_dev) if tipo == "📈 Compra" else entrada * (1 + stop_dev)
    alvo = entrada * (1 + take_dev) if tipo == "📈 Compra" else entrada * (1 - take_dev)
    horario = ult.name.strftime("%d/%m/%Y %H:%M")

    mensagem = f"""🔔 Sinal gerado ({mercado})

Ativo: {ativo}
Sinal: {tipo}
Entrada: {entrada:.5f}
Stop: {stop:.5f}
Take: {alvo:.5f}
Horário: {horario}
Base: EMA + MACD + RSI + BB + IA""" # <<< Atualizado Base

    enviar_telegram(mensagem)

    st.session_state.historico.append({
        "Data/Hora": horario,
        "Mercado": mercado,
        "Ativo": ativo,
        "Sinal": tipo,
        "Entrada": round(entrada, 5),
        "Stop": round(stop, 5),
        "Alvo": round(alvo, 5)
    })

    return mensagem

# Layout Principal
col1, col2 = st.columns([3, 1]) # <<< Colunas para layout

with col1: # <<< Conteúdo principal na coluna maior
    st.markdown("""Bem-vindo ao **Forex Alpha Signals 2.0**!
    Configure os parâmetros na barra lateral esquerda, selecione o ativo e intervalo desejados, e clique em 'Analisar Agora' para gerar um sinal.
    Os sinais são baseados em indicadores técnicos (EMA, MACD, RSI, Bandas de Bollinger) e um modelo simples de IA.
    **Atenção:** Este é um sistema experimental. Use os sinais por sua conta e risco.""")

    if st.button("🔍 Analisar Agora"):
        with st.spinner("Analisando dados..."): # <<< Adiciona spinner
            df = obter_dados(ativo, timeframe)
            # Adiciona verificação para garantir que df não é None antes de analisar
            if df is not None:
                mensagem = analisar(df, ativo)
                if mensagem:
                    st.success("Sinal gerado com sucesso!")
                    st.code(mensagem)
                else:
                    # Caso analisar retorne vazio (ex: dados insuficientes)
                    st.info("Não foi possível gerar um sinal com os dados atuais.")
            # Se df for None, a função obter_dados já terá exibido um erro via st.error

    # Histórico dentro de um expander
    with st.expander("📑 Ver/Ocultar Histórico de Sinais"):
        if st.session_state.historico:
            df_hist = pd.DataFrame(st.session_state.historico)
            st.dataframe(df_hist)
            csv = df_hist.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Baixar Histórico", csv, file_name="historico_sinais.csv", mime="text/csv")
        else:
            st.info("Nenhum sinal gerado ainda.")

with col2: # <<< Pode adicionar mais informações ou controles aqui
    st.write(" ") # Espaço



