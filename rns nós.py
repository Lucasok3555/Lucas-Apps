import RNS
from RNS.Interfaces.TCPClientInterface import TCPClientInterface
import time
import sys

def main():
    # Configurações do nó alvo (Sideband Bootstrap)
    TARGET_HOST = "sideband.connect.reticulum.network"
    TARGET_PORT = 7822

    print(f"[*] Inicializando o Reticulum Network Stack...")
    
    # Inicializa o Reticulum
    # loglevel=RNS.LOG_INFO mostra detalhes da conexão no console
    reticulum = RNS.Reticulum(loglevel=RNS.LOG_INFO)

    print(f"[*] Identidade do nó criada/ carregada: {RNS.Identity.my_hash()}")
    print(f"[*] Tentando conectar a {TARGET_HOST}:{TARGET_PORT}...")

    try:
        # Cria a interface de cliente TCP
        interface = TCPClientInterface(
            target_host=TARGET_HOST,
            target_port=TARGET_PORT
        )

        # Adiciona a interface ao transporte do Reticulum
        RNS.Transport.add_interface(interface)

        # Aguarda alguns segundos para o handshake e estabelecimento do link
        print("[*] Aguardando estabelecimento da conexão (5 segundos)...")
        time.sleep(5)

        # Verifica o status da interface
        if interface.online:
            print(f"[SUCESSO] Conectado à rede Reticulum via {TARGET_HOST}")
            print(f"[*] Peers conhecidos: {len(RNS.Transport.peers)}")
        else:
            print(f"[FALHA] Não foi possível estabelecer conexão online.")
            print(f"[*] Status da interface: {interface.status}")

    except Exception as e:
        print(f"[ERRO] Ocorreu uma exceção: {e}")
        sys.exit(1)

    # Mantém o script rodando por mais um pouco para observar logs se necessário
    # ou encerra. Aqui vamos encerrar após a verificação.
    print("[*] Encerrando script...")

if __name__ == "__main__":
    main()