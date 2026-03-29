# CHECKPOINT 006 - Hotfix V7.1: Turnstile Não Carregava

**Data:** 2026-03-29
**Status:** Hotfix aplicado - Aguardando teste

---

## Problema Reportado

Ao executar o V7 no Kali NetHunter, o widget do Cloudflare Turnstile **não aparecia** na página. O espaço onde deveria estar o checkbox ficava vazio. A página também demorava muito para carregar e atualizar. Mesmo tentando clicar manualmente, não havia nada para clicar.

Nos logs, todas as estratégias falharam com a mesma mensagem: **"Sitekey não encontrado"** e **"Turnstile não encontrado"**, indicando que o widget nunca renderizou.

---

## Diagnóstico

### Causa Raiz: Flag `--disable-web-security`

A flag `--disable-web-security` foi adicionada no V7 como parte das "flags anti-detecção extras". Esta flag **QUEBRA COMPLETAMENTE** o Cloudflare Turnstile desde fevereiro de 2025.

| Evidência | Detalhe |
|-----------|---------|
| **Fonte** | [Cloudflare Community Thread](https://community.cloudflare.com/t/disable-web-security-regression/766856) |
| **Data** | Fevereiro 2025 |
| **Sintoma** | "Every Cloudflare Turnstile site now rejects the browser with an infinite refresh loop" |
| **Causa** | Cloudflare detecta a flag e recusa renderizar o widget |

### Comparação V6 vs V7

O V6 **não tinha** as seguintes flags que foram adicionadas no V7:

| Flag | V6 | V7 | Efeito no Turnstile |
|------|----|----|---------------------|
| `--disable-web-security` | Ausente | Presente | **QUEBRA TOTAL** |
| `--disable-site-isolation-trials` | Ausente | Presente | Pode interferir com iframes |
| `--allow-running-insecure-content` | Ausente | Presente | Suspeito |

### Causa Secundária: Interceptor Agressivo

O `Object.defineProperty` no `window.turnstile` poderia potencialmente interferir com o carregamento do widget em edge cases, embora a causa principal seja a flag do browser.

---

## Correções Aplicadas (V7.1)

### 1. Remoção de Flags Problemáticas

As três flags perigosas foram removidas dos `browser_args`. O V7.1 agora usa exatamente as mesmas flags do V6 (que funcionava) mais apenas os patches de stealth via JavaScript.

### 2. Interceptor Mais Seguro

O interceptor do Turnstile agora tem `try/catch` robusto em todos os pontos críticos. Se o patch falhar, o Turnstile funciona normalmente sem interceptação.

### 3. Diagnóstico de Rede

Nova função `diagnose_turnstile_loading()` que verifica antes de tentar resolver:
- Se `challenges.cloudflare.com` está acessível
- Se o script do Turnstile foi carregado
- Se o iframe do Turnstile apareceu
- Se `window.turnstile` existe

### 4. Espera Adequada

A navegação agora usa `wait_until="networkidle"` (em vez de `domcontentloaded`) e espera 8 segundos para a página estabilizar antes de tentar interagir.

### 5. Re-preenchimento de Email

Após cada reload da página, o email é automaticamente re-preenchido com digitação humanizada.

---

## Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `scripts/manus/manus_creator_v7.py` | Atualizado para V7.1 (2569 linhas) |
| `docs/checkpoints/CHECKPOINT_006_HOTFIX_V71.md` | Este checkpoint |
