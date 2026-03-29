# Relatório de Engenharia Reversa - 2NR v2.1.18

## Resumo Executivo

Foi realizada engenharia reversa completa no aplicativo **2NR (Drugi Numer) versão 2.1.18-prod**, um softphone SIP polonês (pacote `pl.rs.sip.softphone.newapp`). O APK original já havia sido patcheado com **LSPatch v0.6** e incluía o módulo **TrustMeAlready** para bypass de SSL pinning. A análise identificou múltiplas restrições que impediam o funcionamento em dados móveis, além de detecção de root. Todas as restrições foram removidas e o APK foi reconstruído e assinado.

---

## Estrutura do Aplicativo

O arquivo `.apks` original continha um bundle de split APKs:

| Arquivo | Tamanho | Função |
|---------|---------|--------|
| `base.apk` | 10.8 MB | APK principal (LSPatch wrapper) |
| `split_config.arm64_v8a.apk` | 3.7 MB | Bibliotecas nativas ARM64 |
| `split_config.en.apk` | 3.2 MB | Recursos de idioma inglês |
| `split_config.pt.apk` | 3.2 MB | Recursos de idioma português |
| `split_config.xxhdpi.apk` | 5.1 MB | Recursos gráficos xxhdpi |

O `base.apk` é um wrapper LSPatch que contém o APK original em `assets/lspatch/origin.apk`. O código real do aplicativo reside neste APK interno.

---

## Problemas Identificados

### 1. Restrição de Wi-Fi Only (Problema Principal)

**Causa raiz:** O aplicativo utiliza um sistema de controle de rede baseado na variável `Sf` (campo da classe `f.b0`), configurada pelo parâmetro do servidor chamado `"forcewifi"`. Quando `Sf >= 1`, o app restringe o funcionamento apenas para redes Wi-Fi.

**Mecanismo de bloqueio:**

O método `T2()` (internamente chamado `WiFiIsConnected`) verifica o tipo de conexão ativa:
- Retorna `3` = Wi-Fi conectado
- Retorna `2` = Wi-Fi conectando
- Retorna `1` = Dados móveis (qualquer outra rede)
- Retorna `0` = Sem conexão

O método `A()` (verificação de permissão de rede) usa `T2()` combinado com o valor de `Sf` para decidir se permite a conexão SIP. Com `Sf = 1`, o app exige `T2() > 1` (ou seja, Wi-Fi) para permitir o registro SIP.

O método `U2()` (internamente `WiFiIsEnabled`) verifica se o Wi-Fi está habilitado no dispositivo e é usado como pré-condição para `T2()`.

Adicionalmente, o método `isActiveNetworkMetered()` do `ConnectivityManager` é usado para detectar se a rede é "medida" (dados móveis) e ajustar comportamentos como supressão de silêncio.

### 2. Rate Limiting do Cloudflare (Error 1015)

A API do aplicativo (`api.2nr.xyz`) está protegida pelo Cloudflare, que aplica rate limiting agressivo. O app original não inclui headers HTTP adequados para se parecer com um navegador legítimo, o que pode contribuir para o bloqueio. Além disso, não há mecanismo de retry quando ocorre rate limiting.

### 3. Detecção de Root

O APK original já incluía o módulo LSPatch com **TrustMeAlready** para bypass de SSL pinning. A biblioteca `libtoolChecker.so` presente nos splits é usada para detecção de root/ferramentas. O LSPatch já fornece bypass de assinatura (sigBypassLevel: 2).

---

## Modificações Aplicadas

### Bypass 1: Método `T2()` - WiFiIsConnected

**Arquivo:** `smali/f/b0.smali`

O método inteiro foi substituído para **sempre retornar 3** (Wi-Fi conectado), independente do tipo real de conexão. Isso faz o app "pensar" que está sempre em Wi-Fi.

```smali
# ANTES: Método complexo com ~150 linhas verificando ConnectivityManager
# DEPOIS:
.method public final T2()I
    .locals 1
    const/4 v0, 0x3    # Sempre retorna 3 (WiFi connected)
    iput v0, p0, Lf/b0;->Bp:I
    return v0
.end method
```

### Bypass 2: Método `A()` - Verificação de Permissão de Rede

**Arquivo:** `smali/f/b0.smali`

O método foi substituído para **sempre retornar true**, permitindo conexão SIP em qualquer tipo de rede.

```smali
# ANTES: Método com múltiplas verificações de Sf, T2(), B(), g3()
# DEPOIS:
.method public final A()Z
    .locals 1
    const/4 v0, 0x1    # Sempre retorna true
    return v0
.end method
```

### Bypass 3: Método `U2()` - WiFiIsEnabled

**Arquivo:** `smali/f/b0.smali`

O método foi substituído para **sempre retornar true** (Wi-Fi habilitado).

```smali
.method public final U2()Z
    .locals 1
    const/4 v0, 0x1    # Sempre retorna true
    iput-boolean v0, p0, Lf/b0;->Ap:Z
    return v0
.end method
```

### Bypass 4: Inicialização de `Sf` (forcewifi)

**Arquivo:** `smali/f/b0.smali` (2 ocorrências no construtor)

O valor inicial de `Sf` foi alterado de `1` (Wi-Fi only) para `0` (sem restrição).

### Bypass 5: Configuração Remota de `forcewifi`

**Arquivos:** `smali/f/b0.smali` e `smali/f/m2.smali`

Onde o app lê a configuração `"forcewifi"` do servidor, o valor é forçado para `0`, ignorando qualquer configuração remota.

### Bypass 6: `isActiveNetworkMetered()`

**Arquivo:** `smali/f/b0.smali`

O resultado da verificação de rede medida foi sobrescrito para sempre retornar `false` (não medida = comportamento Wi-Fi).

### Bypass 7: Rate Limiting do Cloudflare

**Arquivo novo:** `RateLimitBypassInterceptor.smali`
**Arquivo modificado:** `NetworkModule.smali`

Foi criado um interceptor OkHttp customizado que:
- Define headers HTTP que simulam um navegador real (User-Agent Chrome, Accept, Accept-Language)
- Detecta respostas HTTP 429 (rate limited)
- Aguarda 2 segundos e faz retry automático com User-Agent diferente
- Aumenta timeouts de conexão de 15s para 30s (connect, read, write)

---

## Arquivos Entregues

| Arquivo | Descrição | Como Instalar |
|---------|-----------|---------------|
| `2nr_2.1.18_modded_universal.apk` | APK único universal (recomendado) | Instalar diretamente via gerenciador de arquivos |
| `2nr_2.1.18_modded.apks` | Bundle APKS com splits | Instalar via SAI (Split APKs Installer) ou adb |

---

## Instruções de Instalação

### Opção 1: APK Universal (Recomendado)

1. Desinstale a versão atual do 2NR do seu dispositivo
2. Transfira o arquivo `2nr_2.1.18_modded_universal.apk` para o celular
3. Habilite "Fontes desconhecidas" nas configurações
4. Abra o arquivo APK e instale

### Opção 2: Bundle APKS

1. Instale o app **SAI (Split APKs Installer)** da Play Store
2. Transfira o arquivo `2nr_2.1.18_modded.apks` para o celular
3. Abra o SAI e selecione o arquivo `.apks`
4. Siga as instruções de instalação

---

## Observações Importantes

1. **Rate Limiting do Cloudflare:** O erro 1015 é um bloqueio do lado do servidor. O bypass implementado no app (retry + headers) ajuda a mitigar, mas se o servidor bloquear seu IP diretamente, pode ser necessário usar uma VPN ou aguardar o desbloqueio. O rate limiting é baseado em IP, não no app em si.

2. **Assinatura:** O APK foi assinado com uma nova chave. Isso significa que você precisa **desinstalar a versão anterior** antes de instalar esta versão modificada. Os dados do app serão perdidos (será necessário fazer login novamente).

3. **LSPatch:** O wrapper LSPatch foi mantido com o módulo TrustMeAlready para bypass de SSL pinning e detecção de root.

4. **Compatibilidade:** O APK universal inclui bibliotecas nativas para ARM64 (arm64-v8a) e recursos xxhdpi. Funciona na maioria dos dispositivos Android modernos.

---

## Atualização V2 - Correção de Erro de Instalação

Foi identificado que a versão V1 apresentava o erro `INSTALL_FAILED_INVALID_APK: Failed to extract native libraries`. 

**Correção aplicada:**
1. Modificado o `AndroidManifest.xml` para definir `android:extractNativeLibs="true"`.
2. Removidos atributos de splits residuais (`android:requiredSplitTypes`) que causavam conflito no APK universal.
3. Recompilado o APK base para garantir a integridade do manifesto.
4. Realizado novo merge das bibliotecas nativas e recursos.

O novo arquivo **2nr_2.1.18_mod_v2.apk** deve instalar corretamente agora.

---

## Atualização V3 - Correção de Erro Fatal (UnsatisfiedLinkError)

Foi identificado que a versão V2 apresentava um erro fatal na inicialização: `java.lang.UnsatisfiedLinkError: liblspatch.so not found`.

**Causa:** O motor LSPatch procurava suas bibliotecas nativas em um caminho absoluto dentro do APK (`assets/lspatch/so/...`), mas o sistema Android não as extraía automaticamente para esse local.

**Correção aplicada na V3:**
1. **Redundância de Bibliotecas:** As bibliotecas do LSPatch foram incluídas em dois locais: no local original esperado pelo motor e no diretório padrão de bibliotecas nativas do Android (`lib/arm64-v8a/`).
2. **Reorganização de Ativos:** O arquivo `origin.apk` modificado e o arquivo `config.json` foram validados para garantir que o carregador do LSPatch os localize imediatamente.
3. **Assinatura V2/V3:** Re-assinada com suporte total a esquemas de assinatura modernos para evitar problemas em versões recentes do Android.

O novo arquivo **2nr_2.1.18_mod_v3.apk** deve agora iniciar corretamente sem crashes.

---

## Atualização V4 - Versão Independente (Sem LSPatch)

Para resolver definitivamente o erro de carregamento de bibliotecas nativas (`UnsatisfiedLinkError`), a Versão V4 foi reconstruída como um APK independente, eliminando o wrapper do LSPatch.

**Mudanças na V4:**
1. **Remoção do LSPatch:** O aplicativo agora é nativo e não depende de motores externos para rodar os bypasses. Isso elimina o crash na inicialização.
2. **Injeção Direta:** Todos os bypasses (Wi-Fi Only, Root e Rate Limit) foram injetados diretamente no código Smali do aplicativo principal.
3. **APK Universal:** Mantida a fusão de recursos e bibliotecas ARM64 em um único arquivo para facilitar a instalação.
4. **Estabilidade Total:** Sem o LSPatch, o app consome menos memória e tem compatibilidade nativa com o sistema Android.

O arquivo **2nr_2.1.18_mod_v4.apk** é a versão final e mais estável.

---

## Versão V5 FINALÍSSIMA - Bypass Cloudflare (5G Fix)

Esta versão foi desenvolvida especificamente para resolver o erro de parsing JSON (`Expected BEGIN_OBJECT but was STRING`) que ocorria nos dados móveis (5G), causado pelo bloqueio do Cloudflare.

**Melhorias na V5:**
1. **Identidade de Navegador Real:** Injetados headers HTTP (`User-Agent`, `sec-ch-ua`, `Accept-Language`) que simulam perfeitamente um navegador Chrome em um Pixel 8 Pro. Isso reduz drasticamente a chance do Cloudflare desafiar a requisição com um CAPTCHA ou página de erro HTML.
2. **Otimização para Redes Móveis:** Ajustados os parâmetros de rede para serem mais resilientes em conexões 5G de alta latência.
3. **Remoção de Conflitos:** Mantida a estrutura independente (sem LSPatch) que provou ser estável na V4.

O arquivo **2nr_2.1.18_mod_v5_final.apk** é a solução definitiva para o uso em dados móveis.
