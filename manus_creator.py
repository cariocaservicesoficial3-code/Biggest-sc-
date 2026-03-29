#!/usr/bin/env python3
"""
==============================================================
  MANUS ACCOUNT CREATOR V2 - KALI LINUX NETHUNTER + KeX VNC
  Emailnator + Playwright + Cloudflare Turnstile (Semi-Auto)
  
  FIX: DISPLAY=:1 para VNC/KeX
  FIX: Logs completos em /root/
  FIX: Chromium abre visível no desktop KeX
==============================================================

Fluxo:
1. Pede o link de convite do Manus
2. Gera Gmail temporário via Emailnator (dotGmail)
3. Gera senha forte no padrão aceito pelo Manus
4. Abre Playwright (headless=False) no display VNC
5. Faz o registro via API do Manus
6. Monitora Emailnator para capturar código de 6 dígitos
7. Envia o código de verificação
8. Seleciona Polônia na página de telefone
9. Salva logs e credenciais em /root/

Requisitos:
  export DISPLAY=:1
  pip3 install requests playwright rich
  playwright install chromium
  playwright install-deps chromium
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
from urllib.parse import unquote, urlparse, parse_qs

# ============================================================
# FIX CRÍTICO: SETAR DISPLAY PARA VNC/KeX
# ============================================================
os.environ['DISPLAY'] = ':1'

# ============================================================
# CORES PARA O TERMINAL
# ============================================================
class C:
    R = '\033[91m'    # Red
    G = '\033[92m'    # Green
    Y = '\033[93m'    # Yellow
    B = '\033[94m'    # Blue
    M = '\033[95m'    # Magenta
    CY = '\033[96m'   # Cyan
    W = '\033[97m'    # White
    BD = '\033[1m'    # Bold
    RS = '\033[0m'    # Reset

# ============================================================
# CONFIGURAÇÃO DE LOGS - TUDO EM /root/
# ============================================================
LOG_DIR = "/root"
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')

# Log principal do script
main_log_file = os.path.join(LOG_DIR, f"{timestamp}_manus_creator.log")

# Log de requisições HTTP
http_log_file = os.path.join(LOG_DIR, f"{timestamp}_manus_http.log")

# Log de eventos do Playwright/Browser
browser_log_file = os.path.join(LOG_DIR, f"{timestamp}_manus_browser.log")

# Log de credenciais criadas
creds_file = os.path.join(LOG_DIR, "manus_credentials.log")

# Log de tokens JWT
tokens_file = os.path.join(LOG_DIR, "manus_tokens.log")

# Log de erros
error_log_file = os.path.join(LOG_DIR, f"{timestamp}_manus_errors.log")

# Configurar logger principal
class ColorFmt(logging.Formatter):
    COLORS = {'DEBUG': C.CY, 'INFO': C.G, 'WARNING': C.Y, 'ERROR': C.R, 'CRITICAL': C.R}
    def format(self, record):
        c = self.COLORS.get(record.levelname, C.W)
        record.msg = f"{c}{record.msg}{C.RS}"
        return super().format(record)

# Logger principal
log = logging.getLogger("MANUS")
log.setLevel(logging.DEBUG)

# Handler: arquivo principal (tudo)
fh_main = logging.FileHandler(main_log_file, encoding='utf-8')
fh_main.setLevel(logging.DEBUG)
fh_main.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s'))
log.addHandler(fh_main)

# Handler: arquivo de erros (só erros)
fh_error = logging.FileHandler(error_log_file, encoding='utf-8')
fh_error.setLevel(logging.ERROR)
fh_error.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s\n%(pathname)s:%(lineno)d'))
log.addHandler(fh_error)

# Handler: terminal colorido
sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.DEBUG)
sh.setFormatter(ColorFmt('%(asctime)s [%(levelname)s] %(message)s'))
log.addHandler(sh)

# Logger HTTP separado
http_log = logging.getLogger("HTTP")
http_log.setLevel(logging.DEBUG)
fh_http = logging.FileHandler(http_log_file, encoding='utf-8')
fh_http.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
http_log.addHandler(fh_http)
http_log.addHandler(fh_main)  # Também vai pro log principal

# Logger Browser separado
browser_log = logging.getLogger("BROWSER")
browser_log.setLevel(logging.DEBUG)
fh_browser = logging.FileHandler(browser_log_file, encoding='utf-8')
fh_browser.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
browser_log.addHandler(fh_browser)
browser_log.addHandler(fh_main)  # Também vai pro log principal

def log_separator(title):
    """Imprime separador visual no log"""
    sep = "=" * 60
    log.info(sep)
    log.info(f"  {title}")
    log.info(sep)

def log_to_file(filepath, content):
    """Escreve conteúdo direto em um arquivo de log"""
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().isoformat()}] {content}\n")

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MANUS_API = "https://api.manus.im"
EMAILNATOR_URL = "https://www.emailnator.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"

# Proxy
PROXY_HOST = "74.81.81.81"
PROXY_PORT = "823"
PROXY_USER = "be2c872545392337df6e__cr.br"
PROXY_PASS = "768df629c0304df6"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

# Código de convite padrão
DEFAULT_INVITE = "OB746IYA9QIKG"

# ============================================================
# EMAILNATOR CLIENT
# ============================================================
class Emailnator:
    """Cliente para gerar Gmail temporário e monitorar caixa de entrada via Emailnator"""
    
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
        """Extrai o token XSRF do cookie"""
        try:
            http_log.info(f"GET {EMAILNATOR_URL} (obtendo XSRF token)")
            resp = self.session.get(EMAILNATOR_URL, timeout=15)
            http_log.info(f"  Status: {resp.status_code}")
            http_log.debug(f"  Cookies: {dict(resp.cookies)}")
            
            for cookie in resp.cookies:
                if cookie.name == 'XSRF-TOKEN':
                    self.xsrf_token = unquote(cookie.value)
                    http_log.info(f"  XSRF-TOKEN obtido: {self.xsrf_token[:40]}...")
                    return True
            
            http_log.warning("  XSRF-TOKEN não encontrado nos cookies")
            return False
        except Exception as e:
            http_log.error(f"  Erro ao obter XSRF: {e}")
            log.error(f"Emailnator XSRF falhou: {e}")
            return False
    
    def _headers(self):
        """Headers padrão para requisições ao Emailnator"""
        return {
            'Content-Type': 'application/json',
            'Origin': EMAILNATOR_URL,
            'Referer': f'{EMAILNATOR_URL}/',
            'User-Agent': USER_AGENT,
            'X-Requested-With': 'XMLHttpRequest',
            'X-XSRF-TOKEN': self.xsrf_token,
        }
    
    def generate_email(self):
        """Gera um Gmail temporário com pontos aleatórios (dotGmail)"""
        if not self._get_xsrf():
            return None
        
        try:
            payload = {"email": ["dotGmail"]}
            http_log.info(f"POST {EMAILNATOR_URL}/generate-email")
            http_log.debug(f"  Payload: {json.dumps(payload)}")
            
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
                    log.info(f"Gmail gerado com sucesso: {self.email}")
                    return self.email
            
            log.error(f"Falha ao gerar email. Status: {resp.status_code}")
            return None
        except Exception as e:
            log.error(f"Erro ao gerar email: {e}")
            log.error(traceback.format_exc())
            return None
    
    def get_inbox(self):
        """Verifica a caixa de entrada"""
        if not self.email:
            return None
        
        try:
            payload = {"email": self.email}
            http_log.debug(f"POST {EMAILNATOR_URL}/message-list | email={self.email}")
            
            resp = self.session.post(
                f"{EMAILNATOR_URL}/message-list",
                headers=self._headers(),
                json=payload,
                timeout=15
            )
            
            # Se token expirou, renovar
            if resp.status_code == 419:
                http_log.warning("  Token expirado (419), renovando XSRF...")
                self._get_xsrf()
                resp = self.session.post(
                    f"{EMAILNATOR_URL}/message-list",
                    headers=self._headers(),
                    json=payload,
                    timeout=15
                )
            
            http_log.debug(f"  Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                http_log.debug(f"  Mensagens encontradas: {len(data.get('messageData', []))}")
                return data
            return None
        except Exception as e:
            http_log.error(f"  Erro inbox: {e}")
            return None
    
    def get_message(self, message_id):
        """Lê o conteúdo de uma mensagem específica"""
        try:
            payload = {"email": self.email, "messageID": message_id}
            http_log.info(f"POST {EMAILNATOR_URL}/message-list (msg: {message_id})")
            
            resp = self.session.post(
                f"{EMAILNATOR_URL}/message-list",
                headers=self._headers(),
                json=payload,
                timeout=15
            )
            
            http_log.info(f"  Status: {resp.status_code}")
            http_log.debug(f"  Body (500 chars): {resp.text[:500]}")
            
            if resp.status_code == 200:
                return resp.text
            return None
        except Exception as e:
            http_log.error(f"  Erro ao ler mensagem: {e}")
            return None
    
    def wait_for_code(self, sender_filter="manus", max_wait=180):
        """Monitora a caixa de entrada esperando um código de 6 dígitos"""
        log.info(f"Monitorando inbox: {self.email}")
        log.info(f"Filtro remetente: {sender_filter} | Timeout: {max_wait}s")
        
        start = time.time()
        processed = set()
        attempt = 0
        
        while time.time() - start < max_wait:
            attempt += 1
            elapsed = int(time.time() - start)
            log.info(f"Verificação #{attempt} ({elapsed}s/{max_wait}s)...")
            
            inbox = self.get_inbox()
            if inbox and 'messageData' in inbox:
                messages = inbox['messageData']
                log.debug(f"  Total mensagens: {len(messages)}")
                
                for msg in messages:
                    msg_id = msg.get('messageID')
                    sender = msg.get('from', '').lower()
                    subject = msg.get('subject', '')
                    
                    if msg_id and msg_id not in processed:
                        log.info(f"  Nova msg - De: {sender} | Assunto: {subject}")
                        log_to_file(main_log_file, f"EMAIL RECEBIDO: from={sender} subject={subject} id={msg_id}")
                        
                        if sender_filter.lower() in sender or sender_filter.lower() in subject.lower():
                            processed.add(msg_id)
                            log.info(f"  >>> E-MAIL DO MANUS DETECTADO! De: {sender}")
                            
                            content = self.get_message(msg_id)
                            if content:
                                log_to_file(main_log_file, f"EMAIL CONTEUDO COMPLETO:\n{content[:2000]}")
                                
                                # Extrair código de 6 dígitos
                                codes = re.findall(r'\b(\d{6})\b', content)
                                if codes:
                                    code = codes[0]
                                    log.info(f"  >>> CÓDIGO ENCONTRADO: {code}")
                                    return code
                                else:
                                    log.warning("  Mensagem do Manus sem código de 6 dígitos")
                        
                        processed.add(msg_id)
            
            time.sleep(5)
        
        log.error(f"TIMEOUT: Nenhum código recebido em {max_wait}s")
        return None

# ============================================================
# GERADOR DE SENHA NO PADRÃO DO MANUS
# ============================================================
def generate_manus_password(length=20):
    """
    Gera senha forte aceita pelo Manus.
    Inclui: maiúsculas, minúsculas, números, especiais variados
    """
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
# FLUXO PRINCIPAL COM PLAYWRIGHT
# ============================================================
async def main():
    start_time = time.time()
    
    banner = f"""
{C.CY}{C.BD}
{'='*60}
   MANUS ACCOUNT CREATOR V2 - KALI NETHUNTER + KeX
   Emailnator + Playwright + Turnstile (Semi-Auto)
{'='*60}
   DISPLAY:  {os.environ.get('DISPLAY', 'NÃO DEFINIDO')}
   Proxy:    {PROXY_HOST}:{PROXY_PORT}
   Log Dir:  {LOG_DIR}
   Log File: {main_log_file}
{'='*60}
{C.RS}"""
    print(banner)
    
    log.info("=" * 60)
    log.info("MANUS ACCOUNT CREATOR V2 INICIADO")
    log.info(f"DISPLAY={os.environ.get('DISPLAY')}")
    log.info(f"Python={sys.version}")
    log.info(f"Proxy={PROXY_HOST}:{PROXY_PORT}")
    log.info(f"Timestamp={timestamp}")
    log.info("=" * 60)
    
    # ========================================
    # PASSO 0: PEDIR LINK DE CONVITE
    # ========================================
    log_separator("ETAPA 0: LINK DE CONVITE")
    
    print(f"{C.Y}{C.BD}[?] Cole o link de convite do Manus (ou ENTER para usar padrão):{C.RS}")
    invite_url = input(f"{C.CY}    > {C.RS}").strip()
    
    if not invite_url:
        invite_url = f"https://manus.im/invitation/{DEFAULT_INVITE}?utm_source=invitation&utm_medium=social&utm_campaign=system_share"
        log.warning(f"Usando link padrão: {invite_url}")
    
    # Extrair código de convite
    invite_code = None
    if '/invitation/' in invite_url:
        parts = invite_url.split('/invitation/')
        if len(parts) > 1:
            invite_code = parts[1].split('?')[0].split('/')[0]
    
    if not invite_code:
        log.error("Não foi possível extrair o código de convite!")
        return
    
    log.info(f"Código de convite: {invite_code}")
    log.info(f"Link completo: {invite_url}")
    
    # ========================================
    # PASSO 1: GERAR GMAIL VIA EMAILNATOR
    # ========================================
    log_separator("ETAPA 1: GERANDO GMAIL TEMPORÁRIO")
    
    emailnator = Emailnator()
    email = None
    
    for attempt in range(3):
        log.info(f"Tentativa {attempt+1}/3 de gerar Gmail...")
        email = emailnator.generate_email()
        if email:
            break
        log.warning(f"Tentativa {attempt+1}/3 falhou, resetando sessão...")
        emailnator = Emailnator()
        time.sleep(2)
    
    if not email:
        log.error("FALHA CRÍTICA: Não foi possível gerar Gmail temporário!")
        log.error("Verifique sua conexão ou tente novamente mais tarde.")
        return
    
    print(f"\n{C.G}{C.BD}  [OK] Gmail: {email}{C.RS}")
    
    # ========================================
    # PASSO 2: GERAR SENHA
    # ========================================
    log_separator("ETAPA 2: GERANDO SENHA")
    
    password = generate_manus_password(20)
    print(f"{C.G}{C.BD}  [OK] Senha: {password}{C.RS}")
    
    # Salvar credenciais parciais já
    log_to_file(creds_file, f"INICIO | email={email} | senha={password} | convite={invite_code}")
    
    # ========================================
    # PASSO 3: ABRIR PLAYWRIGHT NO VNC
    # ========================================
    log_separator("ETAPA 3: ABRINDO CHROMIUM NO DESKTOP KeX")
    
    log.info(f"Verificando DISPLAY: {os.environ.get('DISPLAY')}")
    
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        log.info("Playwright inicializado, lançando Chromium...")
        browser_log.info("Lançando Chromium com headless=False no DISPLAY=:1")
        
        try:
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-gpu',
                    '--window-size=1280,720',
                    '--window-position=0,0',
                ]
            )
            browser_log.info("Chromium lançado com sucesso!")
            log.info("Chromium aberto no desktop KeX!")
        except Exception as e:
            log.error(f"FALHA ao lançar Chromium: {e}")
            log.error(traceback.format_exc())
            log.error("")
            log.error("DICA: Verifique se o VNC está rodando:")
            log.error("  vncserver :1 -geometry 1280x720 -depth 24")
            log.error("  export DISPLAY=:1")
            return
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1200, 'height': 680},
            locale='en-US',
        )
        browser_log.info("Contexto do browser criado")
        
        # Remover detecção de automação
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            delete navigator.__proto__.webdriver;
        """)
        browser_log.info("Anti-detecção de automação aplicada")
        
        page = await context.new_page()
        browser_log.info("Nova página criada")
        
        # Variáveis para capturar dados
        captured_data = {
            'cf_token': None,
            'temp_token': None,
            'auth_token': None,
            'all_responses': [],
        }
        
        # Interceptar TODAS as requisições para log completo
        async def on_request(request):
            http_log.debug(f">>> REQUEST: {request.method} {request.url}")
            if request.post_data:
                http_log.debug(f"    Body: {request.post_data[:500]}")
        
        async def on_response(response):
            url = response.url
            status = response.status
            http_log.debug(f"<<< RESPONSE: {status} {url}")
            
            try:
                if 'manus.im' in url or 'api.manus' in url:
                    body = await response.text()
                    http_log.info(f"  MANUS API Response: {body[:500]}")
                    captured_data['all_responses'].append({
                        'url': url,
                        'status': status,
                        'body': body[:2000],
                        'time': datetime.now().isoformat()
                    })
                    
                    try:
                        data = json.loads(body)
                    except:
                        data = {}
                    
                    if 'GetUserPlatforms' in url:
                        if data.get('tempToken'):
                            captured_data['temp_token'] = data['tempToken']
                            log.info(f">>> tempToken CAPTURADO: {data['tempToken'][:50]}...")
                            browser_log.info(f"tempToken capturado via GetUserPlatforms")
                    
                    elif 'RegisterByEmail' in url:
                        if data.get('token'):
                            captured_data['auth_token'] = data['token']
                            log.info(f">>> Auth JWT Token CAPTURADO!")
                            browser_log.info(f"JWT Token capturado via RegisterByEmail")
                    
                    elif 'SendEmailVerifyCode' in url:
                        log.info(">>> Código de verificação ENVIADO pelo Manus!")
                        browser_log.info("SendEmailVerifyCode chamado com sucesso")
                        
            except Exception as e:
                pass
        
        page.on("request", on_request)
        page.on("response", on_response)
        
        # Log de console do browser
        page.on("console", lambda msg: browser_log.debug(f"CONSOLE [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: browser_log.error(f"PAGE ERROR: {err}"))
        
        # Navegar para a página de login
        login_url = f"https://manus.im/login?code={invite_code}"
        log.info(f"Navegando para: {login_url}")
        browser_log.info(f"Navegando: {login_url}")
        
        try:
            await page.goto(login_url, wait_until="networkidle", timeout=60000)
            browser_log.info(f"Página carregada. URL: {page.url}")
        except Exception as e:
            log.warning(f"Timeout ao carregar página (normal): {e}")
            browser_log.warning(f"Timeout na navegação: {e}")
        
        await asyncio.sleep(3)
        
        # Screenshot da página
        try:
            ss_path = os.path.join(LOG_DIR, f"{timestamp}_screenshot_01_login.png")
            await page.screenshot(path=ss_path)
            browser_log.info(f"Screenshot salvo: {ss_path}")
        except:
            pass
        
        # ========================================
        # PASSO 4: PREENCHER E-MAIL
        # ========================================
        log_separator("ETAPA 4: PREENCHENDO E-MAIL")
        
        email_filled = False
        try:
            email_input = await page.wait_for_selector(
                'input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="Email" i]',
                timeout=15000
            )
            
            if email_input:
                await email_input.fill(email)
                email_filled = True
                log.info(f"E-mail preenchido: {email}")
                browser_log.info(f"Campo de email encontrado e preenchido: {email}")
                await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"Campo de e-mail não encontrado pelo seletor principal: {e}")
            browser_log.warning(f"Seletor principal falhou: {e}")
            
            try:
                inputs = await page.query_selector_all('input')
                browser_log.debug(f"Total de inputs na página: {len(inputs)}")
                for i, inp in enumerate(inputs):
                    inp_type = await inp.get_attribute('type') or ''
                    inp_placeholder = await inp.get_attribute('placeholder') or ''
                    inp_name = await inp.get_attribute('name') or ''
                    browser_log.debug(f"  Input #{i}: type={inp_type} placeholder={inp_placeholder} name={inp_name}")
                    
                    if inp_type == 'email' or 'email' in inp_placeholder.lower() or 'email' in inp_name.lower():
                        await inp.fill(email)
                        email_filled = True
                        log.info(f"E-mail preenchido via seletor alternativo (input #{i})")
                        break
            except Exception as e2:
                log.error(f"Falha total ao preencher email: {e2}")
        
        if not email_filled:
            log.warning("E-mail NÃO foi preenchido automaticamente!")
            log.warning("Preencha manualmente no navegador que abriu no desktop KeX")
            print(f"\n{C.Y}{C.BD}  [!] PREENCHA O E-MAIL MANUALMENTE NO NAVEGADOR: {email}{C.RS}\n")
        
        # ========================================
        # PASSO 5: AGUARDAR TURNSTILE
        # ========================================
        log_separator("ETAPA 5: AGUARDANDO RESOLUÇÃO DO TURNSTILE")
        
        print(f"\n{C.Y}{C.BD}")
        print("!" * 60)
        print("!                                                          !")
        print("!  RESOLVA O CAPTCHA TURNSTILE NO NAVEGADOR KeX            !")
        print("!  Depois clique em 'Continue' / 'Sign Up'                 !")
        print("!  O script captura tudo automaticamente!                   !")
        print("!                                                          !")
        print("!" * 60)
        print(f"{C.RS}\n")
        
        log.info("Aguardando resolução manual do Turnstile no desktop KeX...")
        log.info("O script está monitorando todas as requisições em segundo plano...")
        
        wait_start = time.time()
        max_turnstile_wait = 300  # 5 minutos
        dots = 0
        
        while time.time() - wait_start < max_turnstile_wait:
            if captured_data['temp_token']:
                log.info(">>> TURNSTILE RESOLVIDO! tempToken capturado!")
                break
            
            dots += 1
            elapsed = int(time.time() - wait_start)
            if dots % 5 == 0:
                log.info(f"  Aguardando Turnstile... ({elapsed}s/{max_turnstile_wait}s)")
                
                # Screenshot periódico
                try:
                    ss_path = os.path.join(LOG_DIR, f"{timestamp}_screenshot_waiting_{elapsed}s.png")
                    await page.screenshot(path=ss_path)
                except:
                    pass
            
            await asyncio.sleep(2)
        
        if not captured_data['temp_token']:
            log.error(f"TIMEOUT: Turnstile não resolvido em {max_turnstile_wait}s")
            
            # Salvar screenshot final
            try:
                ss_path = os.path.join(LOG_DIR, f"{timestamp}_screenshot_timeout.png")
                await page.screenshot(path=ss_path)
            except:
                pass
            
            await browser.close()
            return
        
        # Screenshot pós-Turnstile
        try:
            ss_path = os.path.join(LOG_DIR, f"{timestamp}_screenshot_02_turnstile_ok.png")
            await page.screenshot(path=ss_path)
            browser_log.info(f"Screenshot pós-Turnstile: {ss_path}")
        except:
            pass
        
        # ========================================
        # PASSO 6: ENVIAR CÓDIGO DE VERIFICAÇÃO
        # ========================================
        log_separator("ETAPA 6: ENVIANDO CÓDIGO DE VERIFICAÇÃO")
        
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
                
                http_log.info(f"POST {MANUS_API}/user.v1.UserAuthPublicService/SendEmailVerifyCodeWithCaptcha")
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
                    log.info("CÓDIGO DE VERIFICAÇÃO ENVIADO COM SUCESSO!")
                else:
                    log.warning(f"Possível erro ao enviar código: {resp.status_code}")
                    log.warning(f"Resposta: {resp.text[:300]}")
                    
            except Exception as e:
                log.error(f"Erro ao enviar código: {e}")
                log.error(traceback.format_exc())
        
        # ========================================
        # PASSO 7: CAPTURAR CÓDIGO DO E-MAIL
        # ========================================
        log_separator("ETAPA 7: CAPTURANDO CÓDIGO DO E-MAIL")
        
        verify_code = emailnator.wait_for_code(sender_filter="manus", max_wait=180)
        
        if not verify_code:
            log.warning("Código não capturado automaticamente via Emailnator.")
            print(f"\n{C.Y}[?] Digite o código de 6 dígitos manualmente:{C.RS}")
            verify_code = input(f"{C.CY}    > {C.RS}").strip()
        
        if not verify_code or len(verify_code) != 6:
            log.error(f"Código de verificação inválido: '{verify_code}'")
            await browser.close()
            return
        
        log.info(f"Código de verificação: {verify_code}")
        
        # ========================================
        # PASSO 8: COMPLETAR REGISTRO
        # ========================================
        log_separator("ETAPA 8: COMPLETANDO REGISTRO VIA API")
        
        # Preencher código na página
        try:
            code_inputs = await page.query_selector_all('input[type="text"], input[type="number"], input[type="tel"]')
            browser_log.info(f"Inputs para código encontrados: {len(code_inputs)}")
            
            if len(code_inputs) >= 6:
                for idx, digit in enumerate(verify_code):
                    if idx < len(code_inputs):
                        await code_inputs[idx].fill(digit)
                        await asyncio.sleep(0.1)
                log.info("Código preenchido nos campos individuais da página")
            elif len(code_inputs) >= 1:
                for inp in code_inputs:
                    placeholder = await inp.get_attribute('placeholder') or ''
                    if 'code' in placeholder.lower() or 'verif' in placeholder.lower() or 'digit' in placeholder.lower():
                        await inp.fill(verify_code)
                        log.info("Código preenchido no campo único")
                        break
            
            await asyncio.sleep(2)
        except Exception as e:
            log.warning(f"Erro ao preencher código na página: {e}")
        
        # Enviar registro via API
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
            
            http_log.info(f"POST {MANUS_API}/user.v1.UserAuthPublicService/RegisterByEmail")
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
                    log.info("REGISTRO CONCLUÍDO COM SUCESSO! JWT Token recebido!")
                else:
                    log.warning(f"Resposta 200 mas sem token: {resp.text[:200]}")
            else:
                log.error(f"Erro no registro: {resp.status_code} - {resp.text[:300]}")
                
        except Exception as e:
            log.error(f"Erro ao registrar via API: {e}")
            log.error(traceback.format_exc())
        
        # Screenshot pós-registro
        try:
            ss_path = os.path.join(LOG_DIR, f"{timestamp}_screenshot_03_register.png")
            await page.screenshot(path=ss_path)
        except:
            pass
        
        # ========================================
        # PASSO 9: SELECIONAR POLÔNIA
        # ========================================
        log_separator("ETAPA 9: SELECIONANDO PAÍS (POLÔNIA +48)")
        
        await asyncio.sleep(5)
        
        try:
            current_url = page.url
            log.info(f"URL atual: {current_url}")
            browser_log.info(f"URL pós-registro: {current_url}")
            
            country_selectors = [
                'select[name*="country"]',
                'select[name*="phone"]',
                '[class*="country"]',
                '[class*="phone"]',
                'button[class*="country"]',
                '[data-testid*="country"]',
            ]
            
            found_country = False
            for selector in country_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        browser_log.info(f"Seletor de país encontrado: {selector}")
                        await element.click()
                        await asyncio.sleep(1)
                        
                        poland = await page.query_selector('text=Poland')
                        if not poland:
                            poland = await page.query_selector('text=Polska')
                        if not poland:
                            poland = await page.query_selector('text=+48')
                        
                        if poland:
                            await poland.click()
                            log.info("POLÔNIA SELECIONADA COM SUCESSO!")
                            found_country = True
                        break
                except:
                    continue
            
            if not found_country:
                try:
                    await page.get_by_text("Poland", exact=False).first.click()
                    log.info("Polônia selecionada via texto!")
                    found_country = True
                except:
                    log.info("Seletor de país precisa de interação manual no KeX")
            
        except Exception as e:
            log.warning(f"Erro ao selecionar país: {e}")
        
        # Screenshot final
        try:
            ss_path = os.path.join(LOG_DIR, f"{timestamp}_screenshot_04_final.png")
            await page.screenshot(path=ss_path)
            browser_log.info(f"Screenshot final: {ss_path}")
        except:
            pass
        
        # ========================================
        # RESULTADO FINAL
        # ========================================
        elapsed_total = int(time.time() - start_time)
        
        log_separator("RESULTADO FINAL")
        
        print(f"\n{C.G}{C.BD}")
        print("*" * 60)
        print("   PROCESSO FINALIZADO!")
        print("*" * 60)
        print(f"   Gmail:      {email}")
        print(f"   Senha:      {password}")
        print(f"   Convite:    {invite_code}")
        print(f"   Código:     {verify_code}")
        print(f"   Tempo:      {elapsed_total}s")
        if captured_data['auth_token']:
            print(f"   Token:      {captured_data['auth_token'][:50]}...")
            print(f"   Status:     CONTA CRIADA COM SUCESSO!")
        else:
            print(f"   Status:     Verifique o navegador para completar")
        print("*" * 60)
        print(f"{C.RS}\n")
        
        # Salvar credenciais finais
        status = "SUCESSO" if captured_data['auth_token'] else "PENDENTE"
        log_to_file(creds_file, f"{status} | email={email} | senha={password} | convite={invite_code} | codigo={verify_code} | tempo={elapsed_total}s")
        log.info(f"Credenciais salvas em: {creds_file}")
        
        # Salvar token JWT
        if captured_data['auth_token']:
            log_to_file(tokens_file, f"email={email} | token={captured_data['auth_token']}")
            log.info(f"Token JWT salvo em: {tokens_file}")
        
        # Salvar dump completo de todas as respostas capturadas
        responses_file = os.path.join(LOG_DIR, f"{timestamp}_manus_api_responses.json")
        with open(responses_file, 'w', encoding='utf-8') as f:
            json.dump(captured_data['all_responses'], f, indent=2, ensure_ascii=False)
        log.info(f"Dump de respostas API salvo em: {responses_file}")
        
        # Resumo dos logs
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
        log.info(f"EXECUÇÃO FINALIZADA em {elapsed_total}s")
        log.info(f"Total de respostas API capturadas: {len(captured_data['all_responses'])}")
        log.info("=" * 60)
        
        print(f"{C.Y}[*] O navegador permanecerá aberto no KeX.")
        print(f"[*] Pressione ENTER para fechar e encerrar.{C.RS}")
        input()
        
        await browser.close()

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    print(f"{C.CY}[*] Verificando DISPLAY...{C.RS}")
    display = os.environ.get('DISPLAY')
    if not display:
        os.environ['DISPLAY'] = ':1'
        print(f"{C.Y}[!] DISPLAY não definido, setando para :1{C.RS}")
    else:
        print(f"{C.G}[OK] DISPLAY={display}{C.RS}")
    
    print(f"{C.CY}[*] Iniciando Manus Account Creator V2...{C.RS}\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C.Y}[!] Interrompido pelo usuário (Ctrl+C){C.RS}")
    except Exception as e:
        print(f"\n{C.R}[ERRO FATAL] {e}{C.RS}")
        traceback.print_exc()
        
        # Salvar erro fatal no log
        error_file = os.path.join(LOG_DIR, f"FATAL_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        with open(error_file, 'w') as f:
            f.write(f"ERRO FATAL: {e}\n\n")
            f.write(traceback.format_exc())
        print(f"{C.Y}[*] Erro salvo em: {error_file}{C.RS}")
