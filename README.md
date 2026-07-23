# Controle de Notas — Simples Nacional (MG) · versão Python

Reescrita em Python da aplicação de **controle de notas fiscais** para uma
empresa optante pelo Simples Nacional em Minas Gerais. A interface usa
**Streamlit**; a lógica de domínio fica em módulos puros, sem dependência de
interface (e com testes).

## Instalar e rodar

Requer Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

O Streamlit abre o app no navegador. Os dados são gravados em
`controle_dados.json` na pasta do projeto (equivalente ao armazenamento local
da versão web).

## Testes

```bash
python test_simples.py
python test_estudo_preco.py
```

Cobrem o RBT12 (com receita de abertura e a regra proporcional de início de
atividade), a separação receita × entradas, a agregação anual e o parse de XML
de NF-e (inclusive a leitura correta do valor com ponto decimal).

## Estrutura

```
app.py              # interface Streamlit (Painel, Importar, Notas, Estudo de Preço, Histórico, Manual, Empresa)
simples.py          # regras do Simples: anexos, RBT12, DAS, agregação mês/ano (puro)
estudo_preco.py      # ICMS-ST, DIFAL e encargos extras sobre um valor de venda (puro)
notas_xml.py        # leitura de XML: NF-e, NFC-e, NFS-e nacional e ABRASF
armazenamento.py    # persistência em JSON + deduplicação por chave
test_simples.py      # testes de sanidade do módulo simples
test_estudo_preco.py # testes de sanidade do estudo de preço
requirements.txt
```

## Funcionalidades

- Importar notas por **XML** (NF-e, NFC-e, NFS-e nacional e ABRASF): arraste
  vários, com classificação automática entre **emitida** (receita) e
  **recebida** (entrada) pelo CNPJ da empresa e **deduplicação pela chave de
  acesso**.
- **Painel mês a mês e anual**: faturamento, RBT12, alíquota efetiva, DAS
  estimado, entradas × saídas e régua com o teto do Simples e o sublimite de MG.
- **Histórico** para informar a receita bruta dos meses anteriores (RBT12
  correto ao entrar no meio do caminho), com regra de início de atividade.
- **Estudo de Preço**: a partir de um valor (digitado ou de uma nota
  existente), calcula o DAS na alíquota efetiva vigente, o **ICMS-ST**
  (quando você informa MVA e alíquota interna do produto), o **DIFAL** em
  vendas interestaduais a consumidor final, e outros encargos livres (frete,
  taxa de cartão, comissão), chegando na margem líquida se um custo for
  informado.
- **Tabela de NCM**: cadastre uma vez cada NCM que você vende, dizendo se ele
  está sujeito a ICMS-ST e qual o seu papel (substituto ou substituído).
  Informando esse NCM numa nota — na importação de XML (extraído
  automaticamente quando a nota tem um único item) ou no cadastro manual — o
  **painel principal segrega automaticamente** a receita já tributada por ST,
  excluindo a parcela de ICMS correspondente do DAS, usando a tabela oficial
  de partilha por Anexo/faixa (Receita Federal). Veja as limitações abaixo —
  MVA e alíquotas de ICMS-ST não vêm pré-cadastradas.
- Registro **manual** avulso e configuração da empresa/anexo.

## Limitações (importante)

- Os valores de **DAS são estimativas** (LC 123/2006); a apuração oficial é no
  PGDAS-D.
- O app **não emite** notas nem as **busca na SEFAZ** — isso exigiria
  certificado digital e um serviço próprio. As notas entram por XML.
- Acima do sublimite de MG, ICMS e ISS saem do DAS; o app sinaliza, mas confirme
  com seu contador.
- **ICMS-ST**: MVA e alíquota interna são definidas por convênio/protocolo
  estadual e variam por NCM/CEST do produto — o app não tem uma tabela por
  produto, você cadastra os NCMs uma vez na aba **Tabela de NCM**. A partir
  daí, notas com NCM marcado como **substituído** (ST já retida antes) têm a
  parcela de ICMS excluída automaticamente do DAS no painel, usando a tabela
  oficial de partilha por Anexo/faixa. Essa segregação só funciona para notas
  com NCM informado; notas antigas ou sem NCM continuam entrando de forma
  não segregada. O NCM só é extraído automaticamente do XML quando a nota tem
  um único item — com vários itens, preencha manualmente.

Não substitui orientação contábil.
