# Biggest-SC - Projeto de Engenharia Reversa e Automação

## Visão Geral

Projeto de engenharia reversa do aplicativo **2NR (v2.1.18)** e automação de processos relacionados, desenvolvido para rodar no **Kali Linux NetHunter** com root.

## Estrutura do Repositório

```
Biggest-sc-/
├── apk/
│   └── modified/              # APKs modificados prontos para instalação
├── scripts/
│   ├── 2nr/                   # Scripts de automação do 2NR
│   └── manus/                 # Scripts de automação do Manus
│       ├── manus_creator.py       # V6 - Patchright + xdotool (referência)
│       └── manus_creator_v7.py    # V7 - Turnstile Ultra Bypass (ATUAL)
├── docs/
│   ├── checkpoints/           # Checkpoints de contexto para futuras sessões
│   ├── reports/               # Relatórios técnicos de engenharia reversa
│   └── guides/                # Guias de uso das ferramentas
├── har-analysis/              # Análises de arquivos HAR capturados
└── logs/                      # Diretório para logs de execução
```

## Ferramentas Principais

| Ferramenta | Versão | Descrição | Localização |
|---|---|---|---|
| **2NR APK V5** | v5 | APK modificado sem restrição de Wi-Fi, root e rate limit | `apk/modified/` |
| **2NR Ultimate V9** | v9 | Script de registro automático com Emailnator + Playwright | `scripts/2nr/2nr_ultimate_v9.py` |
| **2NR Debug V7** | v7 | Script de registro com logs detalhados em tempo real | `scripts/2nr/2nr_kali_warrior_debug.py` |
| **Manus Creator V6** | v6 | Script com Patchright + xdotool (referência) | `scripts/manus/manus_creator.py` |
| **Manus Creator V7** | v7 | **ATUAL** - Turnstile Ultra Bypass Multi-Strategy | `scripts/manus/manus_creator_v7.py` |

## Manus Creator V7 - Turnstile Ultra Bypass

O V7 implementa **4 estratégias de bypass em cascata** para resolver o Cloudflare Turnstile:

1. **Turnstile Render Interceptor** - Intercepta `window.turnstile.render()`, captura parâmetros e resolve via serviço externo
2. **Local Page Token Harvester** - Cria página HTML local com o sitekey, resolve em ambiente controlado
3. **screenX/screenY CDP Patch** - Corrige o bug do Chrome que permite detecção de cliques automatizados
4. **xdotool Fallback** - Clique real com movimento humanizado via curvas de Bézier

Inclui também: WebGL spoofing (NVIDIA GTX 1080 Ti), Canvas noise injection, AudioContext spoofing, Battery/Connection API spoofing.

## Requisitos

- **Kali Linux NetHunter** (chroot) com root
- **Python 3.8+** com pip
- **Patchright** (fork anti-detecção do Playwright) + Chromium
- **xdotool** (para cliques reais no VNC)
- **Proxy Rotativo** (configurado nos scripts)

## Instalação Rápida

```bash
# Dependências
pip3 install patchright requests rich --break-system-packages
python3 -m patchright install chromium
apt install xdotool

# Executar V7 (modo local)
cd scripts/manus/
python3 manus_creator_v7.py

# Executar V7 com serviço externo de CAPTCHA
CAPTCHA_API_KEY="sua_chave" CAPTCHA_SERVICE="capsolver" python3 manus_creator_v7.py
```

## Checkpoints

Consulte `docs/checkpoints/` para contexto completo de cada fase do projeto:

| Checkpoint | Descrição |
|---|---|
| `CHECKPOINT_001` | Contexto geral do projeto e engenharia reversa |
| `CHECKPOINT_002` | Engenharia reversa do 2NR |
| `CHECKPOINT_003` | Scripts de automação |
| `CHECKPOINT_004` | Ambiente Kali NetHunter |
| `CHECKPOINT_005` | **Turnstile Ultra Bypass V7** - Estratégias e implementação |

## Histórico

- **2026-03-29** - V7: Turnstile Ultra Bypass com 4 estratégias em cascata
- **2026-03-29** - V6: Patchright + xdotool + WebGL fix
- **2026-03-29** - Projeto criado com engenharia reversa do 2NR
