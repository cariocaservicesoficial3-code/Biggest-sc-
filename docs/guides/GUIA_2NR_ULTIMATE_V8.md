# Guia de Operação 2NR Ultimate Warrior V8 - Automação Total 👽🔥👩🏻‍💻

## Visão Geral

O script `2nr_ultimate_v8.py` automatiza **100% do processo** de criação de conta no 2NR. Basta executar e esperar. Ele faz tudo sozinho:

1. **Cria um e-mail temporário** @tousma.com (nome aleatório, nunca repete)
2. **Gera uma senha aleatória** segura de 12 caracteres
3. **Registra no 2NR** via API com o seu proxy rotativo
4. **Monitora a caixa de entrada** automaticamente (polling a cada 5s)
5. **Extrai o link de confirmação** do e-mail do 2NR
6. **Valida a conta** via Playwright pelo proxy rotativo
7. **Salva as credenciais** em `2nr_credentials.txt`

---

## Instalação no Kali NetHunter

```bash
# 1. Instalar dependências
apt update && apt install -y python3-pip

# 2. Instalar bibliotecas Python
pip3 install requests playwright

# 3. Instalar navegadores do Playwright
playwright install chromium

# 4. Instalar dependências do Chromium (se necessário)
playwright install-deps chromium
```

---

## Como Usar

```bash
# Executar o script
python3 2nr_ultimate_v8.py
```

O script vai:
- Mostrar cada etapa em tempo real no terminal
- Salvar logs detalhados em um arquivo `.log`
- No final, mostrar o e-mail e senha criados
- Salvar as credenciais em `2nr_credentials.txt`

---

## Logs de Debug

Todos os logs são salvos automaticamente em um arquivo com o formato:
```
YYYY-MM-DD_HHMMSS_2nr_ultimate.log
```

Os logs incluem:
- **[DEBUG]**: Detalhes técnicos (headers, payloads, respostas brutas)
- **[INFO]**: Progresso das etapas
- **[WARNING]**: Alertas (e-mail não mudou, fallback ativado)
- **[ERROR]**: Falhas críticas (bloqueio Cloudflare, timeout)

---

## Proxy Rotativo

O proxy já está configurado no script:
- **Servidor**: 74.81.81.81:823
- **Usuário**: be2c872545392337df6e__cr.br
- **Senha**: 768df629c0304df6

Para trocar o proxy, edite as variáveis no início do script:
```python
PROXY_HOST = "novo_ip"
PROXY_PORT = "nova_porta"
PROXY_USER = "novo_usuario"
PROXY_PASS = "nova_senha"
```

---

## Fallback Manual

Se o monitoramento automático da caixa de entrada não encontrar o e-mail em 3 minutos, o script vai pedir para você colar o link manualmente. Isso é um "plano B" caso o formato do e-mail do 2NR mude.

---

## Credenciais Salvas

Todas as contas criadas são salvas em `2nr_credentials.txt` no formato:
```
2026-03-29T01:30:00 | email@tousma.com | SenhaGerada123
```

---

## Dicas de Especialista

- **Se der erro 403**: O Cloudflare pode estar bloqueando. Tente desligar/ligar o modo avião para trocar o IP.
- **Se der erro 500 no 2NR**: A senha pode ter caracteres que o servidor não aceita. O script gera senhas alfanuméricas para evitar isso.
- **Se o e-mail não chegar**: Verifique se o domínio @tousma.com está funcionando. O script suporta outros domínios (biomails.com, sasmil.org, omailo.top, ingam.top).
