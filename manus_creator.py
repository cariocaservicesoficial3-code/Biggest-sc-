#!/usr/bin/env python3
"""
==============================================================
  MANUS ACCOUNT CREATOR V3 - KALI LINUX NETHUNTER + KeX VNC
  Patchright (Undetected) + Turnstile Bypass + Full Logging
==============================================================

Mudanças V3:
- Patchright no lugar do Playwright (indetectável)
- Turnstile bypass automático (sem precisar resolver manualmente)
- Logs completos em /root/ (7 arquivos por execução)
- Screenshots automáticos de cada etapa
- Fallback: se Patchright não disponível, usa Playwright

Fluxo:
1. Pede o link de convite do Manus
2. Gera Gmail temporário via Emailnator (dotGmail)
3. Gera senha forte no padrão aceito pelo Manus
4. Abre Patchright (headless=False) no display VNC - INDETECTÁVEL
5. Navega para manus.im/login - Turnstile resolve sozinho!
6. Preenche email e clica Continue
7. Monitora Emailnator para capturar código de 6 dígitos
8. Envia o código de verificação
9. Completa registro via API
10. Seleciona Polônia na página de telefone
11. Salva logs e credenciais em /root/

Requisitos:
  pip3 install patchright requests rich
  python3 -m patchright install chromium
  
  Fallback (se patchright não instalar):
  pip3 install playwright requests rich
  playwright install chromium
"""

import asyncio
import json
import logging
import os
import random
import re
import string
import sys
import time
import traceback
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
        print("\033[93mInstale com: pip3 install patchright && python3 -m patchright install chromium\033[0m")
        print("\033[93mOu fallback: pip3 install playwright && playwright install chromium\033[0m")
        sys.exit(1)

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
            log.info(f"Verificação #{attempt} ({elapsed}s/{max_wait}s)...")
            
            inbox = self.get_inbox()
            if inbox and 'messageData' in inbox:
                for msg in inbox['messageData']:
                    msg_id = msg.get('messageID')
                    sender = msg.get('from', '').lower()
                    subject = msg.get('subject', '')
                    
                    if msg_id and msg_id not in processed:
                        log.info(f"  Nova msg - De: {sender} | Assunto: {subject}")
                        log_to_file(main_log_file, f"EMAIL: from={sender} subject={subject}")
                        
                        if sender_filter.lower() in sender or sender_filter.lower() in subject.lower():
                            processed.add(msg_id)
                            log.info(f"  >>> E-MAIL DO MANUS DETECTADO!")
                            content = self.get_message(msg_id)
                            if content:
                                log_to_file(main_log_file, f"EMAIL CONTEUDO:\n{content[:2000]}")
                                codes = re.findall(r'\b(\d{6})\b', content)
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
# TURNSTILE HELPER - Espera o token ser resolvido
# ============================================================
async def wait_for_turnstile(page, timeout=120):
    """
    Com Patchright, o Turnstile resolve SOZINHO porque o browser
    não é detectado como automação. Só precisamos esperar.
    Com Playwright normal, o usuário precisa resolver manualmente.
    """
    log.info("Aguardando resolução do Turnstile...")
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            # Verificar se o Turnstile já resolveu (checkbox marcado)
            # O token fica em um input hidden com name="cf-turnstile-response"
            token = await page.evaluate("""() => {
                // Método 1: input hidden
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                if (input && input.value && input.value.length > 10) return input.value;
                
                // Método 2: dentro de iframe do turnstile
                const iframes = document.querySelectorAll('iframe[src*="turnstile"]');
                for (const iframe of iframes) {
                    try {
                        const doc = iframe.contentDocument;
                        if (doc) {
                            const inp = doc.querySelector('input[name="cf-turnstile-response"]');
                            if (inp && inp.value) return inp.value;
                        }
                    } catch(e) {}
                }
                
                // Método 3: verificar se o checkbox está marcado (success state)
                const success = document.querySelector('[data-turnstile-response]');
                if (success) return success.getAttribute('data-turnstile-response');
                
                // Método 4: window.turnstile
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
            
            # Verificar estado visual do Turnstile
            try:
                state = await page.evaluate("""() => {
                    const el = document.querySelector('.cf-turnstile, [data-sitekey]');
                    if (!el) return 'NOT_FOUND';
                    const iframe = el.querySelector('iframe');
                    if (!iframe) return 'NO_IFRAME';
                    return 'IFRAME_PRESENT';
                }""")
                browser_log.info(f"  Turnstile state: {state}")
            except:
                pass
        
        await asyncio.sleep(2)
    
    log.warning(f"Turnstile não resolveu em {timeout}s")
    return None

# ============================================================
# CLICAR NO TURNSTILE CHECKBOX (se necessário)
# ============================================================
async def click_turnstile_checkbox(page):
    """Tenta clicar no checkbox do Turnstile se ele existir"""
    try:
        # Patchright pode interagir com Shadow DOM e iframes fechados
        # Procurar o iframe do Turnstile
        turnstile_frame = None
        for frame in page.frames:
            if 'turnstile' in frame.url or 'challenges.cloudflare' in frame.url:
                turnstile_frame = frame
                break
        
        if turnstile_frame:
            browser_log.info(f"Turnstile iframe encontrado: {turnstile_frame.url}")
            
            # Tentar clicar no checkbox dentro do iframe
            try:
                checkbox = await turnstile_frame.wait_for_selector(
                    'input[type="checkbox"], .ctp-checkbox-label, #challenge-stage',
                    timeout=5000
                )
                if checkbox:
                    await checkbox.click()
                    browser_log.info("Checkbox do Turnstile clicado!")
                    return True
            except:
                pass
            
            # Tentar clicar por coordenadas no centro do iframe
            try:
                box = await turnstile_frame.frame_element()
                if box:
                    bounding = await box.bounding_box()
                    if bounding:
                        x = bounding['x'] + bounding['width'] / 4
                        y = bounding['y'] + bounding['height'] / 2
                        await page.mouse.click(x, y)
                        browser_log.info(f"Clicado no centro do Turnstile: ({x}, {y})")
                        return True
            except:
                pass
        
        # Fallback: clicar no elemento .cf-turnstile
        try:
            cf_el = await page.query_selector('.cf-turnstile, [data-sitekey]')
            if cf_el:
                box = await cf_el.bounding_box()
                if box:
                    x = box['x'] + 30  # Checkbox fica no lado esquerdo
                    y = box['y'] + box['height'] / 2
                    await page.mouse.click(x, y)
                    browser_log.info(f"Clicado no .cf-turnstile: ({x}, {y})")
                    return True
        except:
            pass
            
    except Exception as e:
        browser_log.warning(f"Erro ao clicar Turnstile: {e}")
    
    return False

# ============================================================
# FLUXO PRINCIPAL
# ============================================================
async def main():
    start_time = time.time()
    
    engine = "PATCHRIGHT (INDETECTÁVEL)" if USING_PATCHRIGHT else "PLAYWRIGHT (detectável - Turnstile manual)"
    
    banner = f"""
{C.CY}{C.BD}
{'='*60}
   MANUS ACCOUNT CREATOR V3 - KALI NETHUNTER + KeX
   {engine}
{'='*60}
   DISPLAY:  {os.environ.get('DISPLAY', 'N/A')}
   Engine:   {engine}
   Proxy:    {PROXY_HOST}:{PROXY_PORT}
   Logs:    {LOG_DIR}
   Log File: {main_log_file}
{'='*60}
{C.RS}"""
    print(banner)
    
    log.info("=" * 60)
    log.info(f"MANUS ACCOUNT CREATOR V3 INICIADO")
    log.info(f"Engine: {engine}")
    log.info(f"DISPLAY={os.environ.get('DISPLAY')}")
    log.info(f"Python={sys.version}")
    log.info("=" * 60)
    
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
        
        # Args do browser - Patchright já aplica patches anti-detecção
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
            '--window-position=0,0',
        ]
        
        # Se for Playwright normal, adicionar args extras de stealth
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
            browser_log.info(f"Browser lançado com sucesso! Engine: {engine}")
            log.info(f"Browser aberto no desktop KeX!")
        except Exception as e:
            log.error(f"FALHA ao lançar browser: {e}")
            log.error(traceback.format_exc())
            log.error("DICA: vncserver :1 -geometry 1280x720 -depth 24")
            return
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1200, 'height': 680},
            locale='en-US',
        )
        
        # Anti-detecção extra (para Playwright normal)
        if not USING_PATCHRIGHT:
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                delete navigator.__proto__.webdriver;
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
                );
                
                // Chrome runtime
                window.chrome = { runtime: {} };
                
                // Plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)
        
        browser_log.info("Contexto criado com anti-detecção")
        
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
            log.warning("Timeout ao carregar (normal)")
        
        await asyncio.sleep(3)
        
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
        
        await asyncio.sleep(1)
        
        # ========================================
        # PASSO 6: AGUARDAR TURNSTILE
        # ========================================
        log_separator("ETAPA 6: RESOLVENDO TURNSTILE")
        
        if USING_PATCHRIGHT:
            print(f"\n{C.G}{C.BD}")
            print("  PATCHRIGHT ATIVO - Turnstile deve resolver AUTOMATICAMENTE!")
            print(f"  Aguardando...{C.RS}\n")
            
            # Com Patchright, o Turnstile geralmente resolve sozinho
            # Mas vamos tentar clicar no checkbox primeiro
            await asyncio.sleep(3)
            await click_turnstile_checkbox(page)
            await asyncio.sleep(2)
            
            # Aguardar resolução
            cf_token = await wait_for_turnstile(page, timeout=60)
            
            if not cf_token:
                log.warning("Turnstile não resolveu automaticamente, tentando novamente...")
                # Recarregar e tentar de novo
                await page.reload(wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)
                
                # Preencher email de novo
                try:
                    email_input = await page.wait_for_selector(
                        'input[type="email"], input[placeholder*="email" i]',
                        timeout=10000
                    )
                    if email_input:
                        await email_input.fill(email)
                except:
                    pass
                
                await asyncio.sleep(2)
                await click_turnstile_checkbox(page)
                cf_token = await wait_for_turnstile(page, timeout=90)
        else:
            print(f"\n{C.Y}{C.BD}")
            print("!" * 60)
            print("!  PLAYWRIGHT DETECTÁVEL - RESOLVA O TURNSTILE MANUALMENTE  !")
            print("!  Clique no checkbox no navegador KeX                       !")
            print("!" * 60)
            print(f"{C.RS}\n")
            cf_token = await wait_for_turnstile(page, timeout=300)
        
        # Screenshot pós-Turnstile
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_02_turnstile.png")
            await page.screenshot(path=ss)
        except:
            pass
        
        # ========================================
        # PASSO 7: CLICAR CONTINUE
        # ========================================
        log_separator("ETAPA 7: CLICANDO CONTINUE")
        
        try:
            # Procurar botão Continue
            continue_btn = await page.wait_for_selector(
                'button:has-text("Continue"), button:has-text("Sign"), button[type="submit"]',
                timeout=10000
            )
            if continue_btn:
                is_disabled = await continue_btn.get_attribute('disabled')
                if is_disabled:
                    log.warning("Botão Continue está desabilitado (Turnstile pode não ter resolvido)")
                    # Esperar mais um pouco
                    await asyncio.sleep(5)
                
                await continue_btn.click()
                log.info("Botão Continue clicado!")
                await asyncio.sleep(3)
        except Exception as e:
            log.warning(f"Botão Continue não encontrado: {e}")
            log.info("Tentando pressionar Enter...")
            try:
                await page.keyboard.press('Enter')
            except:
                pass
        
        # Esperar tempToken ser capturado
        log.info("Aguardando tempToken...")
        wait_start = time.time()
        while time.time() - wait_start < 30:
            if captured_data['temp_token']:
                break
            await asyncio.sleep(1)
        
        # Screenshot
        try:
            ss = os.path.join(LOG_DIR, f"{timestamp}_03_after_continue.png")
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
            log.info("Verificando se a página mudou para tela de código...")
        
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
            ss = os.path.join(LOG_DIR, f"{timestamp}_04_register.png")
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
            ss = os.path.join(LOG_DIR, f"{timestamp}_05_final.png")
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
        
        print(f"\n{C.CY}{C.BD}  LOGS GERADOS:{C.RS}")
        print(f"  {C.CY}  Principal:   {main_log_file}{C.RS}")
        print(f"  {C.CY}  HTTP:        {http_log_file}{C.RS}")
        print(f"  {C.CY}  Browser:     {browser_log_file}{C.RS}")
        print(f"  {C.CY}  Erros:       {error_log_file}{C.RS}")
        print(f"  {C.CY}  Credenciais: {creds_file}{C.RS}")
        print(f"  {C.CY}  Tokens:      {tokens_file}{C.RS}")
        print(f"  {C.CY}  API Dump:    {responses_file}{C.RS}")
        print()
        
        log.info("=" * 60)
        log.info(f"FINALIZADO em {elapsed_total}s | Status: {status}")
        log.info(f"Respostas API capturadas: {len(captured_data['all_responses'])}")
        log.info("=" * 60)
        
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
    print(f"{C.CY}[*] DISPLAY={os.environ.get('DISPLAY')}{C.RS}")
    print(f"{C.CY}[*] Iniciando V3...{C.RS}\n")
    
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
