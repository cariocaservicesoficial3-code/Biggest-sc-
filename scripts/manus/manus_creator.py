#!/usr/bin/env python3
"""
==============================================================
  MANUS ACCOUNT CREATOR V5 - KALI LINUX NETHUNTER + KeX VNC
  Patchright + xdotool REAL CLICK Turnstile Bypass + Logging
==============================================================

Mudanças V5:
- FIX: Removido --sync do xdotool (causava timeout no VNC/KeX)
- FIX: check_continue_enabled agora ignora botões sociais (Facebook/Google/etc)
- FIX: Seletor do botão Continue mais preciso
- FIX: Coordenadas do Turnstile agora usam bounding_box direto (sem window offset)
- xdotool para cliques REAIS no Turnstile (bypass screenX/screenY)
- Patchright (indetectável) + xdotool = combo perfeito
- Logs completos em /sdcard/nh_files/MANUS LOGS/
- ZIP único acumulativo MANUS_LOGS.zip
- Screenshots automáticos de cada etapa

Fluxo:
1. Pede o link de convite do Manus
2. Gera Gmail temporário via Emailnator (dotGmail)
3. Gera senha forte no padrão aceito pelo Manus
4. Abre Patchright (headless=False) no display VNC
5. Navega para manus.im/login
6. Preenche email
7. Localiza iframe do Turnstile e clica com xdotool (REAL CLICK)
8. Clica Continue
9. Monitora Emailnator para capturar código de 6 dígitos
10. Envia o código de verificação
11. Completa registro via API
12. Seleciona Polônia na página de telefone
13. Salva logs e credenciais

Requisitos:
  pip3 install patchright requests rich --break-system-packages
  python3 -m patchright install chromium
  apt install xdotool  (para cliques reais no Turnstile)
"""

import asyncio
import json
import logging
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

# ============================================================
# EMAILNATOR CLIENT
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
        except Exception as e:
            http_log.error(f"  Erro msg: {e}")
            return None
    
    def wait_for_code(self, sender_filter="manus", max_wait=180):
        log.info(f"Monitorando inbox: {self.email} | Filtro: {sender_filter} | Timeout: {max_wait}s")
        start = time.time()
        processed = set()
        attempt = 0
        
        while time.time() - start < max_wait:
            attempt += 1
            elapsed = int(time.time() - start)
            
            if attempt % 5 == 0:
                log.info(f"  Inbox check #{attempt} ({elapsed}s/{max_wait}s)")
            
            inbox = self.get_inbox()
            if inbox and isinstance(inbox, dict):
                messages = inbox.get('messageData', [])
                if isinstance(inbox, list):
                    messages = inbox
                
                for msg in messages:
                    msg_from = msg.get('from', '') if isinstance(msg, dict) else ''
                    msg_subject = msg.get('subject', '') if isinstance(msg, dict) else ''
                    msg_id = msg.get('messageID', '') if isinstance(msg, dict) else ''
                    
                    if not msg_id or msg_id in processed:
                        continue
                    
                    if sender_filter.lower() in msg_from.lower() or sender_filter.lower() in msg_subject.lower():
                        log.info(f"  E-mail encontrado! De: {msg_from} | Assunto: {msg_subject}")
                        
                        body = self.get_message(msg_id)
                        if body:
                            codes = re.findall(r'\b(\d{6})\b', body)
                            if codes:
                                log.info(f"  >>> CÓDIGO: {codes[0]}")
                                return codes[0]
                    processed.add(msg_id)
            time.sleep(5)
        
        log.error(f"TIMEOUT: Nenhum código em {max_wait}s")
        return None

# ============================================================
# GERADOR DE SENHA
# ============================================================
def generate_manus_password(length=20):
    specials = ":;'#@!$%^&*()-_+=<>?"
    parts = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice(string.digits),
        random.choice(specials),
        random.choice(specials),
        random.choice(specials),
    ]
    remaining = length - len(parts)
    all_chars = string.ascii_letters + string.digits + specials
    parts.extend(random.choices(all_chars, k=remaining))
    random.shuffle(parts)
    password = ''.join(parts)
    log.debug(f"Senha gerada ({length} chars): {password}")
    return password

# ============================================================
# XDOTOOL REAL CLICK - Bypass Turnstile screenX/screenY check
# ============================================================
def xdotool_click(x, y):
    """
    Executa um clique REAL no nível do sistema operacional usando xdotool.
    Isso gera um MouseEvent com screenX/screenY corretos (relativos à tela),
    não ao iframe. O Cloudflare Turnstile verifica se screenX/screenY > 100
    para detectar cliques automatizados via CDP.
    NOTA: NÃO usar --sync pois causa timeout no VNC/KeX.
    """
    try:
        # Mover o mouse para a posição (SEM --sync para evitar timeout no VNC)
        subprocess.run(
            ['xdotool', 'mousemove', str(int(x)), str(int(y))],
            timeout=3, capture_output=True
        )
        time.sleep(0.2 + random.uniform(0.05, 0.15))
        
        # Clicar
        subprocess.run(
            ['xdotool', 'click', '1'],
            timeout=3, capture_output=True
        )
        browser_log.info(f"xdotool REAL CLICK em ({int(x)}, {int(y)})")
        return True
    except Exception as e:
        browser_log.error(f"xdotool falhou: {e}")
        return False

def xdotool_human_click(x, y):
    """
    Clique com movimento humano - move em steps para parecer natural.
    NOTA: Sem --sync para evitar timeout no VNC/KeX.
    """
    try:
        # Primeiro, pegar posição atual do mouse
        result = subprocess.run(
            ['xdotool', 'getmouselocation'],
            timeout=3, capture_output=True, text=True
        )
        current_x, current_y = 0, 0
        if result.stdout:
            parts = result.stdout.strip().split()
            for p in parts:
                if p.startswith('x:'):
                    current_x = int(p.split(':')[1])
                elif p.startswith('y:'):
                    current_y = int(p.split(':')[1])
        
        # Mover em steps para parecer humano
        steps = random.randint(5, 10)
        for i in range(steps):
            progress = (i + 1) / steps
            jitter_x = random.uniform(-3, 3) if i < steps - 1 else 0
            jitter_y = random.uniform(-2, 2) if i < steps - 1 else 0
            
            step_x = int(current_x + (x - current_x) * progress + jitter_x)
            step_y = int(current_y + (y - current_y) * progress + jitter_y)
            
            subprocess.run(
                ['xdotool', 'mousemove', str(step_x), str(step_y)],
                timeout=2, capture_output=True
            )
            time.sleep(random.uniform(0.01, 0.04))
        
        # Posição final exata (SEM --sync)
        subprocess.run(
            ['xdotool', 'mousemove', str(int(x)), str(int(y))],
            timeout=3, capture_output=True
        )
        
        # Delay humano antes do clique
        time.sleep(random.uniform(0.08, 0.25))
        
        # Clique
        subprocess.run(
            ['xdotool', 'click', '1'],
            timeout=5, capture_output=True
        )
        
        browser_log.info(f"xdotool HUMAN CLICK em ({int(x)}, {int(y)}) com {steps} steps")
        return True
    except Exception as e:
        browser_log.error(f"xdotool human click falhou: {e}")
        return xdotool_click(x, y)  # Fallback para clique simples

# ============================================================
# TURNSTILE - Encontrar posição do iframe e clicar com xdotool
# ============================================================
def get_window_geometry():
    """
    Usa xdotool para pegar a geometria REAL da janela ativa.
    Retorna (x, y, width, height) da janela na tela.
    """
    try:
        # Pegar ID da janela ativa
        result = subprocess.run(
            ['xdotool', 'getactivewindow'],
            timeout=3, capture_output=True, text=True
        )
        if result.returncode != 0:
            return None
        
        window_id = result.stdout.strip()
        browser_log.info(f"  Janela ativa ID: {window_id}")
        
        # Pegar geometria da janela
        result = subprocess.run(
            ['xdotool', 'getwindowgeometry', window_id],
            timeout=3, capture_output=True, text=True
        )
        if result.returncode == 0:
            # Output: "Window 12345678\n  Position: 0,0 (screen: 0)\n  Geometry: 1280x720"
            lines = result.stdout.strip().split('\n')
            pos_x, pos_y = 0, 0
            width, height = 0, 0
            for line in lines:
                if 'Position:' in line:
                    match = re.search(r'Position:\s*(\d+),(\d+)', line)
                    if match:
                        pos_x = int(match.group(1))
                        pos_y = int(match.group(2))
                if 'Geometry:' in line:
                    match = re.search(r'Geometry:\s*(\d+)x(\d+)', line)
                    if match:
                        width = int(match.group(1))
                        height = int(match.group(2))
            
            browser_log.info(f"  Window geometry: pos=({pos_x},{pos_y}), size={width}x{height}")
            return {'x': pos_x, 'y': pos_y, 'width': width, 'height': height}
    except Exception as e:
        browser_log.warning(f"  get_window_geometry falhou: {e}")
    return None

async def find_and_click_turnstile(page):
    """
    Encontra o iframe do Turnstile, calcula a posição do checkbox na tela,
    e retorna as coordenadas para xdotool.
    
    Estratégia V5:
    1. Usa xdotool getactivewindow + getwindowgeometry para posição REAL da janela
    2. Usa JS getBoundingClientRect para posição do iframe no viewport
    3. Calcula: screen_pos = window_pos + chrome_offset + viewport_pos + checkbox_offset
    """
    log.info("Procurando iframe do Turnstile...")
    
    # Primeiro, pegar a posição real da janela via xdotool
    win_geo = get_window_geometry() if XDOTOOL_AVAILABLE else None
    
    # Pegar info da janela via JS também (para comparar)
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
    browser_log.info(f"  JS Inner: {window_info['innerWidth']}x{window_info['innerHeight']}")
    browser_log.info(f"  JS Outer: {window_info['outerWidth']}x{window_info['outerHeight']}")
    if win_geo:
        browser_log.info(f"  xdotool Window: pos=({win_geo['x']},{win_geo['y']}), size={win_geo['width']}x{win_geo['height']}")
    
    # Calcular chrome offset (barra de título, tabs, URL bar)
    chrome_height = window_info['outerHeight'] - window_info['innerHeight']
    chrome_width_offset = (window_info['outerWidth'] - window_info['innerWidth']) // 2
    browser_log.info(f"  Chrome height: {chrome_height}px, width_offset: {chrome_width_offset}px")
    
    # Determinar posição base da janela
    if win_geo:
        # Preferir xdotool (mais preciso no VNC)
        base_x = win_geo['x']
        base_y = win_geo['y']
        browser_log.info(f"  Usando xdotool para base: ({base_x}, {base_y})")
    else:
        base_x = window_info['screenX']
        base_y = window_info['screenY']
        browser_log.info(f"  Usando JS para base: ({base_x}, {base_y})")
    
    # Método 1: Encontrar iframe do Cloudflare Turnstile via JS
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
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height,
                        src: iframe.src || 'N/A',
                        selector: sel
                    };
                }
            }
            
            const container = document.querySelector('.cf-turnstile, [data-sitekey]');
            if (container) {
                const rect = container.getBoundingClientRect();
                return {
                    found: true,
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                    src: 'container',
                    selector: '.cf-turnstile'
                };
            }
            
            return { found: false };
        }""")
        
        if iframe_info and iframe_info.get('found'):
            browser_log.info(f"Turnstile encontrado via JS: {iframe_info['selector']}")
            browser_log.info(f"  Viewport pos: x={iframe_info['x']}, y={iframe_info['y']}")
            browser_log.info(f"  Tamanho: {iframe_info['width']}x{iframe_info['height']}")
            
            # O checkbox fica ~30px da borda esquerda, centralizado verticalmente
            checkbox_x_in_iframe = 30
            checkbox_y_in_iframe = iframe_info['height'] / 2
            
            # Coordenadas na tela = base_janela + chrome_offset + posição_no_viewport + offset_checkbox
            screen_x = int(base_x + chrome_width_offset + iframe_info['x'] + checkbox_x_in_iframe)
            screen_y = int(base_y + chrome_height + iframe_info['y'] + checkbox_y_in_iframe)
            
            browser_log.info(f"  Cálculo: base({base_x},{base_y}) + chrome(w={chrome_width_offset},h={chrome_height}) + viewport({iframe_info['x']},{iframe_info['y']}) + checkbox({checkbox_x_in_iframe},{checkbox_y_in_iframe})")
            browser_log.info(f"  COORDENADAS FINAIS: ({screen_x}, {screen_y})")
            
            return screen_x, screen_y
    except Exception as e:
        browser_log.warning(f"Erro método 1 (JS): {e}")
    
    # Método 2: Procurar por frames do Playwright/Patchright
    try:
        for frame in page.frames:
            if 'challenges.cloudflare' in frame.url or 'turnstile' in frame.url:
                browser_log.info(f"Frame do Turnstile encontrado: {frame.url[:80]}")
                
                frame_element = await frame.frame_element()
                if frame_element:
                    box = await frame_element.bounding_box()
                    if box:
                        browser_log.info(f"  BoundingBox: x={box['x']}, y={box['y']}, w={box['width']}, h={box['height']}")
                        
                        screen_x = int(base_x + chrome_width_offset + box['x'] + 30)
                        screen_y = int(base_y + chrome_height + box['y'] + box['height'] / 2)
                        
                        browser_log.info(f"  COORDENADAS FINAIS (método 2): ({screen_x}, {screen_y})")
                        return screen_x, screen_y
    except Exception as e:
        browser_log.warning(f"Erro método 2: {e}")
    
    return None, None

# ============================================================
# TURNSTILE HELPER - Espera o token ser resolvido
# ============================================================
async def wait_for_turnstile(page, timeout=120):
    """
    Aguarda o Turnstile ser resolvido. Verifica periodicamente se o token
    apareceu no input hidden.
    """
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
                if (window.turnstile) {
                    try {
                        const widgets = document.querySelectorAll('.cf-turnstile');
                        for (const w of widgets) {
                            const widgetId = w.getAttribute('data-widget-id');
                            if (widgetId) {
                                const resp = window.turnstile.getResponse(widgetId);
                                if (resp) return resp;
                            }
                        }
                    } catch(e) {}
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
            
            # Log do estado visual
            try:
                state = await page.evaluate("""() => {
                    const iframe = document.querySelector('iframe[src*="challenges.cloudflare"], iframe[src*="turnstile"]');
                    if (!iframe) {
                        const container = document.querySelector('.cf-turnstile, [data-sitekey]');
                        if (!container) return 'NOT_FOUND';
                        const innerIframe = container.querySelector('iframe');
                        if (!innerIframe) return 'CONTAINER_NO_IFRAME';
                        return 'CONTAINER_WITH_IFRAME';
                    }
                    return 'IFRAME_PRESENT: ' + (iframe.src || '').substring(0, 60);
                }""")
                browser_log.info(f"  Turnstile state: {state}")
            except:
                pass
        
        await asyncio.sleep(2)
    
    log.warning(f"Turnstile não resolveu em {timeout}s")
    return None

# ============================================================
# VERIFICAR SE BOTÃO CONTINUE ESTÁ HABILITADO
# ============================================================
async def check_continue_enabled(page):
    """Verifica se o botão SUBMIT Continue está habilitado (ignora botões sociais)"""
    try:
        result = await page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            // Palavras que indicam botões sociais (NÃO é o submit)
            const socialKeywords = ['facebook', 'google', 'microsoft', 'apple', 'github', 'twitter'];
            
            for (const btn of btns) {
                const text = btn.textContent.trim().toLowerCase();
                
                // Pular botões de login social
                const isSocial = socialKeywords.some(kw => text.includes(kw));
                if (isSocial) continue;
                
                // Procurar o botão Continue/Sign que é o SUBMIT
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
# FLUXO PRINCIPAL
# ============================================================
async def main():
    start_time = time.time()
    
    engine = "PATCHRIGHT (INDETECTÁVEL)" if USING_PATCHRIGHT else "PLAYWRIGHT (detectável)"
    click_method = "xdotool (REAL CLICK)" if XDOTOOL_AVAILABLE else "CDP (fallback)"
    
    banner = f"""
{C.CY}{C.BD}
{'='*60}
   MANUS ACCOUNT CREATOR V5 - KALI NETHUNTER + KeX
   {engine}
   Turnstile: {click_method}
{'='*60}
   DISPLAY:  {os.environ.get('DISPLAY', 'N/A')}
   Engine:   {engine}
   Click:    {click_method}
   Proxy:    {PROXY_HOST}:{PROXY_PORT}
   Logs:     {LOG_DIR}
   Log File: {main_log_file}
{'='*60}
{C.RS}"""
    print(banner)
    
    log.info("=" * 60)
    log.info(f"MANUS ACCOUNT CREATOR V5 INICIADO")
    log.info(f"Engine: {engine}")
    log.info(f"Click method: {click_method}")
    log.info(f"xdotool disponível: {XDOTOOL_AVAILABLE}")
    log.info(f"DISPLAY={os.environ.get('DISPLAY')}")
    log.info(f"Python={sys.version}")
    log.info("=" * 60)
    
    if not XDOTOOL_AVAILABLE:
        print(f"\n{C.Y}{C.BD}  [!] AVISO: xdotool NÃO instalado!{C.RS}")
        print(f"{C.Y}  Instale com: apt install xdotool{C.RS}")
        print(f"{C.Y}  Sem xdotool, o Turnstile pode falhar.{C.RS}")
        print(f"{C.Y}  Continuando com clique CDP (fallback)...{C.RS}\n")
        log.warning("xdotool NÃO disponível - usando CDP fallback")
    
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
    # PASSO 3: ABRIR BROWSER
    # ========================================
    log_separator(f"ETAPA 3: ABRINDO BROWSER ({engine})")
    
    async with async_playwright() as p:
        
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
            '--window-position=0,0',
        ]
        
        if not USING_PATCHRIGHT:
            browser_args.extend([
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
            ])
        
        try:
            browser = await p.chromium.launch(
                headless=False,
                args=browser_args,
            )
            browser_log.info(f"Browser lançado! Engine: {engine}")
            log.info(f"Browser aberto no desktop KeX!")
        except Exception as e:
            log.error(f"FALHA ao lançar browser: {e}")
            log.error(traceback.format_exc())
            return
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1200, 'height': 680},
            locale='en-US',
        )
        
        if not USING_PATCHRIGHT:
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                delete navigator.__proto__.webdriver;
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
                );
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)
        
        browser_log.info("Contexto criado")
        
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
            await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        except:
            log.warning("Timeout ao carregar (normal)")
        
        # Esperar a página carregar completamente
        await asyncio.sleep(5)
        
        # Screenshot
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_01_login_page.png")
            await page.screenshot(path=ss)
            browser_log.info(f"Screenshot: {ss}")
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
                await asyncio.sleep(0.3)
                await email_input.fill(email)
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
        
        await asyncio.sleep(2)
        
        # ========================================
        # PASSO 6: RESOLVER TURNSTILE COM XDOTOOL
        # ========================================
        log_separator("ETAPA 6: RESOLVENDO TURNSTILE")
        
        cf_token = None
        max_turnstile_attempts = 3
        
        for attempt in range(max_turnstile_attempts):
            log.info(f"Tentativa Turnstile {attempt + 1}/{max_turnstile_attempts}")
            
            # Esperar o iframe do Turnstile aparecer
            log.info("Aguardando iframe do Turnstile carregar...")
            await asyncio.sleep(3)
            
            # Encontrar posição do Turnstile
            screen_x, screen_y = await find_and_click_turnstile(page)
            
            if screen_x is not None and screen_y is not None:
                if XDOTOOL_AVAILABLE:
                    print(f"\n{C.G}{C.BD}")
                    print(f"  XDOTOOL REAL CLICK - Bypass Turnstile!")
                    print(f"  Coordenadas: ({screen_x}, {screen_y})")
                    print(f"{C.RS}\n")
                    
                    # Clique humano com xdotool
                    success = xdotool_human_click(screen_x, screen_y)
                    
                    if success:
                        log.info(f"xdotool clicou em ({screen_x}, {screen_y})")
                    else:
                        log.warning("xdotool falhou, tentando clique simples...")
                        xdotool_click(screen_x, screen_y)
                else:
                    # Fallback: clique CDP (pode ser detectado)
                    log.warning("Usando clique CDP (sem xdotool)")
                    try:
                        # Converter coordenadas de tela de volta para viewport
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
                        vp_x = screen_x - window_info['screenX'] - chrome_w
                        vp_y = screen_y - window_info['screenY'] - chrome_h
                        await page.mouse.click(vp_x, vp_y)
                        browser_log.info(f"CDP click em viewport ({vp_x}, {vp_y})")
                    except Exception as e:
                        browser_log.warning(f"CDP click falhou: {e}")
            else:
                log.warning("Turnstile iframe NÃO encontrado!")
                
                # Tentar encontrar de outra forma - clicar em qualquer checkbox visível
                try:
                    for frame in page.frames:
                        if 'challenges.cloudflare' in frame.url:
                            browser_log.info(f"Tentando clicar dentro do frame: {frame.url[:60]}")
                            try:
                                await frame.click('body', timeout=3000)
                            except:
                                pass
                except:
                    pass
            
            # Screenshot pós-clique
            try:
                ss = os.path.join(LOG_DIR, f"{timestamp}_02_turnstile_attempt{attempt+1}.png")
                await page.screenshot(path=ss)
            except:
                pass
            
            # Esperar resolução
            cf_token = await wait_for_turnstile(page, timeout=30)
            
            if cf_token:
                log.info("TURNSTILE RESOLVIDO COM SUCESSO!")
                break
            
            # Verificar se o botão Continue ficou habilitado (indica sucesso)
            btn_state = await check_continue_enabled(page)
            if btn_state and not btn_state.get('disabled', True):
                log.info(f"Botão Continue HABILITADO! ({btn_state.get('text', '')})")
                break
            
            if attempt < max_turnstile_attempts - 1:
                log.warning("Turnstile não resolveu, recarregando página...")
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                except:
                    pass
                await asyncio.sleep(3)
                
                # Preencher email novamente
                try:
                    email_input = await page.wait_for_selector(
                        'input[type="email"], input[placeholder*="email" i]',
                        timeout=10000
                    )
                    if email_input:
                        await email_input.fill(email)
                        log.info("E-mail preenchido novamente")
                except:
                    pass
                await asyncio.sleep(2)
        
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
            # Procurar APENAS o botão submit Continue (NÃO os botões sociais)
            continue_btn = None
            all_buttons = await page.query_selector_all('button')
            for btn in all_buttons:
                text = (await btn.text_content() or '').strip().lower()
                # Ignorar botões sociais
                social_keywords = ['facebook', 'google', 'microsoft', 'apple', 'github', 'twitter']
                is_social = any(kw in text for kw in social_keywords)
                if is_social:
                    continue
                # Procurar o botão submit
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
                    log.warning("Botão Continue desabilitado - aguardando...")
                    await asyncio.sleep(5)
                
                # Usar xdotool para clicar no Continue também (mais seguro)
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
                            xdotool_click(btn_x, btn_y)
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
                        await asyncio.sleep(0.1)
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
        print("*" * 60)
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
        # COMPACTAR TODOS OS LOGS EM ZIP ÚNICO
        # ========================================
        log_separator("COMPACTANDO LOGS EM ZIP")
        
        # Fechar handlers de log antes de zipar
        for handler in log.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
        for handler in http_log.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
        for handler in browser_log.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
        
        # ZIP ÚNICO persistente
        zip_path = os.path.join(LOG_DIR, "MANUS_LOGS.zip")
        
        log_files_to_zip = [
            main_log_file,
            http_log_file,
            browser_log_file,
            error_log_file,
            creds_file,
            tokens_file,
            responses_file,
        ]
        
        # Adicionar screenshots desta execução
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
    print(f"{C.CY}[*] Iniciando V5...{C.RS}\n")
    
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
