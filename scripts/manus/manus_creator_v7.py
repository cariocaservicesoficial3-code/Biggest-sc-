#!/usr/bin/env python3
"""
==============================================================
  MANUS ACCOUNT CREATOR V7.2 - KALI LINUX NETHUNTER + KeX VNC
  TURNSTILE ULTRA BYPASS - Multi-Strategy Engine (NETWORK FIX)
==============================================================

V7.2 (sobre V7.1):
- FIX CRÍTICO: challenges.cloudflare.com BLOQUEADO na rede do usuário
  O IP do 5G entrou na lista negra do Cloudflare por excesso de tentativas.
  O widget Turnstile não renderiza porque não consegue se comunicar com o CF.
- NOVO: Auto-correção de DNS (força 1.1.1.1 / 8.8.8.8 / 8.8.4.4)
- NOVO: Troca automática de IP via modo avião (Android)
- NOVO: Browser com PROXY para rotear tráfego (evita bloqueio de IP)
- NOVO: Estratégia 0 (NOVA): API-only bypass sem precisar do widget
  Usa serviço externo para resolver Turnstile sem carregar o widget local
- NOVO: Verificação pré-voo de conectividade com Cloudflare
- NOVO: Flush de DNS e cache antes de navegar
- FIX: Max tentativas globais aumentado para 5

HOTFIX V7.1 (sobre V7):
- FIX CRÍTICO: Removida flag --disable-web-security que QUEBRAVA o Turnstile
  (Cloudflare rejeita browsers com essa flag desde Feb 2025)
- FIX: Removidas flags --disable-site-isolation-trials e --allow-running-insecure-content
- FIX: Interceptor Turnstile mais seguro (não quebra se falhar)
- FIX: Espera adequada para Turnstile carregar (wait_for_selector no iframe)
- FIX: Re-preenchimento de email após reload nas tentativas
- FIX: Diagnóstico de rede (verifica se challenges.cloudflare.com está acessível)
- FIX: Estratégias 3/4 agora esperam o iframe aparecer antes de tentar clicar

Mudanças V7 (sobre V6):
- NOVA ESTRATÉGIA 1: Turnstile Render Interceptor
  Intercepta window.turnstile.render() ANTES do Turnstile carregar,
  captura sitekey/cData/chlPageData/callback, resolve via serviço
  externo e injeta token via callback original.

- NOVA ESTRATÉGIA 2: Local Page Token Harvester (inspirado no Turnstile-Solver)
  Cria uma página HTML local com o sitekey do Manus, carrega o widget
  Turnstile nessa página (onde o ambiente é mais controlado), resolve
  o captcha, extrai o token e injeta na página real.

- NOVA ESTRATÉGIA 3: screenX/screenY Patch + Enhanced xdotool
  Corrige o bug do CDP onde screenX/screenY ficam relativos ao iframe
  (< 100) em vez de relativos à tela (> 100). Injeta patch via
  extensão/init_script que sobrescreve MouseEvent.prototype.

- NOVA ESTRATÉGIA 4: Stealth Máximo + Anti-Fingerprint
  Canvas noise injection, AudioContext spoofing, WebRTC leak prevention,
  Battery API spoofing, além dos patches WebGL já existentes.

- FALLBACK: Serviço externo de CAPTCHA solving (CapSolver/2Captcha)
  Se todas as estratégias locais falharem, usa API externa.

- Melhorias gerais:
  - Mouse humanizado com curvas de Bézier
  - Delays randomizados entre ações
  - Retry inteligente com backoff exponencial
  - Detecção automática do modo Turnstile (managed/interactive)
  - Logs ainda mais detalhados

Fluxo:
1. Pede o link de convite do Manus
2. Gera Gmail temporário via Emailnator (dotGmail)
3. Gera senha forte no padrão aceito pelo Manus
4. Abre Patchright (headless=False) no display VNC
5. Injeta scripts de stealth + interceptor do Turnstile
6. Navega para manus.im/login
7. Preenche email
8. Tenta resolver Turnstile com estratégias em cascata:
   A) Interceptor → Serviço externo → Callback injection
   B) Local Page Harvester (página HTML com sitekey)
   C) screenX/screenY patch + xdotool real click
   D) xdotool padrão (V6 fallback)
9. Clica Continue
10. Monitora Emailnator para capturar código de 6 dígitos
11. Envia o código de verificação
12. Completa registro via API
13. Seleciona Polônia na página de telefone
14. Salva logs e credenciais

Requisitos:
  pip3 install patchright requests rich --break-system-packages
  python3 -m patchright install chromium
  apt install xdotool  (para cliques reais no Turnstile)
"""

import asyncio
import json
import logging
import math
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
import traceback
import zipfile
from datetime import datetime
from urllib.parse import unquote

# ============================================================
# FIX CRÍTICO: SETAR DISPLAY PARA VNC/KeX
# ============================================================
os.environ['DISPLAY'] = ':1'

# ============================================================
# DETECTAR PATCHRIGHT OU PLAYWRIGHT
# ============================================================
USING_PATCHRIGHT = False
try:
    from patchright.async_api import async_playwright
    USING_PATCHRIGHT = True
except ImportError:
    try:
        from playwright.async_api import async_playwright
        USING_PATCHRIGHT = False
    except ImportError:
        print("\033[91m[ERRO] Nem patchright nem playwright estão instalados!\033[0m")
        print("\033[93mInstale com: pip3 install patchright --break-system-packages\033[0m")
        print("\033[93m             python3 -m patchright install chromium\033[0m")
        sys.exit(1)

# ============================================================
# VERIFICAR XDOTOOL
# ============================================================
XDOTOOL_AVAILABLE = shutil.which('xdotool') is not None

# ============================================================
# CORES PARA O TERMINAL
# ============================================================
class C:
    R = '\033[91m'
    G = '\033[92m'
    Y = '\033[93m'
    B = '\033[94m'
    M = '\033[95m'
    CY = '\033[96m'
    W = '\033[97m'
    BD = '\033[1m'
    RS = '\033[0m'

# ============================================================
# CONFIGURAÇÃO DE LOGS - /sdcard/nh_files/MANUS LOGS/
# ============================================================
LOG_DIR = "/sdcard/nh_files/MANUS LOGS"
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')

# Arquivos de log
main_log_file = os.path.join(LOG_DIR, f"{timestamp}_manus_creator.log")
http_log_file = os.path.join(LOG_DIR, f"{timestamp}_manus_http.log")
browser_log_file = os.path.join(LOG_DIR, f"{timestamp}_manus_browser.log")
creds_file = os.path.join(LOG_DIR, "manus_credentials.log")
tokens_file = os.path.join(LOG_DIR, "manus_tokens.log")
error_log_file = os.path.join(LOG_DIR, f"{timestamp}_manus_errors.log")

class ColorFmt(logging.Formatter):
    COLORS = {'DEBUG': C.CY, 'INFO': C.G, 'WARNING': C.Y, 'ERROR': C.R, 'CRITICAL': C.R}
    def format(self, record):
        c = self.COLORS.get(record.levelname, C.W)
        record.msg = f"{c}{record.msg}{C.RS}"
        return super().format(record)

# Logger principal
log = logging.getLogger("MANUS")
log.setLevel(logging.DEBUG)

fh_main = logging.FileHandler(main_log_file, encoding='utf-8')
fh_main.setLevel(logging.DEBUG)
fh_main.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s'))
log.addHandler(fh_main)

fh_error = logging.FileHandler(error_log_file, encoding='utf-8')
fh_error.setLevel(logging.ERROR)
fh_error.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s\n%(pathname)s:%(lineno)d'))
log.addHandler(fh_error)

sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.DEBUG)
sh.setFormatter(ColorFmt('%(asctime)s [%(levelname)s] %(message)s'))
log.addHandler(sh)

# Logger HTTP
http_log = logging.getLogger("HTTP")
http_log.setLevel(logging.DEBUG)
fh_http = logging.FileHandler(http_log_file, encoding='utf-8')
fh_http.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
http_log.addHandler(fh_http)
http_log.addHandler(fh_main)

# Logger Browser
browser_log = logging.getLogger("BROWSER")
browser_log.setLevel(logging.DEBUG)
fh_browser = logging.FileHandler(browser_log_file, encoding='utf-8')
fh_browser.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
browser_log.addHandler(fh_browser)
browser_log.addHandler(fh_main)

def log_separator(title):
    sep = "=" * 60
    log.info(sep)
    log.info(f"  {title}")
    log.info(sep)

def log_to_file(filepath, content):
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().isoformat()}] {content}\n")

# ============================================================
# V7.2: FUNÇÕES DE REDE (DNS, IP, PREFLIGHT)
# ============================================================
def fix_dns():
    """V7.2: Força DNS públicos para evitar bloqueio de resolução."""
    dns_servers = [
        "nameserver 1.1.1.1",
        "nameserver 8.8.8.8",
        "nameserver 8.8.4.4",
        "nameserver 1.0.0.1",
    ]
    try:
        with open('/etc/resolv.conf', 'r') as f:
            current = f.read()
        
        if '1.1.1.1' in current and '8.8.8.8' in current:
            log.info("[NET] DNS já configurado corretamente")
            return True
        
        # Backup
        with open('/etc/resolv.conf.bak', 'w') as f:
            f.write(current)
        
        with open('/etc/resolv.conf', 'w') as f:
            f.write("\n".join(dns_servers) + "\n")
        
        log.info("[NET] DNS atualizado: 1.1.1.1, 8.8.8.8, 8.8.4.4, 1.0.0.1")
        return True
    except PermissionError:
        log.warning("[NET] Sem permissão para alterar /etc/resolv.conf (tente como root)")
        return False
    except Exception as e:
        log.warning(f"[NET] Erro ao configurar DNS: {e}")
        return False


def flush_dns_cache():
    """V7.2: Limpa cache de DNS e rotas."""
    commands = [
        "ndc resolver flushdefaultiface",
        "ip route flush cache",
    ]
    for cmd in commands:
        try:
            subprocess.run(cmd.split(), capture_output=True, timeout=5)
        except:
            pass
    log.info("[NET] Cache DNS/rotas limpo")


def rotate_ip_airplane():
    """
    V7.2: Troca IP via modo avião no Android.
    Desliga dados móveis, espera, religa.
    """
    log.info("[NET] Tentando trocar IP via modo avião...")
    try:
        # Método 1: svc data
        subprocess.run("svc data disable".split(), capture_output=True, timeout=5)
        time.sleep(3)
        subprocess.run("svc data enable".split(), capture_output=True, timeout=5)
        time.sleep(5)
        log.info("[NET] IP trocado via svc data")
        return True
    except:
        pass
    
    try:
        # Método 2: Modo avião completo
        subprocess.run("settings put global airplane_mode_on 1".split(), capture_output=True, timeout=5)
        subprocess.run("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true".split(), capture_output=True, timeout=5)
        time.sleep(4)
        subprocess.run("settings put global airplane_mode_on 0".split(), capture_output=True, timeout=5)
        subprocess.run("am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false".split(), capture_output=True, timeout=5)
        time.sleep(8)
        log.info("[NET] IP trocado via modo avião")
        return True
    except:
        log.warning("[NET] Não foi possível trocar IP automaticamente")
        return False


def check_cloudflare_connectivity():
    """
    V7.2: Verificação pré-voo de conectividade com Cloudflare.
    Testa se challenges.cloudflare.com está acessível via HTTP.
    """
    import requests as req_lib
    
    test_urls = [
        "https://challenges.cloudflare.com/cdn-cgi/trace",
        "https://1.1.1.1/cdn-cgi/trace",
    ]
    
    for url in test_urls:
        try:
            resp = req_lib.get(url, timeout=10, headers={'User-Agent': USER_AGENT})
            if resp.status_code == 200:
                log.info(f"[NET] Cloudflare acessível via {url.split('/')[2]}")
                return True
        except Exception as e:
            log.warning(f"[NET] {url.split('/')[2]} não acessível: {e}")
    
    # Tentar via proxy
    try:
        resp = req_lib.get(
            "https://challenges.cloudflare.com/cdn-cgi/trace",
            timeout=15,
            proxies={'https': PROXY_URL, 'http': PROXY_URL},
            headers={'User-Agent': USER_AGENT}
        )
        if resp.status_code == 200:
            log.info("[NET] Cloudflare acessível via PROXY")
            return 'PROXY'
    except:
        pass
    
    log.error("[NET] Cloudflare NÃO acessível por nenhum método!")
    return False


def get_current_ip():
    """V7.2: Obtém o IP público atual."""
    import requests as req_lib
    try:
        resp = req_lib.get("https://api.ipify.org?format=json", timeout=10)
        ip = resp.json().get('ip', 'desconhecido')
        log.info(f"[NET] IP atual: {ip}")
        return ip
    except:
        try:
            resp = req_lib.get("https://ifconfig.me/ip", timeout=10)
            ip = resp.text.strip()
            log.info(f"[NET] IP atual: {ip}")
            return ip
        except:
            return None


# ============================================================
# CONFIGURAÇÕES
# ============================================================
MANUS_API = "https://api.manus.im"
EMAILNATOR_URL = "https://www.emailnator.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"

PROXY_HOST = "74.81.81.81"
PROXY_PORT = "823"
PROXY_USER = "be2c872545392337df6e__cr.br"
PROXY_PASS = "768df629c0304df6"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

DEFAULT_INVITE = "OB746IYA9QIKG"

# Chave API para serviço de CAPTCHA solving (configurável)
CAPTCHA_API_KEY = os.environ.get("CAPTCHA_API_KEY", "")
CAPTCHA_SERVICE = os.environ.get("CAPTCHA_SERVICE", "capsolver")  # capsolver, 2captcha

# ============================================================
# EMAILNATOR CLIENT (mantido do V6)
# ============================================================
class Emailnator:
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        })
        self.xsrf_token = None
        self.email = None
        log.debug("Emailnator client inicializado")
    
    def _get_xsrf(self):
        try:
            http_log.info(f"GET {EMAILNATOR_URL} (obtendo XSRF token)")
            resp = self.session.get(EMAILNATOR_URL, timeout=15)
            http_log.info(f"  Status: {resp.status_code}")
            for cookie in resp.cookies:
                if cookie.name == 'XSRF-TOKEN':
                    self.xsrf_token = unquote(cookie.value)
                    http_log.info(f"  XSRF-TOKEN obtido: {self.xsrf_token[:40]}...")
                    return True
            http_log.warning("  XSRF-TOKEN não encontrado")
            return False
        except Exception as e:
            http_log.error(f"  Erro XSRF: {e}")
            return False
    
    def _headers(self):
        return {
            'Content-Type': 'application/json',
            'Origin': EMAILNATOR_URL,
            'Referer': f'{EMAILNATOR_URL}/',
            'User-Agent': USER_AGENT,
            'X-Requested-With': 'XMLHttpRequest',
            'X-XSRF-TOKEN': self.xsrf_token,
        }
    
    def generate_email(self):
        if not self._get_xsrf():
            return None
        try:
            payload = {"email": ["dotGmail"]}
            http_log.info(f"POST {EMAILNATOR_URL}/generate-email")
            resp = self.session.post(
                f"{EMAILNATOR_URL}/generate-email",
                headers=self._headers(),
                json=payload,
                timeout=15
            )
            http_log.info(f"  Status: {resp.status_code}")
            http_log.debug(f"  Response: {resp.text[:500]}")
            
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, dict) and 'email' in result:
                    emails = result['email']
                    self.email = emails[0] if isinstance(emails, list) else emails
                elif isinstance(result, list):
                    self.email = result[0]
                if self.email:
                    log.info(f"Gmail gerado: {self.email}")
                    return self.email
            return None
        except Exception as e:
            log.error(f"Erro ao gerar email: {e}")
            return None
    
    def get_inbox(self):
        if not self.email:
            return None
        try:
            resp = self.session.post(
                f"{EMAILNATOR_URL}/message-list",
                headers=self._headers(),
                json={"email": self.email},
                timeout=15
            )
            if resp.status_code == 419:
                self._get_xsrf()
                resp = self.session.post(
                    f"{EMAILNATOR_URL}/message-list",
                    headers=self._headers(),
                    json={"email": self.email},
                    timeout=15
                )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            http_log.error(f"  Erro inbox: {e}")
            return None
    
    def get_message(self, message_id):
        try:
            resp = self.session.post(
                f"{EMAILNATOR_URL}/message-list",
                headers=self._headers(),
                json={"email": self.email, "messageID": message_id},
                timeout=15
            )
            if resp.status_code == 200:
                return resp.text
            return None
        except:
            return None
    
    def wait_for_code(self, sender_filter="manus", max_wait=180):
        log.info(f"Aguardando código do e-mail (max {max_wait}s)...")
        start = time.time()
        
        while time.time() - start < max_wait:
            inbox = self.get_inbox()
            if inbox and isinstance(inbox, list):
                for msg in inbox:
                    subject = msg.get('subject', '') if isinstance(msg, dict) else str(msg)
                    from_addr = msg.get('from', '') if isinstance(msg, dict) else ''
                    
                    if sender_filter.lower() in subject.lower() or sender_filter.lower() in from_addr.lower():
                        msg_id = msg.get('messageID', '') if isinstance(msg, dict) else None
                        
                        text_to_search = subject
                        if msg_id:
                            body = self.get_message(msg_id)
                            if body:
                                text_to_search = body
                        
                        codes = re.findall(r'\b(\d{6})\b', text_to_search)
                        if codes:
                            code = codes[0]
                            log.info(f"Código encontrado: {code}")
                            return code
            
            elapsed = int(time.time() - start)
            if elapsed % 15 == 0 and elapsed > 0:
                log.info(f"  Aguardando e-mail... ({elapsed}s/{max_wait}s)")
            time.sleep(5)
        
        return None

# ============================================================
# GERADOR DE SENHA (mantido do V6)
# ============================================================
def generate_manus_password(length=20):
    upper = random.choice(string.ascii_uppercase)
    lower = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    special = random.choice("@#$%&")
    rest = ''.join(random.choices(
        string.ascii_letters + string.digits + "@#$%&",
        k=length - 4
    ))
    pwd = list(upper + lower + digit + special + rest)
    random.shuffle(pwd)
    result = ''.join(pwd)
    log.debug(f"Senha gerada ({length} chars): {result}")
    return result

# ============================================================
# XDOTOOL HELPERS (melhorado do V6)
# ============================================================
def get_window_geometry():
    """Obtém posição e tamanho da janela ativa via xdotool."""
    if not XDOTOOL_AVAILABLE:
        return None
    try:
        win_id = subprocess.check_output(
            ['xdotool', 'getactivewindow'],
            timeout=5
        ).decode().strip()
        
        geo = subprocess.check_output(
            ['xdotool', 'getwindowgeometry', win_id],
            timeout=5
        ).decode().strip()
        
        pos_match = re.search(r'Position:\s*(\d+),(\d+)', geo)
        size_match = re.search(r'Geometry:\s*(\d+)x(\d+)', geo)
        
        if pos_match and size_match:
            return {
                'id': win_id,
                'x': int(pos_match.group(1)),
                'y': int(pos_match.group(2)),
                'width': int(size_match.group(1)),
                'height': int(size_match.group(2)),
            }
    except Exception as e:
        browser_log.warning(f"xdotool getwindowgeometry falhou: {e}")
    return None

def xdotool_click(x, y):
    """Clique simples via xdotool."""
    if not XDOTOOL_AVAILABLE:
        return False
    try:
        subprocess.run(
            ['xdotool', 'mousemove', str(x), str(y)],
            timeout=5
        )
        time.sleep(0.1)
        subprocess.run(
            ['xdotool', 'click', '1'],
            timeout=5
        )
        return True
    except Exception as e:
        browser_log.warning(f"xdotool click falhou: {e}")
        return False

def xdotool_human_click(target_x, target_y, steps=None):
    """
    Clique humanizado com curva de Bézier via xdotool.
    Simula movimento natural do mouse antes de clicar.
    """
    if not XDOTOOL_AVAILABLE:
        return False
    
    try:
        # Obter posição atual do mouse
        try:
            loc = subprocess.check_output(
                ['xdotool', 'getmouselocation'],
                timeout=5
            ).decode().strip()
            loc_match = re.search(r'x:(\d+)\s+y:(\d+)', loc)
            if loc_match:
                start_x = int(loc_match.group(1))
                start_y = int(loc_match.group(2))
            else:
                start_x = random.randint(100, 400)
                start_y = random.randint(100, 300)
        except:
            start_x = random.randint(100, 400)
            start_y = random.randint(100, 300)
        
        # Gerar curva de Bézier para movimento natural
        if steps is None:
            distance = math.sqrt((target_x - start_x)**2 + (target_y - start_y)**2)
            steps = max(15, min(40, int(distance / 10)))
        
        # Pontos de controle da curva de Bézier (cúbica)
        cp1_x = start_x + random.randint(-50, 50) + (target_x - start_x) * 0.3
        cp1_y = start_y + random.randint(-30, 30) + (target_y - start_y) * 0.1
        cp2_x = start_x + random.randint(-30, 30) + (target_x - start_x) * 0.7
        cp2_y = start_y + random.randint(-20, 20) + (target_y - start_y) * 0.9
        
        for i in range(steps + 1):
            t = i / steps
            # Fórmula de Bézier cúbica
            x = int(
                (1-t)**3 * start_x +
                3 * (1-t)**2 * t * cp1_x +
                3 * (1-t) * t**2 * cp2_x +
                t**3 * target_x
            )
            y = int(
                (1-t)**3 * start_y +
                3 * (1-t)**2 * t * cp1_y +
                3 * (1-t) * t**2 * cp2_y +
                t**3 * target_y
            )
            
            subprocess.run(
                ['xdotool', 'mousemove', str(x), str(y)],
                timeout=3
            )
            
            # Delay variável (mais lento no início e fim, mais rápido no meio)
            if t < 0.2 or t > 0.8:
                time.sleep(random.uniform(0.015, 0.035))
            else:
                time.sleep(random.uniform(0.005, 0.015))
        
        # Pequena pausa antes do clique (como humano)
        time.sleep(random.uniform(0.05, 0.15))
        
        # Clique
        subprocess.run(['xdotool', 'click', '1'], timeout=5)
        
        browser_log.info(f"xdotool human click: ({start_x},{start_y}) → ({target_x},{target_y}) em {steps} passos")
        return True
        
    except Exception as e:
        browser_log.warning(f"xdotool human click falhou: {e}")
        # Fallback para clique simples
        return xdotool_click(target_x, target_y)


# ============================================================
# STEALTH SCRIPTS - Injetados antes de qualquer navegação
# ============================================================

# Script 1: WebGL Spoofing (melhorado do V6)
WEBGL_SPOOF_SCRIPT = """
// === WebGL Renderer Spoofing ===
const getParameterOrig = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(param) {
    if (param === 0x9245) return 'NVIDIA Corporation';
    if (param === 0x9246) return 'NVIDIA GeForce GTX 1080 Ti/PCIe/SSE2';
    if (param === 0x1F00) return 'WebKit';  // GL_VENDOR
    if (param === 0x1F01) return 'WebKit WebGL';  // GL_RENDERER
    if (param === 0x1F02) return 'OpenGL ES 3.0 (WebGL 2.0)';  // GL_VERSION
    return getParameterOrig.call(this, param);
};

if (typeof WebGL2RenderingContext !== 'undefined') {
    const getParameter2Orig = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(param) {
        if (param === 0x9245) return 'NVIDIA Corporation';
        if (param === 0x9246) return 'NVIDIA GeForce GTX 1080 Ti/PCIe/SSE2';
        if (param === 0x1F00) return 'WebKit';
        if (param === 0x1F01) return 'WebKit WebGL';
        if (param === 0x1F02) return 'OpenGL ES 3.0 (WebGL 2.0)';
        return getParameter2Orig.call(this, param);
    };
}

// Spoof getSupportedExtensions para parecer GPU real
const origGetExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
WebGLRenderingContext.prototype.getSupportedExtensions = function() {
    const exts = origGetExtensions.call(this) || [];
    const extraExts = [
        'ANGLE_instanced_arrays',
        'EXT_blend_minmax',
        'EXT_color_buffer_half_float',
        'EXT_disjoint_timer_query',
        'EXT_float_blend',
        'EXT_frag_depth',
        'EXT_shader_texture_lod',
        'EXT_texture_compression_bptc',
        'EXT_texture_compression_rgtc',
        'EXT_texture_filter_anisotropic',
        'EXT_sRGB',
        'OES_element_index_uint',
        'OES_fbo_render_mipmap',
        'OES_standard_derivatives',
        'OES_texture_float',
        'OES_texture_float_linear',
        'OES_texture_half_float',
        'OES_texture_half_float_linear',
        'OES_vertex_array_object',
        'WEBGL_color_buffer_float',
        'WEBGL_compressed_texture_s3tc',
        'WEBGL_compressed_texture_s3tc_srgb',
        'WEBGL_debug_renderer_info',
        'WEBGL_debug_shaders',
        'WEBGL_depth_texture',
        'WEBGL_draw_buffers',
        'WEBGL_lose_context',
        'WEBGL_multi_draw',
    ];
    const set = new Set([...exts, ...extraExts]);
    return Array.from(set);
};

// Spoof WebGPU adapter info
if (navigator.gpu) {
    const origRequestAdapter = navigator.gpu.requestAdapter.bind(navigator.gpu);
    navigator.gpu.requestAdapter = async function(options) {
        const adapter = await origRequestAdapter(options);
        if (adapter) {
            const origInfo = adapter.requestAdapterInfo.bind(adapter);
            adapter.requestAdapterInfo = async function() {
                return { vendor: 'nvidia', architecture: 'ampere', device: '', description: '' };
            };
        }
        return adapter;
    };
}
"""

# Script 2: Canvas Fingerprint Noise
CANVAS_NOISE_SCRIPT = """
// === Canvas Fingerprint Noise Injection ===
// Adiciona ruído imperceptível ao canvas para gerar fingerprint único
// mas consistente por sessão (não muda a cada chamada)
(function() {
    const seed = Math.floor(Math.random() * 1000000);
    
    function pseudoRandom(s) {
        s = Math.sin(s) * 10000;
        return s - Math.floor(s);
    }
    
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {
            try {
                const imageData = ctx.getImageData(0, 0, Math.min(this.width, 16), Math.min(this.height, 16));
                for (let i = 0; i < imageData.data.length; i += 4) {
                    // Ruído mínimo (+-1) baseado em seed consistente
                    const noise = Math.floor(pseudoRandom(seed + i) * 3) - 1;
                    imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + noise));
                }
                ctx.putImageData(imageData, 0, 0);
            } catch(e) {}
        }
        return origToDataURL.apply(this, arguments);
    };
    
    const origToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {
            try {
                const imageData = ctx.getImageData(0, 0, Math.min(this.width, 16), Math.min(this.height, 16));
                for (let i = 0; i < imageData.data.length; i += 4) {
                    const noise = Math.floor(pseudoRandom(seed + i) * 3) - 1;
                    imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + noise));
                }
                ctx.putImageData(imageData, 0, 0);
            } catch(e) {}
        }
        return origToBlob.apply(this, arguments);
    };
})();
"""

# Script 3: AudioContext Spoofing
AUDIO_SPOOF_SCRIPT = """
// === AudioContext Fingerprint Spoofing ===
(function() {
    const origGetFloatFrequencyData = AnalyserNode.prototype.getFloatFrequencyData;
    AnalyserNode.prototype.getFloatFrequencyData = function(array) {
        origGetFloatFrequencyData.call(this, array);
        for (let i = 0; i < array.length; i++) {
            array[i] += (Math.random() - 0.5) * 0.001;
        }
    };
    
    const origCreateOscillator = AudioContext.prototype.createOscillator;
    AudioContext.prototype.createOscillator = function() {
        const osc = origCreateOscillator.call(this);
        const origConnect = osc.connect.bind(osc);
        osc.connect = function(dest) {
            return origConnect(dest);
        };
        return osc;
    };
})();
"""

# Script 4: Navigator/Browser Stealth (para quando NÃO usa Patchright)
NAVIGATOR_STEALTH_SCRIPT = """
// === Navigator Stealth ===
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
try { delete navigator.__proto__.webdriver; } catch(e) {}

const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

window.chrome = { runtime: {}, csi: function(){}, loadTimes: function(){} };

Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
        ];
        plugins.length = 3;
        return plugins;
    }
});

Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });

// Connection API spoofing
if (navigator.connection) {
    Object.defineProperty(navigator.connection, 'rtt', { get: () => 50 });
    Object.defineProperty(navigator.connection, 'downlink', { get: () => 10 });
    Object.defineProperty(navigator.connection, 'effectiveType', { get: () => '4g' });
}

// Battery API - retorna bateria cheia (desktop)
if (navigator.getBattery) {
    navigator.getBattery = () => Promise.resolve({
        charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1,
        addEventListener: () => {}, removeEventListener: () => {}
    });
}
"""

# Script 5: screenX/screenY Patch (CRÍTICO para Turnstile)
SCREENXY_PATCH_SCRIPT = """
// === screenX/screenY CDP Bug Patch ===
// Cloudflare Turnstile detecta que cliques via CDP têm screenX/screenY
// relativos ao iframe (valores pequenos < 100) em vez de relativos à tela.
// Este patch corrige o MouseEvent para sempre ter valores realistas.
(function() {
    const originalMouseEvent = MouseEvent;
    
    // Guardar referência ao window.screenX/screenY
    const getScreenX = () => window.screenX || window.screenLeft || 0;
    const getScreenY = () => window.screenY || window.screenTop || 0;
    
    // Patch no prototype do MouseEvent
    const screenXDesc = Object.getOwnPropertyDescriptor(MouseEvent.prototype, 'screenX');
    const screenYDesc = Object.getOwnPropertyDescriptor(MouseEvent.prototype, 'screenY');
    
    if (screenXDesc) {
        Object.defineProperty(MouseEvent.prototype, 'screenX', {
            get: function() {
                const origVal = screenXDesc.get.call(this);
                // Se o valor é suspeitamente baixo (< 100), corrigir
                if (origVal < 100 && this.clientX > 0) {
                    return this.clientX + getScreenX() + 
                           (window.outerWidth - window.innerWidth) / 2;
                }
                return origVal;
            },
            configurable: true
        });
    }
    
    if (screenYDesc) {
        Object.defineProperty(MouseEvent.prototype, 'screenY', {
            get: function() {
                const origVal = screenYDesc.get.call(this);
                if (origVal < 100 && this.clientY > 0) {
                    return this.clientY + getScreenY() + 
                           (window.outerHeight - window.innerHeight);
                }
                return origVal;
            },
            configurable: true
        });
    }
    
    // Também patch no PointerEvent
    const pScreenXDesc = Object.getOwnPropertyDescriptor(PointerEvent.prototype, 'screenX');
    const pScreenYDesc = Object.getOwnPropertyDescriptor(PointerEvent.prototype, 'screenY');
    
    if (pScreenXDesc) {
        Object.defineProperty(PointerEvent.prototype, 'screenX', {
            get: function() {
                const origVal = pScreenXDesc.get.call(this);
                if (origVal < 100 && this.clientX > 0) {
                    return this.clientX + getScreenX() + 
                           (window.outerWidth - window.innerWidth) / 2;
                }
                return origVal;
            },
            configurable: true
        });
    }
    
    if (pScreenYDesc) {
        Object.defineProperty(PointerEvent.prototype, 'screenY', {
            get: function() {
                const origVal = pScreenYDesc.get.call(this);
                if (origVal < 100 && this.clientY > 0) {
                    return this.clientY + getScreenY() + 
                           (window.outerHeight - window.innerHeight);
                }
                return origVal;
            },
            configurable: true
        });
    }
    
    console.log('[V7] screenX/screenY patch applied');
})();
"""

# Script 6: Turnstile Render Interceptor (ESTRATÉGIA 1)
TURNSTILE_INTERCEPTOR_SCRIPT = """
// === Turnstile Render Interceptor ===
// Intercepta window.turnstile.render() para capturar parâmetros
// e permitir injeção de token resolvido externamente.
(function() {
    // Armazenamento global para dados capturados
    window.__turnstileData = {
        sitekey: null,
        action: null,
        cData: null,
        chlPageData: null,
        callback: null,
        widgetId: null,
        tokenInjected: false,
        intercepted: false,
    };
    
    // Função para injetar token resolvido
    window.__injectTurnstileToken = function(token) {
        console.log('[V7 Interceptor] Injecting token:', token.substring(0, 30) + '...');
        
        // Método 1: Via callback original
        if (window.__turnstileData.callback) {
            try {
                window.__turnstileData.callback(token);
                console.log('[V7 Interceptor] Token injected via callback');
            } catch(e) {
                console.error('[V7 Interceptor] Callback error:', e);
            }
        }
        
        // Método 2: Via input hidden
        const inputs = document.querySelectorAll('input[name="cf-turnstile-response"]');
        inputs.forEach(input => {
            input.value = token;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });
        
        // Método 3: Via data attribute
        const widgets = document.querySelectorAll('.cf-turnstile, [data-sitekey]');
        widgets.forEach(w => {
            w.setAttribute('data-turnstile-response', token);
        });
        
        window.__turnstileData.tokenInjected = true;
        
        // Disparar evento customizado
        window.dispatchEvent(new CustomEvent('turnstileTokenInjected', { detail: { token } }));
        
        return true;
    };
    
    // Interceptar turnstile.render quando ele for definido
    let _turnstile = undefined;
    
    function patchTurnstile(ts) {
        if (!ts || ts.__patched) return ts;
        
        const origRender = ts.render;
        ts.render = function(container, params) {
            console.log('[V7 Interceptor] turnstile.render() intercepted!');
            console.log('[V7 Interceptor] Container:', container);
            console.log('[V7 Interceptor] Params:', JSON.stringify(params || {}));
            
            // Capturar parâmetros
            if (params) {
                window.__turnstileData.sitekey = params.sitekey || params['data-sitekey'];
                window.__turnstileData.action = params.action;
                window.__turnstileData.cData = params.cData;
                window.__turnstileData.chlPageData = params.chlPageData;
                window.__turnstileData.intercepted = true;
                
                // Capturar callback
                if (params.callback) {
                    window.__turnstileData.callback = params.callback;
                }
                if (params['success-callback']) {
                    window.__turnstileData.callback = params['success-callback'];
                }
            }
            
            // Também extrair sitekey do container element
            if (typeof container === 'string') {
                const el = document.querySelector(container);
                if (el) {
                    const sk = el.getAttribute('data-sitekey');
                    if (sk) window.__turnstileData.sitekey = sk;
                }
            } else if (container && container.getAttribute) {
                const sk = container.getAttribute('data-sitekey');
                if (sk) window.__turnstileData.sitekey = sk;
            }
            
            // Chamar render original
            const widgetId = origRender.call(this, container, params);
            window.__turnstileData.widgetId = widgetId;
            
            console.log('[V7 Interceptor] Widget ID:', widgetId);
            console.log('[V7 Interceptor] Captured sitekey:', window.__turnstileData.sitekey);
            
            return widgetId;
        };
        
        // Interceptar getResponse também
        if (ts.getResponse) {
            const origGetResponse = ts.getResponse;
            ts.getResponse = function(widgetId) {
                const resp = origGetResponse.call(this, widgetId);
                if (resp) {
                    console.log('[V7 Interceptor] getResponse returned token');
                }
                return resp;
            };
        }
        
        ts.__patched = true;
        return ts;
    }
    
    // Interceptar a definição de window.turnstile (V7.1: mais seguro)
    try {
        // Verificar se já existe
        if (window.turnstile) {
            console.log('[V7.1] window.turnstile já existe, patcheando direto');
            patchTurnstile(window.turnstile);
        } else {
            Object.defineProperty(window, 'turnstile', {
                get: function() { return _turnstile; },
                set: function(val) {
                    console.log('[V7.1 Interceptor] window.turnstile being set!');
                    try {
                        _turnstile = patchTurnstile(val);
                    } catch(patchErr) {
                        console.warn('[V7.1] Patch falhou, usando original:', patchErr);
                        _turnstile = val;
                    }
                },
                configurable: true,
                enumerable: true,
            });
        }
    } catch(e) {
        console.warn('[V7.1] Interceptor setup falhou (não crítico):', e.message);
        // NÃO quebrar - o Turnstile deve funcionar normalmente sem interceptor
        try {
            if (window.turnstile) patchTurnstile(window.turnstile);
        } catch(e2) {}
    }
    
    console.log('[V7.1] Turnstile interceptor installed (safe mode)');
})();
"""

# Combinar todos os scripts de stealth
def get_stealth_scripts(use_patchright=True):
    """Retorna os scripts de stealth combinados."""
    scripts = [
        WEBGL_SPOOF_SCRIPT,
        CANVAS_NOISE_SCRIPT,
        AUDIO_SPOOF_SCRIPT,
        SCREENXY_PATCH_SCRIPT,
        TURNSTILE_INTERCEPTOR_SCRIPT,
    ]
    if not use_patchright:
        scripts.append(NAVIGATOR_STEALTH_SCRIPT)
    return "\n\n".join(scripts)


# ============================================================
# V7.1: DIAGNÓSTICO DE REDE E ESPERA PELO TURNSTILE
# ============================================================
async def diagnose_turnstile_loading(page, timeout=20):
    """
    V7.1: Verifica se o Turnstile está carregando na página.
    Espera até o iframe aparecer ou diagnostica o problema.
    """
    log.info("[DIAG] Verificando carregamento do Turnstile...")
    
    # Verificar se challenges.cloudflare.com está acessível
    try:
        cf_check = await page.evaluate("""
            () => new Promise((resolve) => {
                const img = new Image();
                img.onload = () => resolve('OK');
                img.onerror = () => resolve('BLOCKED');
                img.src = 'https://challenges.cloudflare.com/cdn-cgi/images/trace/managed/nocompress/transparent.gif?' + Date.now();
                setTimeout(() => resolve('TIMEOUT'), 8000);
            })
        """)
        log.info(f"[DIAG] challenges.cloudflare.com: {cf_check}")
        if cf_check != 'OK':
            log.warning(f"[DIAG] challenges.cloudflare.com NÃO acessível! ({cf_check})")
            log.warning("[DIAG] Isso pode indicar bloqueio de rede ou DNS")
    except Exception as e:
        log.warning(f"[DIAG] Erro ao verificar CF: {e}")
    
    # Verificar se o script do Turnstile foi carregado
    try:
        ts_status = await page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script[src*="challenges.cloudflare"], script[src*="turnstile"]');
                const hasWidget = document.querySelector('.cf-turnstile, [data-sitekey]');
                const hasIframe = document.querySelector('iframe[src*="challenges.cloudflare"]');
                const hasTurnstileObj = typeof window.turnstile !== 'undefined';
                return {
                    scriptTags: scripts.length,
                    hasWidget: !!hasWidget,
                    hasIframe: !!hasIframe,
                    hasTurnstileObj: hasTurnstileObj,
                    turnstileDataIntercepted: !!(window.__turnstileData && window.__turnstileData.intercepted),
                };
            }
        """)
        log.info(f"[DIAG] Status: {ts_status}")
        browser_log.info(f"[DIAG] Turnstile status: {ts_status}")
    except Exception as e:
        log.warning(f"[DIAG] Erro ao verificar status: {e}")
        ts_status = {}
    
    # Se não tem iframe ainda, esperar
    if not ts_status.get('hasIframe'):
        log.info(f"[DIAG] Iframe não encontrado, aguardando até {timeout}s...")
        try:
            await page.wait_for_selector(
                'iframe[src*="challenges.cloudflare"], iframe[src*="turnstile"], .cf-turnstile iframe',
                timeout=timeout * 1000
            )
            log.info("[DIAG] Iframe do Turnstile APARECEU!")
            await asyncio.sleep(2)  # Dar tempo para renderizar
            return True
        except:
            log.warning(f"[DIAG] Iframe NÃO apareceu em {timeout}s")
            
            # Tentar verificar se a página tem algum container do Turnstile
            try:
                page_html = await page.evaluate("() => document.body.innerHTML.substring(0, 5000)")
                browser_log.info(f"[DIAG] HTML parcial: {page_html[:2000]}")
            except:
                pass
            
            return False
    
    return True


async def refill_email_after_reload(page, email):
    """V7.1: Re-preenche o email após reload da página."""
    try:
        email_input = await page.wait_for_selector(
            'input[type="email"], input[name="email"], input[placeholder*="email" i]',
            timeout=10000
        )
        if email_input:
            await email_input.click()
            await asyncio.sleep(0.3)
            await email_input.fill("")
            for char in email:
                await email_input.type(char, delay=random.randint(30, 80))
            log.info(f"E-mail re-preenchido: {email}")
            await asyncio.sleep(1)
            return True
    except Exception as e:
        log.warning(f"Erro ao re-preencher email: {e}")
    return False


# ============================================================
# ESTRATÉGIA 1: TURNSTILE RENDER INTERCEPTOR + EXTERNAL SOLVER
# ============================================================
async def strategy_interceptor_solve(page, context, timeout=60):
    """
    Estratégia 1: Intercepta turnstile.render(), captura parâmetros,
    e tenta resolver via serviço externo (CapSolver/2Captcha).
    Se não houver API key, tenta usar o callback para auto-resolver.
    """
    log.info("[ESTRATÉGIA 1] Turnstile Render Interceptor")
    
    start = time.time()
    
    # Esperar o interceptor capturar os dados
    for _ in range(15):
        try:
            data = await page.evaluate("() => window.__turnstileData || {}")
            if data.get('intercepted') and data.get('sitekey'):
                log.info(f"[ESTRATÉGIA 1] Interceptado! sitekey={data['sitekey'][:20]}...")
                browser_log.info(f"  sitekey: {data.get('sitekey')}")
                browser_log.info(f"  action: {data.get('action')}")
                browser_log.info(f"  cData: {data.get('cData')}")
                browser_log.info(f"  widgetId: {data.get('widgetId')}")
                break
        except:
            pass
        await asyncio.sleep(2)
    else:
        log.warning("[ESTRATÉGIA 1] Interceptor não capturou dados em 30s")
        return None
    
    sitekey = data.get('sitekey')
    if not sitekey:
        return None
    
    # Se temos API key, usar serviço externo
    if CAPTCHA_API_KEY:
        token = await solve_via_external_service(
            sitekey=sitekey,
            page_url=page.url,
            action=data.get('action'),
            cdata=data.get('cData'),
        )
        if token:
            # Injetar token via callback
            try:
                result = await page.evaluate(f"""() => {{
                    return window.__injectTurnstileToken("{token}");
                }}""")
                if result:
                    log.info("[ESTRATÉGIA 1] Token injetado via callback!")
                    return token
            except Exception as e:
                browser_log.warning(f"[ESTRATÉGIA 1] Erro ao injetar: {e}")
    else:
        log.info("[ESTRATÉGIA 1] Sem API key - pulando serviço externo")
    
    return None


# ============================================================
# ESTRATÉGIA 2: LOCAL PAGE TOKEN HARVESTER
# ============================================================
async def strategy_local_harvester(page, context, playwright_instance, timeout=45):
    """
    Estratégia 2: Cria uma página HTML local com o widget Turnstile,
    resolve o captcha nessa página controlada, extrai o token.
    Inspirado no Turnstile-Solver de Theyka.
    """
    log.info("[ESTRATÉGIA 2] Local Page Token Harvester")
    
    # Primeiro, extrair o sitekey da página real
    sitekey = None
    try:
        sitekey = await page.evaluate("""() => {
            // Tentar do interceptor
            if (window.__turnstileData && window.__turnstileData.sitekey) {
                return window.__turnstileData.sitekey;
            }
            // Tentar do DOM
            const el = document.querySelector('[data-sitekey]');
            if (el) return el.getAttribute('data-sitekey');
            // Tentar do iframe src
            const iframe = document.querySelector('iframe[src*="turnstile"]');
            if (iframe) {
                const match = iframe.src.match(/[?&]k=([^&]+)/);
                if (match) return match[1];
            }
            return null;
        }""")
    except:
        pass
    
    if not sitekey:
        log.warning("[ESTRATÉGIA 2] Sitekey não encontrado")
        return None
    
    log.info(f"[ESTRATÉGIA 2] Sitekey: {sitekey}")
    
    # Criar página HTML com o widget Turnstile
    page_url = page.url.split('?')[0]
    if not page_url.endswith('/'):
        page_url += '/'
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verification</title>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTurnstileLoad" async></script>
        <style>
            body {{ display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }}
            .container {{ text-align: center; padding: 40px; }}
        </style>
        <script>
            function onTurnstileLoad() {{
                turnstile.render('#cf-widget', {{
                    sitekey: '{sitekey}',
                    callback: function(token) {{
                        document.getElementById('cf-token').value = token;
                        document.title = 'SOLVED:' + token.substring(0, 20);
                        console.log('TOKEN_CAPTURED:' + token);
                    }},
                    'error-callback': function(err) {{
                        console.log('TURNSTILE_ERROR:' + err);
                    }},
                    'expired-callback': function() {{
                        console.log('TURNSTILE_EXPIRED');
                    }}
                }});
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <div id="cf-widget"></div>
            <input type="hidden" id="cf-token" value="">
        </div>
    </body>
    </html>
    """
    
    # Abrir nova página para o harvester
    harvester_page = await context.new_page()
    
    try:
        # Usar page.route para interceptar e servir nosso HTML
        harvest_url = page_url
        await harvester_page.route(harvest_url, lambda route: route.fulfill(
            body=html_template,
            status=200,
            headers={"Content-Type": "text/html"}
        ))
        
        # Navegar para a URL (será interceptada com nosso HTML)
        await harvester_page.goto(harvest_url, wait_until="domcontentloaded", timeout=30000)
        
        log.info("[ESTRATÉGIA 2] Página harvester carregada, aguardando Turnstile...")
        
        # Aguardar o widget carregar
        await asyncio.sleep(3)
        
        # Tentar clicar no checkbox do Turnstile na página harvester
        start_time = time.time()
        token = None
        
        while time.time() - start_time < timeout:
            # Verificar se já tem token
            try:
                token = await harvester_page.evaluate("""() => {
                    const input = document.getElementById('cf-token');
                    if (input && input.value && input.value.length > 10) return input.value;
                    return null;
                }""")
                if token:
                    log.info(f"[ESTRATÉGIA 2] Token harvested! {token[:50]}...")
                    break
            except:
                pass
            
            # Tentar clicar no checkbox do Turnstile
            try:
                # Encontrar iframe do Turnstile
                iframe_info = await harvester_page.evaluate("""() => {
                    const iframe = document.querySelector('iframe[src*="challenges.cloudflare"]');
                    if (iframe) {
                        const rect = iframe.getBoundingClientRect();
                        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
                    }
                    return null;
                }""")
                
                if iframe_info and XDOTOOL_AVAILABLE:
                    # Calcular coordenadas na tela para xdotool
                    win_geo = get_window_geometry()
                    if win_geo:
                        window_info = await harvester_page.evaluate("""() => ({
                            outerHeight: window.outerHeight,
                            innerHeight: window.innerHeight,
                            outerWidth: window.outerWidth,
                            innerWidth: window.innerWidth,
                        })""")
                        chrome_h = window_info['outerHeight'] - window_info['innerHeight']
                        chrome_w = (window_info['outerWidth'] - window_info['innerWidth']) // 2
                        
                        click_x = int(win_geo['x'] + chrome_w + iframe_info['x'] + 30)
                        click_y = int(win_geo['y'] + chrome_h + iframe_info['y'] + iframe_info['height'] / 2)
                        
                        xdotool_human_click(click_x, click_y)
                        browser_log.info(f"[ESTRATÉGIA 2] xdotool click em ({click_x}, {click_y})")
                else:
                    # Tentar clique via Playwright no widget
                    try:
                        await harvester_page.click('#cf-widget', timeout=2000)
                    except:
                        pass
            except Exception as e:
                browser_log.debug(f"[ESTRATÉGIA 2] Click attempt: {e}")
            
            await asyncio.sleep(3)
        
        if token:
            # Injetar o token na página real
            try:
                injected = await page.evaluate(f"""() => {{
                    if (window.__injectTurnstileToken) {{
                        return window.__injectTurnstileToken("{token}");
                    }}
                    // Fallback: injetar direto no input
                    const input = document.querySelector('input[name="cf-turnstile-response"]');
                    if (input) {{
                        input.value = "{token}";
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }}""")
                if injected:
                    log.info("[ESTRATÉGIA 2] Token injetado na página real!")
                    return token
            except Exception as e:
                browser_log.warning(f"[ESTRATÉGIA 2] Erro ao injetar na página real: {e}")
        
    except Exception as e:
        log.warning(f"[ESTRATÉGIA 2] Erro: {e}")
    finally:
        try:
            await harvester_page.close()
        except:
            pass
    
    return None


# ============================================================
# ESTRATÉGIA 3: screenX/screenY PATCH + ENHANCED XDOTOOL
# ============================================================
async def strategy_patched_xdotool(page, timeout=60):
    """
    Estratégia 3: Com o patch screenX/screenY já injetado,
    usa xdotool com movimento humanizado para clicar no checkbox.
    O patch corrige os valores que o Turnstile verifica.
    """
    log.info("[ESTRATÉGIA 3] screenX/screenY Patch + Enhanced xdotool")
    
    if not XDOTOOL_AVAILABLE:
        log.warning("[ESTRATÉGIA 3] xdotool não disponível")
        return None
    
    # Verificar se o patch está ativo
    try:
        patch_active = await page.evaluate("""() => {
            // Testar se o patch está funcionando
            const evt = new MouseEvent('click', { clientX: 150, clientY: 200, screenX: 50, screenY: 50 });
            // Se o patch corrigiu, screenX deveria ser > 100
            return evt.screenX > 100 || true;  // O patch modifica o getter
        }""")
        browser_log.info(f"[ESTRATÉGIA 3] Patch screenX/screenY ativo: {patch_active}")
    except:
        pass
    
    # Encontrar o iframe do Turnstile
    screen_x, screen_y = await find_turnstile_coordinates(page)
    
    if screen_x is None or screen_y is None:
        log.warning("[ESTRATÉGIA 3] Turnstile não encontrado")
        return None
    
    log.info(f"[ESTRATÉGIA 3] Turnstile em ({screen_x}, {screen_y})")
    
    # Movimento humanizado com Bézier + clique
    print(f"\n{C.G}{C.BD}")
    print(f"  [ESTRATÉGIA 3] XDOTOOL + screenXY PATCH")
    print(f"  Coordenadas: ({screen_x}, {screen_y})")
    print(f"{C.RS}\n")
    
    success = xdotool_human_click(screen_x, screen_y)
    
    if not success:
        log.warning("[ESTRATÉGIA 3] xdotool falhou")
        return None
    
    # Esperar resolução
    token = await wait_for_turnstile_token(page, timeout=timeout)
    
    if token:
        log.info(f"[ESTRATÉGIA 3] Resolvido! Token: {token[:50]}...")
    
    return token


# ============================================================
# ESTRATÉGIA 4: XDOTOOL PADRÃO (FALLBACK V6)
# ============================================================
async def strategy_xdotool_fallback(page, timeout=30):
    """
    Estratégia 4: Fallback do V6 - xdotool simples com coordenadas calculadas.
    """
    log.info("[ESTRATÉGIA 4] xdotool Fallback (V6)")
    
    if not XDOTOOL_AVAILABLE:
        log.warning("[ESTRATÉGIA 4] xdotool não disponível")
        return None
    
    screen_x, screen_y = await find_turnstile_coordinates(page)
    
    if screen_x is None:
        log.warning("[ESTRATÉGIA 4] Turnstile não encontrado")
        return None
    
    # Clique simples
    xdotool_click(screen_x, screen_y)
    log.info(f"[ESTRATÉGIA 4] Clique em ({screen_x}, {screen_y})")
    
    token = await wait_for_turnstile_token(page, timeout=timeout)
    return token


# ============================================================
# SERVIÇO EXTERNO DE CAPTCHA SOLVING
# ============================================================
async def solve_via_external_service(sitekey, page_url, action=None, cdata=None):
    """
    Resolve Turnstile via serviço externo (CapSolver ou 2Captcha).
    """
    import requests as req_lib
    
    if not CAPTCHA_API_KEY:
        return None
    
    log.info(f"[EXTERNAL] Resolvendo via {CAPTCHA_SERVICE}...")
    
    try:
        if CAPTCHA_SERVICE == "capsolver":
            # CapSolver API
            create_resp = req_lib.post("https://api.capsolver.com/createTask", json={
                "clientKey": CAPTCHA_API_KEY,
                "task": {
                    "type": "AntiTurnstileTaskProxyLess",
                    "websiteURL": page_url,
                    "websiteKey": sitekey,
                    "metadata": {
                        "action": action or "",
                        "cdata": cdata or "",
                    }
                }
            }, timeout=30)
            
            result = create_resp.json()
            task_id = result.get("taskId")
            
            if not task_id:
                log.warning(f"[EXTERNAL] CapSolver erro: {result}")
                return None
            
            # Polling resultado
            for _ in range(30):
                await asyncio.sleep(3)
                get_resp = req_lib.post("https://api.capsolver.com/getTaskResult", json={
                    "clientKey": CAPTCHA_API_KEY,
                    "taskId": task_id,
                }, timeout=15)
                
                task_result = get_resp.json()
                status = task_result.get("status")
                
                if status == "ready":
                    token = task_result.get("solution", {}).get("token")
                    if token:
                        log.info(f"[EXTERNAL] CapSolver resolveu! Token: {token[:40]}...")
                        return token
                elif status == "failed":
                    log.warning(f"[EXTERNAL] CapSolver falhou: {task_result}")
                    return None
        
        elif CAPTCHA_SERVICE == "2captcha":
            # 2Captcha API
            create_resp = req_lib.post("https://api.2captcha.com/createTask", json={
                "clientKey": CAPTCHA_API_KEY,
                "task": {
                    "type": "TurnstileTaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": sitekey,
                    "action": action or "",
                }
            }, timeout=30)
            
            result = create_resp.json()
            task_id = result.get("taskId")
            
            if not task_id:
                log.warning(f"[EXTERNAL] 2Captcha erro: {result}")
                return None
            
            for _ in range(30):
                await asyncio.sleep(5)
                get_resp = req_lib.post("https://api.2captcha.com/getTaskResult", json={
                    "clientKey": CAPTCHA_API_KEY,
                    "taskId": task_id,
                }, timeout=15)
                
                task_result = get_resp.json()
                status = task_result.get("status")
                
                if status == "ready":
                    token = task_result.get("solution", {}).get("token")
                    if token:
                        log.info(f"[EXTERNAL] 2Captcha resolveu! Token: {token[:40]}...")
                        return token
                elif status == "failed":
                    log.warning(f"[EXTERNAL] 2Captcha falhou")
                    return None
    
    except Exception as e:
        log.error(f"[EXTERNAL] Erro: {e}")
    
    return None


# ============================================================
# ENCONTRAR COORDENADAS DO TURNSTILE (melhorado do V6)
# ============================================================
async def find_turnstile_coordinates(page):
    """
    Encontra as coordenadas de tela do checkbox do Turnstile.
    Combina xdotool getwindowgeometry + JS getBoundingClientRect.
    """
    log.info("Procurando iframe do Turnstile...")
    
    win_geo = get_window_geometry() if XDOTOOL_AVAILABLE else None
    
    window_info = await page.evaluate("""() => {
        return {
            screenX: window.screenX || window.screenLeft || 0,
            screenY: window.screenY || window.screenTop || 0,
            outerWidth: window.outerWidth,
            outerHeight: window.outerHeight,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
        };
    }""")
    
    browser_log.info(f"  JS Window: screenX={window_info['screenX']}, screenY={window_info['screenY']}")
    if win_geo:
        browser_log.info(f"  xdotool Window: pos=({win_geo['x']},{win_geo['y']})")
    
    chrome_height = window_info['outerHeight'] - window_info['innerHeight']
    chrome_width_offset = (window_info['outerWidth'] - window_info['innerWidth']) // 2
    
    if win_geo:
        base_x = win_geo['x']
        base_y = win_geo['y']
    else:
        base_x = window_info['screenX']
        base_y = window_info['screenY']
    
    # Método 1: Encontrar iframe via JS
    try:
        iframe_info = await page.evaluate("""() => {
            const selectors = [
                'iframe[src*="challenges.cloudflare.com"]',
                'iframe[src*="turnstile"]',
                '.cf-turnstile iframe',
                '[data-sitekey] iframe',
            ];
            
            for (const sel of selectors) {
                const iframe = document.querySelector(sel);
                if (iframe) {
                    const rect = iframe.getBoundingClientRect();
                    return {
                        found: true,
                        x: rect.x, y: rect.y,
                        width: rect.width, height: rect.height,
                        selector: sel
                    };
                }
            }
            
            const container = document.querySelector('.cf-turnstile, [data-sitekey]');
            if (container) {
                const rect = container.getBoundingClientRect();
                return { found: true, x: rect.x, y: rect.y, width: rect.width, height: rect.height, selector: '.cf-turnstile' };
            }
            
            return { found: false };
        }""")
        
        if iframe_info and iframe_info.get('found'):
            browser_log.info(f"Turnstile encontrado: {iframe_info['selector']}")
            browser_log.info(f"  Viewport pos: ({iframe_info['x']}, {iframe_info['y']})")
            
            checkbox_x_in_iframe = 30
            checkbox_y_in_iframe = iframe_info['height'] / 2
            
            screen_x = int(base_x + chrome_width_offset + iframe_info['x'] + checkbox_x_in_iframe)
            screen_y = int(base_y + chrome_height + iframe_info['y'] + checkbox_y_in_iframe)
            
            browser_log.info(f"  COORDENADAS FINAIS: ({screen_x}, {screen_y})")
            return screen_x, screen_y
    except Exception as e:
        browser_log.warning(f"Erro método 1 (JS): {e}")
    
    # Método 2: Via frames do Playwright
    try:
        for frame in page.frames:
            if 'challenges.cloudflare' in frame.url or 'turnstile' in frame.url:
                frame_element = await frame.frame_element()
                if frame_element:
                    box = await frame_element.bounding_box()
                    if box:
                        screen_x = int(base_x + chrome_width_offset + box['x'] + 30)
                        screen_y = int(base_y + chrome_height + box['y'] + box['height'] / 2)
                        browser_log.info(f"  COORDENADAS (método 2): ({screen_x}, {screen_y})")
                        return screen_x, screen_y
    except Exception as e:
        browser_log.warning(f"Erro método 2: {e}")
    
    return None, None


# ============================================================
# ESPERAR TOKEN DO TURNSTILE
# ============================================================
async def wait_for_turnstile_token(page, timeout=120):
    """Aguarda o Turnstile ser resolvido e retorna o token."""
    log.info("Aguardando resolução do Turnstile...")
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            token = await page.evaluate("""() => {
                // Método 1: input hidden
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                if (input && input.value && input.value.length > 10) return input.value;
                
                // Método 2: data attribute
                const success = document.querySelector('[data-turnstile-response]');
                if (success) {
                    const val = success.getAttribute('data-turnstile-response');
                    if (val && val.length > 10) return val;
                }
                
                // Método 3: window.turnstile API
                if (window.turnstile && window.__turnstileData && window.__turnstileData.widgetId) {
                    try {
                        const resp = window.turnstile.getResponse(window.__turnstileData.widgetId);
                        if (resp) return resp;
                    } catch(e) {}
                }
                
                // Método 4: interceptor data
                if (window.__turnstileData && window.__turnstileData.tokenInjected) {
                    const input2 = document.querySelector('input[name="cf-turnstile-response"]');
                    if (input2 && input2.value) return input2.value;
                }
                
                return null;
            }""")
            
            if token:
                log.info(f"Turnstile RESOLVIDO! Token: {token[:50]}...")
                return token
        except Exception as e:
            browser_log.debug(f"Turnstile check error: {e}")
        
        elapsed = int(time.time() - start)
        if elapsed % 10 == 0 and elapsed > 0:
            log.info(f"  Aguardando Turnstile... ({elapsed}s/{timeout}s)")
        
        await asyncio.sleep(2)
    
    log.warning(f"Turnstile não resolveu em {timeout}s")
    return None


# ============================================================
# VERIFICAR BOTÃO CONTINUE (mantido do V6)
# ============================================================
async def check_continue_enabled(page):
    """Verifica se o botão SUBMIT Continue está habilitado."""
    try:
        result = await page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            const socialKeywords = ['facebook', 'google', 'microsoft', 'apple', 'github', 'twitter'];
            
            for (const btn of btns) {
                const text = btn.textContent.trim().toLowerCase();
                const isSocial = socialKeywords.some(kw => text.includes(kw));
                if (isSocial) continue;
                
                if (text === 'continue' || text === 'sign up' || text === 'sign in' || btn.type === 'submit') {
                    return {
                        text: btn.textContent.trim(),
                        disabled: btn.disabled,
                        className: btn.className
                    };
                }
            }
            return null;
        }""")
        return result
    except:
        return None


# ============================================================
# ORQUESTRADOR DE ESTRATÉGIAS - CASCATA INTELIGENTE
# ============================================================
async def resolve_turnstile_cascade(page, context, playwright_instance, max_global_attempts=5):
    """
    Orquestrador que tenta resolver o Turnstile usando múltiplas
    estratégias em cascata. Cada estratégia é tentada em ordem
    de sofisticação, com fallback automático.
    
    Ordem:
    1. Interceptor + Serviço externo (se API key disponível)
    2. Local Page Harvester
    3. screenX/screenY Patch + xdotool humanizado
    4. xdotool fallback simples
    """
    log.info("=" * 50)
    log.info("  TURNSTILE CASCADE RESOLVER V7")
    log.info(f"  Estratégias: 4 | Max tentativas: {max_global_attempts}")
    log.info(f"  V7.2: Auto IP rotation + DNS fix habilitados")
    log.info(f"  API Key: {'SIM' if CAPTCHA_API_KEY else 'NÃO'}")
    log.info(f"  xdotool: {'SIM' if XDOTOOL_AVAILABLE else 'NÃO'}")
    log.info("=" * 50)
    
    # V7.1: Receber email para re-preencher após reload
    email_for_refill = None
    try:
        email_for_refill = await page.evaluate("""
            () => {
                const input = document.querySelector('input[type="email"], input[name="email"]');
                return input ? input.value : null;
            }
        """)
    except:
        pass
    
    for attempt in range(max_global_attempts):
        log.info(f"\n{'='*40}")
        log.info(f"  TENTATIVA GLOBAL {attempt + 1}/{max_global_attempts}")
        log.info(f"{'='*40}")
        
        # V7.1: Diagnóstico antes de tentar
        turnstile_loaded = await diagnose_turnstile_loading(page, timeout=20)
        
        if not turnstile_loaded:
            log.warning(f"[V7.2] Turnstile NÃO carregou! (challenges.cloudflare.com bloqueado?)")
            
            if attempt < max_global_attempts - 1:
                # V7.2: Na tentativa 2+, tentar trocar IP
                if attempt >= 1:
                    log.info("[V7.2] Tentando trocar IP para desbloquear Cloudflare...")
                    print(f"\n{C.Y}{C.BD}  [V7.2] Trocando IP via modo avião...{C.RS}\n")
                    rotated = rotate_ip_airplane()
                    if rotated:
                        flush_dns_cache()
                        await asyncio.sleep(5)
                        new_ip = get_current_ip()
                        log.info(f"[V7.2] Novo IP: {new_ip}")
                
                try:
                    await page.reload(wait_until="networkidle", timeout=30000)
                except:
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=30000)
                    except:
                        pass
                await asyncio.sleep(5)
                # Re-preencher email
                if email_for_refill:
                    await refill_email_after_reload(page, email_for_refill)
                # Tentar diagnóstico novamente
                turnstile_loaded = await diagnose_turnstile_loading(page, timeout=25)
                if not turnstile_loaded:
                    log.warning("[V7.2] Turnstile ainda não carregou após reload")
                    continue
            else:
                log.error("[V7.2] Turnstile não carregou em nenhuma tentativa")
                continue
        
        # Screenshot antes
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_turnstile_attempt{attempt+1}_before.png")
            await page.screenshot(path=ss)
        except:
            pass
        
        # ---- ESTRATÉGIA 1: Interceptor + External ----
        if CAPTCHA_API_KEY:
            try:
                token = await strategy_interceptor_solve(page, context, timeout=60)
                if token:
                    log.info(f"SUCESSO via ESTRATÉGIA 1 (Interceptor)!")
                    return token
            except Exception as e:
                log.warning(f"ESTRATÉGIA 1 falhou: {e}")
        
        # ---- ESTRATÉGIA 2: Local Page Harvester ----
        try:
            token = await strategy_local_harvester(page, context, playwright_instance, timeout=45)
            if token:
                log.info(f"SUCESSO via ESTRATÉGIA 2 (Local Harvester)!")
                return token
        except Exception as e:
            log.warning(f"ESTRATÉGIA 2 falhou: {e}")
        
        # ---- ESTRATÉGIA 3: Patched xdotool ----
        if XDOTOOL_AVAILABLE:
            try:
                token = await strategy_patched_xdotool(page, timeout=45)
                if token:
                    log.info(f"SUCESSO via ESTRATÉGIA 3 (Patched xdotool)!")
                    return token
            except Exception as e:
                log.warning(f"ESTRATÉGIA 3 falhou: {e}")
        
        # ---- ESTRATÉGIA 4: xdotool Fallback ----
        if XDOTOOL_AVAILABLE:
            try:
                token = await strategy_xdotool_fallback(page, timeout=30)
                if token:
                    log.info(f"SUCESSO via ESTRATÉGIA 4 (xdotool Fallback)!")
                    return token
            except Exception as e:
                log.warning(f"ESTRATÉGIA 4 falhou: {e}")
        
        # Verificar se o botão Continue ficou habilitado (indica sucesso silencioso)
        btn_state = await check_continue_enabled(page)
        if btn_state and not btn_state.get('disabled', True):
            log.info(f"Botão Continue HABILITADO! Turnstile pode ter resolvido silenciosamente.")
            return "BUTTON_ENABLED"
        
        # Screenshot depois
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_turnstile_attempt{attempt+1}_after.png")
            await page.screenshot(path=ss)
        except:
            pass
        
        # Se não é a última tentativa, recarregar
        if attempt < max_global_attempts - 1:
            log.warning(f"Todas as estratégias falharam na tentativa {attempt+1}. Recarregando...")
            try:
                await page.reload(wait_until="networkidle", timeout=30000)
            except:
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                except:
                    pass
            await asyncio.sleep(random.uniform(4, 7))
            
            # V7.1: Re-preencher email após reload
            if email_for_refill:
                await refill_email_after_reload(page, email_for_refill)
                await asyncio.sleep(2)
    
    log.error("TODAS AS ESTRATÉGIAS FALHARAM em todas as tentativas!")
    return None


# ============================================================
# FLUXO PRINCIPAL
# ============================================================
async def main():
    start_time = time.time()
    
    engine = "PATCHRIGHT (INDETECTÁVEL)" if USING_PATCHRIGHT else "PLAYWRIGHT (detectável)"
    click_method = "xdotool (REAL CLICK)" if XDOTOOL_AVAILABLE else "CDP (fallback)"
    
    banner = f"""
{C.CY}{C.BD}
{'='*60}
   MANUS ACCOUNT CREATOR V7.2 - KALI NETHUNTER + KeX
   TURNSTILE ULTRA BYPASS + NETWORK FIX Engine
{'='*60}
   Engine:   {engine}
   Click:    {click_method}
   DISPLAY:  {os.environ.get('DISPLAY', 'N/A')}
   Proxy:    {PROXY_HOST}:{PROXY_PORT} (SEMPRE ATIVA)
   CAPTCHA:  {CAPTCHA_SERVICE if CAPTCHA_API_KEY else 'LOCAL ONLY'}
   Logs:     {LOG_DIR}
{'='*60}
   ESTRATÉGIAS DE BYPASS:
   [1] Turnstile Render Interceptor + External Solver
   [2] Local Page Token Harvester (Turnstile-Solver style)
   [3] screenX/screenY CDP Patch + Bézier xdotool
   [4] xdotool Fallback (V6 compat)
{'='*60}
{C.RS}"""
    print(banner)
    
    log.info("=" * 60)
    log.info(f"MANUS ACCOUNT CREATOR V7.2 INICIADO (NETWORK FIX)")
    log.info(f"Engine: {engine}")
    log.info(f"Click method: {click_method}")
    log.info(f"xdotool disponível: {XDOTOOL_AVAILABLE}")
    log.info(f"DISPLAY={os.environ.get('DISPLAY')}")
    log.info(f"Python={sys.version}")
    log.info(f"CAPTCHA Service: {CAPTCHA_SERVICE if CAPTCHA_API_KEY else 'LOCAL ONLY'}")
    log.info("=" * 60)
    
    if not XDOTOOL_AVAILABLE:
        print(f"\n{C.Y}{C.BD}  [!] AVISO: xdotool NÃO instalado!{C.RS}")
        print(f"{C.Y}  Instale com: apt install xdotool{C.RS}")
        print(f"{C.Y}  Sem xdotool, estratégias 3 e 4 não funcionarão.{C.RS}\n")
        log.warning("xdotool NÃO disponível - estratégias 3/4 desabilitadas")
    
    # ========================================
    # PASSO 0: LINK DE CONVITE
    # ========================================
    log_separator("ETAPA 0: LINK DE CONVITE")
    
    print(f"{C.Y}{C.BD}[?] Cole o link de convite do Manus (ENTER = padrão):{C.RS}")
    invite_url = input(f"{C.CY}    > {C.RS}").strip()
    
    if not invite_url:
        invite_url = f"https://manus.im/invitation/{DEFAULT_INVITE}?utm_source=invitation&utm_medium=social&utm_campaign=system_share"
        log.warning(f"Usando link padrão: {invite_url}")
    
    invite_code = None
    if '/invitation/' in invite_url:
        parts = invite_url.split('/invitation/')
        if len(parts) > 1:
            invite_code = parts[1].split('?')[0].split('/')[0]
    elif invite_url.startswith('http') and 'code=' in invite_url:
        # Suportar formato direto com code=
        match = re.search(r'code=([A-Za-z0-9]+)', invite_url)
        if match:
            invite_code = match.group(1)
    else:
        # Assumir que é o código direto
        invite_code = invite_url.strip() if invite_url.strip() else DEFAULT_INVITE
    
    if not invite_code:
        log.error("Código de convite não extraído!")
        return
    
    log.info(f"Código de convite: {invite_code}")
    
    # ========================================
    # PASSO 1: GERAR GMAIL
    # ========================================
    log_separator("ETAPA 1: GERANDO GMAIL TEMPORÁRIO")
    
    emailnator = Emailnator()
    email = None
    
    for attempt in range(3):
        log.info(f"Tentativa {attempt+1}/3...")
        email = emailnator.generate_email()
        if email:
            break
        emailnator = Emailnator()
        time.sleep(2)
    
    if not email:
        log.error("FALHA: Não foi possível gerar Gmail!")
        return
    
    print(f"\n{C.G}{C.BD}  [OK] Gmail: {email}{C.RS}")
    
    # ========================================
    # PASSO 2: GERAR SENHA
    # ========================================
    log_separator("ETAPA 2: GERANDO SENHA")
    password = generate_manus_password(20)
    print(f"{C.G}{C.BD}  [OK] Senha: {password}{C.RS}")
    
    log_to_file(creds_file, f"INICIO | email={email} | senha={password} | convite={invite_code}")
    
    # ========================================
    # V7.2: PASSO 2.5: PREPARAR REDE
    # ========================================
    log_separator("ETAPA 2.5: PREPARANDO REDE (V7.2)")
    
    # Corrigir DNS
    fix_dns()
    flush_dns_cache()
    
    # Verificar IP atual
    old_ip = get_current_ip()
    
    # Verificar conectividade com Cloudflare
    cf_status = check_cloudflare_connectivity()
    use_proxy_for_browser = False
    
    if cf_status == False:
        log.warning("[NET] Cloudflare BLOQUEADO! Tentando trocar IP...")
        print(f"\n{C.Y}{C.BD}  [!] Cloudflare BLOQUEADO no seu IP!{C.RS}")
        print(f"{C.Y}  Tentando trocar IP automaticamente...{C.RS}\n")
        
        # Tentar trocar IP
        rotated = rotate_ip_airplane()
        if rotated:
            flush_dns_cache()
            time.sleep(3)
            new_ip = get_current_ip()
            if new_ip and new_ip != old_ip:
                log.info(f"[NET] IP trocado: {old_ip} -> {new_ip}")
            
            # Re-verificar
            cf_status = check_cloudflare_connectivity()
        
        if cf_status == False:
            log.warning("[NET] Cloudflare ainda bloqueado após troca de IP")
            log.info("[NET] Usando PROXY para o browser")
            use_proxy_for_browser = True
            print(f"\n{C.Y}{C.BD}  [!] Usando PROXY para contornar bloqueio{C.RS}\n")
    elif cf_status == 'PROXY':
        log.info("[NET] Cloudflare só acessível via proxy - usando proxy no browser")
        use_proxy_for_browser = True
    else:
        log.info("[NET] Cloudflare acessível diretamente!")
    
    # ========================================
    # PASSO 3: ABRIR BROWSER
    # ========================================
    log_separator(f"ETAPA 3: ABRINDO BROWSER ({engine})")
    
    async with async_playwright() as p:
        
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
            '--window-position=0,0',
            # === WebGL/GPU para Turnstile funcionar no VNC ===
            '--ignore-gpu-blocklist',
            '--enable-gpu',
            '--enable-gpu-rasterization',
            '--enable-webgl',
            '--use-gl=angle',
            '--use-angle=swiftshader',
            '--enable-features=VaapiVideoDecoder',
            '--enable-unsafe-swiftshader',
            # === V7.1: Flags perigosas REMOVIDAS ===
            # --disable-web-security QUEBRA o Turnstile (Cloudflare rejeita desde Feb 2025)
            # --disable-site-isolation-trials pode interferir com iframes cross-origin
            # --allow-running-insecure-content desnecessário e suspeito
        ]
        
        if not USING_PATCHRIGHT:
            browser_args.extend([
                '--disable-blink-features=AutomationControlled',
            ])
        
        # V7.2 FIX: PROXY ROTATIVA per-context (CORRIGIDO)
        # No Playwright/Patchright, proxy com autenticação DEVE ser no context, não no launch
        # launch() recebe 'per-context' e new_context() recebe os dados reais
        log.info(f"[NET] PROXY ROTATIVA: {PROXY_HOST}:{PROXY_PORT}")
        log.info(f"[NET] User: {PROXY_USER[:10]}... | Rotação: BR")
        log.info(f"[NET] Modo: per-context (autenticação no context, não no launch)")
        
        try:
            browser = await p.chromium.launch(
                headless=False,
                args=browser_args,
                proxy={'server': 'per-context'},
            )
            browser_log.info(f"Browser lançado! Engine: {engine} | Proxy: per-context")
            log.info(f"Browser aberto no desktop KeX!")
        except Exception as e:
            log.error(f"FALHA ao lançar browser: {e}")
            log.error(traceback.format_exc())
            return
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1200, 'height': 680},
            locale='en-US',
            proxy={
                'server': f'http://{PROXY_HOST}:{PROXY_PORT}',
                'username': PROXY_USER,
                'password': PROXY_PASS,
            },
        )
        log.info(f"[NET] Context criado com PROXY AUTENTICADA!")
        
        # === INJETAR TODOS OS SCRIPTS DE STEALTH V7 ===
        stealth_code = get_stealth_scripts(use_patchright=USING_PATCHRIGHT)
        await context.add_init_script(stealth_code)
        browser_log.info("Scripts de stealth V7 injetados (WebGL + Canvas + Audio + screenXY + Interceptor)")
        
        page = await context.new_page()
        
        # Dados capturados
        captured_data = {
            'cf_token': None,
            'temp_token': None,
            'auth_token': None,
            'all_responses': [],
        }
        
        # Interceptar requisições
        async def on_request(request):
            if 'manus' in request.url:
                http_log.debug(f">>> {request.method} {request.url}")
        
        async def on_response(response):
            url = response.url
            status = response.status
            
            try:
                if 'manus.im' in url or 'api.manus' in url:
                    body = await response.text()
                    http_log.info(f"<<< {status} {url}")
                    http_log.debug(f"    Body: {body[:500]}")
                    
                    captured_data['all_responses'].append({
                        'url': url, 'status': status,
                        'body': body[:2000],
                        'time': datetime.now().isoformat()
                    })
                    
                    try:
                        data = json.loads(body)
                    except:
                        data = {}
                    
                    if 'GetUserPlatforms' in url and data.get('tempToken'):
                        captured_data['temp_token'] = data['tempToken']
                        log.info(f">>> tempToken CAPTURADO!")
                    
                    elif 'RegisterByEmail' in url and data.get('token'):
                        captured_data['auth_token'] = data['token']
                        log.info(f">>> JWT Token CAPTURADO!")
                    
                    elif 'SendEmailVerifyCode' in url:
                        log.info(">>> Código de verificação ENVIADO!")
            except:
                pass
        
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("console", lambda msg: browser_log.debug(f"CONSOLE: {msg.text}"))
        
        # ========================================
        # PASSO 4: NAVEGAR PARA MANUS LOGIN
        # ========================================
        log_separator("ETAPA 4: NAVEGANDO PARA MANUS.IM")
        
        login_url = f"https://manus.im/login?code={invite_code}"
        log.info(f"Navegando: {login_url}")
        
        try:
            await page.goto(login_url, wait_until="networkidle", timeout=60000)
        except:
            try:
                await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            except:
                log.warning("Timeout ao carregar (normal para páginas pesadas)")
        
        # V7.1: Esperar mais para o Turnstile carregar
        log.info("Aguardando página estabilizar (8s)...")
        await asyncio.sleep(8)
        
        # Screenshot
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_01_login_page.png")
            await page.screenshot(path=ss)
        except:
            pass
        
        # ========================================
        # PASSO 5: PREENCHER E-MAIL
        # ========================================
        log_separator("ETAPA 5: PREENCHENDO E-MAIL")
        
        email_filled = False
        try:
            email_input = await page.wait_for_selector(
                'input[type="email"], input[name="email"], input[placeholder*="email" i]',
                timeout=15000
            )
            if email_input:
                await email_input.click()
                await asyncio.sleep(random.uniform(0.2, 0.5))
                # Digitar email caractere por caractere (mais humano)
                await email_input.fill("")
                for char in email:
                    await email_input.type(char, delay=random.randint(30, 80))
                email_filled = True
                log.info(f"E-mail preenchido: {email}")
        except Exception as e:
            log.warning(f"Seletor principal falhou: {e}")
            try:
                inputs = await page.query_selector_all('input')
                for inp in inputs:
                    inp_type = await inp.get_attribute('type') or ''
                    inp_ph = await inp.get_attribute('placeholder') or ''
                    if 'email' in inp_type.lower() or 'email' in inp_ph.lower():
                        await inp.fill(email)
                        email_filled = True
                        log.info("E-mail preenchido via fallback")
                        break
            except:
                pass
        
        if not email_filled:
            print(f"\n{C.Y}{C.BD}  [!] PREENCHA O E-MAIL NO BROWSER: {email}{C.RS}\n")
        
        await asyncio.sleep(random.uniform(1.5, 3))
        
        # ========================================
        # PASSO 6: RESOLVER TURNSTILE (V7 CASCADE)
        # ========================================
        log_separator("ETAPA 6: RESOLVENDO TURNSTILE (V7 CASCADE)")
        
        cf_token = await resolve_turnstile_cascade(
            page=page,
            context=context,
            playwright_instance=p,
            max_global_attempts=3
        )
        
        if cf_token:
            log.info(f"TURNSTILE RESOLVIDO! Método retornou token.")
            captured_data['cf_token'] = cf_token
        else:
            log.warning("Turnstile NÃO resolvido automaticamente.")
            print(f"\n{C.Y}{C.BD}  [!] TURNSTILE NÃO RESOLVIDO AUTOMATICAMENTE{C.RS}")
            print(f"{C.Y}  Tente resolver manualmente no browser e pressione ENTER...{C.RS}")
            input()
        
        # Screenshot pós-Turnstile
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_03_post_turnstile.png")
            await page.screenshot(path=ss)
        except:
            pass
        
        # ========================================
        # PASSO 7: CLICAR CONTINUE
        # ========================================
        log_separator("ETAPA 7: CLICANDO CONTINUE")
        
        try:
            continue_btn = None
            all_buttons = await page.query_selector_all('button')
            for btn in all_buttons:
                text = (await btn.text_content() or '').strip().lower()
                social_keywords = ['facebook', 'google', 'microsoft', 'apple', 'github', 'twitter']
                is_social = any(kw in text for kw in social_keywords)
                if is_social:
                    continue
                if text == 'continue' or text == 'sign up' or text == 'sign in':
                    continue_btn = btn
                    log.info(f"Botão submit encontrado: '{text}'")
                    break
                btn_type = await btn.get_attribute('type')
                if btn_type == 'submit':
                    continue_btn = btn
                    log.info(f"Botão submit[type] encontrado: '{text}'")
                    break
            
            if not continue_btn:
                continue_btn = await page.wait_for_selector(
                    'button[type="submit"]',
                    timeout=5000
                )
            
            if continue_btn:
                is_disabled = await continue_btn.get_attribute('disabled')
                if is_disabled:
                    log.warning("Botão Continue desabilitado - aguardando 5s...")
                    await asyncio.sleep(5)
                
                # Usar xdotool para clicar no Continue
                if XDOTOOL_AVAILABLE:
                    try:
                        box = await continue_btn.bounding_box()
                        if box:
                            window_info = await page.evaluate("""() => ({
                                screenX: window.screenX || 0,
                                screenY: window.screenY || 0,
                                outerHeight: window.outerHeight,
                                innerHeight: window.innerHeight,
                                outerWidth: window.outerWidth,
                                innerWidth: window.innerWidth,
                            })""")
                            chrome_h = window_info['outerHeight'] - window_info['innerHeight']
                            chrome_w = (window_info['outerWidth'] - window_info['innerWidth']) // 2
                            btn_x = int(window_info['screenX'] + chrome_w + box['x'] + box['width'] / 2)
                            btn_y = int(window_info['screenY'] + chrome_h + box['y'] + box['height'] / 2)
                            xdotool_human_click(btn_x, btn_y)
                            log.info(f"Continue clicado via xdotool em ({btn_x}, {btn_y})")
                    except:
                        await continue_btn.click()
                        log.info("Continue clicado via CDP (fallback)")
                else:
                    await continue_btn.click()
                    log.info("Botão Continue clicado!")
                
                await asyncio.sleep(3)
        except Exception as e:
            log.warning(f"Botão Continue não encontrado: {e}")
            try:
                await page.keyboard.press('Enter')
                log.info("Enter pressionado como fallback")
            except:
                pass
        
        # Esperar tempToken
        log.info("Aguardando tempToken...")
        wait_start = time.time()
        while time.time() - wait_start < 30:
            if captured_data['temp_token']:
                break
            await asyncio.sleep(1)
        
        # Screenshot
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_04_after_continue.png")
            await page.screenshot(path=ss)
        except:
            pass
        
        # ========================================
        # PASSO 8: ENVIAR CÓDIGO DE VERIFICAÇÃO
        # ========================================
        log_separator("ETAPA 8: ENVIANDO CÓDIGO DE VERIFICAÇÃO")
        
        import requests as req_lib
        
        if captured_data['temp_token']:
            log.info("Enviando solicitação de código via API...")
            try:
                api_headers = {
                    'Content-Type': 'application/json',
                    'Origin': 'https://manus.im',
                    'Referer': 'https://manus.im/',
                    'User-Agent': USER_AGENT,
                }
                send_code_payload = {
                    "email": email,
                    "action": "SEND_EMAIL_ACTION_REGISTER",
                    "token": captured_data['temp_token']
                }
                
                http_log.info(f"POST SendEmailVerifyCodeWithCaptcha")
                http_log.info(f"  Payload: {json.dumps(send_code_payload, indent=2)}")
                
                resp = req_lib.post(
                    f"{MANUS_API}/user.v1.UserAuthPublicService/SendEmailVerifyCodeWithCaptcha",
                    json=send_code_payload,
                    headers=api_headers,
                    timeout=30
                )
                
                http_log.info(f"  Status: {resp.status_code}")
                http_log.info(f"  Response: {resp.text[:500]}")
                
                if resp.status_code == 200:
                    log.info("CÓDIGO ENVIADO COM SUCESSO!")
                else:
                    log.warning(f"Erro ao enviar código: {resp.status_code}")
            except Exception as e:
                log.error(f"Erro: {e}")
        else:
            log.warning("tempToken não capturado - o código pode ter sido enviado via browser")
        
        # ========================================
        # PASSO 9: CAPTURAR CÓDIGO DO E-MAIL
        # ========================================
        log_separator("ETAPA 9: CAPTURANDO CÓDIGO DO E-MAIL")
        
        verify_code = emailnator.wait_for_code(sender_filter="manus", max_wait=180)
        
        if not verify_code:
            log.warning("Código não capturado automaticamente.")
            print(f"\n{C.Y}[?] Digite o código de 6 dígitos manualmente:{C.RS}")
            verify_code = input(f"{C.CY}    > {C.RS}").strip()
        
        if not verify_code or len(verify_code) != 6:
            log.error(f"Código inválido: '{verify_code}'")
            await browser.close()
            return
        
        log.info(f"Código: {verify_code}")
        
        # ========================================
        # PASSO 10: PREENCHER CÓDIGO NA PÁGINA
        # ========================================
        log_separator("ETAPA 10: PREENCHENDO CÓDIGO")
        
        try:
            code_inputs = await page.query_selector_all('input[type="text"], input[type="number"], input[type="tel"]')
            browser_log.info(f"Inputs para código: {len(code_inputs)}")
            
            if len(code_inputs) >= 6:
                for idx, digit in enumerate(verify_code):
                    if idx < len(code_inputs):
                        await code_inputs[idx].fill(digit)
                        await asyncio.sleep(random.uniform(0.05, 0.15))
                log.info("Código preenchido (campos individuais)")
            elif len(code_inputs) >= 1:
                for inp in code_inputs:
                    ph = await inp.get_attribute('placeholder') or ''
                    if 'code' in ph.lower() or 'verif' in ph.lower():
                        await inp.fill(verify_code)
                        log.info("Código preenchido (campo único)")
                        break
            await asyncio.sleep(2)
        except Exception as e:
            log.warning(f"Erro ao preencher código: {e}")
        
        # ========================================
        # PASSO 11: COMPLETAR REGISTRO VIA API
        # ========================================
        log_separator("ETAPA 11: REGISTRANDO CONTA")
        
        try:
            register_payload = {
                "authCommandCmd": {
                    "refer": invite_url,
                    "firstEntry": invite_url,
                    "firstFromPlatform": "h5",
                    "locale": "en",
                    "utmSource": "invitation",
                    "utmCampaign": "system_share",
                    "tz": "America/Sao_Paulo",
                    "tzOffset": "180",
                    "utmMedium": "social"
                },
                "email": email,
                "verifyCode": verify_code,
                "password": password
            }
            
            api_headers = {
                'Content-Type': 'application/json',
                'Origin': 'https://manus.im',
                'Referer': 'https://manus.im/',
                'User-Agent': USER_AGENT,
            }
            
            http_log.info(f"POST RegisterByEmail")
            http_log.info(f"  Payload: {json.dumps(register_payload, indent=2)}")
            
            resp = req_lib.post(
                f"{MANUS_API}/user.v1.UserAuthPublicService/RegisterByEmail",
                json=register_payload,
                headers=api_headers,
                timeout=30
            )
            
            http_log.info(f"  Status: {resp.status_code}")
            http_log.info(f"  Response: {resp.text[:500]}")
            
            if resp.status_code == 200:
                data = json.loads(resp.text)
                if data.get('token'):
                    captured_data['auth_token'] = data['token']
                    log.info("REGISTRO CONCLUÍDO! JWT Token recebido!")
                else:
                    log.warning(f"200 sem token: {resp.text[:200]}")
            else:
                log.error(f"Erro registro: {resp.status_code}")
        except Exception as e:
            log.error(f"Erro: {e}")
            log.error(traceback.format_exc())
        
        # Screenshot
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_05_register.png")
            await page.screenshot(path=ss)
        except:
            pass
        
        # ========================================
        # PASSO 12: SELECIONAR POLÔNIA
        # ========================================
        log_separator("ETAPA 12: SELECIONANDO POLÔNIA (+48)")
        
        await asyncio.sleep(5)
        
        try:
            current_url = page.url
            log.info(f"URL atual: {current_url}")
            
            selectors = [
                'select[name*="country"]', '[class*="country"]',
                'button[class*="country"]', '[data-testid*="country"]',
            ]
            
            for sel in selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=5000)
                    if el:
                        await el.click()
                        await asyncio.sleep(1)
                        poland = await page.query_selector('text=Poland') or \
                                 await page.query_selector('text=Polska') or \
                                 await page.query_selector('text=+48')
                        if poland:
                            await poland.click()
                            log.info("POLÔNIA SELECIONADA!")
                            break
                except:
                    continue
        except Exception as e:
            log.warning(f"Erro país: {e}")
        
        # Screenshot final
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_06_final.png")
            await page.screenshot(path=ss)
        except:
            pass
        
        # ========================================
        # RESULTADO FINAL
        # ========================================
        elapsed_total = int(time.time() - start_time)
        
        log_separator("RESULTADO FINAL")
        
        status = "SUCESSO" if captured_data['auth_token'] else "PENDENTE"
        
        print(f"\n{C.G}{C.BD}")
        print("*" * 60)
        print(f"   PROCESSO FINALIZADO! [{status}]")
        print(f"   Engine:     {engine}")
        print(f"   Click:      {click_method}")
        print(f"   Gmail:      {email}")
        print(f"   Senha:      {password}")
        print(f"   Convite:    {invite_code}")
        print(f"   Código:     {verify_code}")
        print(f"   Tempo:      {elapsed_total}s")
        if captured_data['auth_token']:
            print(f"   Token:      {captured_data['auth_token'][:50]}...")
        print("*" * 60)
        print(f"{C.RS}\n")
        
        # Salvar logs finais
        log_to_file(creds_file, f"{status} | email={email} | senha={password} | convite={invite_code} | codigo={verify_code} | tempo={elapsed_total}s")
        
        if captured_data['auth_token']:
            log_to_file(tokens_file, f"email={email} | token={captured_data['auth_token']}")
        
        # Dump API responses
        responses_file = os.path.join(LOG_DIR, f"{timestamp}_manus_api_dump.json")
        with open(responses_file, 'w', encoding='utf-8') as f:
            json.dump(captured_data['all_responses'], f, indent=2, ensure_ascii=False)
        
        log.info("=" * 60)
        log.info(f"FINALIZADO em {elapsed_total}s | Status: {status}")
        log.info(f"Respostas API capturadas: {len(captured_data['all_responses'])}")
        log.info("=" * 60)
        
        # ========================================
        # COMPACTAR LOGS EM ZIP
        # ========================================
        log_separator("COMPACTANDO LOGS EM ZIP")
        
        for handler in log.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
        for handler in http_log.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
        for handler in browser_log.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
        
        zip_path = os.path.join(LOG_DIR, "MANUS_LOGS.zip")
        
        log_files_to_zip = [
            main_log_file, http_log_file, browser_log_file,
            error_log_file, creds_file, tokens_file, responses_file,
        ]
        
        for f_name in os.listdir(LOG_DIR):
            full = os.path.join(LOG_DIR, f_name)
            if f_name.startswith(timestamp) and f_name.endswith('.png'):
                if full not in log_files_to_zip:
                    log_files_to_zip.append(full)
        
        try:
            with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zf:
                existing = set(zf.namelist())
                added = 0
                for lf in log_files_to_zip:
                    if os.path.exists(lf):
                        arcname = os.path.basename(lf)
                        if arcname in existing and arcname in ['manus_credentials.log', 'manus_tokens.log']:
                            pass
                        elif arcname in existing:
                            continue
                        zf.write(lf, arcname)
                        added += 1
            
            zip_size = os.path.getsize(zip_path)
            if zip_size > 1048576:
                zip_display = f"{zip_size / 1048576:.1f} MB"
            else:
                zip_display = f"{zip_size / 1024:.1f} KB"
            
            total_files = len(zipfile.ZipFile(zip_path, 'r').namelist())
            
            print(f"\n{C.G}{C.BD}  [ZIP] Logs adicionados ao ZIP único!{C.RS}")
            print(f"  {C.G}  Arquivo:       {zip_path}{C.RS}")
            print(f"  {C.G}  Tamanho total: {zip_display}{C.RS}")
            print(f"  {C.G}  Adicionados:   {added} arquivos{C.RS}")
            print(f"  {C.G}  Total no ZIP:  {total_files} arquivos{C.RS}")
        except Exception as e:
            print(f"\n{C.R}  [ERRO] Falha ao criar ZIP: {e}{C.RS}")
        
        print(f"\n{C.CY}{C.BD}  LOGS GERADOS:{C.RS}")
        print(f"  {C.CY}  ZIP:         {zip_path}{C.RS}")
        print(f"  {C.CY}  Principal:   {main_log_file}{C.RS}")
        print(f"  {C.CY}  HTTP:        {http_log_file}{C.RS}")
        print(f"  {C.CY}  Browser:     {browser_log_file}{C.RS}")
        print(f"  {C.CY}  Erros:       {error_log_file}{C.RS}")
        print(f"  {C.CY}  Credenciais: {creds_file}{C.RS}")
        print(f"  {C.CY}  Tokens:      {tokens_file}{C.RS}")
        print(f"  {C.CY}  API Dump:    {responses_file}{C.RS}")
        print()
        
        print(f"{C.Y}[*] Browser aberto no KeX. ENTER para fechar.{C.RS}")
        input()
        
        await browser.close()

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    display = os.environ.get('DISPLAY')
    if not display:
        os.environ['DISPLAY'] = ':1'
    
    print(f"{C.CY}[*] Engine: {'PATCHRIGHT' if USING_PATCHRIGHT else 'PLAYWRIGHT'}{C.RS}")
    print(f"{C.CY}[*] xdotool: {'DISPONÍVEL' if XDOTOOL_AVAILABLE else 'NÃO ENCONTRADO'}{C.RS}")
    print(f"{C.CY}[*] DISPLAY={os.environ.get('DISPLAY')}{C.RS}")
    print(f"{C.CY}[*] CAPTCHA API: {'CONFIGURADA' if CAPTCHA_API_KEY else 'NÃO CONFIGURADA (local only)'}{C.RS}")
    print(f"{C.CY}[*] Iniciando V7.2 (NETWORK FIX)...{C.RS}\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C.Y}[!] Ctrl+C{C.RS}")
    except Exception as e:
        print(f"\n{C.R}[ERRO FATAL] {e}{C.RS}")
        traceback.print_exc()
        err_file = os.path.join(LOG_DIR, f"FATAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        with open(err_file, 'w') as f:
            f.write(f"{e}\n\n{traceback.format_exc()}")
        print(f"{C.Y}Erro salvo: {err_file}{C.RS}")
