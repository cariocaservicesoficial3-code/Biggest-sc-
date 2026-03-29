# Guia de Uso - Manus Creator V7 (Turnstile Ultra Bypass)

**Versão:** 7.0
**Data:** 2026-03-29
**Ambiente:** Kali Linux NetHunter + KeX VNC

---

## Pré-requisitos

### Hardware/Software

- Kali Linux NetHunter (chroot) com root
- KeX VNC ativo (DISPLAY=:1)
- Python 3.8+
- Conexão com internet (dados móveis ou Wi-Fi)

### Instalação de Dependências

```bash
# Instalar Patchright (fork anti-detecção do Playwright)
pip3 install patchright requests rich --break-system-packages

# Instalar browser Chromium via Patchright
python3 -m patchright install chromium

# Instalar xdotool (ESSENCIAL para cliques reais)
apt install xdotool

# Verificar instalação
python3 -c "from patchright.async_api import async_playwright; print('Patchright OK')"
which xdotool && echo "xdotool OK"
```

---

## Modos de Operação

### Modo 1: Local Only (sem API externa)

O modo padrão. Usa apenas estratégias locais (Harvester + xdotool).

```bash
python3 manus_creator_v7.py
```

### Modo 2: Com Serviço Externo de CAPTCHA

Adiciona a Estratégia 1 (Interceptor + External Solver) para máxima taxa de sucesso.

```bash
# Com CapSolver
CAPTCHA_API_KEY="CAP-XXXXXXX" CAPTCHA_SERVICE="capsolver" python3 manus_creator_v7.py

# Com 2Captcha
CAPTCHA_API_KEY="XXXXXXX" CAPTCHA_SERVICE="2captcha" python3 manus_creator_v7.py
```

---

## Fluxo de Execução

### Etapa 0: Link de Convite

O script pede o link de convite do Manus. Aceita:
- URL completa: `https://manus.im/invitation/CODIGO?utm_source=...`
- URL com code: `https://manus.im/login?code=CODIGO`
- Código direto: `CODIGO`
- ENTER para usar o padrão

### Etapa 1-2: Gmail + Senha

Gera automaticamente via Emailnator (dotGmail) e senha forte de 20 caracteres.

### Etapa 3: Browser

Abre Chromium via Patchright no display VNC com todos os patches de stealth injetados.

### Etapa 4-5: Navegação + Email

Navega para manus.im/login e preenche o email (digitação humanizada).

### Etapa 6: Turnstile Cascade (o coração do V7)

Tenta resolver o Turnstile com 4 estratégias em cascata:

```
┌─────────────────────────────────────────┐
│  ESTRATÉGIA 1: Interceptor + External   │
│  (requer CAPTCHA_API_KEY)               │
│  ↓ falhou                               │
├─────────────────────────────────────────┤
│  ESTRATÉGIA 2: Local Page Harvester     │
│  (página HTML com sitekey)              │
│  ↓ falhou                               │
├─────────────────────────────────────────┤
│  ESTRATÉGIA 3: screenXY Patch + xdotool │
│  (patch CDP + Bézier humanizado)        │
│  ↓ falhou                               │
├─────────────────────────────────────────┤
│  ESTRATÉGIA 4: xdotool Fallback        │
│  (clique simples - V6 compat)          │
└─────────────────────────────────────────┘
         ↓ todas falharam
    Recarrega página e tenta novamente
    (até 3 tentativas globais)
```

Se todas falharem, o script pausa e pede resolução manual.

### Etapas 7-12: Continue + Verificação + Registro

Fluxo padrão: clica Continue, envia código de verificação via API, captura código do email via Emailnator, registra conta, seleciona Polônia.

---

## Troubleshooting

### Turnstile fica em "Verifying..." e falha

**Causa provável:** WebGL ainda reportando SwiftShader ou screenX/screenY não patcheado.

**Soluções:**
1. Verificar nos logs do browser se o patch foi aplicado:
   ```
   CONSOLE: [V7] screenX/screenY patch applied
   CONSOLE: [V7] Turnstile interceptor installed
   ```
2. Se não aparecer, verificar se o `add_init_script` está sendo executado
3. Tentar com serviço externo: `CAPTCHA_API_KEY=... python3 manus_creator_v7.py`

### xdotool clica no lugar errado

**Causa:** Coordenadas calculadas incorretamente no VNC.

**Soluções:**
1. Verificar se a janela do browser está maximizada e na posição (0,0)
2. Verificar nos logs: `xdotool Window: pos=(X,Y)` deve ser (0,0) ou próximo
3. Se necessário, ajustar `--window-position=0,0` nos args do browser

### Emailnator retorna 419

**Causa:** Token XSRF expirado.

**Solução:** O V7 já trata isso automaticamente com retry. Se persistir, pode ser rate limit do Emailnator.

### "Verification failed" mesmo com clique manual

**Causa:** O ambiente VNC/SwiftShader está sendo detectado pelo Turnstile independente do clique.

**Soluções:**
1. Usar serviço externo (Estratégia 1) que resolve em ambiente limpo
2. Considerar usar proxy residencial em vez de datacenter
3. Considerar instalar Chrome real em vez de Chromium

---

## Logs

Todos os logs são salvos em `/sdcard/nh_files/MANUS LOGS/`:

| Arquivo | Conteúdo |
|---------|----------|
| `*_manus_creator.log` | Log principal com todas as etapas |
| `*_manus_http.log` | Requisições HTTP detalhadas |
| `*_manus_browser.log` | Eventos do browser e console |
| `*_manus_errors.log` | Apenas erros com stack trace |
| `manus_credentials.log` | Credenciais geradas (acumulativo) |
| `manus_tokens.log` | JWT tokens capturados (acumulativo) |
| `*_manus_api_dump.json` | Dump de todas as respostas da API |
| `*.png` | Screenshots de cada etapa |
| `MANUS_LOGS.zip` | ZIP acumulativo com tudo |

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DISPLAY` | `:1` | Display X11 do VNC |
| `CAPTCHA_API_KEY` | (vazio) | Chave API do serviço de CAPTCHA |
| `CAPTCHA_SERVICE` | `capsolver` | Serviço: `capsolver` ou `2captcha` |

---

## Diferenças V6 vs V7

| Aspecto | V6 | V7 |
|---------|----|----|
| Estratégias Turnstile | 1 (xdotool) | 4 (cascata) |
| screenX/screenY patch | Não | Sim |
| Canvas noise | Não | Sim |
| AudioContext spoof | Não | Sim |
| Mouse humanizado | Básico | Bézier cúbico |
| Digitação | fill() | Caractere por caractere |
| Serviço externo | Não | Opcional (CapSolver/2Captcha) |
| Local Harvester | Não | Sim |
| Interceptor | Não | Sim |
| Linhas de código | ~1600 | ~2400 |
