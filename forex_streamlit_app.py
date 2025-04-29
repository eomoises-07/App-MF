
# Sistema Forex Alpha Signals - Completo e Profissional

import streamlit as st
import yfinance as yf
import pandas as pd
import pytz
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from sklearn.tree import DecisionTreeClassifier
import requests
import io
import datetime

# Configuração da página
st.set_page_config(page_title="Forex Alpha Signals", layout="wide")
st.markdown("<h1 style='text-align: center;'>Forex Alpha Signals</h1>", unsafe_allow_html=True)

# Senha de acesso
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    senha = st.text_input("Digite a senha de acesso:", type="password")
if senha != "Deuséfiel":
    st.stop()
else:
    st.session_state.autenticado = True
    st.rerun()

# Token e Chat ID do Telegram
TELEGRAM_TOKEN = "7721305430:AAG1f_3Ne79H3vPkrgPIaJ6VtrM4o0z62ws"
TELEGRAM_CHAT_ID = "5780415948"

# Fuso horário
BR_TZ = pytz.timezone("America/Sao_Paulo")

# Histórico de sinais
if "historico" not in st.session_state:
    st.session_state.historico = []

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=data)
    except:
        pass

def obter_dados(par):
    df = yf.download(par, period="7d", interval="1h")
    df.dropna(inplace=True)
    df.index = df.index.tz_localize("UTC").tz_convert(BR_TZ)
    return df

def analisar_sinais(df):
    close = df["Close"].squeeze()
    df["EMA9"] = EMAIndicator(close, window=9).ema_indicator()
    df["EMA21"] = EMAIndicator(close, window=21).ema_indicator()
    df["MACD"] = MACD(close).macd()
    df["RSI"] = RSIIndicator(close).rsi()
    df.dropna(inplace=True)

    df["Target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
    features = ["EMA9", "EMA21", "MACD", "RSI"]
    X = df[features]
    y = df["Target"]

    modelo = DecisionTreeClassifier()
    modelo.fit(X, y)
    df["Previsao"] = modelo.predict(X)

    ult = df.iloc[-1]
    tipo = "Compra" if ult["Previsao"] == 1 else "Venda"
    entrada = ult["Close"]
    stop = entrada * (0.997 if tipo == "Compra" else 1.003)
    alvo = entrada * (1.003 if tipo == "Compra" else 0.997)

    datahora = ult.name.strftime("%d/%m/%Y %H:%M")
    msg = f"""🔔 Novo Sinal Gerado

• Par de Moedas: {par}
• Sinal: {tipo}
• Preço de Entrada: {entrada:.5f}
• Stop Loss: {stop:.5f}
• Take Profit: {alvo:.5f}
• Horário: {datahora}
• Análise: Baseado em EMA + RSI + MACD + IA"""

    enviar_telegram(msg)

    # Salvar no histórico
    st.session_state.historico.append({
        "Data/Hora": datahora,
        "Par": par,
        "Tipo": tipo,
        "Entrada": round(entrada, 5),
        "Stop": round(stop, 5),
        "Alvo": round(alvo, 5),
        "Motivo": "EMA + RSI + MACD + IA"
    })

    return msg

# Interface principal
pares = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X", "USDCHF=X"]
par = st.selectbox("Selecione o par de moedas:", pares)

if st.button("Atualizar Análise"):
    dados = obter_dados(par)
    mensagem = analisar_sinais(dados)
    st.success("Sinal gerado e enviado para o Telegram!")
    st.code(mensagem)

# Exibir histórico
st.subheader("Histórico de Sinais")
if st.session_state.historico:
    df_hist = pd.DataFrame(st.session_state.historico)
    st.dataframe(df_hist)

    # Botão para baixar
    csv = df_hist.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar Histórico CSV", csv, file_name="historico_sinais.csv", mime="text/csv")
else:
    st.info("Nenhum sinal gerado ainda.")
