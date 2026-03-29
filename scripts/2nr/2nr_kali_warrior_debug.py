import requests
import json
import random
import time
import asyncio
import logging
import sys
from datetime import datetime
from playwright.async_api import async_playwright

# CONFIGURAÇÃO DE LOGS (DEBUG EM TEMPO REAL)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("debug_2nr.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("2NR_DEBUG")

# CONFIGURAÇÕES DO PROXY (ROTATIVO)
PROXY_SERVER = "http://74.81.81.81:823"
PROXY_USER = "be2c872545392337df6e__cr.br"
PROXY_PASS = "768df629c0304df6"

# CONFIGURAÇÕES DO 2NR
BASE_URL = "https://api.2nr.xyz"
REGISTER_ENDPOINT = f"{BASE_URL}/auth/register"

# HEADERS DE NAVEGADOR REAL (V5 BYPASS)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "Content-Type": "application/json; charset=UTF-8",
}

def generate_imei():
    imei = "".join([str(random.randint(0, 9)) for _ in range(16)])
    logger.debug(f"IMEI Gerado: {imei}")
    return imei

async def validate_link_with_playwright(url):
    logger.info(f"Iniciando validação do link via Playwright (Proxy: {PROXY_SERVER})...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            proxy={
                "server": PROXY_SERVER,
                "username": PROXY_USER,
                "password": PROXY_PASS,
            },
            user_agent=HEADERS["User-Agent"]
        )
        
        page = await context.new_page()
        
        try:
            logger.debug(f"Acessando link: {url}")
            response = await page.goto(url, wait_until="networkidle", timeout=60000)
            
            logger.debug(f"Status da Resposta Playwright: {response.status}")
            content = await page.content()
            
            if "Error 1015" in content or "You have been blocked" in content:
                logger.error("Bloqueio Cloudflare detectado no Playwright!")
                return False
            
            await asyncio.sleep(5)
            title = await page.title()
            logger.info(f"Validação concluída! Título da página: {title}")
            return True
            
        except Exception as e:
            logger.exception(f"Erro crítico no Playwright: {e}")
            return False
        finally:
            await browser.close()

def register_2nr(email, password):
    imei = generate_imei()
    payload = {
        "query": {
            "email": email,
            "imei": imei,
            "password": password
        },
        "id": 103
    }
    
    proxies = {
        "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_SERVER.replace('http://', '')}",
        "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_SERVER.replace('http://', '')}"
    }
    
    logger.info("--- INICIANDO REQUISIÇÃO DE REGISTRO ---")
    logger.debug(f"URL: {REGISTER_ENDPOINT}")
    logger.debug(f"Payload: {json.dumps(payload)}")
    logger.debug(f"Headers: {json.dumps(HEADERS)}")
    
    try:
        # Testar proxy antes
        logger.debug("Testando conexão com o Proxy...")
        test_res = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
        logger.info(f"IP do Proxy detectado: {test_res.json().get('ip')}")
        
        response = requests.post(REGISTER_ENDPOINT, headers=HEADERS, json=payload, proxies=proxies, timeout=20)
        
        logger.info(f"Código de Resposta do Servidor: {response.status_code}")
        logger.debug(f"Response Headers: {response.headers}")
        logger.debug(f"Response Content: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                logger.info("REGISTRO ENVIADO COM SUCESSO!")
                return True
            else:
                logger.warning(f"Erro retornado pela API: {data}")
        elif response.status_code == 500:
            logger.error("ERRO 500: O servidor do 2NR rejeitou a requisição. Verifique se o e-mail já existe ou se há caracteres especiais na senha.")
        elif response.status_code == 1015:
            logger.error("ERRO 1015: Bloqueio de Rate Limit do Cloudflare no Proxy.")
            
    except Exception as e:
        logger.exception(f"Falha na conexão de rede: {e}")
    return False

async def main():
    print("\n" + "="*60)
    print("      2NR KALI WARRIOR - DEBUG MODE V7 (REAL-TIME LOGS)      ")
    print("="*60 + "\n")
    
    email = input("[?] Digite o e-mail: ")
    password = input("[?] Digite a senha: ")
    
    logger.info(f"Iniciando processo para: {email}")
    
    if register_2nr(email, password):
        print("\n" + "!"*60)
        print("! REGISTRO FEITO! AGORA PEGUE O LINK NO SEU E-MAIL !")
        print("!"*60 + "\n")
        
        link = input("[?] Cole o link de confirmação aqui: ")
        
        if link:
            success = await validate_link_with_playwright(link)
            if success:
                logger.info("PROCESSO FINALIZADO COM SUCESSO!")
            else:
                logger.error("Falha na validação automática.")
    else:
        logger.error("O registro falhou. Verifique os logs acima para detalhes.")
    
    print(f"\n[*] Logs detalhados salvos em: {datetime.now().strftime('%Y-%m-%d')}_debug_2nr.log")

if __name__ == "__main__":
    asyncio.run(main())
