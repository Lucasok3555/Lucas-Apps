import RNS
import time
import os
import sys
import sqlite3
import datetime
import threading

# --- CONFIGURAÇÃO ---
TCP_SERVER = "rns.beleth.net"
TCP_PORT = 4242
STORAGE_DIR = os.path.expanduser("~/.reticulum_relay_custom")
CONFIG_PATH = os.path.join(STORAGE_DIR, "config")
DB_PATH = os.path.join(STORAGE_DIR, "relay.db")

APP_NAME = "relay_custom"
ANNOUNCE_INTERVAL = 300  # segundos entre anúncios automáticos (5 min)

# --- BANCO DE DADOS ---

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endereco TEXT NOT NULL,
            relay_host TEXT NOT NULL,
            relay_port INTEGER NOT NULL,
            conectado_em TEXT NOT NULL,
            encerrado_em TEXT,
            modo TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS anuncios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direcao TEXT NOT NULL,
            endereco TEXT NOT NULL,
            dados TEXT,
            momento TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def registrar_sessao(endereco, relay_host, relay_port, modo):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    agora = datetime.datetime.now().isoformat()
    c.execute("""
        INSERT INTO sessoes (endereco, relay_host, relay_port, conectado_em, modo)
        VALUES (?, ?, ?, ?, ?)
    """, (endereco, relay_host, relay_port, agora, modo))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def encerrar_sessao(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    agora = datetime.datetime.now().isoformat()
    c.execute("UPDATE sessoes SET encerrado_em = ? WHERE id = ?", (agora, session_id))
    conn.commit()
    conn.close()

def listar_sessoes(limite=5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT endereco, relay_host, relay_port, conectado_em, encerrado_em, modo
        FROM sessoes ORDER BY id DESC LIMIT ?
    """, (limite,))
    rows = c.fetchall()
    conn.close()
    return rows

def salvar_anuncio(direcao, endereco, dados=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    agora = datetime.datetime.now().isoformat()
    c.execute("""
        INSERT INTO anuncios (direcao, endereco, dados, momento)
        VALUES (?, ?, ?, ?)
    """, (direcao, endereco, dados, agora))
    conn.commit()
    conn.close()

# --- CONFIG RETICULUM ---

def setup_custom_config():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)

    config_content = f"""
[reticulum]
enable_transport = True
share_instance = Yes

[logging]
loglevel = 4

[interfaces]
  [[Beleth-TCP-Relay]]
    type = TCPClientInterface
    enabled = Yes
    target_host = {TCP_SERVER}
    target_port = {TCP_PORT}
"""
    with open(CONFIG_PATH, "w") as f:
        f.write(config_content)
    print(f"[+] Configuração personalizada criada em: {CONFIG_PATH}")

# --- ANÚNCIO RETICULUM ---

def criar_destination(identidade):
    """Cria um Destination anunciável associado à identidade local."""
    dest = RNS.Destination(
        identidade,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        APP_NAME,
        "node"
    )
    dest.set_proof_strategy(RNS.Destination.PROVE_ALL)
    return dest

def enviar_anuncio(dest, app_data=None):
    """Envia um anúncio desta instância para a rede Reticulum."""
    if app_data and isinstance(app_data, str):
        app_data = app_data.encode("utf-8")
    dest.announce(app_data=app_data)
    endereco = RNS.prettyhexrep(dest.hash)
    dados_str = app_data.decode("utf-8") if app_data else "(sem dados)"
    print(f"[↑] Anúncio enviado   addr={endereco}  dados={dados_str!r}")
    salvar_anuncio("saida", endereco, dados_str)

def callback_anuncio_recebido(destination_hash, announced_identity, app_data):
    """Chamado automaticamente quando outro nó anuncia presença na rede."""
    endereco = RNS.prettyhexrep(destination_hash)
    dados = ""
    if app_data:
        try:
            dados = app_data.decode("utf-8")
        except Exception:
            dados = app_data.hex()
    print(f"[↓] Anúncio recebido  addr={endereco}  dados={dados!r}")
    salvar_anuncio("entrada", endereco, dados)

def loop_anuncio_automatico(dest, intervalo, app_data=None):
    """Thread que reenvia o anúncio periodicamente."""
    while True:
        time.sleep(intervalo)
        try:
            enviar_anuncio(dest, app_data)
        except Exception as e:
            print(f"[!] Erro no anúncio automático: {e}")

# --- RELAY PRINCIPAL ---

def start_relay():
    init_db()

    reticulum = None
    modo = "novo"

    # Tenta conectar à instância compartilhada já existente
    default_config = os.path.expanduser("~/.reticulum")
    shared_socket = os.path.join(default_config, "reticulum.sock")

    if os.path.exists(shared_socket):
        print("[i] Detectado Reticulum já em execução — tentando usar instância existente...")
        try:
            reticulum = RNS.Reticulum()
            modo = "shared"
            print("[OK] Conectado à instância Reticulum existente (modo compartilhado).")
        except Exception as e:
            print(f"[!] Falha ao usar instância existente: {e}")
            reticulum = None

    if reticulum is None:
        print("[+] Iniciando nova instância Reticulum com config personalizada...")
        setup_custom_config()
        try:
            reticulum = RNS.Reticulum(configdir=STORAGE_DIR)
            modo = "novo"
            print(f"[OK] Conectado ao Relay: {TCP_SERVER}:{TCP_PORT}")
        except Exception as e:
            print(f"[ERRO FATAL] Não foi possível iniciar o Reticulum: {e}")
            sys.exit(1)

    # Identidade e endereço da rede
    identidade = RNS.Identity()
    endereco = RNS.prettyhexrep(identidade.hash)

    transport_ativo = reticulum.is_connected_to_shared_instance or RNS.Transport.owner is not None

    print(f"\n[★] Endereço desta instância : {endereco}")
    print(f"[i] Modo                      : {modo}")
    print(f"[i] Transport Ativo           : {transport_ativo}")
    print(f"[i] Banco de dados            : {DB_PATH}")
    print("-" * 55)

    # Últimas sessões
    sessoes = listar_sessoes(3)
    if sessoes:
        print("[i] Últimas sessões registradas:")
        for s in sessoes:
            enc = s[4] if s[4] else "em andamento"
            print(f"    {s[3][:19]}  addr={s[0]}  relay={s[1]}:{s[2]}  modo={s[5]}  enc={enc}")
        print("-" * 55)

    # Registra sessão atual
    session_id = registrar_sessao(endereco, TCP_SERVER, TCP_PORT, modo)

    # Cria destination e registra listener para anúncios recebidos
    dest = criar_destination(identidade)
    RNS.Transport.register_announce_handler(
        lambda dh, ai, ad, sig: callback_anuncio_recebido(dh, ai, ad)
    )

    # Envia primeiro anúncio imediatamente
    app_data_inicial = f"relay_custom_node:{endereco[:12]}"
    enviar_anuncio(dest, app_data_inicial)

    # Thread de anúncio automático periódico
    t = threading.Thread(
        target=loop_anuncio_automatico,
        args=(dest, ANNOUNCE_INTERVAL, app_data_inicial),
        daemon=True
    )
    t.start()
    print(f"[i] Anúncio automático a cada {ANNOUNCE_INTERVAL}s ativado.")
    print("[!] Pressione Ctrl+C para encerrar.")
    print("-" * 55)

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] Encerrando...")
        encerrar_sessao(session_id)
        print(f"[i] Sessão #{session_id} encerrada e salva no banco.")
        sys.exit(0)

    except Exception as e:
        encerrar_sessao(session_id)
        print(f"\n[ERRO FATAL] {e}")

if __name__ == "__main__":
    start_relay()
