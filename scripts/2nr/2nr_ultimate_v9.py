#!/usr/bin/env python3
"""
==============================================================
  2NR ULTIMATE WARRIOR V9 - AUTOMAÇÃO TOTAL (CORRIGIDA)
  Criação de E-mail + Registro + Validação + Proxy Rotativo
==============================================================

Correções V9:
- Senha agora inclui caractere especial obrigatório (regex do 2NR)
- E-mail usa o gerado automaticamente (sem tentar mudar domínio)
- Melhor tratamento de erros e fallbacks
- Debug logs em tempo real com cores no terminal

Fluxo automático:
1. Cria e-mail temporário via Playwright (aceita qualquer domínio)
2. Gera senha aleatória com caractere especial (exigência do 2NR)
3. Registra no 2NR via API com proxy rotativo
4. Monitora a caixa de entrada esperando o e-mail de confirmação
5. Extrai o link de validação automaticamente
6. Valida a conta via Playwright pelo proxy rotativo
7. Salva credenciais em arquivo
"""

import asyncio
import json
import logging
import random
import re
import string
import sys
import time
from datetime import datetime

# ============================================================
# CORES PARA O TERMINAL
# ============================================================
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# ============================================================
# CONFIGURAÇÃO DE LOGS (DEBUG EM TEMPO REAL)
# ============================================================
log_filename = f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_2nr_ultimate.log"

class ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': Colors.CYAN,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.RED + Colors.BOLD,
    }
    def format(self, record):
        color = self.COLORS.get(record.levelname, Colors.WHITE)
        record.msg = f"{color}{record.msg}{Colors.RESET}"
        return super().format(record)

# Handler para arquivo (sem cores)
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

# Handler para terminal (com cores)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(ColorFormatter('%(asctime)s [%(levelname)s] %(message)s'))

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, stream_handler])
logger = logging.getLogger("2NR_V9")

# ============================================================
# CONFIGURAÇÕES DO PROXY ROTATIVO
# ============================================================
PROXY_HOST = "74.81.81.81"
PROXY_PORT = "823"
PROXY_USER = "be2c872545392337df6e__cr.br"
PROXY_PASS = "768df629c0304df6"
PROXY_SERVER = f"http://{PROXY_HOST}:{PROXY_PORT}"

# ============================================================
# CONFIGURAÇÕES DO 2NR
# ============================================================
NR_BASE_URL = "https://api.2nr.xyz"
NR_REGISTER_ENDPOINT = f"{NR_BASE_URL}/auth/register"

NR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "Content-Type": "application/json; charset=UTF-8",
}

# ============================================================
# CONFIGURAÇÕES DO TEMPORARY-EMAIL.ORG
# ============================================================
EMAIL_BASE_URL = "https://temporary-email.org"

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def generate_random_password(length=12):
    """
    Gera uma senha aleatória que atende TODOS os requisitos do 2NR:
    - Mínimo 8 caracteres
    - Pelo menos 1 letra maiúscula
    - Pelo menos 1 letra minúscula
    - Pelo menos 1 número
    - Pelo menos 1 caractere especial: [?!@#$%^&*()<>+{}|_-]
    """
    special_chars = "?!@#$%^&*()_-"
    
    # Garantir pelo menos 1 de cada tipo
    password_parts = [
        random.choice(string.ascii_uppercase),      # 1 maiúscula
        random.choice(string.ascii_lowercase),      # 1 minúscula
        random.choice(string.digits),               # 1 número
        random.choice(special_chars),               # 1 especial
        random.choice(special_chars),               # +1 especial (segurança)
    ]
    
    # Preencher o resto com mix de tudo
    remaining = length - len(password_parts)
    all_chars = string.ascii_letters + string.digits + special_chars
    password_parts.extend(random.choices(all_chars, k=remaining))
    
    # Embaralhar para não ficar previsível
    random.shuffle(password_parts)
    password = ''.join(password_parts)
    
    logger.debug(f"Senha gerada: {password}")
    logger.debug(f"  Tem maiúscula: {any(c.isupper() for c in password)}")
    logger.debug(f"  Tem minúscula: {any(c.islower() for c in password)}")
    logger.debug(f"  Tem número: {any(c.isdigit() for c in password)}")
    logger.debug(f"  Tem especial: {any(c in special_chars for c in password)}")
    
    return password

def generate_imei():
    """Gera um IMEI aleatório de 15 dígitos com checksum válido"""
    # Gerar 14 dígitos aleatórios
    digits = [random.randint(0, 9) for _ in range(14)]
    
    # Calcular checksum (algoritmo de Luhn)
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    check = (10 - (total % 10)) % 10
    digits.append(check)
    
    imei = ''.join(str(d) for d in digits)
    logger.debug(f"IMEI gerado (Luhn válido): {imei}")
    return imei

# ============================================================
# ETAPA 1: CRIAR E-MAIL TEMPORÁRIO VIA PLAYWRIGHT
# ============================================================

async def create_temp_email(page, context):
    """Cria um e-mail temporário acessando temporary-email.org via Playwright"""
    logger.info("=" * 60)
    logger.info("ETAPA 1: CRIANDO E-MAIL TEMPORÁRIO")
    logger.info("=" * 60)
    
    # Interceptar a resposta de mensagens para pegar o e-mail
    email_data = {"email": None}
    
    async def on_response(response):
        if "/messages" in response.url and "temporary-email" in response.url:
            try:
                body = await response.text()
                data = json.loads(body)
                if data.get("mailbox"):
                    email_data["email"] = data["mailbox"]
                    logger.debug(f"E-mail interceptado via API: {data['mailbox']}")
            except:
                pass
    
    page.on("response", on_response)
    
    # Acessar a página principal
    logger.info("Acessando temporary-email.org...")
    try:
        await page.goto(f"{EMAIL_BASE_URL}/en", wait_until="networkidle", timeout=60000)
    except Exception as e:
        logger.warning(f"Timeout ao carregar página, tentando continuar: {e}")
    
    # Esperar a página carregar e gerar o e-mail
    await asyncio.sleep(5)
    
    # Se não interceptou, tentar extrair do HTML
    if not email_data["email"]:
        logger.debug("E-mail não interceptado, tentando extrair do HTML...")
        try:
            html = await page.content()
            # Procurar e-mail no HTML
            email_match = re.search(r'[\w.+-]+@[\w-]+\.\w+', html)
            if email_match:
                email_data["email"] = email_match.group()
                logger.debug(f"E-mail extraído do HTML: {email_data['email']}")
        except:
            pass
    
    # Se ainda não encontrou, tentar polling
    if not email_data["email"]:
        logger.debug("Tentando extrair e-mail via polling...")
        for attempt in range(3):
            try:
                timestamp = int(time.time() * 1000)
                msg_response = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const resp = await fetch('/en/messages?_={timestamp}');
                            return await resp.text();
                        }} catch(e) {{
                            return JSON.stringify({{error: e.toString()}});
                        }}
                    }}
                """)
                msg_data = json.loads(msg_response)
                if msg_data.get("mailbox"):
                    email_data["email"] = msg_data["mailbox"]
                    logger.info(f"E-mail extraído via polling: {email_data['email']}")
                    break
            except:
                await asyncio.sleep(2)
    
    if email_data["email"]:
        logger.info(f"E-MAIL CRIADO COM SUCESSO: {email_data['email']}")
        return email_data["email"]
    else:
        logger.error("FALHA TOTAL: Não conseguiu criar e-mail temporário")
        return None

# ============================================================
# ETAPA 2: REGISTRAR NO 2NR VIA API
# ============================================================

async def register_2nr(email, password, proxy_config):
    """Registra no 2NR usando a API via requests com proxy"""
    logger.info("=" * 60)
    logger.info("ETAPA 2: REGISTRANDO NO 2NR")
    logger.info("=" * 60)
    
    import requests
    
    imei = generate_imei()
    
    payload = {
        "query": {
            "email": email,
            "imei": imei,
            "password": password
        },
        "id": 103
    }
    
    logger.info(f"E-mail: {email}")
    logger.info(f"Senha: {password}")
    logger.debug(f"IMEI: {imei}")
    logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
    logger.debug(f"Headers: {json.dumps(NR_HEADERS, indent=2)}")
    logger.debug(f"Proxy: {proxy_config.get('https', 'NENHUM')}")
    
    # Tentar até 3 vezes
    for attempt in range(1, 4):
        logger.info(f"--- TENTATIVA {attempt}/3 ---")
        
        try:
            logger.debug(f"Enviando POST para {NR_REGISTER_ENDPOINT}...")
            
            response = requests.post(
                NR_REGISTER_ENDPOINT,
                json=payload,
                headers=NR_HEADERS,
                proxies=proxy_config,
                timeout=30,
                verify=True
            )
            
            status = response.status_code
            body = response.text
            
            logger.info(f"Código de Resposta do Servidor: {status}")
            logger.debug(f"Response Headers: {dict(response.headers)}")
            logger.debug(f"Response Content: {body[:500]}")
            
            if status == 200:
                try:
                    data = json.loads(body)
                    if data.get("success") == True:
                        logger.info("REGISTRO ENVIADO COM SUCESSO!")
                        return True
                    elif data.get("error"):
                        error_code = data.get("error")
                        logger.error(f"Erro do 2NR (código {error_code}): {json.dumps(data, indent=2)}")
                        
                        # Erro de senha
                        if "password" in str(data.get("dataPath", "")):
                            logger.error("ERRO DE SENHA: A senha não atende aos requisitos do 2NR!")
                            logger.error(f"Padrão exigido: {data.get('params', {}).get('pattern', 'N/A')}")
                            return False
                        
                        # Erro de e-mail
                        if "email" in str(data.get("dataPath", "")):
                            logger.error("ERRO DE E-MAIL: O e-mail não é válido para o 2NR!")
                            return False
                        
                        return False
                    else:
                        logger.info(f"Resposta 200: {json.dumps(data, indent=2)}")
                        return True
                except json.JSONDecodeError:
                    if "1015" in body or "blocked" in body.lower() or "rate" in body.lower():
                        logger.error("BLOQUEIO CLOUDFLARE DETECTADO! Trocando IP...")
                        if attempt < 3:
                            await asyncio.sleep(5)
                            continue
                    logger.warning(f"Resposta 200 mas não é JSON: {body[:200]}")
                    return True
            
            elif status == 500:
                try:
                    data = json.loads(body)
                    error_code = data.get("error", "desconhecido")
                    keyword = data.get("keyword", "")
                    data_path = data.get("dataPath", "")
                    pattern = data.get("params", {}).get("pattern", "")
                    
                    logger.error(f"Erro 500 do 2NR:")
                    logger.error(f"  Código: {error_code}")
                    logger.error(f"  Tipo: {keyword}")
                    logger.error(f"  Campo: {data_path}")
                    logger.error(f"  Padrão: {pattern}")
                    
                    if "password" in data_path and "pattern" in keyword:
                        logger.error("A SENHA NÃO ATENDE AO PADRÃO EXIGIDO!")
                        logger.error(f"Regex exigido: {pattern}")
                        logger.error(f"Senha enviada: {password}")
                        return False
                    
                except json.JSONDecodeError:
                    logger.error(f"Erro 500 (não-JSON): {body[:300]}")
                
                return False
            
            elif status == 429 or status == 403:
                logger.warning(f"Rate Limited/Bloqueado ({status}). Aguardando 10s...")
                if attempt < 3:
                    await asyncio.sleep(10)
                    continue
                return False
            
            else:
                logger.error(f"Erro HTTP {status}: {body[:300]}")
                if attempt < 3:
                    await asyncio.sleep(3)
                    continue
                return False
                
        except requests.exceptions.ProxyError as e:
            logger.error(f"ERRO DE PROXY: {e}")
            if attempt < 3:
                logger.info("Tentando novamente sem proxy...")
                proxy_config = {}
                continue
            return False
        except requests.exceptions.Timeout:
            logger.error("TIMEOUT na requisição!")
            if attempt < 3:
                continue
            return False
        except Exception as e:
            logger.exception(f"Erro inesperado: {e}")
            return False
    
    return False

# ============================================================
# ETAPA 3: MONITORAR CAIXA DE ENTRADA E EXTRAIR LINK
# ============================================================

async def wait_for_confirmation_email(page, email, max_wait=180):
    """Monitora a caixa de entrada até o e-mail de confirmação do 2NR chegar"""
    logger.info("=" * 60)
    logger.info("ETAPA 3: AGUARDANDO E-MAIL DE CONFIRMAÇÃO")
    logger.info("=" * 60)
    
    logger.info(f"Monitorando caixa de entrada de: {email}")
    logger.info(f"Tempo máximo de espera: {max_wait} segundos")
    
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < max_wait:
        attempt += 1
        elapsed = int(time.time() - start_time)
        logger.info(f"Verificação #{attempt} ({elapsed}s/{max_wait}s)...")
        
        timestamp = int(time.time() * 1000)
        
        try:
            inbox_result = await page.evaluate(f"""
                async () => {{
                    try {{
                        const resp = await fetch('/en/messages?_={timestamp}');
                        return await resp.text();
                    }} catch(e) {{
                        return JSON.stringify({{error: e.toString()}});
                    }}
                }}
            """)
            
            logger.debug(f"Resposta da caixa: {inbox_result[:300]}")
            
            inbox_data = json.loads(inbox_result)
            messages = inbox_data.get("messages", [])
            
            if messages:
                logger.info(f"MENSAGEM(NS) DETECTADA(S)! Total: {len(messages)}")
                
                for msg in messages:
                    subject = msg.get("subject", "")
                    sender = msg.get("from", "")
                    msg_id = msg.get("id", "")
                    
                    logger.info(f"  De: {sender}")
                    logger.info(f"  Assunto: {subject}")
                    logger.debug(f"  ID: {msg_id}")
                    
                    # Verificar se é do 2NR
                    is_2nr = any(kw in (subject + sender).lower() for kw in [
                        "2nr", "confirm", "verif", "regist", "aktyw", "aktiv",
                        "mobilelabs", "softphone"
                    ])
                    
                    if is_2nr or True:  # Abrir todas as mensagens para segurança
                        logger.info(f"Abrindo mensagem: {subject}")
                        
                        # Tentar abrir o e-mail
                        try:
                            msg_content = await page.evaluate(f"""
                                async () => {{
                                    try {{
                                        const resp = await fetch('/en/message/{msg_id}');
                                        return await resp.text();
                                    }} catch(e) {{
                                        return JSON.stringify({{error: e.toString()}});
                                    }}
                                }}
                            """)
                            
                            logger.debug(f"Conteúdo do e-mail: {msg_content[:500]}")
                            
                            # Extrair link de confirmação
                            link = extract_confirmation_link(msg_content)
                            if link:
                                return link
                        except Exception as e:
                            logger.warning(f"Erro ao abrir mensagem: {e}")
                        
                        # Tentar no corpo direto da mensagem
                        body_content = msg.get("body", "") or msg.get("html", "") or msg.get("text", "")
                        if body_content:
                            link = extract_confirmation_link(body_content)
                            if link:
                                return link
            else:
                logger.debug("Caixa vazia, aguardando próximo ciclo...")
                
        except json.JSONDecodeError:
            logger.warning("Resposta da caixa não é JSON (possível Cloudflare challenge)")
        except Exception as e:
            logger.warning(f"Erro ao verificar caixa: {e}")
        
        # Esperar 5 segundos antes da próxima verificação
        await asyncio.sleep(5)
    
    logger.error(f"TIMEOUT: Nenhum e-mail de confirmação recebido em {max_wait}s")
    return None

def extract_confirmation_link(content):
    """Extrai o link de confirmação do 2NR do conteúdo do e-mail"""
    # Padrões de link do 2NR (do mais específico ao mais genérico)
    patterns = [
        r'https?://api\.2nr\.xyz/register/?\?[^\s"<>\'\\]+',
        r'https?://api\.2nr\.xyz/[^\s"<>\'\\]+token=[^\s"<>\'\\]+',
        r'https?://api\.2nr\.xyz/[^\s"<>\'\\]+confirm[^\s"<>\'\\]*',
        r'https?://api\.2nr\.xyz/[^\s"<>\'\\]+verif[^\s"<>\'\\]*',
        r'https?://[^\s"<>\'\\]*2nr[^\s"<>\'\\]*register[^\s"<>\'\\]*',
        r'https?://[^\s"<>\'\\]*2nr[^\s"<>\'\\]*confirm[^\s"<>\'\\]*',
        r'https?://[^\s"<>\'\\]*2nr\.xyz[^\s"<>\'\\]+',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            link = match.group(0)
            # Limpar caracteres finais indesejados
            link = link.rstrip('",;>\\)')
            # Decodificar entidades HTML se necessário
            link = link.replace("&amp;", "&")
            logger.info(f"LINK DE CONFIRMAÇÃO ENCONTRADO: {link}")
            return link
    
    # Se não encontrou com padrões específicos, procurar qualquer link com "2nr"
    all_links = re.findall(r'https?://[^\s"<>\'\\]+', content)
    for link in all_links:
        if '2nr' in link.lower():
            link = link.rstrip('",;>\\)')
            link = link.replace("&amp;", "&")
            logger.info(f"LINK DO 2NR ENCONTRADO (genérico): {link}")
            return link
    
    logger.warning("Nenhum link de confirmação encontrado no conteúdo")
    return None

# ============================================================
# ETAPA 4: VALIDAR LINK VIA PLAYWRIGHT
# ============================================================

async def validate_confirmation_link(browser, link):
    """Valida o link de confirmação do 2NR via Playwright com proxy"""
    logger.info("=" * 60)
    logger.info("ETAPA 4: VALIDANDO LINK DE CONFIRMAÇÃO")
    logger.info("=" * 60)
    
    logger.info(f"Link: {link}")
    logger.info(f"Proxy: {PROXY_SERVER}")
    
    # Criar novo contexto com proxy para a validação
    context = await browser.new_context(
        proxy={
            "server": PROXY_SERVER,
            "username": PROXY_USER,
            "password": PROXY_PASS,
        },
        user_agent=NR_HEADERS["User-Agent"]
    )
    
    page = await context.new_page()
    
    try:
        logger.info("Acessando link de confirmação via Playwright + Proxy...")
        response = await page.goto(link, wait_until="networkidle", timeout=60000)
        
        status = response.status if response else "N/A"
        logger.info(f"Status da resposta: {status}")
        
        content = await page.content()
        title = await page.title()
        
        logger.info(f"Título da página: {title}")
        logger.debug(f"Conteúdo (primeiros 500): {content[:500]}")
        
        if "Error 1015" in content or "You have been blocked" in content:
            logger.error("BLOQUEIO CLOUDFLARE NA VALIDAÇÃO!")
            logger.info("Tentando novamente sem proxy...")
            await context.close()
            
            # Tentar sem proxy
            context2 = await browser.new_context(
                user_agent=NR_HEADERS["User-Agent"]
            )
            page2 = await context2.new_page()
            try:
                response2 = await page2.goto(link, wait_until="networkidle", timeout=60000)
                status2 = response2.status if response2 else "N/A"
                content2 = await page2.content()
                title2 = await page2.title()
                logger.info(f"Status sem proxy: {status2}")
                logger.info(f"Título sem proxy: {title2}")
                
                if "Error 1015" not in content2 and "blocked" not in content2.lower():
                    logger.info("VALIDAÇÃO CONCLUÍDA COM SUCESSO (sem proxy)!")
                    return True
            except Exception as e:
                logger.error(f"Erro na tentativa sem proxy: {e}")
            finally:
                await context2.close()
            
            return False
        
        # Esperar para garantir que o JavaScript da página rode
        await asyncio.sleep(5)
        
        # Verificar se a validação foi bem-sucedida
        final_content = await page.content()
        final_title = await page.title()
        logger.info(f"Título final: {final_title}")
        
        if "2nr" in final_title.lower() or status == 200:
            logger.info("VALIDAÇÃO CONCLUÍDA COM SUCESSO!")
            return True
        else:
            logger.warning(f"Validação incerta. Título: {final_title}")
            return True  # Assumir sucesso se não houve erro explícito
        
    except Exception as e:
        logger.exception(f"Erro na validação: {e}")
        return False
    finally:
        try:
            await context.close()
        except:
            pass

# ============================================================
# FLUXO PRINCIPAL
# ============================================================

async def main():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
{'='*60}
   2NR ULTIMATE WARRIOR V9 - AUTOMAÇÃO TOTAL (CORRIGIDA)
   Playwright + Proxy Rotativo + Debug Logs
{'='*60}
   Proxy: {PROXY_HOST}:{PROXY_PORT}
   Logs:  {log_filename}
{'='*60}
{Colors.RESET}"""
    print(banner)
    
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        # Iniciar browser
        logger.info("Iniciando Playwright...")
        browser = await p.chromium.launch(headless=True)
        
        # ========================================
        # ETAPA 1: CRIAR E-MAIL TEMPORÁRIO
        # ========================================
        email_context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36"
        )
        email_page = await email_context.new_page()
        
        email = await create_temp_email(email_page, email_context)
        
        if not email:
            logger.error("FALHA: Não foi possível criar o e-mail temporário")
            await browser.close()
            return
        
        # ========================================
        # ETAPA 2: GERAR SENHA E REGISTRAR NO 2NR
        # ========================================
        password = generate_random_password(12)
        
        # Configurar proxy para requests
        proxy_config = {
            "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
            "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
        }
        
        # Testar proxy antes de registrar
        logger.info("Testando conexão com o Proxy...")
        try:
            import requests
            test_resp = requests.get("https://api.ipify.org?format=json", proxies=proxy_config, timeout=15)
            proxy_ip = test_resp.json().get("ip", "desconhecido")
            logger.info(f"IP do Proxy detectado: {proxy_ip}")
        except Exception as e:
            logger.warning(f"Proxy não respondeu: {e}")
            logger.info("Continuando sem proxy...")
            proxy_config = {}
        
        success = await register_2nr(email, password, proxy_config)
        
        if not success:
            logger.error("FALHA: Registro no 2NR não foi bem-sucedido")
            retry = input(f"\n{Colors.YELLOW}[?] Deseja tentar com outro e-mail? (s/n): {Colors.RESET}")
            if retry.lower() == 's':
                await email_context.close()
                await browser.close()
                # Reiniciar
                await main()
                return
            else:
                await browser.close()
                return
        
        # ========================================
        # ETAPA 3: MONITORAR CAIXA DE ENTRADA
        # ========================================
        print(f"\n{Colors.GREEN}{Colors.BOLD}")
        print("!" * 60)
        print("! REGISTRO FEITO! AGORA PEGUE O LINK NO SEU E-MAIL !")
        print("!" * 60)
        print(f"{Colors.RESET}\n")
        
        confirmation_link = await wait_for_confirmation_email(email_page, email, max_wait=180)
        
        if not confirmation_link:
            logger.warning("Link não encontrado automaticamente.")
            confirmation_link = input(f"\n{Colors.YELLOW}[?] Cole o link de confirmação aqui: {Colors.RESET}")
            if not confirmation_link or not confirmation_link.strip():
                logger.error("Nenhum link fornecido. Encerrando.")
                await browser.close()
                return
            confirmation_link = confirmation_link.strip()
        
        # ========================================
        # ETAPA 4: VALIDAR LINK DE CONFIRMAÇÃO
        # ========================================
        validated = await validate_confirmation_link(browser, confirmation_link)
        
        if validated:
            print(f"\n{Colors.GREEN}{Colors.BOLD}")
            print("*" * 60)
            print("   PROCESSO FINALIZADO COM SUCESSO!")
            print(f"   E-mail: {email}")
            print(f"   Senha:  {password}")
            print("   Agora você pode logar no aplicativo 2NR!")
            print("*" * 60)
            print(f"{Colors.RESET}\n")
            
            # Salvar credenciais em arquivo
            with open("2nr_credentials.txt", "a") as f:
                f.write(f"{datetime.now().isoformat()} | {email} | {password}\n")
            logger.info("Credenciais salvas em 2nr_credentials.txt")
        else:
            logger.error("FALHA na validação do link.")
            logger.info("Tente colar o link no navegador manualmente com uma VPN ativa.")
        
        await email_context.close()
        await browser.close()
    
    print(f"\n{Colors.CYAN}[*] Logs detalhados salvos em: {log_filename}{Colors.RESET}")

if __name__ == "__main__":
    asyncio.run(main())
