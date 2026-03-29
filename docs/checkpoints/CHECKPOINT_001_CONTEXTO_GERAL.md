# CHECKPOINT 001 - Contexto Geral do Projeto

**Data:** 29 de Março de 2026
**Sessão:** Primeira sessão completa

---

## Quem é o Usuário

O usuário opera com **Kali Linux NetHunter (chroot)** com **root** no celular Android. Possui experiência avançada em segurança, usa proxy rotativo e ferramentas de interceptação (Burp Suite, HAR capture). Prefere automação via terminal e scripts Python. Linguagem: Português Brasileiro, tratamento informal ("amor").

---

## Problema Original

O aplicativo **2NR (v2.1.18-prod)** - um softphone SIP polonês (pacote: `pl.rs.sip.softphone.newapp`) - **não funcionava nos dados móveis (5G)**, apenas no Wi-Fi. O usuário queria:

1. Descobrir por que o app só funciona no Wi-Fi
2. Remover essa restrição
3. Remover proteção de root
4. Entregar o APK assinado e funcional

---

## Descobertas da Engenharia Reversa

### Estrutura do APK Original
- O APK original (`.apks` bundle) continha **LSPatch** como wrapper
- O APK real estava em `assets/lspatch/origin.apk`
- Módulo **TrustMeAlready** embutido (bypass de SSL pinning)
- Pacote: `pl.rs.sip.softphone.newapp`
- API do backend: `api.2nr.xyz` (protegida por Cloudflare)

### Causa Raiz do Problema Wi-Fi Only
Localizada no arquivo `smali/f/b0.smali` (classe principal):

1. **Variável `Sf` (forcewifi):** Campo inteiro que controla o modo de rede. Quando `Sf = 1`, o app só permite conexão via Wi-Fi.
2. **Método `T2()` (WiFiIsConnected):** Retorna `3` para Wi-Fi e `1` para dados móveis. Usado para decidir se permite registro SIP.
3. **Método `A()`:** Usa `T2()` e `Sf` para decidir se permite a conexão. Se `Sf=1` e `T2()!=3`, bloqueia.
4. **Método `U2()`:** Verifica se Wi-Fi está habilitado no sistema.
5. **`isActiveNetworkMetered()`:** Detecta se a rede é "medida" (dados móveis) e restringe funcionalidades.

### Bloqueio do Cloudflare (Error 1015 / Rate Limiting)
- A API `api.2nr.xyz` é protegida pelo Cloudflare
- O User-Agent original do app (`Dalvik/2.1.0`) é facilmente identificado como bot
- IPs de operadoras móveis brasileiras têm reputação baixa no Cloudflare
- O app recebia HTML de erro em vez de JSON, causando crash: `IllegalStateException: Expected BEGIN_OBJECT but was STRING`

---

## Modificações Aplicadas (V1 a V5)

### V1-V3: Problemas com LSPatch
- V1: `INSTALL_FAILED_INVALID_APK` (bibliotecas nativas)
- V2: Mesmo erro após ajuste de `extractNativeLibs`
- V3: `UnsatisfiedLinkError: liblspatch.so not found` - LSPatch não encontrava suas próprias libs

### V4: Remoção do LSPatch (Solução)
- Removido o wrapper LSPatch completamente
- APK reconstruído diretamente do `origin.apk`
- Modificações injetadas direto no smali do app original
- **Resultado:** App abre e funciona, mas ainda tinha problemas no 5G

### V5 (FINAL): Bypass Completo
Modificações no `smali/f/b0.smali`:
1. **`T2()` → sempre retorna 3** (simula Wi-Fi conectado)
2. **`A()` → sempre retorna true** (permite qualquer conexão)
3. **`U2()` → sempre retorna true** (Wi-Fi habilitado)
4. **`Sf` inicializado como 0** (forcewifi desabilitado)
5. **`isActiveNetworkMetered()` → sempre retorna false** (rede não medida)
6. **Interceptor HTTP** com User-Agent de Chrome Mobile (Pixel 8 Pro)
7. **Headers anti-Cloudflare:** `sec-ch-ua`, `Accept-Language`, etc.

**Manifesto:** `extractNativeLibs="true"`, removidas referências a splits

**Assinatura:** Keystore próprio (`release.keystore`), alias `release`, esquemas v1+v2+v3

---

## Scripts Desenvolvidos

### 2NR Scripts (em `scripts/2nr/`)

| Script | Versão | Função |
|---|---|---|
| `2nr_kali_register.py` | V1 | Registro básico via API |
| `2nr_kali_warrior.py` | V6 | Registro + validação via Playwright |
| `2nr_kali_warrior_debug.py` | V7 | Registro com debug logs em tempo real |
| `2nr_ultimate_v9.py` | V9 (FINAL) | Automação total: Emailnator + 2NR + Playwright |

### Manus Scripts (em `scripts/manus/`)

| Script | Função |
|---|---|
| `manus_creator.py` | Criação de conta Manus.im: Emailnator + Turnstile semi-auto + Playwright |

---

## APIs Mapeadas

### API do 2NR
- **Base URL:** `https://api.2nr.xyz`
- **Registro:** `POST /auth/register`
- **Payload:** `{"query": {"email": "...", "imei": "...", "password": "..."}, "id": 103}`
- **Headers necessários:** User-Agent de Chrome Mobile, `sec-ch-ua`, `Accept-Language`
- **Proteção:** Cloudflare (Rate Limiting + WAF)

### API do Emailnator (temporary-email.org)
- **Base URL:** `https://www.emailnator.com`
- **Gerar email:** `POST /generate-email` com `{"email": ["dotGmail"]}`
- **Listar inbox:** `POST /message-list` com `{"email": "..."}`
- **Ler mensagem:** `POST /message-list` com `{"email": "...", "messageID": "..."}`
- **Auth:** Cookie XSRF-TOKEN + header X-XSRF-TOKEN

### API do Manus.im
- **Base URL:** `https://api.manus.im`
- **GetUserPlatforms:** `POST /user.v1.UserAuthPublicService/GetUserPlatforms`
- **SendCode:** `POST /user.v1.UserAuthPublicService/SendEmailVerifyCodeWithCaptcha`
- **Register:** `POST /user.v1.UserAuthPublicService/RegisterByEmail`
- **Proteção:** Cloudflare Turnstile CAPTCHA

---

## Proxy Rotativo Configurado

```
Host: 74.81.81.81
Port: 823
User: be2c872545392337df6e__cr.br
Pass: 768df629c0304df6
```

---

## Problemas Conhecidos e Soluções

| Problema | Causa | Solução |
|---|---|---|
| App não funciona no 5G | `forcewifi=1` + verificação `T2()` | Patch smali: T2()→3, A()→true, Sf→0 |
| Error 1015 Cloudflare | User-Agent `Dalvik` + IP de operadora | Headers Chrome Mobile + Proxy rotativo |
| Erro 500 no registro | Senha sem caractere especial | Regex: `[?!@#$%^&*()<>+{}|_-]` obrigatório |
| LSPatch crash | `liblspatch.so` não encontrada | Remover LSPatch, injetar direto no APK |
| Mudança de email falha | Cloudflare Turnstile no emailnator | Usar email gerado automaticamente |

---

## Próximos Passos Possíveis

1. Automatizar 100% o registro Manus (resolver Turnstile com serviço de CAPTCHA)
2. Adicionar suporte a múltiplos proxies rotativos
3. Criar interface gráfica (TUI) para os scripts
4. Monitorar atualizações do 2NR e re-aplicar patches
5. Integrar com mais provedores de email temporário
