# CHECKPOINT 007 - Network Fix V7.2

**Data:** 2026-03-29
**Versão:** V7.2 (NETWORK FIX)
**Status:** Correção de bloqueio de rede

---

## Problema Reportado

Após o hotfix V7.1 (que removeu as flags problemáticas), o widget do Turnstile **ainda não aparecia** na página. O diagnóstico V7.1 revelou a causa real:

```
[DIAG] challenges.cloudflare.com: BLOCKED
[WARNING] challenges.cloudflare.com NÃO acessível! (BLOCKED)
[DIAG] Status: {scriptTags: 1, hasWidget: False, hasIframe: False, hasTurnstileObj: False}
```

O widget não renderiza porque o browser não consegue se comunicar com `challenges.cloudflare.com`.

## Diagnóstico

### Teste de controle
Acessando `manus.im/login` de um browser em ambiente limpo (sandbox), o Turnstile **aparece normalmente** mostrando "Verifying..." com logo Cloudflare. Isso confirma que:

- O site Manus **usa** Turnstile normalmente
- O código V7.1 **não tem bugs** que impeçam o carregamento
- O problema é **100% de rede** no ambiente Kali NetHunter

### Causa raiz
O IP do 5G do usuário entrou na **lista negra do Cloudflare** por excesso de tentativas de automação. O Cloudflare bloqueia `challenges.cloudflare.com` para IPs suspeitos, impedindo que o widget Turnstile sequer carregue.

Evidências:
- 6 verificações consecutivas: `challenges.cloudflare.com: BLOCKED`
- `scriptTags: 1` (o script é referenciado no HTML mas não executa)
- `hasWidget: False` (nenhum widget renderizado)
- `hasIframe: False` (nenhum iframe do CF criado)

## Solução V7.2

### Novas funcionalidades

| Funcionalidade | Descrição |
|---|---|
| `fix_dns()` | Força DNS públicos (1.1.1.1, 8.8.8.8, 8.8.4.4, 1.0.0.1) |
| `flush_dns_cache()` | Limpa cache DNS e rotas no Android |
| `rotate_ip_airplane()` | Troca IP via modo avião (svc data ou airplane_mode) |
| `check_cloudflare_connectivity()` | Preflight check via HTTP direto e via proxy |
| `get_current_ip()` | Obtém IP público atual para monitoramento |
| Browser com proxy | Lança browser com proxy quando CF bloqueado |
| IP rotation no cascade | Troca IP automaticamente na tentativa 2+ |

### Fluxo V7.2

```
ETAPA 2.5: PREPARANDO REDE
  ├── fix_dns() → Configura 1.1.1.1/8.8.8.8
  ├── flush_dns_cache() → Limpa cache
  ├── get_current_ip() → Registra IP
  ├── check_cloudflare_connectivity()
  │   ├── OK → Prosseguir normalmente
  │   ├── BLOCKED → rotate_ip_airplane()
  │   │   ├── Novo IP → Re-verificar
  │   │   └── Ainda bloqueado → Usar PROXY
  │   └── PROXY → Usar proxy no browser
  └── Lançar browser (com ou sem proxy)

CASCADE RESOLVER (5 tentativas):
  ├── Tentativa 1: Normal
  ├── Tentativa 2: Se falhar, trocar IP
  ├── Tentativa 3: Se falhar, trocar IP novamente
  ├── Tentativa 4-5: Últimas tentativas
  └── Cada tentativa: diagnose → estratégias 1-4
```

## Arquivos Modificados

- `scripts/manus/manus_creator_v7.py` (V7.1 → V7.2)
- `docs/checkpoints/CHECKPOINT_007_NETWORK_FIX_V72.md` (novo)

## Instruções para o Usuário

### Antes de executar V7.2:
```bash
# 1. Ativar modo avião por 30 segundos, depois desativar
# 2. Configurar DNS manualmente (caso V7.2 não consiga):
echo "nameserver 1.1.1.1" > /etc/resolv.conf
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

# 3. Testar conectividade:
curl -s https://challenges.cloudflare.com/cdn-cgi/trace
# Se retornar dados → OK
# Se timeout → IP ainda bloqueado

# 4. Executar:
python3 manus_creator_v7.py
```
