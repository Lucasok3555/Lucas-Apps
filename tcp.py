import socket
import threading

def handle_client(client_socket, address):
    """
    Função para lidar com a comunicação individual de cada cliente.
    """
    print(f"[NOVA CONEXÃO] {address} conectado.")
    
    try:
        while True:
            # Recebe dados do cliente (tamanho do buffer de 1024 bytes)
            data = client_socket.recv(1024)
            if not data:
                # Se não houver dados, o cliente fechou a conexão
                break
            
            # Decodifica a mensagem recebida
            message = data.decode('utf-8')
            print(f"[{address}] Mensagem recebida: {message}")
            
            # Prepara e envia uma resposta
            response = f"Servidor recebeu a sua mensagem: {message}"
            client_socket.send(response.encode('utf-8'))
            
    except Exception as e:
        print(f"[ERRO] Erro na comunicação com {address}: {e}")
    finally:
        # Garante que o socket do cliente seja fechado
        print(f"[DESCONECTADO] {address} encerrou a sessão.")
        client_socket.close()

def start_server():
    """
    Configura e inicia o servidor TCP principal.
    """
    # Configurações de rede
    IP = "127.0.0.1"  # Localhost
    PORT = 7777      # Porta para escuta
    
    # Cria o objeto socket (AF_INET = IPv4, SOCK_STREAM = TCP)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        # Vincula o servidor ao IP e porta definidos
        server.bind((IP, PORT))
        
        # Começa a escutar conexões (limite de 5 conexões na fila)
        server.listen(5)
        print(f"[INICIADO] Servidor a escutar em {IP}:{PORT}")
        
        while True:
            # Aceita uma nova conexão
            client_sock, address = server.accept()
            
            # Cria uma nova thread para gerir o cliente sem bloquear o servidor principal
            client_handler = threading.Thread(target=handle_client, args=(client_sock, address))
            client_handler.start()
            print(f"[THREADS ATIVAS] {threading.active_count() - 1}")
            
    except KeyboardInterrupt:
        print("\n[ENCERRANDO] Servidor parado manualmente.")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()