
import streamlit as st
import yfinance as yf
import pandas as pd
import pytz
import requests
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from datetime import datetime
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# CONFIG
st.set_page_config(page_title="Sistema de Sinais Forex", layout="wide")
BR_TZ = pytz.timezone("America/Sao_Paulo")
SENHA_CORRETA = "Deuséfiel"

# TELEGRAM CONFIG
TOKEN = "7721305430:AAG1f_3Ne79H3vPkrgPIaJ6VtrM4o0z62ws"
CHAT_ID = "5780415948"

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.warning(f"Erro ao enviar alerta: {e}")

# LOGIN
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if not st.session_state.autenticado:
    senha = st.text_input("Digite a senha para acessar o sistema:", type="password")
    if senha == SENHA_CORRETA:
        st.session_state.autenticado = True
        st.rerun()
    else:
        st.stop()

# INTERFACE
st.title("Sistema de Oportunidades Forex - Baixo/Médio Risco")
st.markdown("Clique no botão abaixo para atualizar a análise manualmente.")
st.caption(f"Última atualização: {datetime.now(BR_TZ).strftime('%d/%m/%Y %H:%M:%S')}")

atualizar = st.button("🔄 Atualizar Agora")

pares = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"]
par_nome = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
}

def obter_dados(par):
    df = yf.download(par, interval="1h", period="2d")
    df.index = df.index.tz_convert(BR_TZ)
    return df

def analisar(par):
    df = obter_dados(par)
    close = df["Close"].squeeze()
    df["RSI"] = RSIIndicator(close).rsi()
    df["EMA20"] = EMAIndicator(close, window=20).ema_indicator()
    df["EMA50"] = EMAIndicator(close, window=50).ema_indicator()
    macd = MACD(close)
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    bb = BollingerBands(close)
    df["bb_high"] = bb.bollinger_hband()
    df["bb_low"] = bb.bollinger_lband()

    sinais = []
    i = -1
    if df["RSI"].iloc[i] < 30 and df["MACD"].iloc[i] > df["MACD_signal"].iloc[i] and df["Close"].iloc[i] > df["EMA20"].iloc[i]:
        sinais.append(("COMPRA", "RSI abaixo de 30, MACD cruzando pra cima e acima da EMA20"))
    elif df["RSI"].iloc[i] > 70 and df["MACD"].iloc[i] < df["MACD_signal"].iloc[i] and df["Close"].iloc[i] < df["EMA20"].iloc[i]:
        sinais.append(("VENDA", "RSI acima de 70, MACD cruzando pra baixo e abaixo da EMA20"))
    return df, sinais

if atualizar:
    for par in pares:
        df, sinais = analisar(par)
        st.subheader(f"{par_nome[par]} - Última vela: {df.index[-1].strftime('%d/%m/%Y %H:%M')}")
        if sinais:
            for tipo, motivo in sinais:
                preco = df["Close"].iloc[-1]
                sl = preco * (0.995 if tipo == "COMPRA" else 1.005)
                tp = preco * (1.01 if tipo == "COMPRA" else 0.99)
                mensagem = f"🚨 SINAL DE {tipo} 🚨\n\nPar: {par_nome[par]}\nPreço: {preco:.4f}\nSL: {sl:.4f}\nTP: {tp:.4f}\n\nMotivo: {motivo}\n\nHora: {datetime.now(BR_TZ).strftime('%d/%m/%Y %H:%M:%S')}"
                enviar_telegram(mensagem)
                st.success(mensagem)
        else:
            st.info("Sem sinais de entrada neste par no momento.")
        with st.expander("Ver Gráfico"):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Preço"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["EMA20"], name="EMA20", line=dict(color="blue")), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["EMA50"], name="EMA50", line=dict(color="orange")), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="green")), row=2, col=1)
            fig.update_layout(height=500, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Clique em 'Atualizar Agora' para ver os sinais mais recentes.")
