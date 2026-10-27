#!/usr/bin/env python3
"""
Instalador do Reticulum Network como serviço do sistema (Windows / Linux / macOS).

- Só instala o Reticulum se ele ainda não estiver instalado.
- Pergunta se deve instalar como serviço do sistema.
- Cria a configuração padrão (instância compartilhada + interfaces padrão).
- Mostra o status do serviço ao final.
- Outros aplicativos usam a mesma instância compartilhada (porta local 37428),
  basta iniciar o RNS normalmente: ele se conecta ao rnsd que já está rodando.
"""
import importlib.util
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

SISTEMA = platform.system()  # Windows / Linux / Darwin
NOME_SERVICO = "reticulum-rnsd"
PORTA_COMPARTILHADA = 37428
PORTA_CONTROLE = 37429

BASE_DIR = Path.home() / ".reticulum-service"
VENV_DIR = BASE_DIR / "venv"
CONFIG_DIR = Path.home() / ".reticulum"
CONFIG_FILE = CONFIG_DIR / "config"

CONFIG_PADRAO = f"""# Configuração padrão gerada pelo instalador do Reticulum
[reticulum]
  enable_transport = False
  share_instance = Yes
  shared_instance_port = {PORTA_COMPARTILHADA}
  instance_control_port = {PORTA_CONTROLE}
  panic_on_interface_error = No

[logging]
  loglevel = 4

[interfaces]

  # Rede local
  [[Rede Local]]
    type = AutoInterface
    enabled = Yes

  # Interfaces de internet
  [[Sideband Hub]]
    type = TCPClientInterface
    enabled = Yes
    target_host = sideband.connect.reticulum.network
    target_port = 7822

  [[Beleth RNS Hub]]
    type = TCPClientInterface
    enabled = Yes
    target_host = rns.beleth.net
    target_port = 4242

  [[RNS 107.172.16.33]]
    type = TCPClientInterface
    enabled = Yes
    target_host = 107.172.16.33
    target_port = 4242
"""


# ---------------------------------------------------------------- utilidades
def executar(cmd, log, check=True, **kw):
    log("$ " + " ".join(str(c) for c in cmd))
    kwargs = dict(capture_output=True, text=True, **kw)
    if SISTEMA == "Windows":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    r = subprocess.run([str(c) for c in cmd], **kwargs)
    saida = (r.stdout or "") + (r.stderr or "")
    if saida.strip():
        log(saida.strip())
    if check and r.returncode != 0:
        raise RuntimeError(f"Comando falhou (código {r.returncode})")
    return r


def e_admin():
    try:
        if SISTEMA == "Windows":
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


def porta_aberta(porta, host="127.0.0.1"):
    try:
        with socket.create_connection((host, porta), timeout=1.5):
            return True
    except OSError:
        return False


def pasta_scripts(venv):
    return venv / ("Scripts" if SISTEMA == "Windows" else "bin")


def localizar_rnsd():
    """Retorna o comando (lista) para rodar o rnsd, ou None se não instalado."""
    exe = shutil.which("rnsd")
    if exe:
        return [exe]
    nome = "rnsd.exe" if SISTEMA == "Windows" else "rnsd"
    p = pasta_scripts(VENV_DIR) / nome
    if p.exists():
        return [str(p)]
    if importlib.util.find_spec("RNS") is not None:
        return [sys.executable, "-m", "RNS.Utilities.rnsd"]
    return None


def reticulum_instalado():
    return localizar_rnsd() is not None


# ---------------------------------------------------------------- instalação
def instalar_reticulum(log):
    log("Criando ambiente isolado para o Reticulum...")
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    executar([sys.executable, "-m", "venv", VENV_DIR], log)
    py = pasta_scripts(VENV_DIR) / ("python.exe" if SISTEMA == "Windows" else "python")
    executar([py, "-m", "pip", "install", "--upgrade", "pip"], log, check=False)
    log("Instalando Reticulum Network (pacote 'rns')...")
    executar([py, "-m", "pip", "install", "--upgrade", "rns"], log)
    log("Reticulum instalado.")


def escrever_config(log):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        log(f"Já existe uma configuração em {CONFIG_FILE}; mantida sem alterações.")
        # garante apenas que a instância compartilhada esteja habilitada
        txt = CONFIG_FILE.read_text(encoding="utf-8", errors="ignore")
        if "share_instance" not in txt.lower():
            log("Aviso: 'share_instance' não está definido na config existente "
                "(o padrão do Reticulum já é compartilhar).")
        return
    CONFIG_FILE.write_text(CONFIG_PADRAO, encoding="utf-8")
    log(f"Configuração padrão criada em {CONFIG_FILE}")


# ---------------------------------------------------------------- serviços
def cmd_rnsd_str(rnsd):
    return " ".join(f'"{c}"' if " " in c else c for c in rnsd + ["--config", str(CONFIG_DIR), "-s"])


def instalar_servico_linux(rnsd, log):
    exec_start = cmd_rnsd_str(rnsd)
    unit = f"""[Unit]
Description=Reticulum Network Stack Daemon
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=5

[Install]
WantedBy={"multi-user.target" if e_admin() else "default.target"}
"""
    if e_admin():
        unit = unit.replace("[Service]", f"[Service]\nUser={os.environ.get('SUDO_USER', 'root')}")
        Path(f"/etc/systemd/system/{NOME_SERVICO}.service").write_text(unit)
        executar(["systemctl", "daemon-reload"], log)
        executar(["systemctl", "enable", "--now", NOME_SERVICO], log)
    else:
        d = Path.home() / ".config/systemd/user"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{NOME_SERVICO}.service").write_text(unit)
        executar(["systemctl", "--user", "daemon-reload"], log)
        executar(["systemctl", "--user", "enable", "--now", NOME_SERVICO], log)
        executar(["loginctl", "enable-linger", os.environ.get("USER", "")], log, check=False)


def instalar_servico_mac(rnsd, log):
    args = rnsd + ["--config", str(CONFIG_DIR), "-s"]
    xml_args = "\n".join(f"    <string>{a}</string>" for a in args)
    label = "network.reticulum.rnsd"
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{xml_args}
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
"""
    d = Path.home() / "Library/LaunchAgents"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{label}.plist"
    p.write_text(plist)
    executar(["launchctl", "unload", str(p)], log, check=False)
    executar(["launchctl", "load", "-w", str(p)], log)


def instalar_servico_windows(rnsd, log):
    comando = cmd_rnsd_str(rnsd)
    tr = comando.replace('"', '\\"')
    base = ["schtasks", "/Create", "/F", "/TN", NOME_SERVICO, "/TR", f'"{tr}"']
    if e_admin():
        executar(base + ["/SC", "ONSTART", "/RU", "SYSTEM", "/RL", "HIGHEST"], log)
    else:
        log("Sem privilégios de administrador: o serviço iniciará ao fazer login.")
        executar(base + ["/SC", "ONLOGON"], log)
    executar(["schtasks", "/Run", "/TN", NOME_SERVICO], log, check=False)


def instalar_servico(rnsd, log):
    if SISTEMA == "Linux":
        instalar_servico_linux(rnsd, log)
    elif SISTEMA == "Darwin":
        instalar_servico_mac(rnsd, log)
    elif SISTEMA == "Windows":
        instalar_servico_windows(rnsd, log)
    else:
        raise RuntimeError(f"Sistema não suportado: {SISTEMA}")


def iniciar_sem_servico(rnsd, log):
    log("Iniciando o rnsd em segundo plano (sem serviço)...")
    kw = {}
    if SISTEMA == "Windows":
        kw["creationflags"] = 0x00000008 | 0x08000000  # DETACHED | NO_WINDOW
    else:
        kw["start_new_session"] = True
    subprocess.Popen(rnsd + ["--config", str(CONFIG_DIR), "-s"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)


# ---------------------------------------------------------------- status
def obter_status():
    for _ in range(15):
        if porta_aberta(PORTA_COMPARTILHADA):
            break
        time.sleep(1)
    rodando = porta_aberta(PORTA_COMPARTILHADA)
    linhas = [
        "● SERVIÇO RODANDO" if rodando else "○ SERVIÇO NÃO ESTÁ RODANDO",
        f"Instância compartilhada: 127.0.0.1:{PORTA_COMPARTILHADA}"
        + (" (ativa)" if rodando else " (inativa)"),
        f"Configuração: {CONFIG_FILE}",
    ]
    if rodando:
        nome = "rnstatus.exe" if SISTEMA == "Windows" else "rnstatus"
        rs = shutil.which("rnstatus") or str(pasta_scripts(VENV_DIR) / nome)
        try:
            r = subprocess.run([rs, "--config", str(CONFIG_DIR)], capture_output=True,
                               text=True, timeout=20)
            if r.stdout.strip():
                linhas += ["", r.stdout.strip()]
        except Exception:
            pass
        linhas += ["", "Outros aplicativos podem usar esta mesma instância: ao iniciar "
                       "RNS.Reticulum() eles se conectam automaticamente a ela."]
    return rodando, "\n".join(linhas)


# ---------------------------------------------------------------- fluxo
def fluxo(como_servico, log):
    if reticulum_instalado():
        log("Reticulum já está instalado — instalação ignorada.")
    else:
        instalar_reticulum(log)

    rnsd = localizar_rnsd()
    if not rnsd:
        raise RuntimeError("Não foi possível localizar o rnsd após a instalação.")

    escrever_config(log)

    if porta_aberta(PORTA_COMPARTILHADA):
        log("Já existe uma instância do Reticulum rodando; ela será reutilizada.")
    elif como_servico:
        instalar_servico(rnsd, log)
    else:
        iniciar_sem_servico(rnsd, log)

    log("Verificando status...")
    return obter_status()


# ---------------------------------------------------------------- interfaces
def rodar_gui():
    import tkinter as tk
    from tkinter import ttk, scrolledtext

    raiz = tk.Tk()
    raiz.title("Instalador do Reticulum Network")
    raiz.geometry("640x520")

    ttk.Label(raiz, text="Instalador do Reticulum Network",
              font=("Segoe UI", 15, "bold")).pack(pady=(14, 4))
    ja = reticulum_instalado()
    ttk.Label(raiz, text=("Reticulum já instalado — será apenas configurado."
                          if ja else "O Reticulum será instalado automaticamente.")
              ).pack()

    var_servico = tk.BooleanVar(value=True)
    ttk.Checkbutton(raiz, variable=var_servico,
                    text=f"Instalar como serviço do sistema ({ {'Darwin': 'macOS'}.get(SISTEMA, SISTEMA) })"
                    ).pack(pady=10)

    botao = ttk.Button(raiz, text="Instalar")
    botao.pack()

    status = tk.StringVar(value="")
    lbl = ttk.Label(raiz, textvariable=status, font=("Segoe UI", 11, "bold"))
    lbl.pack(pady=6)

    caixa = scrolledtext.ScrolledText(raiz, height=18, state="disabled", font=("Consolas", 9))
    caixa.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def log(msg):
        def _f():
            caixa.config(state="normal")
            caixa.insert("end", msg + "\n")
            caixa.see("end")
            caixa.config(state="disabled")
        raiz.after(0, _f)

    def trabalho():
        try:
            rodando, texto = fluxo(var_servico.get(), log)
            raiz.after(0, lambda: status.set("● Serviço rodando" if rodando else "○ Serviço parado"))
            log("\n" + texto)
        except Exception as e:
            log(f"ERRO: {e}")
            raiz.after(0, lambda: status.set("Falha na instalação"))
        finally:
            raiz.after(0, lambda: botao.config(state="normal"))

    def clicar():
        botao.config(state="disabled")
        status.set("Instalando...")
        threading.Thread(target=trabalho, daemon=True).start()

    botao.config(command=clicar)
    raiz.mainloop()


def rodar_cli():
    print("=== Instalador do Reticulum Network ===")
    r = input("Instalar como serviço do sistema? [S/n] ").strip().lower()
    try:
        _, texto = fluxo(r != "n", print)
        print("\n" + texto)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        rodar_cli()
    else:
        try:
            import tkinter  # noqa
            rodar_gui()
        except ImportError:
            rodar_cli()
