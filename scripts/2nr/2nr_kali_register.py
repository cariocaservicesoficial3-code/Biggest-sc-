import requests
import json
import time
import random

# CONFIGURAÇÕES DO 2NR
BASE_URL = "https://api.2nr.xyz"
REGISTER_ENDPOINT = f"{BASE_URL}/auth/register"

# HEADERS QUE INJETAMOS NO APP (V5) - ESSENCIAIS PARA BYPASS CLOUDFLARE
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "Content-Type": "application/json; charset=UTF-8",
    "Accept-Encoding": "gzip"
}

def generate_imei():
    return "".join([str(random.randint(0, 9)) for _ in range(16)])

def register_2nr(email, password):
    imei = generate_imei()
    
    # ESTRUTURA IDENTIFICADA NO HAR
    payload = {
        "query": {
            "email": email,
            "imei": imei,
            "password": password
        },
        "id": 103
    }
    
    print(f"[*] Tentando registro para: {email}")
    print(f"[*] IMEI Gerado: {imei}")
    
    try:
        response = requests.post(REGISTER_ENDPOINT, headers=HEADERS, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("[+] REGISTRO ENVIADO COM SUCESSO!")
                print(f"[+] Resposta: {data}")
                print("[!] Agora verifique seu e-mail para confirmar o registro.")
            else:
                print(f"[-] Erro no registro: {data}")
        elif response.status_code == 1015 or response.status_code == 429:
            print("[-] BLOQUEIO CLOUDFLARE (RATE LIMIT 1015).")
            print("[!] DICA: Troque de IP (Modo Avião) ou use uma VPN no Kali.")
        else:
            print(f"[-] Erro Inesperado: {response.status_code}")
            print(f"[-] Conteúdo: {response.text[:200]}...")
            
    except Exception as e:
        print(f"[-] Falha na conexão: {e}")

if __name__ == "__main__":
    print("--- 2NR KALI REGISTER TOOL (V5 BYPASS) ---")
    email = input("Digite o e-email: ")
    password = input("Digite a senha: ")
    register_2nr(email, password)
