# Forex Alpha Signals 2.0 - Versão corrigida para evitar erros de timezone e dados vazios

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from sklearn.tree import DecisionTreeClassifier
import requests

st.set_page_config(page_title="Forex Alpha Signals 2.0", layout="wide")
st.title("📊 Forex Alpha Signals 2.0")

# Autenticação
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if not st.session_state.autenticado:
    senha = st.text_input("Digite a senha:", type="password")
    if senha != "Deuséfiel":
        st.stop()
    else:
        st.session_state.autenticado = True
        st.rerun()

# Telegram
TELEGRAM_TOKEN = "7721305430:AAG1f_3Ne79H3vPkrgPIaJ6VtrM4o0z62ws"
TELEGRAM_CHAT_ID = "5780415948"

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=data)
    except:
        pass

# Seleção
mercado = st.selectbox("Escolha o Mercado", ["Câmbio (Forex)", "Criptomoedas", "Ações", "Commodities"])
ativos = {
    "Câmbio (Forex)": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"],
    "Criptomoedas": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "Ações": ["AAPL", "MSFT", "AMZN", "PETR4.SA", "VALE3.SA"],
    "Commodities": ["GC=F", "CL=F", "SI=F"]
}
ativo = st.selectbox("Selecione o Ativo", ativos[mercado])
timeframe = st.selectbox("Intervalo de Tempo", ["1h", "2h", "4h", "1d"])

if "historico" not in st.session_state:
    st.session_state.historico = []

# Função corrigida para obter dados
def obter_dados(ticker, tf):
    dias = "5d" if tf in ["1h", "2h", "4h"] else "30d"
    try:
        df = yf.download(ticker, period=dias, interval=tf)
        df = df.dropna()
        if df.empty:
            return df
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert("America/Sao_Paulo")
        else:
            df.index = df.index.tz_convert("America/Sao_Paulo")
        return df
    except Exception as e:
        st.error(f"Erro ao obter dados: {e}")
        return pd.DataFrame()

# Função de análise
def analisar(df, ativo):
    close = df["Close"].squeeze()
    df["EMA9"] = EMAIndicator(close, window=9).ema_indicator()
    df["EMA21"] = EMAIndicator(close, window=21).ema_indicator()
    df["MACD"] = MACD(close).macd()
    df["RSI"] = RSIIndicator(close).rsi()
    df = df.dropna()

    if df.empty or df.shape[0] < 10:
        st.warning(f"Dados insuficientes para análise. Foram encontrados apenas {df.shape[0]} registros.")
        return ""

    df["Alvo"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
    X = df[["EMA9", "EMA21", "MACD", "RSI"]]
    y = df["Alvo"]

    modelo = DecisionTreeClassifier()
    modelo.fit(X, y)
    df["Previsao"] = modelo.predict(X)

    ult = df.iloc[-1]
    tipo = "📈 Compra" if ult["Previsao"] == 1 else "📉 Venda"
    entrada = ult["Close"]
    stop = entrada * (0.997 if tipo == "📈 Compra" else 1.003)
    alvo = entrada * (1.003 if tipo == "📈 Compra" else 0.997)
    horario = ult.name.strftime("%d/%m/%Y %H:%M")

    mensagem = f"""🔔 Sinal gerado ({mercado})

Ativo: {ativo}
Sinal: {tipo}
Entrada: {entrada:.5f}
Stop: {stop:.5f}
Take: {alvo:.5f}
Horário: {horario}
Base: EMA + MACD + RSI + IA"""

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

# Execução manual
if st.button("🔍 Analisar Agora"):
    df = obter_dados(ativo, timeframe)
    if df.empty:
        st.warning("Não foi possível carregar dados para este ativo e intervalo. Tente outro.")
    else:
        mensagem = analisar(df, ativo)
        if mensagem:
            st.success("Sinal gerado com sucesso!")
            st.code(mensagem)

# Histórico
st.subheader("📑 Histórico de Sinais")
if st.session_state.historico:
    df_hist = pd.DataFrame(st.session_state.historico)
    st.dataframe(df_hist)
    csv = df_hist.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Baixar Histórico", csv, file_name="historico_sinais.csv", mime="text/csv")
else:
    st.info("Nenhum sinal gerado ainda.")
