# CHECKPOINT 003 - Scripts de Automação

**Data:** 29 de Março de 2026
**Foco:** Evolução e detalhes dos scripts desenvolvidos

---

## Evolução dos Scripts 2NR

### V1 (`2nr_kali_register.py`) - Registro Básico
- Registro simples via API com requests
- User-Agent de Chrome Mobile
- Proxy rotativo integrado
- **Problema:** Sem validação de link, sem debug

### V6 (`2nr_kali_warrior.py`) - Registro + Validação
- Adicionado Playwright para validar link de confirmação
- Fluxo: Registro → Colar link → Validação via Playwright
- **Problema:** Sem logs detalhados, difícil debugar

### V7 (`2nr_kali_warrior_debug.py`) - Debug Mode
- Logs em tempo real com timestamps
- Salvamento em arquivo `.log`
- Exibição de headers, payloads e respostas completas
- Teste de proxy antes do registro
- **Resultado:** Identificou erro 500 (senha sem especial) e erro 1010

### V9 (`2nr_ultimate_v9.py`) - Automação Total (FINAL)
- Integração com Emailnator (Gmail temporário dotGmail)
- Geração de senha com caracteres especiais obrigatórios
- IMEI com checksum Luhn válido
- Monitoramento automático de caixa de entrada
- Extração de link de confirmação via regex
- Validação via Playwright + Proxy
- Fallback manual para código/link
- Cores no terminal + logs em arquivo
- Salvamento de credenciais em `2nr_credentials.txt`
- **STATUS: FUNCIONANDO 100%** (testado e confirmado pelo usuário)

---

## Script Manus Creator (`manus_creator.py`)

### Fluxo Completo
1. Pede link de convite → extrai código
2. Gera Gmail via Emailnator (dotGmail)
3. Gera senha de 20 chars no padrão Manus
4. Abre Playwright VISÍVEL (headless=False)
5. Navega para `manus.im/login?code=XXX`
6. Preenche e-mail automaticamente
7. **Usuário resolve Turnstile manualmente** (Opção A)
8. Intercepta `tempToken` da resposta `GetUserPlatforms`
9. Envia código de verificação via API
10. Monitora Emailnator para capturar código de 6 dígitos
11. Completa registro via API `RegisterByEmail`
12. Navega até página de telefone → seleciona Polônia
13. Salva credenciais e JWT token

### Padrão de Senha Manus
```
Exemplo: OEBm0F4NL:Ja7'9r;#8P
Caracteres: maiúsculas + minúsculas + números + especiais (:;'#@!$%^&*()-_+=<>?)
Tamanho: 20 caracteres
```

### Interceptação de Respostas
O script intercepta responses do Playwright para capturar:
- `tempToken` de `GetUserPlatforms`
- `token` (JWT) de `RegisterByEmail`
- Confirmação de `SendEmailVerifyCode`

---

## API do Emailnator

### Fluxo de Uso
```python
# 1. Obter XSRF token
GET https://www.emailnator.com
# Extrair cookie XSRF-TOKEN

# 2. Gerar email
POST https://www.emailnator.com/generate-email
Headers: X-XSRF-TOKEN: {token}
Body: {"email": ["dotGmail"]}
# Resposta: {"email": ["na.di.n.e.a.rguill.e.s26@gmail.com"]}

# 3. Verificar inbox
POST https://www.emailnator.com/message-list
Body: {"email": "na.di.n.e.a.rguill.e.s26@gmail.com"}
# Resposta: {"messageData": [{"messageID": "...", "from": "...", "subject": "..."}]}

# 4. Ler mensagem
POST https://www.emailnator.com/message-list
Body: {"email": "...", "messageID": "..."}
# Resposta: HTML do email
```

### Notas Importantes
- Se status 419: token expirado, renovar com novo GET
- O email gerado pode ser @gmail.com com pontos aleatórios
- Não é possível escolher o endereço (Cloudflare Turnstile bloqueia)
- O domínio pode variar (@sasmil.org, @ingam.top, @tousma.com)

---

## Proxy Rotativo

```
Servidor: 74.81.81.81:823
Usuário: be2c872545392337df6e__cr.br
Senha: 768df629c0304df6
Formato URL: http://be2c872545392337df6e__cr.br:768df629c0304df6@74.81.81.81:823
```

Usado em:
- Requisições `requests` (proxies dict)
- Playwright (`proxy` parameter no `browser.new_context`)

---

## Dependências dos Scripts

```bash
# Para todos os scripts
pip3 install requests playwright rich

# Instalar navegador
playwright install chromium

# Opcional (para o emailnator original)
pip3 install quopri
```

---

## Arquivos de Saída

| Arquivo | Conteúdo |
|---|---|
| `2nr_credentials.txt` | Email, senha de cada conta 2NR criada |
| `manus_credentials.txt` | Email, senha, convite, código de cada conta Manus |
| `manus_tokens.txt` | JWT tokens das contas Manus |
| `*_2nr_ultimate.log` | Logs detalhados de cada execução do 2NR |
| `*_manus_creator.log` | Logs detalhados de cada execução do Manus |
