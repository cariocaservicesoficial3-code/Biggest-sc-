# CHECKPOINT 005 - Turnstile Ultra Bypass V7

**Data:** 2026-03-29
**Status:** Implementado - Aguardando teste no Kali

---

## Contexto: O Problema do Turnstile no V6

O Manus Account Creator V6 utilizava **Patchright + xdotool** para resolver o Cloudflare Turnstile no ambiente Kali Linux NetHunter + KeX VNC. Apesar de funcionar parcialmente, o Turnstile consistentemente falhava com o status **"Verification failed"** mesmo com cliques manuais no navegador.

### Diagnóstico Raiz (V6)

| Problema | Causa | Impacto |
|----------|-------|---------|
| WebGL "Software only" | SwiftShader no VNC sem GPU | Turnstile rejeita por fingerprint de VM |
| screenX/screenY bug | CDP reporta valores relativos ao iframe | Turnstile detecta clique automatizado |
| Canvas fingerprint | Sem GPU = fingerprint genérico | Baixa pontuação de confiança |
| Falta de noise | AudioContext/Canvas idênticos | Fingerprint de bot |
| xdotool coordenadas | Cálculo impreciso no VNC | Clique fora do checkbox |

### Evidências dos Logs V6

```
2026-03-29 07:56:20,381 [INFO] Tentativa Turnstile 1/3
2026-03-29 07:56:24,137 [INFO] xdotool clicou em (151, 670)
2026-03-29 07:56:56,200 [WARNING] Turnstile não resolveu em 30s
2026-03-29 07:56:56,229 [WARNING] Turnstile não resolveu, recarregando página...
```

O Turnstile ficava preso em **"Verifying..."** e depois falhava, indicando que o clique era detectado como não-humano.

---

## Solução V7: Multi-Strategy Cascade Engine

O V7 implementa **4 estratégias de bypass em cascata**, cada uma mais sofisticada que a anterior, com fallback automático.

### Estratégia 1: Turnstile Render Interceptor + External Solver

**Conceito:** Intercepta `window.turnstile.render()` antes do widget carregar, captura os parâmetros (sitekey, cData, chlPageData, callback), e resolve via serviço externo.

**Fluxo:**
1. Script injetado via `add_init_script` intercepta a definição de `window.turnstile`
2. Quando `turnstile.render()` é chamado, captura todos os parâmetros
3. Envia para CapSolver ou 2Captcha via API
4. Recebe token resolvido
5. Injeta via `window.__injectTurnstileToken(token)` que chama o callback original

**Requisito:** Chave API do CapSolver ou 2Captcha (variável `CAPTCHA_API_KEY`)

### Estratégia 2: Local Page Token Harvester

**Conceito:** Inspirado no **Turnstile-Solver** de Theyka. Cria uma página HTML local com o sitekey do Manus, carrega o widget Turnstile nessa página controlada, resolve o captcha, e injeta o token na página real.

**Fluxo:**
1. Extrai o sitekey da página real (via interceptor ou DOM)
2. Cria HTML com `<div class="cf-turnstile" data-sitekey="...">` e callback
3. Usa `page.route()` para interceptar URL e servir o HTML customizado
4. Abre nova aba com a página harvester
5. Turnstile carrega e exibe checkbox
6. Clica via xdotool (ambiente mais controlado)
7. Extrai token do input hidden
8. Injeta na página real via `__injectTurnstileToken()`

**Vantagem:** O widget carrega em ambiente limpo, sem interferência da página do Manus.

### Estratégia 3: screenX/screenY CDP Patch + Enhanced xdotool

**Conceito:** Corrige o bug do Chrome DevTools Protocol onde `MouseEvent.screenX/screenY` ficam relativos ao iframe (valores < 100) em vez de relativos à tela (valores > 100). O Cloudflare Turnstile verifica exatamente isso para detectar cliques automatizados.

**Implementação:**
```javascript
// Patch no MouseEvent.prototype.screenX getter
Object.defineProperty(MouseEvent.prototype, 'screenX', {
    get: function() {
        const origVal = screenXDesc.get.call(this);
        if (origVal < 100 && this.clientX > 0) {
            return this.clientX + getScreenX() + 
                   (window.outerWidth - window.innerWidth) / 2;
        }
        return origVal;
    }
});
```

Combinado com **xdotool humanizado** usando curvas de Bézier para movimento natural do mouse.

### Estratégia 4: xdotool Fallback (V6 Compat)

**Conceito:** Fallback do V6 com clique xdotool simples. Mantido para compatibilidade.

---

## Melhorias Adicionais V7

### Stealth Anti-Fingerprint

| Componente | Técnica |
|------------|---------|
| WebGL | Spoof renderer para NVIDIA GTX 1080 Ti + extensões reais |
| Canvas | Noise injection com seed consistente por sessão |
| AudioContext | Ruído imperceptível no getFloatFrequencyData |
| Navigator | Plugins, languages, platform, hardwareConcurrency |
| Battery API | Sempre retorna desktop (charging=true, level=1) |
| Connection API | rtt=50, downlink=10, effectiveType='4g' |

### Mouse Humanizado (Curva de Bézier)

O V7 implementa movimento de mouse com **curva de Bézier cúbica**:
- 4 pontos de controle com variação aleatória
- 15-40 passos dependendo da distância
- Delays variáveis (mais lento no início/fim, mais rápido no meio)
- Pausa natural antes do clique (50-150ms)

### Digitação Humanizada

Email digitado caractere por caractere com delay aleatório de 30-80ms entre cada tecla.

---

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `scripts/manus/manus_creator_v7.py` | Script principal V7 (2400 linhas) |
| `scripts/manus/manus_creator.py` | Script V6 (mantido como referência) |
| `docs/checkpoints/CHECKPOINT_005_TURNSTILE_V7.md` | Este checkpoint |

---

## Instalação e Uso

```bash
# Dependências
pip3 install patchright requests rich --break-system-packages
python3 -m patchright install chromium
apt install xdotool

# Executar (modo local - sem API externa)
python3 manus_creator_v7.py

# Executar com serviço de CAPTCHA externo
CAPTCHA_API_KEY="sua_chave" CAPTCHA_SERVICE="capsolver" python3 manus_creator_v7.py
```

---

## Próximos Passos

1. Testar V7 no Kali NetHunter com KeX VNC
2. Validar se o patch screenX/screenY corrige a detecção
3. Testar Local Page Harvester isoladamente
4. Se necessário, integrar Camoufox (Firefox fork anti-detecção)
5. Considerar proxy residencial para melhorar reputação de IP
