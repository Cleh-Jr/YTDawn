# 🌅 YTDawn — Portable Media Downloader & FFmpeg Converter

Aplicativo **100% portátil** (sem instalação necessária) com visual minimalista inspirado na **Aurora (Dawn)**. Permite baixar vídeos e músicas de diversas redes sociais e converter mídias locais com máxima fidelidade ou compressão inteligente via `FFmpeg`.

---

## ✨ Recursos Principais

### 📥 1. Download de Mídia
- **Formatos suportados**: `MP4 (Vídeo)` e `MP3 (Áudio)`.
- **Limite de Resolução**:
  - **`1080p`** *(Padrão)*: Limita o download a Full HD (ou à resolução máxima original do vídeo se for menor), impedindo downloads acidentais em 4K que consomem muito espaço e memória.
  - **`720p`**: Baixa em HD para economizar dados e acelerar o download.
- **Opções de Compressão (Círculos Seletores)**:
  - **`None`** *(Padrão)*: **Sem compressão**. O arquivo é salvo imediatamente com máxima velocidade e integridade.
  - **`Full`**: Reduz o tamanho do vídeo para aproximadamente **80% do original** (~20% de economia).
  - **`Half`**: Reduz o tamanho do vídeo para aproximadamente **50% do original** (~50% de economia).
- **Capas e Metadados**: Tags ID3/MP4 e Thumbnails (capas) embutidas automaticamente nos arquivos.
- **Botão Inteligente**: O botão de ação funciona como **Iniciar** e alterna para **Cancelar** durante a execução.

### 🔄 2. Conversão Local de Arquivos
- Suporte a múltiplos formatos de entrada e saída (`MP4`, `MKV`, `MP3`, `AAC`, `FLAC`, etc.).
- Permite manter o tamanho original apenas mudando a extensão (`None`) ou aplicar compressão (`Full` / `Half`).

### 🧹 3. Limpeza de Cache em 1 Clique
- Botão **`🧹 Limpar Cache`** no cabeçalho para renovar o estado do programa e limpar arquivos temporários do `yt-dlp` instantaneamente.

---

## 🍪 Autenticação e Bypass de Verificação de Bot ("Sign in to confirm you're not a bot")

Alguns vídeos e músicas com proteção do YouTube exigem que você esteja autenticado na sua conta para liberar o download. O YTDawn suporta autenticação direta e segura via arquivo `cookies.txt`.

### 📌 Como exportar os cookies em 3 passos:

1. **Instale a Extensão no seu navegador (Chrome ou Edge)**:
   - [Get cookies.txt LOCALLY (Chrome Web Store)](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   *(No Microsoft Edge, basta clicar em "Permitir extensões de outras lojas" para instalar direto da Chrome Web Store).*

2. **Exporte seus cookies do YouTube**:
   - Abra o [YouTube](https://www.youtube.com) no navegador estando logado na sua conta.
   - Dê play em qualquer vídeo por 3 a 5 segundos (para renovar a sessão ativa).
   - Clique no ícone da extensão no topo do navegador e clique no botão **"Export"** (ela fará o download do arquivo `cookies.txt`).

3. **Carregue no YTDawn**:
   - No YTDawn, clique no botão **`🍪 Cookies`** no cabeçalho superior direito.
   - Selecione o arquivo `cookies.txt` baixado.
   - O YTDawn guardará o arquivo na pasta do programa e todos os downloads futuros usarão sua sessão autenticada, eliminando qualquer tela de confirmação de bot!

---

## 📁 Como Executar

1. Baixe o pacote compactado na aba **[Releases](../../releases)**.
2. Extraia o arquivo `.zip` em qualquer pasta ou pendrive.
3. Dê um duplo clique em **`YTDawn.exe`** ou em **`Iniciar_YTDawn.bat`**.

