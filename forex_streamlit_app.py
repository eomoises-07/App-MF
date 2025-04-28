#Sistema de Análise Forex - Completo 

import streamlit as st from datetime import datetime import pytz import yfinance as yf import pandas as pd import requests from ta.trend import EMAIndicator, MACD from ta.momentum import RSIIndicator from sklearn.tree import DecisionTreeClassifier import plotly.graph_objects as go from plotly.subplots import make_subplots 

st.set_page_config(page_title="Sistema de Análise Forex com IA", layout="wide") BR_TZ = pytz.timezone("America/Sao_Paulo")

Telegram Bot 

BOT_TOKEN = '7721305430:AAG1f_3Ne79H3vPkrgPIaJ6VtrM4o0z62ws' CHAT_ID = '5780415948'

def enviar_telegram(mensagem): url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" data = {"chat_id": CHAT_ID, "text": mensagem} requests.post(url, data=data)

Função para calcular SL e TP 

def calcular_sl_tp(tipo, entrada): if tipo == "COMPRA": sl = entrada * (1 - 0.015) tp = entrada * (1 + 0.025) elif tipo == "VENDA": sl = entrada * (1 + 0.015) tp = entrada * (1 - 0.025) else: sl, tp = None, None return round(sl, 4), round(tp, 4)

Login simples 

SENHA_CORRETA = "Deuséfiel"

if "autenticado" not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado: senha = st.text_input("Digite a senha para acessar o sistema:", type="password") if senha == SENHA_CORRETA: st.session_state.autenticado = True st.rerun() else: st.stop()

Inicializar histórico 

if "historico" not in st.session_state: st.session_state.historico = []

Estrutura 

titulo = "Análise de Oportunidades Forex com IA" st.title(titulo) st.caption(f"Última Atualização: {datetime.now(BR_TZ).strftime('%d/%m/%Y %H:%M:%S')} (Horário de Brasília)")

Sugestão inteligente de timeframe 

def sugerir_timeframe(par): if par in ["XAU/USD", "GBP/JPY", "AUD/JPY"]: return "4h" elif par in ["GBP/USD", "EUR/JPY", "AUD/USD"]: return "4h" else: return "1h"

st.subheader("Escolha o Timeframe:") timeframe_usuario = st.radio("Selecione o timeframe (opcional):", ["Automático", "1h", "4h", "1d"], horizontal=True)

st.subheader("Escolha os Pares para Analisar:") pares_disponiveis = [ "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY", "NZD/USD", "USD/CHF", "XAU/USD" ] pares_selecionados = st.multiselect("Selecione os pares:", pares_disponiveis, default=["EUR/USD", "GBP/USD"])

Botão Atualizar estilizado 

st.markdown(""" 

🔄 Atualizar Agora 

""", unsafe_allow_html=True) 

atualizar = st.button("Clique aqui para atualizar", key="atualizar_botao")

Função IA 

def prever_tendencia_ia(df): try: df = df.dropna() X = df[["Close", "High", "Low", "Volume", "RSI", "EMA20", "MACD"]].values[:-1] y = (df["Close"].shift(-1) > df["Close"]).astype(int).values[:-1] modelo = DecisionTreeClassifier(max_depth=5) modelo.fit(X, y) X_hoje = df[["Close", "High", "Low", "Volume", "RSI", "EMA20", "MACD"]].values[-1].reshape(1, -1) previsao = modelo.predict(X_hoje)[0] return previsao except Exception: return None

Função para análise 

def analisar_sinais(par, timeframe): simbolo = par.replace("/", "") + "=X" if par != "XAU/USD" else "GC=F" intervalo = {"1h": "1h", "4h": "4h", "1d": "1d"}[timeframe] try: df = yf.download(simbolo, interval=intervalo, period="5d") df.index = df.index.tz_convert(BR_TZ) close = df["Close"].squeeze() df["RSI"] = RSIIndicator(close).rsi() df["EMA20"] = EMAIndicator(close, window=20).ema_indicator() df["MACD"] = MACD(close).macd() df["MACD_signal"] = MACD(close).macd_signal() sinais = [] i = -1 if df["RSI"].iloc[i] < 30 and df["MACD"].iloc[i] > df["MACD_signal"].iloc[i] and df["Close"].iloc[i] > df["EMA20"].iloc[i]: sinais.append(("COMPRA", df["Close"].iloc[i])) elif df["RSI"].iloc[i] > 70 and df["MACD"].iloc[i] < df["MACD_signal"].iloc[i] and df["Close"].iloc[i] < df["EMA20"].iloc[i]: sinais.append(("VENDA", df["Close"].iloc[i])) return df, sinais except Exception: return None, []

Resultados 

st.subheader("Resultados:") if atualizar: if not pares_selecionados: st.warning("Nenhum par selecionado!") else: for par in pares_selecionados: if timeframe_usuario == "Automático": timeframe = sugerir_timeframe(par) st.caption(f"Sugestão automática para {par}: Analisar no timeframe {timeframe}") else: timeframe = timeframe_usuario

df, sinais = analisar_sinais(par, timeframe) if sinais: for tipo, preco in sinais: sl, tp = calcular_sl_tp(tipo, preco) st.success(f"{par} - {tipo} no preço {preco:.4f} | SL: {sl:.4f} | TP: {tp:.4f}") st.session_state.historico.append({ "Data": datetime.now(BR_TZ).strftime('%d/%m/%Y %H:%M'), "Par": par, "Tipo": tipo, "Entrada": f"{preco:.4f}", "Stop Loss": f"{sl:.4f}", "Take Profit": f"{tp:.4f}" }) mensagem = f"🚨 Novo Sinal Forex!\n\nPar: {par}\nDireção: {tipo}\nEntrada: {preco:.4f}\nStop Loss: {sl:.4f}\nTake Profit: {tp:.4f}\nHorário: {datetime.now(BR_TZ).strftime('%d/%m/%Y %H:%M')}" enviar_telegram(mensagem) else: st.info(f"{par} - Sem sinais no momento.") if df is not None: previsao = prever_tendencia_ia(df) if previsao == 1: st.success(f"Previsão da IA para {par}: Alta provável") elif previsao == 0: st.warning(f"Previsão da IA para {par}: Baixa provável") else: st.info(f"Previsão da IA para {par}: Indefinida") with st.expander(f"Ver Gráfico de {par}"): if df is not None: fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3]) fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candles"), row=1, col=1) fig.add_trace(go.Scatter(x=df.index, y=df["EMA20"], line=dict(color='blue'), name="EMA20"), row=1, col=1) fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color='green'), name="RSI"), row=2, col=1) fig.update_layout(height=600, showlegend=True) st.plotly_chart(fig, use_container_width=True) 

else: st.info("Clique em 'Atualizar Agora' para ver as análises.")

Histórico 

df_hist = pd.DataFrame(st.session_state.historico) if not df_hist.empty: st.subheader("Histórico de Sinais Recentes:") st.dataframe(df_hist) else: st.info("Nenhum sinal gerado ainda nesta sessão.")

