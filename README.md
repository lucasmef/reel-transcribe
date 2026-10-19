# Reel Transcribe

CLI local para baixar um Reel publico do Instagram e usar o Gemini para
transcrever toda a fala em portugues. Quando o audio estiver em outro idioma,
a ferramenta gera uma traducao integral, sem resumo. Links de posts publicos
com fotos (inclusive carrosseis) tambem sao aceitos: as fotos sao salvas em ordem,
na maior resolucao disponivel, junto da legenda original em TXT UTF-8, sem
traducao e sem usar o Gemini.

Ao concluir, ela salva na pasta configurada como destino padrao dois arquivos
com o mesmo nome. O destino padrao e `~/Videos/reel-transcribe`.
Use `--output` ou a variavel `REEL_TRANSCRIBE_OUTPUT` para personaliza-lo:

```text
2026-06-06-Primeira frase do Reel.mp4
2026-06-06-Primeira frase do Reel.txt
```

Para posts com imagem, os arquivos sao salvos em:

```text
~/Downloads/CODIGO-1.jpg
~/Downloads/CODIGO-2.jpg
~/Downloads/CODIGO-legenda.txt
```

## O que você pode fazer

- Salvar um Reel e sua transcrição integral em português.
- Traduzir a fala de vídeos em outros idiomas, sem resumir o conteúdo.
- Baixar fotos de posts e carrosséis com a legenda original, sem usar Gemini.
- Escolher as pastas de saída e usar a sessão de um navegador explicitamente.

## Requisitos

- Windows, macOS ou Linux
- Python 3.11 ou mais recente
- Uma chave da [Gemini API](https://aistudio.google.com/app/apikey) para
  transcrever videos
- `ffmpeg` no `PATH` (obrigatorio para combinar streams quando necessario e
  extrair somente o audio antes do envio ao Gemini)

No Windows, instale o Python pelo site oficial e marque a opcao para adiciona-lo
ao `PATH`. O `ffmpeg` pode ser instalado com:

```powershell
winget install Gyan.FFmpeg
```

Feche e abra o terminal depois da instalacao.

## Instalacao

Clone o repositório e entre na pasta:

```sh
git clone https://github.com/lucasmef/reel-transcribe.git
cd reel-transcribe
```

### macOS e Linux

Com Python e `ffmpeg` disponíveis no `PATH`:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export GEMINI_API_KEY="sua-chave-aqui"
reel-transcribe "https://www.instagram.com/reel/CODIGO/"
```

A variável acima vale para o terminal atual. A CLI não carrega `.env`
automaticamente; `.env.example` documenta o nome da variável. Posts de fotos
não precisam da chave Gemini.

### Windows

Abra o PowerShell na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Configure a chave apenas para o terminal atual:

```powershell
$env:GEMINI_API_KEY="sua-chave-aqui"
```

Para mante-la configurada em futuros terminais:

```powershell
setx GEMINI_API_KEY "sua-chave-aqui"
```

## Uso

```powershell
reel-transcribe "https://www.instagram.com/reel/CODIGO/"
```

Para baixar as fotos de um post/carrossel e sua legenda:

```powershell
reel-transcribe "https://www.instagram.com/p/CODIGO/"
```

Escolha outro diretorio ou modelo:

```powershell
reel-transcribe "URL" --output "C:\Videos" --model "gemini-3.1-flash-lite"
```

Escolha outro diretorio para imagens:

```powershell
reel-transcribe "URL" --image-output "~/Downloads"
```

Consulte todas as opcoes:

```powershell
reel-transcribe --help
```

## Comportamento e erros

- Por padrao, nenhum cookie do navegador e lido. Se o Instagram exigir uma
  sessao, use explicitamente `--cookies-from-browser safari` (ou outro navegador
  listado em `--help`). Isso usa sua conta; baixe apenas conteudo autorizado.
- Fotos e legendas sao publicadas na pasta Downloads do usuario por padrao.
- Posts com imagem usam o codigo do post e o indice da imagem, sem data:
  `CODIGO-1.jpg`, `CODIGO-2.jpg`, etc.
- A legenda e salva como `CODIGO-legenda.txt`, preservando quebras de linha,
  emojis, hashtags e mencoes. Posts sem legenda geram um TXT vazio. Se a legenda
  estiver indisponivel, as fotos ainda sao salvas e um aviso e exibido.
- Em carrosseis mistos, apenas as fotos sao baixadas; capas de videos sao ignoradas.
- Repetir o mesmo post reutiliza os mesmos nomes e substitui os arquivos,
  evitando duplicados.
- O modelo padrao e `gemini-3.5-flash`.
- Se o modelo inicial falhar ou exceder 45 segundos, a ferramenta tenta
  automaticamente `gemini-3.1-flash-lite`, sem repetir as tentativas internas
  demoradas do cliente Gemini.
- Para videos, o nome comeca pela data local da execucao e nao inclui o codigo
  do Reel.
- Somente um MP3 mono otimizado para fala e enviado ao Gemini; o MP4 permanece
  local.
- O TXT contem texto corrido, sem timestamps.
- A resposta inclui apenas a fala integral, sem descricoes de cenas, sons ou
  elementos visuais.
- Caracteres invalidos e nomes reservados do Windows sao removidos.
- Se o Gemini falhar depois do download, o video e preservado como
  `AAAA-MM-DD-reel.mp4` e nenhum TXT parcial e criado.
- Arquivos temporarios sao removidos ao final. A exclusao do upload remoto do
  Gemini e tentada ao finalizar; uma falha gera um aviso, sem descartar o resultado.
- Imagens sao baixadas apenas por HTTPS de `cdninstagram.com` ou `fbcdn.net`,
  incluindo seus subdominios. Redirecionamentos sao validados da mesma forma.
- Cada imagem tem limite de 20 MiB e os metadados, de 5 MiB. O download de video
  usa o limite de tamanho do yt-dlp (512 MiB quando o tamanho e conhecido), e a
  extracao de audio tem limite de 10 minutos. O ffmpeg nao recebe acesso a
  protocolos de rede durante a extracao.
- A ferramenta nao contorna controles de acesso. Baixe somente conteudo que
  voce tenha direito de usar.

## Desenvolvimento

```powershell
python -m pip install -e ".[dev]"
pytest
```

Os testes usam simulacoes do downloader e do Gemini; a suite normal nao acessa
a rede nem consome a API.

Consulte [SECURITY.md](SECURITY.md) para orientacoes sobre credenciais, envio de
audio e relatos privados de vulnerabilidades.

## Privacidade e arquivos locais

A transcrição envia o áudio para a API Gemini. Vídeos ficam no computador;
o download de fotos e legendas não utiliza Gemini. Cookies de navegador só
são acessados quando você informa `--cookies-from-browser`.

O `.gitignore` exclui credenciais `.env`, cookies, logs, a pasta `output/`,
ambientes virtuais e arquivos de build. Guarde downloads pessoais fora do
código versionado. Nunca inclua chaves reais em exemplos ou commits.

## Estrutura do projeto

- `src/reel_transcribe/`: CLI, downloads, extração de áudio e transcrição.
- `tests/`: testes automatizados com dados simulados.
- `.github/workflows/`: testes e verificações de segurança no GitHub.
- `SECURITY.md`: tratamento de credenciais e relatos de vulnerabilidades.
