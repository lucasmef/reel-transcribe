# Seguranca

Relate vulnerabilidades pelo canal privado do GitHub:
https://github.com/lucasmef/reel-transcribe/security/advisories/new

Inclua a versao ou commit, plataforma, passos de reproducao e impacto esperado.
Use dados de teste. Nao envie chaves de API, cookies, arquivos privados ou dados
de outras pessoas. Nao publique detalhes de uma vulnerabilidade exploravel em
issues publicas antes de uma correcao.

## Uso e limites

- Esta ferramenta e uma CLI local. Nao foi projetada para receber requisicoes
  anonimas como um servico publico.
- A chave Gemini e lida de `GEMINI_API_KEY`. Cada usuario fornece sua propria
  chave. Nunca inclua chaves ou cookies em commits ou logs compartilhados.
- Cookies do navegador so sao lidos com `--cookies-from-browser`. Essa opcao
  usa a sessao da conta selecionada e deve ser usada apenas para conteudo que
  voce tem autorizacao para acessar.
- A transcricao envia o audio ao Gemini. A exclusao remota e tentada ao final;
  se falhar, o programa avisa. Evite enviar conteudo confidencial sem avaliar
  o tratamento de dados do provedor.
- O download direto de imagens aceita apenas HTTPS nas CDNs do Instagram/Meta,
  valida redirecionamentos e limita o tamanho da resposta. O ffmpeg executa sem
  shell, sem protocolos de rede na extracao e com tempo limite.
- Mantenha Python, ffmpeg e dependencias atualizados. Os scanners detectam
  classes conhecidas de problemas; testes aprovados nao garantem ausencia de
  vulnerabilidades.

## Verificacoes

O workflow `Tests and security` executa testes, pip-audit, Bandit e Gitleaks em
pull requests e pushes para `main`, sem chaves de API ou cookies do usuario.
O CodeQL e configurado separadamente nas opcoes de seguranca do GitHub.
