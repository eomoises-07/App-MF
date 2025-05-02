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

import threading # <<< ADICIONADO AQUI
import time # <<< Adicionado para possível uso futuro (pausas)

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

timeframe = st.sidebar.selectbox("Intervalo de Tempo", ["15m", "30m", "1h", "4h", "1d", "1wk", "1mo"])

st.sidebar.header("Gerenciamento de Risco")
stop_dev = st.sidebar.number_input("Desvio Stop Loss (ex: 0.003 para 0.3%)", min_value=0.0001, max_value=0.1, value=0.003, step=0.0001, format="%.4f")
take_dev = st.sidebar.number_input("Desvio Take Profit (ex: 0.003 para 0.3%)", min_value=0.0001, max_value=0.1, value=0.003, step=0.0001, format="%.4f")

# Histórico
if "historico" not in st.session_state:
    st.session_state.historico = []

# Funções de análise
@st.cache_data(ttl=600) # Cache de 10 minutos
def obter_dados(ticker, tf):
    if tf in ["15m", "30m"]:
        periodo = "60d"
    elif tf in ["1h", "4h"]:
        periodo = "730d"
    elif tf == "1d":
        periodo = "5y"
    elif tf == "1wk":
        periodo = "10y"
    elif tf == "1mo":
        periodo = "max"
    else:
        periodo = "1mo"

    intervalo = tf
    print(f"Baixando dados para {ticker} | Intervalo: {intervalo} | Período: {periodo}")
    try:
        df = yf.download(ticker, period=periodo, interval=intervalo, progress=False)
        if df.empty:
            st.error(f"Erro: Nenhum dado retornado por yfinance para {ticker} com intervalo {tf} e período {periodo}.")
            return None
        df = df.dropna()
        if df.empty:
            st.error(f"Erro: Dados retornados, mas vazios após dropna para {ticker} com intervalo {tf}.")
            return None
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

def analisar(df, ativo, mercado, stop_dev, take_dev):
    if df is None:
        print(f"[Analisar] Erro: DataFrame vazio recebido para {ativo}.")
        return None
    close = df["Close"].squeeze()
    df["EMA9"] = EMAIndicator(close, window=9).ema_indicator()
    df["EMA21"] = EMAIndicator(close, window=21).ema_indicator()
    df["MACD"] = MACD(close).macd()
    df["RSI"] = RSIIndicator(close).rsi()
    bb = BollingerBands(close, window=20, window_dev=2)
    df["BB_High"] = bb.bollinger_hband()
    df["BB_Mid"] = bb.bollinger_mavg()
    df["BB_Low"] = bb.bollinger_lband()
    df = df.dropna()
    if df.empty or df.shape[0] < 10:
        print(f"[Analisar] Dados insuficientes para {ativo} após cálculo de indicadores.")
        return None
    df["Alvo"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
    df_train = df.iloc[:-1].copy()
    df_train = df_train.dropna()
    if df_train.empty or df_train.shape[0] < 10:
        print(f"[Analisar] Dados insuficientes para treinar modelo para {ativo} após ajustes.")
        return None
    features = ["EMA9", "EMA21", "MACD", "RSI", "BB_High", "BB_Mid", "BB_Low"]
    X_train = df_train[features]
    y_train = df_train["Alvo"]
    X_predict = df[features].iloc[-1:]
    modelo = DecisionTreeClassifier(random_state=42)
    modelo.fit(X_train, y_train)
    previsao_ult = modelo.predict(X_predict)[0]
    ult = df.iloc[-1]
    tipo = "📈 Compra" if previsao_ult == 1 else "📉 Venda"
    entrada = ult["Close"]
    stop = entrada * (1 - stop_dev) if tipo == "📈 Compra" else entrada * (1 + stop_dev)
    alvo = entrada * (1 + take_dev) if tipo == "📈 Compra" else entrada * (1 - take_dev)
    horario_utc = ult.name.tz_convert('UTC')
    horario_str = horario_utc.strftime("%d/%m/%Y %H:%M UTC")
    mensagem = f"""🔔 Sinal gerado ({mercado})

Ativo: {ativo}
Sinal: {tipo}
Entrada: {entrada:.5f}
Stop: {stop:.5f}
Take: {alvo:.5f}
Horário: {horario_str}
Base: EMA + MACD + RSI + BB + IA"""
    sinal_info = {
        "Data/Hora": horario_str,
        "Mercado": mercado,
        "Ativo": ativo,
        "Sinal": tipo,
        "Entrada": round(entrada, 5),
        "Stop": round(stop, 5),
        "Alvo": round(alvo, 5),
        "Mensagem": mensagem
    }
    print(f"[Analisar] Sinal gerado para {ativo}: {tipo}")
    return sinal_info

# --- Funções para Análise em Background --- <<< MOVIDO PARA ANTES DO LAYOUT
def analisar_ativo(ativo, mercado, timeframe, stop_dev, take_dev):
    """Obtém dados e analisa um único ativo/timeframe."""
    print(f"[BG] Iniciando análise para {ativo} ({mercado}) - {timeframe}")
    df = obter_dados(ativo, timeframe)
    if df is not None:
        sinal_info = analisar(df, ativo, mercado, stop_dev, take_dev)
        return sinal_info
    else:
        print(f"[BG] Falha ao obter dados para {ativo} - {timeframe}. Pulando análise.")
        return None

def analisar_todos_ativos_background(ativos_dict, timeframe, stop_dev, take_dev):
    """Função para ser executada em background, analisando todos os ativos do mercado selecionado."""
    # Acessa a variável 'mercado' definida globalmente pela sidebar
    mercado_selecionado_na_sidebar = mercado
    lista_ativos_para_analisar = ativos_dict.get(mercado_selecionado_na_sidebar, [])

    if not lista_ativos_para_analisar:
        print(f"[BG] Nenhum ativo encontrado para o mercado selecionado: {mercado_selecionado_na_sidebar}")
        return []

    print(f"[BG] Iniciando análise para o mercado: {mercado_selecionado_na_sidebar}...")
    novos_sinais = []
    for ativo in lista_ativos_para_analisar:
        # Passa o nome correto do mercado para analisar_ativo
        sinal = analisar_ativo(ativo, mercado_selecionado_na_sidebar, timeframe, stop_dev, take_dev)
        if sinal:
            novos_sinais.append(sinal)
            try:
                enviar_telegram(sinal["Mensagem"])
                print(f"[BG] Notificação enviada para {ativo}.")
            except Exception as e:
                print(f"[BG] Erro ao tentar enviar notificação para {ativo}: {e}")
        # time.sleep(1) # Pausa opcional

    print(f"[BG] Análise em background concluída para {mercado_selecionado_na_sidebar}. {len(novos_sinais)} sinais gerados.")

    # Atualizar o histórico na session_state
    if novos_sinais:
        if "historico" not in st.session_state:
            st.session_state.historico = []
        st.session_state.historico = novos_sinais + st.session_state.historico
        print("[BG] Histórico atualizado na session_state.")

    return novos_sinais
# -----------------------------------------

# Layout Principal
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("""Bem-vindo ao **Forex Alpha Signals 2.0**!
    Configure os parâmetros na barra lateral esquerda (Mercado, Intervalo, Risco).
    Clique em **Analisar TODOS os Ativos Agora** para iniciar uma análise em segundo plano para todos os ativos do mercado selecionado.
    Sinais gerados serão enviados ao Telegram e o histórico abaixo será atualizado.
    Base da Análise: EMA, MACD, RSI, Bandas de Bollinger + IA (Árvore de Decisão).
    **Atenção:** Este é um sistema experimental. Use os sinais por sua conta e risco.""")

    if st.button("🔍 Analisar TODOS os Ativos Agora"):
        st.info("Iniciando análise completa de todos os ativos em segundo plano... O histórico será atualizado ao concluir.")
        # Criar e iniciar a thread (passa o dict completo, a função filtra internamente)
        thread = threading.Thread(
            target=analisar_todos_ativos_background,
            args=(ativos, timeframe, stop_dev, take_dev),
            daemon=True
        )
        thread.start()

    with st.expander("📑 Ver/Ocultar Histórico de Sinais"):
        if st.session_state.historico:
            df_hist = pd.DataFrame(st.session_state.historico)
            st.dataframe(df_hist)
            csv = df_hist.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Baixar Histórico", csv, file_name="historico_sinais.csv", mime="text/csv")
        else:
            st.info("Nenhum sinal gerado ainda.")

with col2:
    st.write(" ")

