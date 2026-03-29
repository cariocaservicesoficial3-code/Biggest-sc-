#!/usr/bin/env python3
"""
==============================================================
  MANUS ACCOUNT CREATOR - KALI LINUX NETHUNTER
  Emailnator + Playwright + Cloudflare Turnstile (Semi-Auto)
==============================================================

Fluxo:
1. Pede o link de convite do Manus
2. Gera Gmail temporário via Emailnator (dotGmail)
3. Gera senha forte no padrão aceito pelo Manus
4. Abre Playwright (headless=False) para resolver Turnstile
5. Faz o registro via API do Manus
6. Monitora Emailnator para capturar código de 6 dígitos
7. Envia o código de verificação
8. Seleciona Polônia na página de telefone
9. Salva logs e credenciais

Requisitos:
  pip3 install requests playwright rich
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
from datetime import datetime
from urllib.parse import unquote, urlparse, parse_qs

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
# CONFIGURAÇÃO DE LOGS
# ============================================================
log_filename = datetime.now().strftime('%Y-%m-%d_%H%M%S') + "_manus_creator.log"
log_path = os.path.join(os.path.expanduser("~"), log_filename)

file_handler = logging.FileHandler(log_path)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)

class ColorFmt(logging.Formatter):
    COLORS = {'DEBUG': C.CY, 'INFO': C.G, 'WARNING': C.Y, 'ERROR': C.R}
    def format(self, record):
        c = self.COLORS.get(record.levelname, C.W)
        record.msg = f"{c}{record.msg}{C.RS}"
        return super().format(record)

stream_handler.setFormatter(ColorFmt('%(asctime)s [%(levelname)s] %(message)s'))
logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, stream_handler])
log = logging.getLogger("MANUS")

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MANUS_API = "https://api.manus.im"
EMAILNATOR_URL = "https://www.emailnator.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"

# Proxy (mesmo do 2NR)
PROXY_HOST = "74.81.81.81"
PROXY_PORT = "823"
PROXY_USER = "be2c872545392337df6e__cr.br"
PROXY_PASS = "768df629c0304df6"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

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
    
    def _get_xsrf(self):
        """Extrai o token XSRF do cookie"""
        try:
            resp = self.session.get(EMAILNATOR_URL, timeout=15)
            for cookie in resp.cookies:
                if cookie.name == 'XSRF-TOKEN':
                    self.xsrf_token = unquote(cookie.value)
                    log.debug(f"XSRF-TOKEN obtido: {self.xsrf_token[:30]}...")
                    return True
            log.warning("XSRF-TOKEN não encontrado nos cookies")
            return False
        except Exception as e:
            log.error(f"Erro ao obter XSRF: {e}")
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
            resp = self.session.post(
                f"{EMAILNATOR_URL}/generate-email",
                headers=self._headers(),
                json={"email": ["dotGmail"]},
                timeout=15
            )
            
            log.debug(f"Generate email status: {resp.status_code}")
            log.debug(f"Generate email response: {resp.text[:300]}")
            
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
        """Verifica a caixa de entrada"""
        if not self.email:
            return None
        
        try:
            resp = self.session.post(
                f"{EMAILNATOR_URL}/message-list",
                headers=self._headers(),
                json={"email": self.email},
                timeout=15
            )
            
            # Se token expirou, renovar
            if resp.status_code == 419:
                log.debug("Token expirado (419), renovando...")
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
            log.error(f"Erro ao verificar inbox: {e}")
            return None
    
    def get_message(self, message_id):
        """Lê o conteúdo de uma mensagem específica"""
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
            log.error(f"Erro ao ler mensagem: {e}")
            return None
    
    def wait_for_code(self, sender_filter="manus", max_wait=180):
        """Monitora a caixa de entrada esperando um código de 6 dígitos"""
        log.info(f"Monitorando caixa de entrada: {self.email}")
        log.info(f"Filtro de remetente: {sender_filter}")
        log.info(f"Tempo máximo: {max_wait}s")
        
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
                log.debug(f"Mensagens na caixa: {len(messages)}")
                
                for msg in messages:
                    msg_id = msg.get('messageID')
                    sender = msg.get('from', '').lower()
                    subject = msg.get('subject', '')
                    
                    if msg_id and msg_id not in processed:
                        log.debug(f"  Nova msg - De: {sender} | Assunto: {subject}")
                        
                        if sender_filter.lower() in sender or sender_filter.lower() in subject.lower():
                            processed.add(msg_id)
                            log.info(f"E-MAIL DO MANUS DETECTADO! De: {sender}")
                            
                            content = self.get_message(msg_id)
                            if content:
                                log.debug(f"Conteúdo (primeiros 500): {content[:500]}")
                                
                                # Extrair código de 6 dígitos
                                codes = re.findall(r'\b(\d{6})\b', content)
                                if codes:
                                    code = codes[0]
                                    log.info(f"CÓDIGO DE VERIFICAÇÃO ENCONTRADO: {code}")
                                    return code
                                else:
                                    log.warning("Mensagem do Manus sem código de 6 dígitos")
                        
                        processed.add(msg_id)
            
            time.sleep(5)
        
        log.error(f"TIMEOUT: Nenhum código recebido em {max_wait}s")
        return None

# ============================================================
# GERADOR DE SENHA NO PADRÃO DO MANUS
# ============================================================
def generate_manus_password(length=20):
    """
    Gera senha no padrão aceito pelo Manus.
    Exemplo: OEBm0F4NL:Ja7'9r;#8P
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
    
    log.debug(f"Senha gerada: {password}")
    return password

# ============================================================
# FLUXO PRINCIPAL COM PLAYWRIGHT
# ============================================================
async def main():
    banner = f"""
{C.CY}{C.BD}
{'='*60}
   MANUS ACCOUNT CREATOR - KALI LINUX NETHUNTER
   Emailnator + Playwright + Turnstile (Semi-Auto)
{'='*60}
   Proxy: {PROXY_HOST}:{PROXY_PORT}
   Logs:  {log_path}
{'='*60}
{C.RS}"""
    print(banner)
    
    # ========================================
    # PASSO 0: PEDIR LINK DE CONVITE
    # ========================================
    print(f"{C.Y}{C.BD}[?] Cole o link de convite do Manus:{C.RS}")
    invite_url = input(f"{C.CY}    > {C.RS}").strip()
    
    if not invite_url:
        invite_url = "https://manus.im/invitation/OB746IYA9QIKG?utm_source=invitation&utm_medium=social&utm_campaign=system_share"
        log.warning(f"Nenhum link fornecido, usando padrão: {invite_url}")
    
    # Extrair código de convite
    invite_code = None
    if '/invitation/' in invite_url:
        parts = invite_url.split('/invitation/')
        if len(parts) > 1:
            invite_code = parts[1].split('?')[0].split('/')[0]
    
    if not invite_code:
        log.error("Não foi possível extrair o código de convite do link!")
        return
    
    log.info(f"Código de convite: {invite_code}")
    log.info(f"Link completo: {invite_url}")
    
    # ========================================
    # PASSO 1: GERAR GMAIL VIA EMAILNATOR
    # ========================================
    print(f"\n{C.G}{C.BD}{'='*60}")
    print(f"  ETAPA 1: GERANDO GMAIL TEMPORÁRIO")
    print(f"{'='*60}{C.RS}\n")
    
    emailnator = Emailnator()
    email = None
    
    for attempt in range(3):
        email = emailnator.generate_email()
        if email:
            break
        log.warning(f"Tentativa {attempt+1}/3 falhou, tentando novamente...")
        emailnator = Emailnator()  # Reset session
        time.sleep(2)
    
    if not email:
        log.error("FALHA: Não foi possível gerar Gmail temporário!")
        return
    
    print(f"{C.G}{C.BD}  Gmail gerado: {email}{C.RS}")
    
    # ========================================
    # PASSO 2: GERAR SENHA
    # ========================================
    password = generate_manus_password(20)
    print(f"{C.G}{C.BD}  Senha gerada: {password}{C.RS}")
    
    # ========================================
    # PASSO 3: ABRIR PLAYWRIGHT PARA TURNSTILE
    # ========================================
    print(f"\n{C.M}{C.BD}{'='*60}")
    print(f"  ETAPA 2: RESOLVENDO CLOUDFLARE TURNSTILE")
    print(f"{'='*60}{C.RS}\n")
    
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        # Lançar browser VISÍVEL para resolver Turnstile
        log.info("Iniciando Playwright (modo visível para Turnstile)...")
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 430, 'height': 932},
            locale='en-US',
        )
        
        # Remover detecção de automação
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            delete navigator.__proto__.webdriver;
        """)
        
        page = await context.new_page()
        
        # Variáveis para capturar dados
        captured_data = {
            'cf_token': None,
            'temp_token': None,
            'auth_token': None,
        }
        
        # Interceptar requisições para capturar tokens
        async def on_response(response):
            url = response.url
            try:
                if 'GetUserPlatforms' in url:
                    body = await response.text()
                    data = json.loads(body)
                    if data.get('tempToken'):
                        captured_data['temp_token'] = data['tempToken']
                        log.info(f"tempToken capturado: {data['tempToken']}")
                
                elif 'RegisterByEmail' in url:
                    body = await response.text()
                    data = json.loads(body)
                    if data.get('token'):
                        captured_data['auth_token'] = data['token']
                        log.info(f"Auth JWT Token capturado!")
                
                elif 'SendEmailVerifyCode' in url:
                    log.info("Código de verificação enviado pelo Manus!")
                    
            except:
                pass
        
        page.on("response", on_response)
        
        # Navegar para a página de login com o código de convite
        login_url = f"https://manus.im/login?code={invite_code}"
        log.info(f"Navegando para: {login_url}")
        
        try:
            await page.goto(login_url, wait_until="networkidle", timeout=60000)
        except:
            log.warning("Timeout ao carregar página, continuando...")
        
        await asyncio.sleep(3)
        
        # ========================================
        # PASSO 4: PREENCHER E-MAIL E RESOLVER TURNSTILE
        # ========================================
        print(f"\n{C.Y}{C.BD}{'='*60}")
        print(f"  ETAPA 3: PREENCHENDO FORMULÁRIO")
        print(f"{'='*60}{C.RS}\n")
        
        # Tentar encontrar e preencher o campo de e-mail
        log.info("Procurando campo de e-mail...")
        
        try:
            # Esperar o campo de e-mail aparecer
            email_input = await page.wait_for_selector(
                'input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="Email" i]',
                timeout=15000
            )
            
            if email_input:
                await email_input.fill(email)
                log.info(f"E-mail preenchido: {email}")
                await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"Campo de e-mail não encontrado automaticamente: {e}")
            log.info("Tentando via seletor alternativo...")
            try:
                inputs = await page.query_selector_all('input')
                for inp in inputs:
                    inp_type = await inp.get_attribute('type')
                    inp_placeholder = await inp.get_attribute('placeholder') or ''
                    if inp_type == 'email' or 'email' in inp_placeholder.lower():
                        await inp.fill(email)
                        log.info(f"E-mail preenchido via seletor alternativo")
                        break
            except:
                pass
        
        # Agora o usuário precisa resolver o Turnstile manualmente
        print(f"\n{C.Y}{C.BD}")
        print("!" * 60)
        print("!  RESOLVA O CAPTCHA TURNSTILE NO NAVEGADOR QUE ABRIU  !")
        print("!  Depois clique em 'Continue' / 'Sign Up'             !")
        print("!  O script vai capturar tudo automaticamente          !")
        print("!" * 60)
        print(f"{C.RS}\n")
        
        log.info("Aguardando resolução do Turnstile e envio do formulário...")
        log.info("O script está monitorando as requisições em segundo plano...")
        
        # Esperar até que o tempToken seja capturado (significa que o Turnstile foi resolvido)
        wait_start = time.time()
        max_turnstile_wait = 300  # 5 minutos
        
        while time.time() - wait_start < max_turnstile_wait:
            if captured_data['temp_token']:
                log.info("Turnstile resolvido! tempToken capturado!")
                break
            await asyncio.sleep(2)
        
        if not captured_data['temp_token']:
            log.error("TIMEOUT: Turnstile não foi resolvido em 5 minutos")
            await browser.close()
            return
        
        # ========================================
        # PASSO 5: ENVIAR CÓDIGO DE VERIFICAÇÃO
        # ========================================
        print(f"\n{C.B}{C.BD}{'='*60}")
        print(f"  ETAPA 4: ENVIANDO CÓDIGO DE VERIFICAÇÃO")
        print(f"{'='*60}{C.RS}\n")
        
        # Verificar se o Manus já enviou o código automaticamente
        # Se não, enviar manualmente via API
        import requests as req_lib
        
        if captured_data['temp_token']:
            log.info("Enviando solicitação de código de verificação via API...")
            
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
                
                log.debug(f"Payload SendCode: {json.dumps(send_code_payload, indent=2)}")
                
                resp = req_lib.post(
                    f"{MANUS_API}/user.v1.UserAuthPublicService/SendEmailVerifyCodeWithCaptcha",
                    json=send_code_payload,
                    headers=api_headers,
                    timeout=30
                )
                
                log.info(f"SendCode Status: {resp.status_code}")
                log.debug(f"SendCode Response: {resp.text[:300]}")
                
                if resp.status_code == 200:
                    log.info("CÓDIGO DE VERIFICAÇÃO ENVIADO COM SUCESSO!")
                else:
                    log.warning(f"Possível erro ao enviar código: {resp.status_code}")
                    
            except Exception as e:
                log.error(f"Erro ao enviar código: {e}")
        
        # ========================================
        # PASSO 6: MONITORAR EMAILNATOR PARA CÓDIGO
        # ========================================
        print(f"\n{C.CY}{C.BD}{'='*60}")
        print(f"  ETAPA 5: CAPTURANDO CÓDIGO DO E-MAIL")
        print(f"{'='*60}{C.RS}\n")
        
        verify_code = emailnator.wait_for_code(sender_filter="manus", max_wait=180)
        
        if not verify_code:
            log.warning("Código não capturado automaticamente.")
            print(f"\n{C.Y}[?] Digite o código de 6 dígitos manualmente:{C.RS}")
            verify_code = input(f"{C.CY}    > {C.RS}").strip()
        
        if not verify_code or len(verify_code) != 6:
            log.error("Código de verificação inválido!")
            await browser.close()
            return
        
        log.info(f"Código de verificação: {verify_code}")
        
        # ========================================
        # PASSO 7: COMPLETAR REGISTRO VIA API
        # ========================================
        print(f"\n{C.G}{C.BD}{'='*60}")
        print(f"  ETAPA 6: COMPLETANDO REGISTRO")
        print(f"{'='*60}{C.RS}\n")
        
        # Preencher o código no campo da página
        try:
            code_inputs = await page.query_selector_all('input[type="text"], input[type="number"], input[type="tel"]')
            
            # Se há múltiplos inputs (um por dígito)
            if len(code_inputs) >= 6:
                for idx, digit in enumerate(verify_code):
                    if idx < len(code_inputs):
                        await code_inputs[idx].fill(digit)
                        await asyncio.sleep(0.1)
                log.info("Código preenchido nos campos individuais")
            elif len(code_inputs) >= 1:
                # Input único para o código
                for inp in code_inputs:
                    placeholder = await inp.get_attribute('placeholder') or ''
                    if 'code' in placeholder.lower() or 'verif' in placeholder.lower() or 'digit' in placeholder.lower():
                        await inp.fill(verify_code)
                        log.info("Código preenchido no campo único")
                        break
            
            await asyncio.sleep(2)
            
        except Exception as e:
            log.warning(f"Erro ao preencher código na página: {e}")
            log.info("Tentando completar via API diretamente...")
        
        # Também enviar via API para garantir
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
            
            log.debug(f"Register Payload: {json.dumps(register_payload, indent=2)}")
            
            resp = req_lib.post(
                f"{MANUS_API}/user.v1.UserAuthPublicService/RegisterByEmail",
                json=register_payload,
                headers=api_headers,
                timeout=30
            )
            
            log.info(f"Register Status: {resp.status_code}")
            log.debug(f"Register Response: {resp.text[:500]}")
            
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
        
        # ========================================
        # PASSO 8: NAVEGAR ATÉ PÁGINA DE TELEFONE
        # ========================================
        print(f"\n{C.M}{C.BD}{'='*60}")
        print(f"  ETAPA 7: SELECIONANDO PAÍS (POLÔNIA)")
        print(f"{'='*60}{C.RS}\n")
        
        # Esperar a página de telefone carregar
        await asyncio.sleep(5)
        
        try:
            # Verificar se estamos na página de telefone
            current_url = page.url
            log.info(f"URL atual: {current_url}")
            
            # Tentar encontrar o seletor de país
            # Procurar por dropdown de país ou campo de telefone
            country_selectors = [
                'select[name*="country"]',
                'select[name*="phone"]',
                '[class*="country"]',
                '[class*="phone"]',
                'button[class*="country"]',
                '[data-testid*="country"]',
            ]
            
            for selector in country_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        log.info(f"Seletor de país encontrado: {selector}")
                        await element.click()
                        await asyncio.sleep(1)
                        
                        # Procurar por "Poland" ou "Polska" na lista
                        poland = await page.query_selector('text=Poland')
                        if not poland:
                            poland = await page.query_selector('text=Polska')
                        if not poland:
                            poland = await page.query_selector('text=+48')
                        
                        if poland:
                            await poland.click()
                            log.info("POLÔNIA SELECIONADA COM SUCESSO!")
                        break
                except:
                    continue
            
            # Se não encontrou automaticamente, tentar via texto
            try:
                # Procurar qualquer elemento com "Poland"
                await page.get_by_text("Poland", exact=False).first.click()
                log.info("Polônia selecionada via texto!")
            except:
                log.info("Seletor de país pode precisar de interação manual")
                log.info("O navegador está aberto para você completar se necessário")
            
        except Exception as e:
            log.warning(f"Erro ao selecionar país: {e}")
        
        # ========================================
        # RESULTADO FINAL
        # ========================================
        print(f"\n{C.G}{C.BD}")
        print("*" * 60)
        print("   PROCESSO FINALIZADO!")
        print("*" * 60)
        print(f"   Gmail:    {email}")
        print(f"   Senha:    {password}")
        print(f"   Convite:  {invite_code}")
        print(f"   Código:   {verify_code}")
        if captured_data['auth_token']:
            print(f"   Token:    {captured_data['auth_token'][:50]}...")
            print(f"   Status:   CONTA CRIADA COM SUCESSO!")
        else:
            print(f"   Status:   Verifique o navegador para completar")
        print("*" * 60)
        print(f"{C.RS}\n")
        
        # Salvar credenciais
        creds_file = os.path.join(os.path.expanduser("~"), "manus_credentials.txt")
        with open(creds_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {email} | {password} | {invite_code} | {verify_code}\n")
        log.info(f"Credenciais salvas em: {creds_file}")
        
        # Salvar token JWT se capturado
        if captured_data['auth_token']:
            token_file = os.path.join(os.path.expanduser("~"), "manus_tokens.txt")
            with open(token_file, "a") as f:
                f.write(f"{datetime.now().isoformat()} | {email} | {captured_data['auth_token']}\n")
            log.info(f"Token JWT salvo em: {token_file}")
        
        print(f"{C.Y}[*] O navegador permanecerá aberto para você completar a etapa do telefone se necessário.")
        print(f"[*] Pressione ENTER para fechar o navegador e encerrar.{C.RS}")
        input()
        
        await browser.close()
    
    print(f"\n{C.CY}[*] Logs detalhados salvos em: {log_path}{C.RS}")

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    asyncio.run(main())
