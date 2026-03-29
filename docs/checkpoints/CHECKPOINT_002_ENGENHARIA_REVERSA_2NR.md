# CHECKPOINT 002 - Engenharia Reversa do 2NR

**Data:** 29 de Março de 2026
**Foco:** Detalhes técnicos da análise e modificação do APK

---

## Ferramentas Utilizadas

| Ferramenta | Versão | Uso |
|---|---|---|
| apktool | 2.9.3 | Descompilação/recompilação smali |
| jadx | 1.5.0 | Descompilação para Java legível |
| apksigner | Android SDK | Assinatura do APK |
| zipalign | Android SDK | Alinhamento do APK |
| keytool | JDK | Geração de keystore |

---

## Estrutura do APK Original

O arquivo original era um `.apks` (bundle):

```
2nr_2.1.18-prod.apks (ZIP)
├── base.apk                    # APK principal (wrapper LSPatch)
│   ├── AndroidManifest.xml     # Manifesto com LSPatch AppComponentFactory
│   ├── classes.dex             # Código LSPatch (metaloader)
│   ├── assets/
│   │   └── lspatch/
│   │       ├── config.json     # Configuração LSPatch
│   │       ├── origin.apk      # <-- APK REAL DO 2NR
│   │       ├── modules/
│   │       │   └── TrustMeAlready.apk
│   │       └── so/
│   │           └── arm64-v8a/
│   │               └── liblspatch.so
│   └── lib/
│       └── arm64-v8a/
│           ├── liblspatch.so
│           └── (outras libs)
├── split_config.arm64_v8a.apk  # Libs nativas ARM64
├── split_config.xxhdpi.apk     # Recursos de densidade
└── split_config.pt.apk         # Recursos de idioma
```

---

## Arquivos Smali Críticos

### `smali/f/b0.smali` (Classe Principal)
Este é o arquivo mais importante. Contém toda a lógica de rede e conectividade.

**Métodos modificados:**

1. **`T2()` - WiFiIsConnected** (linha ~37900)
   - Original: Verifica `ConnectivityManager` e retorna tipo de rede
   - Modificado: `const/4 v0, 0x3` + `return v0` (sempre retorna 3 = Wi-Fi)

2. **`A()` - AllowConnection** (linha ~15800)
   - Original: Verifica `Sf` e `T2()` para decidir se permite conexão
   - Modificado: `const/4 v0, 0x1` + `return v0` (sempre true)

3. **`U2()` - WiFiEnabled** (linha ~38800)
   - Original: Verifica `WifiManager.isWifiEnabled()`
   - Modificado: `const/4 v0, 0x1` + `return v0` (sempre true)

4. **`isActiveNetworkMetered`** (linha ~23200)
   - Original: Chama `ConnectivityManager.isActiveNetworkMetered()`
   - Modificado: Resultado sobrescrito para `false` (rede não medida)

### `smali/f/b0.smali` - Campo `Sf` (forcewifi)
- Tipo: `int`
- Valor original: `1` (forçar Wi-Fi)
- Valor modificado: `0` (permitir qualquer rede)
- Inicializado no construtor (linha ~6150)
- Lido de configuração em `m2.smali` (linha ~9530)

### `smali/f/m2.smali` - Leitura de forcewifi
- Linha ~9530: Lê valor de `forcewifi` da configuração do servidor
- Modificado para sempre definir `Sf = 0`

### `smali_classes2/.../NetworkModule.smali`
- Configuração do OkHttp/Retrofit
- Adicionado interceptor customizado para headers anti-Cloudflare

---

## Keystore de Assinatura

```
Arquivo: release.keystore
Alias: release
Senha: android123
Algoritmo: RSA 2048
Validade: 10000 dias
```

---

## Comandos de Reconstrução

```bash
# Descompilar
java -jar apktool.jar d origin.apk -o origin_decoded -f

# Recompilar
java -jar apktool.jar b origin_decoded -o origin_rebuilt.apk --use-aapt2

# Criar APK universal (combinar base + splits)
mkdir -p universal_temp
cd universal_temp
unzip ../origin_rebuilt.apk
# Copiar libs de split_config.arm64_v8a.apk
unzip -o ../split_config.arm64_v8a.apk "lib/*"
cd ..
cd universal_temp && zip -r ../universal.apk . && cd ..

# Zipalign
zipalign -v -p 4 universal.apk universal_aligned.apk

# Assinar
apksigner sign --ks release.keystore --ks-key-alias release \
  --ks-pass pass:android123 --key-pass pass:android123 \
  --v1-signing-enabled true --v2-signing-enabled true \
  --v3-signing-enabled true universal_aligned.apk
```

---

## Validação de Senha do 2NR

O servidor do 2NR valida a senha com o seguinte padrão regex:

```
[?!@#$%^&*()<>+{}|_-]
```

A senha DEVE conter pelo menos 1 caractere especial desta lista. Senhas apenas alfanuméricas retornam erro 1010 (status 500).

---

## Endpoints da API 2NR

```
Base: https://api.2nr.xyz
Registro: POST /auth/register
Content-Type: application/json

Payload:
{
  "query": {
    "email": "usuario@email.com",
    "imei": "926827409262726",  // 15 dígitos, checksum Luhn
    "password": "SenhaComEspecial!123"
  },
  "id": 103
}

Resposta sucesso:
{"success": true, "time": 1774757261773}

Resposta erro senha:
{"error": 1010, "keyword": "pattern", "dataPath": "/password", ...}
```

---

## Notas para Futuras Modificações

1. Se o 2NR atualizar, o campo `Sf` e os métodos `T2()`, `A()`, `U2()` provavelmente continuarão na mesma classe (maior classe smali do app)
2. Buscar por `forcewifi` no smali para encontrar rapidamente o ponto de patch
3. O `isActiveNetworkMetered` pode mudar de localização entre versões
4. Sempre verificar se o LSPatch ainda é usado ou se mudaram para outro framework
5. A API pode mudar o endpoint de `/auth/register` - verificar via HAR capture
