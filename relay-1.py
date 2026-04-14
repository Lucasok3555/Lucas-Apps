import RNS
import time
import os
import sys

# --- CONFIGURAÇÃO ---
TCP_SERVER = "rns.beleth.net"
TCP_PORT = 4242
STORAGE_DIR = os.path.expanduser("~/.reticulum_relay_custom")
CONFIG_PATH = os.path.join(STORAGE_DIR, "config")

def setup_custom_config():
    """
    Cria um arquivo de configuração limpo que evita os bugs do Android
    e foca apenas no Relay TCP.
    """
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)

    # Configuração minimalista: desativa AutoInterface e ativa Transport
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

def start_relay():
    print(f"[+] Iniciando Reticulum em modo Soberano (Android Fix)...")
    
    # Prepara o ambiente antes de subir o RNS
    setup_custom_config()

    try:
        # Inicializa apontando para a config que acabamos de criar
        reticulum = RNS.Reticulum(configdir=STORAGE_DIR)
        
        print(f"\n[OK] Conectado ao Relay: {TCP_SERVER}:{TCP_PORT}")
        print("[i] Transport (Relay) Ativo: Sim")
        print("[!] Pressione Ctrl+C (ou pare o app) para encerrar.")
        print("-" * 50)

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] Encerrando...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")

if __name__ == "__main__":
    start_relay()