# CHECKPOINT 004 - Ambiente e Configuração Kali Linux

**Data:** 29 de Março de 2026
**Foco:** Setup do ambiente do usuário e comandos úteis

---

## Ambiente do Usuário

| Item | Detalhe |
|---|---|
| **Dispositivo** | Android com root |
| **Sistema** | Kali Linux NetHunter (chroot) |
| **Terminal** | Termux / NetHunter Terminal |
| **Root** | Sim (acesso total) |
| **Rede** | 5G (dados móveis) + Wi-Fi |
| **Navegador** | Brave Browser |
| **Python** | 3.x (via pip3) |

---

## Comandos Úteis para o Kali

### Limpeza de DNS
```bash
ndc resolver flushdefaultiface
ndc resolver flushiface wlan0         # Wi-Fi
ndc resolver flushiface rmnet_data0   # Dados Móveis
```

### Reset de IP (Forçar Novo IP no 5G)
```bash
svc data disable && sleep 2 && svc data enable
```

### Limpar Cache de Roteamento
```bash
ip route flush cache
```

### Forçar DNS Cloudflare
```bash
echo "nameserver 1.1.1.1" > /etc/resolv.conf
echo "nameserver 1.0.0.1" >> /etc/resolv.conf
```

### Modo Avião via Terminal
```bash
settings put global airplane_mode_on 1
am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true
sleep 3
settings put global airplane_mode_on 0
am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false
```

---

## Instalação de Dependências

```bash
# Atualizar pip
pip3 install --upgrade pip

# Instalar dependências dos scripts
pip3 install requests playwright rich

# Instalar Chromium para Playwright
playwright install chromium

# Se Playwright der erro no ARM64
pip3 install playwright==1.40.0
PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright playwright install chromium
```

---

## Estrutura de Arquivos no Kali

```
/root/
├── 2nr_kali.py                 # Script 2NR ativo
├── 2nr_ultimate_v9.py          # Script 2NR automação total
├── manus_creator.py            # Script Manus creator
├── 2nr_credentials.txt         # Credenciais 2NR salvas
├── manus_credentials.txt       # Credenciais Manus salvas
├── manus_tokens.txt            # JWT tokens Manus
├── config.json                 # Config do Emailnator monitor
├── *_2nr_ultimate.log          # Logs de execução
└── *_manus_creator.log         # Logs de execução
```

---

## Dicas de Troubleshooting

1. **Erro 419 no Emailnator:** Token XSRF expirou. O script renova automaticamente.
2. **Erro 500 no 2NR:** Verificar se a senha tem caractere especial.
3. **Cloudflare bloqueando:** Trocar IP com modo avião ou usar proxy diferente.
4. **Playwright não abre:** Verificar se Chromium está instalado: `playwright install chromium`
5. **Proxy não conecta:** Testar com `curl -x http://user:pass@host:port https://api.ipify.org`
