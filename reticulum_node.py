#!/usr/bin/env python3
"""
Nó Reticulum Network
Conecta ao servidor: sideband.connect.reticulum.network:7822
"""

import RNS
import time
import sys

# Endereço do servidor de entrada
SERVER_HOST = "sideband.connect.reticulum.network"
SERVER_PORT = 7822

def iniciar_no():
    print("=" * 50)
    print("  Iniciando Nó Reticulum Network")
    print(f"  Servidor: {SERVER_HOST}:{SERVER_PORT}")
    print("=" * 50)

    # Configuração do Reticulum com interface TCP
    config = f"""
[reticulum]
  enable_transport = False
  share_instance = Yes
  shared_instance_port = 37428
  instance_control_port = 37429
  panic_on_interface_error = No

[logging]
  loglevel = 4

[interfaces]

  [[TCP Client Interface]]
    type = TCPClientInterface
    interface_enabled = True
    outgoing = True
    target_host = {SERVER_HOST}
    target_port = {SERVER_PORT}
"""

    # Salva config temporária
    import os
    import tempfile

    config_dir = os.path.join(tempfile.gettempdir(), "reticulum_node")
    os.makedirs(config_dir, exist_ok=True)

    config_path = os.path.join(config_dir, "config")
    with open(config_path, "w") as f:
        f.write(config)

    print(f"\n[*] Configuração salva em: {config_path}")

    # Inicializa o Reticulum
    print("[*] Inicializando Reticulum...")
    try:
        reticulum = RNS.Reticulum(config_dir)
        print("[+] Reticulum iniciado com sucesso!")
    except Exception as e:
        print(f"[!] Erro ao iniciar Reticulum: {e}")
        sys.exit(1)

    # Exibe identidade do nó
    identidade = RNS.Identity()
    print(f"\n[*] Identidade do Nó:")
    print(f"    Hash: {RNS.prettyhexrep(identidade.hash)}")

    # Aguarda conexão
    print(f"\n[*] Tentando conexão com {SERVER_HOST}:{SERVER_PORT}...")
    print("[*] Aguardando anúncios da rede...\n")

    # Registra destino de exemplo para anunciar presença
    destino = RNS.Destination(
        identidade,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        "reticulum_node",
        "exemplo"
    )

    destino.set_proof_strategy(RNS.Destination.PROVE_ALL)

    # Anuncia o nó na rede
    destino.announce()
    print(f"[+] Nó anunciado na rede!")
    print(f"    Destino: {RNS.prettyhexrep(destino.hash)}")

    # Loop principal - mantém o nó ativo
    print("\n[*] Nó ativo. Pressione Ctrl+C para encerrar.\n")
    
    try:
        contador = 0
        while True:
            time.sleep(10)
            contador += 1
            
            # Mostra status a cada 30 segundos
            if contador % 3 == 0:
                stats = reticulum.get_interface_stats()
                print(f"[{time.strftime('%H:%M:%S')}] Nó ativo | Interfaces: {len(stats)}")
                for iface in stats:
                    nome = iface.get("name", "desconhecida")
                    rxb = iface.get("rxbytes", 0)
                    txb = iface.get("txbytes", 0)
                    print(f"    Interface: {nome} | RX: {rxb} bytes | TX: {txb} bytes")

            # Re-anuncia a cada 5 minutos (30 ciclos de 10s)
            if contador % 30 == 0:
                destino.announce()
                print(f"[{time.strftime('%H:%M:%S')}] Re-anúncio enviado à rede.")

    except KeyboardInterrupt:
        print("\n\n[*] Encerrando nó Reticulum...")
        print("[+] Nó encerrado com sucesso.")
        sys.exit(0)


if __name__ == "__main__":
    iniciar_no()
