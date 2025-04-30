
# Forex Alpha Signals 2.0 - Sistema Integrado (corrigido)

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from sklearn.tree import DecisionTreeClassifier
import requests
from datetime import datetime

# CONFIGURAÇÕES INICIAIS
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
        response = requests.post(url, data=data, timeout=10) # Adicionado timeout
        response.raise_for_status() # Levanta exceção para erros HTTP (4xx ou 5xx)
        print("Notificação Telegram enviada com sucesso.") # Adicionado feedback
    except requests.exceptions.RequestException as e:
        print(f"ALERTA: Falha ao enviar notificação para o Telegram: {e}")
    except Exception as e:
        print(f"ALERTA: Ocorreu um erro inesperado ao enviar notificação para o Telegram: {e}")

# Seleção de mercado e ativos
mercado = st.selectbox("Escolha o Mercado", ["Câmbio (Forex)", "Criptomoedas", "Ações", "Commodities"])

ativos = {
    "Câmbio (Forex)": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"],
    "Criptomoedas": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "Ações": ["AAPL", "MSFT", "AMZN", "PETR4.SA", "VALE3.SA"],
    "Commodities": ["GC=F", "CL=F", "SI=F"]
}

ativo = st.selectbox("Selecione o Ativo", ativos[mercado])
timeframe = st.selectbox("Intervalo de Tempo", ["15m", "30m", "1h", "4h", "1d", "1wk", "1mo"])

# Histórico
if "historico" not in st.session_state:
    st.session_state.historico = []

# Funções de análise
def obter_dados(ticker, tf):
    # Define o período com base no intervalo, respeitando limites do yfinance
    # Intervalos < 1d: max 730d (mas 60d é mais seguro para intraday)
    # Intervalos >= 1d: sem limite prático recente
    if tf in ["15m", "30m", "1h", "4h"]:
        periodo = "60d" # 60 dias para intervalos intradiários
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
    df["EMA9"] = EMAIndicator(close, window=9).ema_indicator()
    df["EMA21"] = EMAIndicator(close, window=21).ema_indicator()
    df["MACD"] = MACD(close).macd()
    df["RSI"] = RSIIndicator(close).rsi()
    df = df.dropna()

    if df.empty or df.shape[0] < 10:
        st.warning("Dados insuficientes para análise. Tente outro ativo ou intervalo de tempo.")
        return ""

    df["Alvo"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    # Remover a última linha para treino, pois seu alvo é NaN e não deve ser usado
    df_train = df.iloc[:-1].copy()
    df_train = df_train.dropna() # Garante que não há NaNs no treino

    if df_train.empty or df_train.shape[0] < 10:
        st.warning("Dados insuficientes para treinar o modelo após ajustes. Tente outro ativo ou intervalo.")
        return ""

    X_train = df_train[["EMA9", "EMA21", "MACD", "RSI"]]
    y_train = df_train["Alvo"]

    # Preparar dados da última linha para previsão
    X_predict = df[["EMA9", "EMA21", "MACD", "RSI"]].iloc[-1:]

    modelo = DecisionTreeClassifier(random_state=42) # Adicionar random_state para reprodutibilidade
    modelo.fit(X_train, y_train)
    previsao_ult = modelo.predict(X_predict)[0]

    ult = df.iloc[-1]
    tipo = "📈 Compra" if previsao_ult == 1 else "📉 Venda"
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

# Botão para analisar
if st.button("🔍 Analisar Agora"):
    df = obter_dados(ativo, timeframe)
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
