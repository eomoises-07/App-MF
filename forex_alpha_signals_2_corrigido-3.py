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

# A seleção de ativo individual foi removida, pois a análise agora é para todos os ativos do mercado selecionado.
# ativo = st.sidebar.selectbox("Selecione o Ativo", ativos[mercado])
timeframe = st.sidebar.selectbox("Intervalo de Tempo", ["15m", "30m", "1h", "4h", "1d", "1wk", "1mo"])

st.sidebar.header("Gerenciamento de Risco")
# Multiplicadores como desvio percentual (ex: 0.003 para 0.3%)
stop_dev = st.sidebar.number_input("Desvio Stop Loss (ex: 0.003 para 0.3%)", min_value=0.0001, max_value=0.1, value=0.003, step=0.0001, format="%.4f")
take_dev = st.sidebar.number_input("Desvio Take Profit (ex: 0.003 para 0.3%)", min_value=0.0001, max_value=0.1, value=0.003, step=0.0001, format="%.4f")

# Histórico
if "historico" not in st.session_state:
    st.session_state.historico = []

# Funções de análise
@st.cache_data(ttl=600) # Cache de 10 minutos
def obter_dados(ticker, tf):
    # Define o período com base no intervalo, respeitando limites do yfinance
    # Intervalos < 1h: Tentaremos 60d (limite pode ser 7d ou 60d dependendo da API/ativo)
    # Intervalos 1h, 4h: Tentaremos 730d (aprox. 2 anos)
    # Intervalo 1d: Tentaremos 5y (5 anos)
    # Intervalo 1wk: Tentaremos 10y (10 anos)
    # Intervalo 1mo: Usaremos 'max'
    if tf in ["15m", "30m"]:
        periodo = "60d" # Tentar 60 dias para intervalos < 1h
    elif tf in ["1h", "4h"]:
        periodo = "730d" # Tentar 2 anos para 1h e 4h
    elif tf == "1d":
        periodo = "5y" # 5 anos para diário
    elif tf == "1wk":
        periodo = "10y" # 10 anos para semanal
    elif tf == "1mo":
        periodo = "max" # Máximo disponível para mensal
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

def analisar(df, ativo, mercado, stop_dev, take_dev): # <<< Parâmetros adicionados
    # Verifica se df é None logo no início
    if df is None:
        print(f"[Analisar] Erro: DataFrame vazio recebido para {ativo}.")
        return None

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
        # st.warning(...) será removido pois esta função rodará em background
        print(f"[Analisar] Dados insuficientes para {ativo} após cálculo de indicadores.")
        return None # <<< Retorna None em vez de string vazia

    df["Alvo"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    # Remover a última linha para treino, pois seu alvo é NaN e não deve ser usado
    df_train = df.iloc[:-1].copy()
    df_train = df_train.dropna() # Garante que não há NaNs no treino

    if df_train.empty or df_train.shape[0] < 10:
        print(f"[Analisar] Dados insuficientes para treinar modelo para {ativo} após ajustes.")
        return None # <<< Retorna None

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
    # Usa os desvios passados como parâmetro
    stop = entrada * (1 - stop_dev) if tipo == "📈 Compra" else entrada * (1 + stop_dev)
    alvo = entrada * (1 + take_dev) if tipo == "📈 Compra" else entrada * (1 - take_dev)
    # Usar UTC para horário do sinal para consistência
    horario_utc = ult.name.tz_convert('UTC')
    horario_str = horario_utc.strftime("%d/%m/%Y %H:%M UTC")

    mensagem = f"""🔔 Sinal gerado ({mercado})

Ativo: {ativo}
Sinal: {tipo}
Entrada: {entrada:.5f}
Stop: {stop:.5f}
Take: {alvo:.5f}
Horário: {horario_str}
Base: EMA + MACD + RSI + BB + IA""" # <<< Atualizado Base

    # Não envia Telegram nem atualiza histórico aqui
    # enviar_telegram(mensagem)
    # st.session_state.historico.append({...})

    # Retorna os dados do sinal como dicionário
    sinal_info = {
        "Data/Hora": horario_str,
        "Mercado": mercado,
        "Ativo": ativo,
        "Sinal": tipo,
        "Entrada": round(entrada, 5),
        "Stop": round(stop, 5),
        "Alvo": round(alvo, 5),
        "Mensagem": mensagem # Inclui a mensagem formatada
    }
    print(f"[Analisar] Sinal gerado para {ativo}: {tipo}")
    return sinal_info # <<< Retorna dicionário com info do sinal

# Layout Principal
col1, col2 = st.columns([3, 1]) # <<< Colunas para layout
with col1: # <<< Conteúdo principal na coluna maior
    st.markdown("""Bem-vindo ao **Forex Alpha Signals 2.0**!
    Configure os parâmetros na barra lateral esquerda (Mercado, Intervalo, Risco).
    Clique em **Analisar TODOS os Ativos Agora** para iniciar uma análise em segundo plano para todos os ativos do mercado selecionado.
    Sinais gerados serão enviados ao Telegram e o histórico abaixo será atualizado.
    Base da Análise: EMA, MACD, RSI, Bandas de Bollinger + IA (Árvore de Decisão).
    **Atenção:** Este é um sistema experimental. Use os sinais por sua conta e risco.""")
    # Modificado para iniciar análise de TODOS os ativos em background
    if st.button("🔍 Analisar TODOS os Ativos Agora"):
        st.info("Iniciando análise completa de todos os ativos em segundo plano... O histórico será atualizado ao concluir.")
        # Criar e iniciar a thread
        thread = threading.Thread(
            target=analisar_todos_ativos_background,
            args=(ativos, timeframe, stop_dev, take_dev), # Passa o dict de ativos e os params da sidebar
            daemon=True # Permite que o app feche mesmo se a thread estiver rodando
        )
        thread.start()
        # Não espera a thread terminar, a interface continua responsiva
        # O spinner foi removido pois a análise agora é em background

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




# --- Funções para Análise em Background ---

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
    """Função para ser executada em background, analisando todos os ativos."""
    print("[BG] Iniciando análise de todos os ativos em background...")
    novos_sinais = []
    for mercado, lista_ativos in ativos_dict.items():
        print(f"[BG] Analisando mercado: {mercado}")
        for ativo in lista_ativos:
            sinal = analisar_ativo(ativo, mercado, timeframe, stop_dev, take_dev)
            if sinal:
                novos_sinais.append(sinal)
                # Enviar notificação imediatamente após gerar o sinal
                try:
                    enviar_telegram(sinal["Mensagem"])
                    print(f"[BG] Notificação enviada para {ativo}.")
                except Exception as e:
                    print(f"[BG] Erro ao tentar enviar notificação para {ativo}: {e}")
            # Pequena pausa para não sobrecarregar a API (opcional, ajustar conforme necessário)
            # time.sleep(1)

    print(f"[BG] Análise em background concluída. {len(novos_sinais)} sinais gerados.")

    # Atualizar o histórico na session_state (requer cuidado com threads)
    # A forma mais segura é usar st.session_state diretamente se o Streamlit >= 1.18
    # ou usar um mecanismo de fila/callback se for versão anterior ou para maior robustez.
    # Por simplicidade agora, vamos tentar adicionar diretamente, mas cientes do risco.
    if novos_sinais:
        if "historico" not in st.session_state:
            st.session_state.historico = []
        # Adiciona os novos sinais no início da lista
        st.session_state.historico = novos_sinais + st.session_state.historico
        print("[BG] Histórico atualizado na session_state.")

    # Poderia retornar os sinais ou apenas finalizar
    return novos_sinais

# -----------------------------------------

