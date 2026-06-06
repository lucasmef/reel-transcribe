# Reel Transcribe

CLI local para baixar um Reel publico do Instagram e usar o Gemini para
transcrever toda a fala em portugues. Quando o audio estiver em outro idioma,
a ferramenta gera uma traducao integral, sem resumo.

Ao concluir, ela salva na pasta
`C:\Users\lucas\Transmissão no Google Drive\Meu Drive\VIDEOS\MODEL` dois
arquivos com o mesmo nome:

```text
2026-06-06-Primeira frase do Reel.mp4
2026-06-06-Primeira frase do Reel.txt
```

## Requisitos

- Windows, macOS ou Linux
- Python 3.11 ou mais recente
- Uma chave da [Gemini API](https://aistudio.google.com/app/apikey)
- `ffmpeg` no `PATH` (obrigatorio para combinar streams quando necessario e
  extrair somente o audio antes do envio ao Gemini)

No Windows, instale o Python pelo site oficial e marque a opcao para adiciona-lo
ao `PATH`. O `ffmpeg` pode ser instalado com:

```powershell
winget install Gyan.FFmpeg
```

Feche e abra o terminal depois da instalacao.

## Instalacao

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

Escolha outro diretorio ou modelo:

```powershell
reel-transcribe "URL" --output "C:\Videos" --model "gemini-3.1-flash-lite"
```

Consulte todas as opcoes:

```powershell
reel-transcribe --help
```

## Comportamento e erros

- Somente Reels publicos que nao exigem login sao aceitos.
- O modelo padrao e `gemini-3.5-flash`.
- O nome comeca pela data local da execucao e nao inclui o codigo do Reel.
- Somente um MP3 mono otimizado para fala e enviado ao Gemini; o MP4 permanece
  local.
- O TXT contem texto corrido, sem timestamps.
- A resposta inclui apenas a fala integral, sem descricoes de cenas, sons ou
  elementos visuais.
- Caracteres invalidos e nomes reservados do Windows sao removidos.
- Se o Gemini falhar depois do download, o video e preservado como
  `AAAA-MM-DD-reel.mp4` e nenhum TXT parcial e criado.
- Arquivos temporarios e o upload remoto do Gemini sao removidos ao final.
- A ferramenta nao contorna controles de acesso. Baixe somente conteudo que
  voce tenha direito de usar.

## Desenvolvimento

```powershell
python -m pip install -e ".[dev]"
pytest
```

Os testes usam simulacoes do downloader e do Gemini; a suite normal nao acessa
a rede nem consome a API.
