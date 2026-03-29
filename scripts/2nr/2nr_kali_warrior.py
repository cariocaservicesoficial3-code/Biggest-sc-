import requests
import json
import random
import time
import asyncio
from playwright.async_api import async_playwright

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
    return "".join([str(random.randint(0, 9)) for _ in range(16)])

async def validate_link_with_playwright(url):
    print(f"[*] Iniciando validação do link via Playwright (Proxy: {PROXY_SERVER})...")
    async with async_playwright() as p:
        # Configurar o navegador com proxy
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
            print(f"[*] Acessando link de confirmação...")
            response = await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Verificar se fomos bloqueados pelo Cloudflare
            content = await page.content()
            if "Error 1015" in content or "You have been blocked" in content:
                print("[-] ERRO: Cloudflare bloqueou o acesso pelo Proxy!")
                return False
            
            print("[+] Página carregada com sucesso. Verificando resultado...")
            # Esperar um pouco para garantir que o script de validação do site rode
            await asyncio.sleep(5)
            
            title = await page.title()
            print(f"[+] Título da página: {title}")
            print("[+] Validação concluída via Playwright!")
            return True
            
        except Exception as e:
            print(f"[-] Erro durante a validação: {e}")
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
    
    print(f"[*] Enviando solicitação de registro (Proxy Ativo)...")
    try:
        response = requests.post(REGISTER_ENDPOINT, headers=HEADERS, json=payload, proxies=proxies, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("[+] REGISTRO ENVIADO COM SUCESSO! (Código 200)")
                return True
            else:
                print(f"[-] Erro na API: {data}")
        else:
            print(f"[-] Erro no servidor: {response.status_code}")
            if "1015" in response.text:
                print("[-] BLOQUEIO CLOUDFLARE DETECTADO.")
    except Exception as e:
        print(f"[-] Falha na conexão: {e}")
    return False

async def main():
    print("="*50)
    print("      2NR KALI WARRIOR - AUTO REGISTER & VALIDATE      ")
    print("="*50)
    
    email = input("[?] Digite o e-mail: ")
    password = input("[?] Digite a senha: ")
    
    if register_2nr(email, password):
        print("\n" + "!"*50)
        print("! REGISTRO FEITO! AGORA PEGUE O LINK NO SEU E-MAIL !")
        print("!"*50 + "\n")
        
        link = input("[?] Cole o link de confirmação aqui: ")
        
        if link:
            success = await validate_link_with_playwright(link)
            if success:
                print("\n[***] PROCESSO FINALIZADO COM SUCESSO! [***]")
                print("[*] Agora você pode logar no aplicativo modificado.")
            else:
                print("\n[!] Falha na validação automática. Tente novamente ou use uma VPN.")
    else:
        print("\n[!] O registro falhou. Verifique seu proxy ou IP.")

if __name__ == "__main__":
    asyncio.run(main())
