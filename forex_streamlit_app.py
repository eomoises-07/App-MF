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

st.set_page_config(page_title='Analisador de Forex', layout='wide')
st.title('Sistema de Análise Forex - Atualizado')

def baixar_dados(par):
    return yf.download(par, interval='1h', period='7d')

def analisar(par):
    df = baixar_dados(par)
    df.dropna(inplace=True)
    df['EMA9'] = EMAIndicator(df['Close'], window=9).ema_indicator()
    df['EMA21'] = EMAIndicator(df['Close'], window=21).ema_indicator()
    df['RSI'] = RSIIndicator(df['Close']).rsi()
    macd = MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df.dropna(inplace=True)
    df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    X = df[['EMA9', 'EMA21', 'RSI', 'MACD', 'MACD_Signal']]
    y = df['Target']
    modelo = DecisionTreeClassifier(max_depth=5)
    modelo.fit(X, y)
    previsao = modelo.predict(X)
    df['Previsao'] = previsao
    sinais = []
    for i in range(1, len(df)):
        if df['Previsao'].iloc[i] == 1 and df['Previsao'].iloc[i-1] == 0:
            sinais.append((df.index[i], 'Compra'))
        elif df['Previsao'].iloc[i] == 0 and df['Previsao'].iloc[i-1] == 1:
            sinais.append((df.index[i], 'Venda'))
    return df, sinais

def enviar_telegram(mensagem):
    token = '7721305430:AAG1f_3Ne79H3vPkrgPIaJ6VtrM4o0z62ws'
    chat_id = '5780415948'
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    params = {'chat_id': chat_id, 'text': mensagem}
    try:
        requests.get(url, params=params)
    except:
        pass

pares = ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X', 'USDCHF=X', 'NZDUSD=X']
par = st.selectbox('Escolha o par de moedas:', pares)

if st.button('Atualizar Análise'):
    df, sinais = analisar(par)
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    if sinais:
        for tempo, tipo in sinais[-3:]:
            tempo_br = tempo.tz_convert(fuso_brasilia)
            st.success(f'{tipo} detectado em {tempo_br.strftime("%d/%m/%Y %H:%M")}')
            mensagem = f'Sinal Forex {par}: {tipo}\nHorário: {tempo_br.strftime("%d/%m/%Y %H:%M")}\nSugestão: STOP 30 pips, ALVO 50 pips.'
            enviar_telegram(mensagem)
    else:
        st.info('Nenhum sinal recente.')
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Candles'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'], line=dict(color='blue', width=1), name='EMA9'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], line=dict(color='red', width=1), name='EMA21'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple', width=1), name='RSI'), row=2, col=1)
    fig.update_layout(height=800, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.caption('Sistema de Análise Forex - Atualizado para Telegram e com IA Básica')
