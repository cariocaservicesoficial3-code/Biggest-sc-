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
├── docs/
│   ├── checkpoints/           # Checkpoints de contexto para futuras sessões
│   ├── reports/               # Relatórios técnicos de engenharia reversa
│   └── guides/                # Guias de uso das ferramentas
├── har-analysis/              # Análises de arquivos HAR capturados
└── logs/                      # Diretório para logs de execução
```

## Ferramentas Principais

| Ferramenta | Descrição | Localização |
|---|---|---|
| **2NR APK V5** | APK modificado sem restrição de Wi-Fi, root e rate limit | `apk/modified/` |
| **2NR Ultimate V9** | Script de registro automático com Emailnator + Playwright | `scripts/2nr/2nr_ultimate_v9.py` |
| **2NR Debug V7** | Script de registro com logs detalhados em tempo real | `scripts/2nr/2nr_kali_warrior_debug.py` |
| **Manus Creator** | Script de criação de conta Manus com Turnstile semi-auto | `scripts/manus/manus_creator.py` |

## Requisitos

- **Kali Linux NetHunter** (chroot) com root
- **Python 3.8+** com pip
- **Playwright** + Chromium
- **Proxy Rotativo** (configurado nos scripts)

## Instalação Rápida

```bash
pip3 install requests playwright rich
playwright install chromium
```

## Checkpoints

Consulte `docs/checkpoints/` para contexto completo de cada fase do projeto. Útil para retomar o trabalho em novas sessões.

## Data de Criação

29 de Março de 2026
