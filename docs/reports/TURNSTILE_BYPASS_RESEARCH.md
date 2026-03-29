# Pesquisa: Técnicas de Bypass do Cloudflare Turnstile

**Data:** 2026-03-29
**Objetivo:** Documentar todas as técnicas pesquisadas para resolver o Cloudflare Turnstile em ambiente automatizado (Kali Linux VNC)

---

## O que é o Cloudflare Turnstile

O Cloudflare Turnstile é um CAPTCHA "invisível" que substitui o reCAPTCHA. Ele verifica se o visitante é humano sem exigir interação explícita (na maioria dos casos). Opera em 3 modos:

| Modo | Descrição | Interação |
|------|-----------|-----------|
| **Managed** | Cloudflare decide se mostra desafio | Automático ou checkbox |
| **Non-interactive** | Nunca mostra desafio visual | Invisível |
| **Interactive** | Sempre mostra checkbox | Clique obrigatório |

O Manus.im usa o modo **Managed**, que pode degradar para **Interactive** quando detecta ambiente suspeito.

---

## Como o Turnstile Detecta Bots

### 1. Bug screenX/screenY do CDP (Chrome DevTools Protocol)

**Descoberta crítica:** Quando um clique é disparado via CDP (usado por Playwright, Puppeteer, Selenium), os valores de `MouseEvent.screenX` e `MouseEvent.screenY` ficam relativos ao iframe em vez de relativos à tela.

- **Clique humano real:** `screenX > 100`, `screenY > 100` (posição na tela)
- **Clique via CDP:** `screenX < 100`, `screenY < 100` (posição no iframe)

O Turnstile verifica: `if (event.screenX === event.clientX)` → bot detectado.

**Referência:** [Chrome Issue #40280325](https://issues.chromium.org/issues/40280325)

### 2. WebGL Fingerprint

O Turnstile verifica o renderer WebGL:
- `UNMASKED_RENDERER_WEBGL` (param 0x9246)
- `UNMASKED_VENDOR_WEBGL` (param 0x9245)

Renderers suspeitos:
- "Google SwiftShader" → VM/VNC sem GPU
- "Mesa" → Linux sem GPU proprietária
- "llvmpipe" → Software rendering

### 3. Canvas Fingerprint

Gera um fingerprint único baseado em como o browser renderiza canvas. Ambientes de VM/VNC geram fingerprints genéricos que estão em listas de bots.

### 4. navigator.webdriver

Browsers automatizados definem `navigator.webdriver = true`. O Patchright já corrige isso, mas Playwright padrão não.

### 5. Análise Comportamental

- Tempo entre eventos (muito rápido = bot)
- Padrão de movimento do mouse (linear = bot)
- Presença de eventos intermediários (mousemove antes de click)

---

## Ferramentas e Projetos Estudados

### Patchright

Fork do Playwright que remove detecções de automação. Não corrige o bug screenX/screenY.

**GitHub:** [AjaxMultiCommentary/patchright](https://github.com/AjaxMultiCommentary/patchright)

### Turnstile-Solver (Theyka)

Solver Python que usa Patchright para resolver Turnstile. Técnica principal: cria página HTML local com o widget Turnstile e resolve nela.

**GitHub:** [Theyka/Turnstile-Solver](https://github.com/Theyka/Turnstile-Solver)

### CDP screenX/screenY Patcher

Extensão Chrome que corrige o bug screenX/screenY via patch no `MouseEvent.prototype`.

**GitHub:** [ObjectAscended/CDP-bug-MouseEvent-.screenX-.screenY-patcher](https://github.com/ObjectAscended/CDP-bug-MouseEvent-.screenX-.screenY-patcher)

### ohmycaptcha

Biblioteca Python para resolver múltiplos tipos de CAPTCHA incluindo Turnstile. Usa serviços externos (CapSolver, 2Captcha).

**GitHub:** [shenhao-stu/ohmycaptcha](https://github.com/shenhao-stu/ohmycaptcha)

### Camoufox

Fork do Firefox com anti-fingerprinting avançado. Alternativa ao Chromium para ambientes onde a detecção é muito agressiva.

**GitHub:** [daijro/camoufox](https://github.com/daijro/camoufox)

---

## Técnicas de Bypass Documentadas

### Técnica 1: Interceptação do turnstile.render()

Intercepta a chamada `window.turnstile.render()` antes do widget carregar, captura os parâmetros (sitekey, callback), resolve via serviço externo, e injeta o token via callback.

**Prós:** Funciona independente do ambiente
**Contras:** Requer serviço pago

### Técnica 2: Local Page Harvester

Cria página HTML local com o sitekey, usa `page.route()` para servir o HTML, resolve o Turnstile na página controlada, extrai e injeta o token.

**Prós:** Gratuito, ambiente mais controlado
**Contras:** Ainda precisa resolver o captcha localmente

### Técnica 3: Patch screenX/screenY

Sobrescreve os getters de `MouseEvent.prototype.screenX/screenY` para retornar valores corrigidos quando detecta valores suspeitamente baixos.

**Prós:** Corrige a detecção principal do Turnstile
**Contras:** Pode ser detectado por verificação de integridade do prototype

### Técnica 4: Clique Real via xdotool

Usa `xdotool` para gerar eventos de mouse no nível do X11, que são indistinguíveis de cliques humanos reais.

**Prós:** Clique genuíno no nível do SO
**Contras:** Precisa de DISPLAY X11, coordenadas precisas

### Técnica 5: Serviço Externo (CapSolver/2Captcha)

Envia sitekey e URL para serviço que resolve o Turnstile em browsers reais e retorna o token.

**Prós:** Alta taxa de sucesso, independente do ambiente
**Contras:** Custo (~$0.10-0.50 por 1000 resoluções)

---

## Conclusão

A combinação de **múltiplas técnicas em cascata** é a abordagem mais robusta. O V7 implementa todas as 4 técnicas principais com fallback automático, maximizando a chance de sucesso em qualquer condição do ambiente.
