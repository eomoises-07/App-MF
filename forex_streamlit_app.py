
import streamlit as st
import yfinance as yf
import pandas as pd
import pytz
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from datetime import datetime
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import os

# CONFIG
st.set_page_config(page_title="Sistema de Sinais Forex", layout="wide")
BR_TZ = pytz.timezone("America/Sao_Paulo")
SENHA_CORRETA = "Deuséfiel"

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
st.markdown("As análises são atualizadas a cada hora automaticamente.")

pares = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"]
par_nome = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
}

@st.cache_data(ttl=3600)
def obter_dados(par):
    df = yf.download(par, interval="1h", period="2d")
    df.index = df.index.tz_localize("UTC").tz_convert(BR_TZ)
    return df

def analisar(par):
    df = obter_dados(par)
    df['RSI'] = RSIIndicator(df['Close']).rsi()
    df['EMA20'] = EMAIndicator(df['Close'], window=20).ema_indicator()
    df['EMA50'] = EMAIndicator(df['Close'], window=50).ema_indicator()
    macd = MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    bb = BollingerBands(df['Close'])
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()

    sinais = []
    i = -1
    if df['RSI'].iloc[i] < 30 and df['MACD'].iloc[i] > df['MACD_signal'].iloc[i] and df['Close'].iloc[i] > df['EMA20'].iloc[i]:
        sinais.append(("COMPRA", "RSI abaixo de 30, MACD cruzando pra cima e acima da EMA20"))
    elif df['RSI'].iloc[i] > 70 and df['MACD'].iloc[i] < df['MACD_signal'].iloc[i] and df['Close'].iloc[i] < df['EMA20'].iloc[i]:
        sinais.append(("VENDA", "RSI acima de 70, MACD cruzando pra baixo e abaixo da EMA20"))

    return df, sinais

for par in pares:
    df, sinais = analisar(par)
    st.subheader(f"{par_nome[par]} - Última vela: {df.index[-1].strftime('%d/%m/%Y %H:%M')}")
    if sinais:
        for tipo, motivo in sinais:
            preco = df['Close'].iloc[-1]
            sl = preco * (0.995 if tipo == "COMPRA" else 1.005)
            tp = preco * (1.01 if tipo == "COMPRA" else 0.99)
            st.success(f"SINAL DE {tipo} | Preço: {preco:.4f} | SL: {sl:.4f} | TP: {tp:.4f}")
            st.caption(f"Motivo: {motivo}")
    else:
        st.info("Sem sinais de entrada neste par no momento.")

    with st.expander("Ver Gráfico"):
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Preço'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], name='EMA20', line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], name='EMA50', line=dict(color='orange')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='green')), row=2, col=1)
        fig.update_layout(height=500, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
