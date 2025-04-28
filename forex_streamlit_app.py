import streamlit as st
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd
import requests
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from sklearn.tree import DecisionTreeClassifier
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Sistema de Análise Forex", layout="wide")
st.title("Sistema de Análise Forex - Atualizado")

BR_TZ = pytz.timezone('America/Sao_Paulo')

def enviar_telegram(mensagem):
    token = '7721305430:AAG1f_3Ne79H3vPkrgPIaJ6VtrM4o0z62ws'
    chat_id = '5780415948'
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensagem}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Erro ao enviar notificação: {e}")

@st.cache_data
def obter_dados(par, periodo="7d", intervalo="15m"):
    df = yf.download(par, period=periodo, interval=intervalo)
    df.index = df.index.tz_convert(BR_TZ)
    return df

def analisar(par):
    df = obter_dados(par)

    df['EMA9'] = EMAIndicator(df['Close'], window=9).ema_indicator()
    df['EMA21'] = EMAIndicator(df['Close'], window=21).ema_indicator()
    df['MACD'] = MACD(df['Close']).macd()
    df['RSI'] = RSIIndicator(df['Close']).rsi()

    df['EMA_cross'] = (df['EMA9'] > df['EMA21']).astype(int)
    df['MACD_cross'] = (df['MACD'] > 0).astype(int)
    df['RSI_overbought'] = (df['RSI'] > 70).astype(int)
    df['RSI_oversold'] = (df['RSI'] < 30).astype(int)

    features = ['EMA_cross', 'MACD_cross', 'RSI_overbought', 'RSI_oversold']
    df.dropna(inplace=True)

    X = df[features]
    y = ((df['EMA9'].shift(-1) > df['EMA21'].shift(-1)).astype(int))

    modelo = DecisionTreeClassifier()
    modelo.fit(X, y)

    df['Sinal_Previsto'] = modelo.predict(X)

    sinais = []
    for idx, row in df.iterrows():
        if row['Sinal_Previsto'] == 1:
            sinais.append(f"🟢 Compra em {row['Close']:.2f} ({idx.strftime('%d/%m %H:%M')}) - Stop Loss: {row['Close']*0.995:.2f} - Take Profit: {row['Close']*1.005:.2f}")
        elif row['Sinal_Previsto'] == 0:
            sinais.append(f"🔴 Venda em {row['Close']:.2f} ({idx.strftime('%d/%m %H:%M')}) - Stop Loss: {row['Close']*1.005:.2f} - Take Profit: {row['Close']*0.995:.2f}")
    return df, sinais

pares = ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X', 'NZDUSD=X', 'USDCHF=X']
par = st.selectbox("Escolha o par de moedas:", pares)

if st.button("Atualizar Análise"):
    df, sinais = analisar(par)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Preço", "Indicadores"),
                        vertical_spacing=0.2)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'], line=dict(color='blue', width=1), name="EMA9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], line=dict(color='red', width=1), name="EMA21"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='purple', width=1), name="MACD"), row=2, col=1)

    fig.update_layout(height=800, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Sinais Gerados:")
    for sinal in sinais[-5:]:
        st.write(sinal)
        enviar_telegram(sinal)

