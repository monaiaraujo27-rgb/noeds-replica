#!/usr/bin/env python3
"""
Gera as páginas-app do dossiê:
  - gerar.html    : cola as respostas -> Gemini interpreta -> preenche dossiê -> salva no Supabase
  - clientes.html : lista clientes salvos (lê do Supabase via RPC + token)

Chamado por build.py. Mantém o mesmo visual (CSS do site + sidebar global).

CONFIG (preencher quando as chaves chegarem):
  - SUPABASE_URL / SUPABASE_ANON : projeto "Dossie"
  - Autenticação da equipe       : Supabase Auth (email/senha) — ver _auth_gate_js()
    e os RPCs *_auth (get_clientes_auth, get_respostas_auth, delete_resposta_auth,
    set_share_token_auth), que checam auth.uid() contra team_members. O token
    hardcoded (READ_TOKEN) usado até 2026-07-11 foi descomissionado do client.
  - GEMINI via /api/interpret    : função serverless Vercel (a key NÃO vai no HTML)
"""

# ---- projeto Supabase "SETUP" (ref cvzaqqlagwueldpookdf) ----
SUPABASE_URL = "https://cvzaqqlagwueldpookdf.supabase.co"
SUPABASE_ANON = "sb_publishable_guPZajaIZW8_hABcLqIx1w_AD3EKh_o"

# os 9 documentos do dossiê e os placeholders que cada um espera receber
# (a IA preenche estes campos a partir do texto colado)
DOSSIE_FIELDS = [
    ("clinica",        "Nome da clínica/empresa"),
    ("responsavel",    "Nome do responsável"),
    ("especialidade",  "Especialidade / nicho"),
    ("cidade",         "Cidade / região"),
    ("faturamento",    "Faturamento médio mensal"),
    ("ticket",         "Ticket médio"),
    ("principal_dor",  "Principal dor / gargalo"),
    ("objetivo",       "Objetivo principal (6-12 meses)"),
    ("publico",        "Público-alvo predominante"),
    ("diferencial",    "Maior diferencial competitivo"),
]

import json as _json

# ---------------------------------------------------------------------------
# CONTRATO DOS 9 DOCUMENTOS
# Cada spec: slug (= arquivo .html), nome, e "formato" = molde JSON que a IA devolve.
# O MESMO contrato é usado pelo renderer em build.py (RENDER_JS) para injetar no design.
# Versão ENXUTA (3 personas, scripts essenciais) conforme decidido.
# ---------------------------------------------------------------------------
DOC_SPECS = [
    {
        "slug": "diagnostico", "nome": "Diagnóstico de Impacto",
        "instrucoes": (
            "Este é o documento mais importante do dossiê e deve ser DENSO e ESPECÍFICO, mostrando com clareza quais "
            "pontos estão travando o crescimento do cliente. NÃO seja genérico: conecte cada ponto ao cenário real "
            "descrito no contexto da empresa. "
            "REGRA DE NÚMEROS: use SOMENTE números que apareçam no contexto da empresa; "
            "para qualquer KPI não informado, escreva 'Não informado' no valor e descreva o que medir. NÃO invente números. "
            "Os 7 motores são fixos e nesta ordem: 1 Geração de Demanda, 2 Conversão Comercial, 3 Indicadores, "
            "4 Reativação, 5 Positivo e Oferta, 6 Indicação, 7 Prova Social. "
            "Cada motor recebe um campo 'status' com a leitura geral daquele motor: 'ok' (funciona bem), 'atencao' "
            "(funciona parcialmente, tem perdas) ou 'critico' (não existe ou está travando o crescimento). Seja honesto: "
            "um dossiê típico tem 1-2 motores ok, o resto dividido entre atenção e crítico conforme o contexto. "
            "Cada item de motor tem no máximo 110 caracteres, no formato 'situação. Ação.' quando apontar problema. "
            "Cada motor deve ter EXATAMENTE 5 itens analíticos (frases completas, leitura consultiva da realidade da empresa) "
            "respondendo, no motor correspondente: (Geração de Demanda) o cliente tem demanda suficiente e como atrai leads "
            "hoje; (Conversão Comercial) o atendimento está preparado para converter; (Indicadores) existe controle dos "
            "números do negócio; (Reativação) existe reativação da base de clientes/leads antigos; (Positivo e Oferta) a "
            "oferta está clara e bem posicionada; (Indicação) existe estratégia de indicação; (Prova Social) existe prova "
            "social suficiente. Cada motor deve deixar claro se o funil está organizado e onde o cliente está perdendo "
            "oportunidade. "
            "O Resumo do Cliente deve descrever a empresa concretamente (quem é, responsável, equipe, estrutura, "
            "funcionamento, faturamento) com base no contexto."
        ),
        "formato": {
            "resumo_titulo": "Resumo do Cliente",
            "resumo_intro": "1 frase: quem é a empresa hoje",
            "resumo_campos": [{"rotulo": "ex. Empresa", "texto": "descrição concreta, 1-2 frases"}],  # 6 itens: Empresa, Responsável, Equipe, Estrutura, Funcionamento, Faturamento atual
            "indicadores": [{"rotulo": "ex. Leads / mês", "valor": "número informado OU 'Não informado'", "nota": "1 frase do que significa/medir"}],  # 6 itens
            "motores": [{"titulo": "ex. Motor 1 · Geração de Demanda", "status": "ok | atencao | critico", "itens": ["item analítico, máx. 110 caracteres"]}],  # 7 motores, 5 itens cada
            "gargalo_intro": "1 frase: leitura cruzada dos sete motores",
            "gargalo": ["ponto de perda de venda, 1-2 frases"],  # 5 itens
            "metas": [{"rotulo": "ex. Meta 6 meses", "texto": "descrição, 'Não informado' se não houver número"}],  # 4 itens: Meta 6m, Meta 12m, Pacientes desejados, Investimento previsto
            "conclusao": "1-2 frases de fechamento motivacional e estratégico",
        },
        "_counts": {"resumo_campos": 6, "indicadores": 6, "motores": 7, "gargalo": 5, "metas": 4},
        "_array_item_counts": {"motores": {"itens": 5}},
        "temperatura": 0.15,
        # few-shot de nicho DIFERENTE (oficina mecânica) — evita contaminar o conteúdo
        # do cliente real (tipicamente clínica/estética/serviços), só ilustra a forma.
        "_exemplo": {
            "resumo_titulo": "Resumo do Cliente",
            "resumo_intro": "A Oficina Motriz é uma oficina mecânica especializada em suspensão e freios, em operação há 6 anos em Curitiba.",
            "resumo_campos": [
                {"rotulo": "Empresa", "texto": "Oficina Motriz, especializada em suspensão, freios e revisão preventiva, atendendo majoritariamente carros de passeio."},
                {"rotulo": "Responsável", "texto": "Marcos Vieira, mecânico-chefe e sócio-fundador, atua também no atendimento ao cliente."},
                {"rotulo": "Equipe", "texto": "4 mecânicos e 1 recepcionista, sem consultor comercial dedicado."},
                {"rotulo": "Estrutura", "texto": "Galpão próprio com 3 elevadores, localizado em avenida de médio fluxo."},
                {"rotulo": "Funcionamento", "texto": "Atendimento por ordem de chegada e agendamento via WhatsApp pessoal do responsável."},
                {"rotulo": "Faturamento atual", "texto": "Não informado"},
            ],
            "indicadores": [
                {"rotulo": "Carros/mês", "valor": "Não informado", "nota": "Volume de veículos atendidos no período."},
                {"rotulo": "Ticket médio", "valor": "Não informado", "nota": "Valor médio por ordem de serviço fechada."},
                {"rotulo": "Taxa de retorno", "valor": "Não informado", "nota": "Percentual de clientes que voltam para nova revisão."},
                {"rotulo": "Orçamentos aprovados", "valor": "Não informado", "nota": "Percentual de orçamentos que viram serviço fechado."},
                {"rotulo": "Indicações/mês", "valor": "Não informado", "nota": "Novos clientes vindos de indicação direta."},
                {"rotulo": "Tempo médio de execução", "valor": "Não informado", "nota": "Tempo entre entrada e entrega do veículo."},
            ],
            "motores": [
                {"titulo": "Motor 1 · Geração de Demanda", "status": "critico", "itens": [
                    "Captação depende só de boca a boca. Ativar busca local e redes sociais.",
                    "Nenhuma campanha paga rodando na região. Testar verba mínima em busca local.",
                    "Perfil no Google Maps sem fotos e avaliações recentes. Atualizar e pedir avaliações.",
                    "Sem oferta de entrada. Criar diagnóstico de freios gratuito para gerar primeira visita.",
                    "Concorrência já domina a busca por \"oficina suspensão\" na região.",
                ]},
                {"titulo": "Motor 2 · Conversão Comercial", "status": "atencao", "itens": [
                    "Orçamentos passados verbalmente. Registrar por escrito para facilitar aprovação.",
                    "Orçamento recusado morre ali. Implantar follow-up em 48h.",
                    "Explicação técnica confunde o cliente leigo. Criar roteiro em linguagem simples.",
                    "Sem segunda oferta na recusa. Oferecer parcelamento ou revisão parcial.",
                    "Tempo de resposta no WhatsApp não é medido. Padronizar em até 1h.",
                ]},
                {"titulo": "Motor 3 · Indicadores", "status": "critico", "itens": [
                    "Ordens de serviço em caderno físico. Migrar para planilha ou sistema simples.",
                    "Faturamento por tipo de serviço desconhecido. Separar por categoria no fechamento.",
                    "Estoque sem controle gera compra emergencial. Implantar contagem semanal.",
                    "Sem fechamento mensal de custo fixo × variável. Criar rotina financeira.",
                    "Elevadores ociosos em horários específicos. Mapear e ocupar com agendamento.",
                ]},
                {"titulo": "Motor 4 · Reativação", "status": "critico", "itens": [
                    "Base de clientes antigos sem lista organizada. Consolidar contatos em um lugar.",
                    "Sem lembrete de revisão periódica. Automatizar aviso a cada 6 meses.",
                    "Cliente sumido há 12 meses não recebe contato. Criar campanha de retorno.",
                    "Sem benefício para cliente recorrente. Testar programa de fidelidade simples.",
                    "Contatos dispersos entre WhatsApp pessoal e papel. Centralizar a base.",
                ]},
                {"titulo": "Motor 5 · Positivo e Oferta", "status": "atencao", "itens": [
                    "Especialização em suspensão e freios não é comunicada. Assumir o nicho publicamente.",
                    "Identidade visual inconsistente. Padronizar fachada, uniforme e papelaria.",
                    "Diferencial frente a generalistas não é dito. Comunicar o baixo retrabalho.",
                    "Sem conteúdo educativo do trabalho técnico. Gravar vídeos curtos de bancada.",
                    "Marca não registrada nem protegida digitalmente. Regularizar.",
                ]},
                {"titulo": "Motor 6 · Indicação", "status": "critico", "itens": [
                    "Nenhum pedido formal de indicação pós-serviço. Incluir no checklist de entrega.",
                    "Cliente satisfeito não tem incentivo para indicar. Criar benefício claro.",
                    "Origem por indicação não é rastreada. Perguntar e registrar na entrada.",
                    "Falta link ou cartão fácil de compartilhar. Criar material de indicação.",
                    "Parcerias com seguradoras e despachantes inexploradas. Abrir 2 conversas locais.",
                ]},
                {"titulo": "Motor 7 · Prova Social", "status": "atencao", "itens": [
                    "Poucas avaliações públicas no Google. Pedir avaliação na entrega do carro.",
                    "Fotos de antes/depois não são usadas. Documentar cada serviço relevante.",
                    "Depoimentos não são coletados. Gravar 5 clientes satisfeitos este mês.",
                    "Sem selo ou certificação visível. Exibir credenciais técnicas da equipe.",
                    "Ausente dos grupos locais de proprietários. Participar com conteúdo útil.",
                ]},
            ],
            "gargalo_intro": "Cruzando os sete motores, o gargalo real não é a qualidade técnica do serviço, e sim a ausência de processo comercial e de captação estruturada.",
            "gargalo": [
                "Clientes satisfeitos não retornam nem indicam de forma sistemática. Depende da lembrança espontânea.",
                "Orçamentos recusados não recebem follow-up. Vendas quase fechadas se perdem.",
                "A oficina não aparece para quem pesquisa o serviço na região agora.",
                "Sem controle de ordens de serviço, não se sabe qual serviço dá mais retorno.",
                "Nenhuma oferta de entrada reduz o risco de experimentar a oficina pela primeira vez.",
            ],
            "metas": [
                {"rotulo": "Meta 6 meses", "texto": "Não informado"},
                {"rotulo": "Meta 12 meses", "texto": "Não informado"},
                {"rotulo": "Clientes desejados", "texto": "Não informado"},
                {"rotulo": "Investimento previsto", "texto": "Não informado"},
            ],
            "conclusao": "A Oficina Motriz tem base técnica sólida — o próximo passo é transformar essa qualidade em um sistema comercial que capta, converte e retém de forma previsível.",
        },
    },
    {
        "slug": "swot", "nome": "Análise SWOT",
        "instrucoes": (
            "Cada uma das 4 listas (forças, fraquezas, oportunidades, ameaças) deve ter EXATAMENTE 5 itens, "
            "cada item começando por um rótulo curto de 2-4 palavras seguido de ':' e a explicação específica "
            "de NO MÁXIMO 90 caracteres (ex.: 'Laboratório próprio: prótese em prazo que a concorrência não acompanha'). "
            "Os 4 cruzamentos são fixos: Forças com Oportunidades, Forças com Ameaças, Fraquezas com Oportunidades, "
            "Fraquezas com Ameaças — cada um UMA estratégia concreta em 1 frase de até 25 palavras, começando com verbo."
        ),
        "formato": {
            "forcas": ["Rótulo: explicação específica"],       # 5 itens
            "fraquezas": ["Rótulo: explicação"],               # 5 itens
            "oportunidades": ["Rótulo: explicação"],           # 5 itens
            "ameacas": ["Rótulo: explicação"],                 # 5 itens
            "cruzamentos": [{"titulo": "Forças com Oportunidades", "texto": "estratégia concreta, 1-2 frases"}],  # 4 fixos
        },
        "_counts": {"forcas": 5, "fraquezas": 5, "oportunidades": 5, "ameacas": 5, "cruzamentos": 4},
        "temperatura": 0.15,
        # few-shot de nicho DIFERENTE (oficina mecânica) — mesma razão do diagnóstico acima.
        "_exemplo": {
            "forcas": [
                "Equipe técnica experiente: mecânicos com mais de 10 anos de bancada, especializados em suspensão e freios.",
                "Estrutura própria: galpão com 3 elevadores evita fila de espera em horários de pico.",
                "Reputação local: 6 anos de operação geraram uma base de clientes fiéis na região.",
                "Diagnóstico preciso: baixo índice de retrabalho por identificar o problema real na primeira visita.",
                "Localização de fácil acesso: avenida de médio fluxo com estacionamento para os clientes.",
            ],
            "fraquezas": [
                "Ausência digital: sem presença ativa em busca local, redes sociais ou avaliações no Google.",
                "Gestão manual: ordens de serviço e estoque controlados em caderno, sem sistema.",
                "Sem processo comercial: orçamentos recusados não recebem follow-up nem segunda oferta.",
                "Dependência do fundador: atendimento comercial concentrado só no responsável, sem backup.",
                "Sem controle de indicadores: não há dado de ticket médio, retorno ou tempo de execução.",
            ],
            "oportunidades": [
                "Revisão preventiva recorrente: criar um programa de lembrete periódico para gerar receita previsível.",
                "Busca local: otimizar perfil no Google Maps para captar quem pesquisa oficina na região agora.",
                "Parcerias com despachantes e seguradoras: canal de indicação ainda não explorado.",
                "Conteúdo educativo: vídeos curtos explicando problemas comuns aumentam autoridade e confiança.",
                "Programa de indicação: incentivar clientes satisfeitos a indicar formalmente, hoje só espontâneo.",
            ],
            "ameacas": [
                "Concorrência com presença digital mais forte capturando clientes que pesquisam online.",
                "Redes de oficina de franquia na região com marketing estruturado e preço agressivo.",
                "Sazonalidade: queda de demanda em períodos específicos sem estratégia de reativação de base.",
                "Dependência de boca a boca deixa o fluxo de clientes vulnerável a qualquer período mais fraco.",
                "Aumento do custo de peças pode pressionar margem sem repasse claro ao cliente.",
            ],
            "cruzamentos": [
                {"titulo": "Forças com Oportunidades", "texto": "Usar a reputação e o diagnóstico preciso já existentes como argumento central da comunicação digital, atraindo quem pesquisa online por um serviço confiável."},
                {"titulo": "Forças com Ameaças", "texto": "Reforçar a experiência técnica da equipe como diferencial frente às franquias, comunicando profundidade de conhecimento que um atendimento padronizado não oferece."},
                {"titulo": "Fraquezas com Oportunidades", "texto": "Implementar um sistema simples de gestão que já viabilize o programa de revisão preventiva recorrente, resolvendo duas fraquezas com uma única ação."},
                {"titulo": "Fraquezas com Ameaças", "texto": "Estruturar um processo comercial mínimo (follow-up de orçamento) antes que a concorrência com marketing mais agressivo capture esses clientes indecisos."},
            ],
        },
    },
    {
        "slug": "bcg", "nome": "Matriz BCG",
        "instrucoes": (
            "Classifique os PROCEDIMENTOS/SERVIÇOS reais da empresa nos 4 quadrantes. Para Estrela, Vaca e "
            "Interrogação, dê o nome do procedimento + EXATAMENTE 5 itens analíticos de no máximo 120 caracteres "
            "cada. Para Abacaxi, nome + 3 itens (ou indique que o portfólio está enxuto se não houver). "
            "Alocação: 3 linhas fixas (Estrela ~60%, Vaca ~25%, Interrogação ~15%), 1 frase curta de foco cada, "
            "mantendo o percentual entre parênteses no rótulo."
        ),
        "formato": {
            "portfolio": "leitura geral do portfólio da empresa, 2-3 frases",
            "estrela": {"nome": "procedimento estrela", "itens": ["análise, 1 frase"]},        # 5 itens
            "vaca": {"nome": "procedimento vaca leiteira", "itens": ["análise, 1 frase"]},     # 5 itens
            "interrogacao": {"nome": "procedimento interrogação", "itens": ["análise, 1 frase"]},  # 5 itens
            "abacaxi": {"nome": "procedimento abacaxi ou 'portfólio enxuto'", "itens": ["análise, 1 frase"]},  # 3 itens
            "alocacao": [{"rotulo": "Estrela (60%)", "texto": "foco de investimento, 1 frase"}],  # 3 fixos
            "conclusao": "1-2 frases de foco do ciclo",
        },
        "_counts": {"alocacao": 3},
        "_nested_counts": {"estrela": {"itens": 5}, "vaca": {"itens": 5}, "interrogacao": {"itens": 5}, "abacaxi": {"itens": 3}},
        "temperatura": 0.15,
    },
    {
        "slug": "persona", "nome": "Persona Estratégica",
        "instrucoes": (
            "Crie EXATAMENTE 3 personas (ICP) para os principais serviços/segmentos da empresa. Cada persona: "
            "nome fictício + faixa etária no título, perfil demográfico, o serviço/procedimento-alvo dela, "
            "EXATAMENTE 4 dores, 4 desejos, 3 medos/objeções (cada item com no máximo 90 caracteres), o gatilho "
            "de decisão e uma frase curta em primeira pessoa que essa persona diria sobre a própria dor "
            "(ex.: 'Tenho vergonha de sorrir nas fotos.'). Conteúdo específico da área do cliente."
        ),
        "formato": {
            "intro": "parágrafo introdutório sobre o mapeamento, 2-3 frases",
            "personas": [{  # EXATAMENTE 3
                "titulo": "ex. Fernanda, 40-55 anos", "perfil": "perfil demográfico e contexto, 2 frases",
                "servico": "serviço/procedimento-alvo desta persona",
                "frase": "fala em primeira pessoa sobre a dor, entre 5 e 12 palavras",
                "dores": ["dor específica, máx. 90 caracteres"],        # 4
                "desejos": ["desejo específico, máx. 90 caracteres"],   # 4
                "objecoes": ["medo/objeção, máx. 90 caracteres"],       # 3
                "gatilho": "o que faz decidir, 1 frase",
            }],
            "motivos": ["motivo de escolher esta empresa, 1 frase"],  # 4 itens
        },
        "_counts": {"personas": 3, "motivos": 4},
        "_array_item_counts": {"personas": {"dores": 4, "desejos": 4, "objecoes": 3}},
        "temperatura": 0.25,
    },
    {
        "slug": "marketing", "nome": "Plano de Marketing Inteligente",
        "instrucoes": (
            "Plano de execução em blocos. Os 4 blocos são fixos e nesta ordem: 'Primeiros 38 dias · Fundação', "
            "'Metodologia de Tráfego Pago', 'Recuperação de Base', 'Primeiros 90 dias'. Cada bloco: estratégia "
            "(1-2 frases), operação como LISTA de 3-4 passos práticos (cada passo começa com verbo, máx. 110 "
            "caracteres) e resultado esperado (1 frase, com o número da meta quando houver base no contexto). "
            "Depois, 7 motores de crescimento (rótulo + 1 frase focada em AÇÃO, sem repetir o diagnóstico) e o "
            "caminho até a escala."
        ),
        "formato": {
            "visao_geral": "visão geral da jornada, 2-3 frases",
            "blocos": [{"titulo": "Primeiros 38 dias · Fundação", "estrategia": "1-2 frases",
                        "operacao": ["passo prático começando com verbo, máx. 110 caracteres"],  # 3-4 passos
                        "resultado": "resultado esperado, 1 frase"}],  # 4 fixos
            "motores": [{"rotulo": "ex. Demanda", "texto": "1 frase de ação"}],  # 7 itens
            "escala": "caminho até a escala, 2 frases",
        },
        "_counts": {"blocos": 4, "motores": 7},
        "temperatura": 0.25,
    },
    {
        "slug": "conteudo", "nome": "Plano de Conteúdo Estratégico",
        "instrucoes": (
            "Os 5 pilares são fixos com pesos: Autoridade 25%, Prova Social 25%, Educação 20%, Desejo 15%, Conversão 15% — "
            "cada um com 1-2 frases do que entra. O banco de ideias deve ter 8 itens, cada um com tema (título), gancho "
            "(frase de abertura entre aspas), desenvolvimento (o que mostrar, 1 frase de máx. 130 caracteres), o pilar "
            "a que pertence (um dos 5 nomes exatos) e o formato sugerido (Reel, Carrossel, Story ou Post). "
            "Distribua os 8 itens entre os pilares aproximadamente conforme os pesos. Tudo específico dos serviços da empresa."
        ),
        "formato": {
            "porque": "por que o plano de conteúdo existe p/ esta empresa, 2-3 frases",
            "pilares": [{"peso": "25%", "nome": "Autoridade", "texto": "o que entra aqui, 1-2 frases"}],  # 5 fixos
            "banco": [{"tema": "título do conteúdo", "gancho": "\"frase de abertura\"", "desenvolvimento": "o que mostrar, 1 frase",
                       "pilar": "Autoridade | Prova Social | Educação | Desejo | Conversão", "formato": "Reel | Carrossel | Story | Post"}],  # 8 itens
            "acao": "primeiros passos práticos desta semana, 2 frases",
        },
        "_counts": {"pilares": 5, "banco": 8},
        "temperatura": 0.4,
    },
    {
        "slug": "playbook", "nome": "Playbook Comercial",
        "instrucoes": (
            "Playbook de atendimento no WhatsApp/comercial. fundamentos: 5 princípios, cada um com a regra em até "
            "12 palavras seguida de 1 frase curta de justificativa. scripts: 5 situações essenciais "
            "(ex.: Primeira abordagem, Follow-up sem resposta, Reativação de base, Agendamento da avaliação, Pós-venda) "
            "cada uma com uma mensagem PRONTA pra copiar (2-3 frases, tom humano, sem jargão). objecoes: 5 objeções "
            "reais da área (ex.: 'está caro', 'vou pensar') com a resposta de contorno."
        ),
        "formato": {
            "fundamentos": ["princípio de atendimento, 1 frase"],  # 5 itens
            "scripts": [{"situacao": "ex. Follow-up sem resposta", "mensagem": "mensagem pronta de WhatsApp, 2-3 frases"}],  # 5 itens
            "objecoes": [{"objecao": "ex. Está caro", "resposta": "contorno, 1-2 frases"}],  # 5 itens
        },
        "_counts": {"fundamentos": 5, "scripts": 5, "objecoes": 5},
        "temperatura": 0.4,
    },
    {
        "slug": "certificado", "nome": "Certificado de Conformidade",
        "instrucoes": (
            "Documento de fechamento. resumo: síntese do ciclo concluído citando a empresa, máx. 2 frases. "
            "auditados: os 7 documentos fixos (Diagnóstico de Impacto, Análise SWOT, Matriz BCG, Persona Estratégica, "
            "Plano de Marketing Inteligente, Plano de Conteúdo Estratégico, Playbook Comercial). conformidade: 4 áreas "
            "(Estratégia, Posicionamento, Marketing, Comercial), escopo de NO MÁXIMO 2 frases curtas dizendo O QUE FOI "
            "DEFINIDO naquela área (a decisão, não o resumo do documento; NÃO repita números do diagnóstico). "
            "proximo: trajetória recomendada em NO MÁXIMO 3 frases, cada uma um marco concreto."
        ),
        "formato": {
            "resumo": "síntese do ciclo concluído, citando a empresa, 2-3 frases",
            "auditados": ["nome do documento entregue"],  # 7 fixos
            "conformidade": [{"area": "Estratégia", "escopo": "escopo específico da empresa, 1-2 frases"}],  # 4 fixos
            "proximo": "próximo nível / trajetória recomendada, 1-2 frases",
        },
        "_counts": {"auditados": 7, "conformidade": 4},
        "temperatura": 0.25,
    },
]


def _doc_specs_json():
    # emite a lista (slug, nome, instrucoes?, formato, _counts?, _nested_counts?,
    # _array_item_counts?, temperatura?, _exemplo?) como literal JS. Os campos _* são
    # usados por validarDoc() para checar a resposta da IA contra as contagens declaradas,
    # e _exemplo (few-shot de nicho diferente) é injetado no prompt por _montarPromptDoc().
    return _json.dumps(
        [{"slug": d["slug"], "nome": d["nome"],
          "instrucoes": d.get("instrucoes", ""), "formato": d["formato"],
          "_counts": d.get("_counts", {}), "_nested_counts": d.get("_nested_counts", {}),
          "_array_item_counts": d.get("_array_item_counts", {}),
          "temperatura": d.get("temperatura", 0.2),
          "_exemplo": d.get("_exemplo")} for d in DOC_SPECS],
        ensure_ascii=False,
    )


def _page(title, active, body, css, sidebar_css, sidebar_js, sidebar_html, fonts, print_css, extra_js="", theme_boot_js=""):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{theme_boot_js}
{fonts}
<style>{css}
{print_css}
{sidebar_css}
{APP_CSS}</style>
</head>
<body class="app-panel">
{sidebar_html(active)}
<div class="min-h-screen bg-background text-foreground">
<div class="mx-auto max-w-[920px] px-6 pt-24 app-content-top pb-32 sm:px-10 lg:px-12">
{body}
</div></div>
{sidebar_js}
{extra_js}
</body>
</html>
"""


APP_CSS = """
/* ---------- tema do painel interno (gerar/clientes) ----------
   Padrão claro; [data-theme="dark"] no <html> (ver THEME_BOOT_JS/toggle em
   build.py, compartilhado com o dossiê) troca pra a paleta escura. Variáveis
   de status (--status-*) centralizam as cores de erro/sucesso/aviso/perigo
   que antes estavam espalhadas como hex soltos em várias classes — mais
   fácil auditar contraste nos dois temas a partir de uma fonte única.
   IMPORTANTE: o atributo data-theme é setado no <html> (ver THEME_BOOT_JS),
   não em .app-panel (classe do <body>) — por isso os seletores usam
   "html[data-theme=dark] .app-panel", não ".app-panel[data-theme=dark]"
   (esse último nunca bate, porque o atributo não está nesse elemento). */
html:not([data-theme="dark"]) .app-panel {
  --background:#ffffff; --foreground:#1a1a1a; --surface:#f7f6f3; --surface-2:#efeee9;
  --border:#e2e0d9; --muted-foreground:#6b6b6b; --faint:#8f8d85;
  --color-background:#ffffff; --color-foreground:#1a1a1a; --color-border:#e2e0d9;
  --status-err:#e0726a; --status-ok:#7bbf8a; --status-warn:#c98a3a;
  --status-danger:#c0473f; --status-danger-fg:#ffffff; --status-copied:#4a9b6a; --status-copied-fg:#ffffff;
}
html[data-theme="dark"] .app-panel {
  --background:#000000; --foreground:#ffffff; --surface:#080808; --surface-2:#0e0e0e;
  --border:#151515; --muted-foreground:#a0a0a0; --faint:#707070;
  --color-background:#000000; --color-foreground:#ffffff; --color-border:#151515;
  --status-err:#e0726a; --status-ok:#7bbf8a; --status-warn:#c98a3a;
  --status-danger:#c0473f; --status-danger-fg:#ffffff; --status-copied:#4a9b6a; --status-copied-fg:#ffffff;
}
html:not([data-theme="dark"]) .app-panel #auth-gate.auth-gate { --background:#ffffff; --color-background:#ffffff; }
html[data-theme="dark"] .app-panel #auth-gate.auth-gate { --background:#000000; --color-background:#000000; }
/* o CSS original tem ::selection{color:#fff;background:#ffffff1f} (pensado pro
   tema escuro) — no claro isso é texto branco em fundo quase-branco, invisível
   ao selecionar texto em qualquer campo. Redeclara os dois casos. */
html:not([data-theme="dark"]) .app-panel ::selection { color:#1a1a1a; background:#d8d4c4; }
html[data-theme="dark"] .app-panel ::selection { color:#ffffff; background:#ffffff33; }
/* espaço extra no topo do conteúdo do painel: o hambúrguer (#ng-toggle) e o
   switch de tema (#ng-theme-toggle, Preto/Creme) são fixos em top:18px,
   altura 42px (terminam em y:60px) — com pt-24 (96px) puro o título "Banco
   de clientes"/"Gerar dossiê" (fonte grande) ainda começava alto o
   bastante pra ficar atrás desses botões. !important pra vencer a classe
   Tailwind pt-24 já aplicada no mesmo elemento. */
.app-content-top { padding-top:132px !important; }
.app-eyebrow { font-family:var(--font-sans); font-size:10px; letter-spacing:.3em; text-transform:uppercase; color:var(--faint); }
.app-h1 { font-family:var(--font-serif); font-size:44px; line-height:1.05; letter-spacing:-.01em; margin-top:28px; }
.app-sub { color:var(--faint); font-size:14px; margin-top:18px; font-weight:300; }
.app-card { background:var(--surface); border:1px solid var(--border); padding:28px; margin-top:28px; }
.app-label { font-size:10px; letter-spacing:.24em; text-transform:uppercase; color:var(--faint); display:block; margin-bottom:10px; }
.app-textarea, .app-input { width:100%; background:var(--background); border:1px solid var(--border); color:var(--foreground);
  padding:14px 16px; font-family:var(--font-sans); font-size:14px; font-weight:300; line-height:1.7; }
.app-textarea { min-height:240px; resize:vertical; }
.app-input:focus, .app-textarea:focus { outline:none; border-color:var(--foreground); }
.app-btn { display:inline-flex; align-items:center; gap:10px; background:var(--foreground); color:var(--background);
  border:none; padding:14px 28px; font-size:11px; letter-spacing:.24em; text-transform:uppercase; cursor:pointer;
  transition:opacity .2s; margin-top:22px; }
.app-btn:hover { opacity:.85; }
.app-btn:disabled { opacity:.4; cursor:not-allowed; }
.app-btn.ghost { background:transparent; color:var(--muted-foreground); border:1px solid var(--border); }
.app-btn.ghost:hover { color:var(--foreground); border-color:var(--foreground); }
.app-grid { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border); border:1px solid var(--border); margin-top:24px; }
.app-grid > div { background:var(--surface); padding:18px 20px; }
.app-grid .k { font-size:10px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint); }
.app-grid .v { font-family:var(--font-serif); font-size:18px; margin-top:6px; color:var(--foreground); }
.app-status { margin-top:18px; font-size:13px; color:var(--muted-foreground); min-height:20px; }
.app-status.err { color:var(--status-err); }
.app-status.ok { color:var(--status-ok); }
.client-row { display:flex; align-items:center; justify-content:space-between; gap:16px;
  background:var(--surface); border:1px solid var(--border); padding:18px 22px; margin-top:-1px; }
.client-row:hover { background:var(--surface-2); }
.client-row .nm { font-family:var(--font-serif); font-size:19px; color:var(--foreground); }
.client-row .meta { font-size:12px; color:var(--faint); margin-top:4px; }
.client-acts { display:flex; gap:8px; flex-shrink:0; flex-wrap:wrap; justify-content:flex-end; }
.client-acts .app-btn { margin-top:0; padding:11px 18px; }
.spinner { width:14px; height:14px; border:2px solid currentColor; border-top-color:transparent; border-radius:50%;
  display:inline-block; animation:ngspin .7s linear infinite; vertical-align:middle; }
@keyframes ngspin { to { transform:rotate(360deg); } }
.conn-card { border-color:var(--border); }
.conn-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.conn-hint { font-size:13px; color:var(--muted-foreground); font-weight:300; margin:14px 0 14px; line-height:1.6; }
#conn-state { font-size:10px; letter-spacing:.2em; text-transform:uppercase; padding:5px 12px; border:1px solid var(--border); }
#conn-state.conn-on { color:var(--status-ok); border-color:var(--status-ok); }
#conn-state.conn-off { color:var(--faint); }
/* abas de provedor de IA */
.prov-tabs { display:flex; gap:0; margin-top:16px; border:1px solid var(--border); width:fit-content; }
.prov-tab { background:transparent; border:none; color:var(--muted-foreground); cursor:pointer;
  padding:9px 22px; font-size:11px; letter-spacing:.18em; text-transform:uppercase; transition:.2s;
  border-right:1px solid var(--border); }
.prov-tab:last-child { border-right:none; }
.prov-tab:hover { color:var(--foreground); }
.prov-tab.on { background:var(--foreground); color:var(--background); }
.model-row { margin-top:14px; display:flex; align-items:center; gap:12px; }
.model-row select { max-width:340px; cursor:pointer; padding:11px 14px; }
.model-row select option { background:var(--surface); color:var(--foreground); }
/* painel de progresso da geração */
.prog { margin-top:22px; border:1px solid var(--border); background:var(--background); padding:20px 22px; }
.prog-head { display:flex; align-items:baseline; justify-content:space-between; }
.prog-count { font-family:var(--font-serif); font-size:20px; color:var(--foreground); }
.prog-faltam { font-size:11px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint); }
.prog-bar { height:3px; background:var(--border); margin:14px 0 8px; overflow:hidden; }
.prog-fill { height:100%; background:var(--foreground); transition:width .4s ease; }
.prog-tempo { font-size:11px; letter-spacing:.1em; color:var(--muted-foreground); }
.prog-list { list-style:none; margin:18px 0 0; padding:0; }
.prog-item { display:flex; align-items:center; gap:12px; padding:9px 0; border-top:1px solid var(--border); font-size:14px; font-weight:300; }
.prog-item .pi-ic { width:18px; text-align:center; flex-shrink:0; }
.prog-item.ok    { color:var(--foreground); }      .prog-item.ok .pi-ic { color:var(--status-ok); }
.prog-item.falha { color:var(--muted-foreground); } .prog-item.falha .pi-ic { color:var(--status-err); }
.prog-item.fazendo { color:var(--foreground); }
.prog-item.wait  { color:var(--faint); }
.prog-item .pi-sub { margin-left:auto; font-size:11px; color:var(--faint); letter-spacing:.05em; }
.mini-spin { width:11px; height:11px; border:2px solid var(--foreground); border-top-color:transparent; border-radius:50%;
  display:inline-block; animation:ngspin .7s linear infinite; }
/* modal de leitura das respostas do cliente */
.resp-modal { position:fixed; inset:0; z-index:200; background:rgba(0,0,0,.55);
  display:flex; justify-content:center; align-items:flex-start; overflow-y:auto; padding:6vh 20px; }
.resp-modal-in { background:var(--background); border:1px solid var(--border); max-width:760px; width:100%;
  padding:44px 48px 56px; position:relative; }
.resp-close { position:absolute; top:20px; right:22px; background:none; border:none; color:var(--faint);
  font-size:20px; cursor:pointer; line-height:1; }
.resp-close:hover { color:var(--foreground); }
.resp-sec { margin-top:34px; }
.resp-sec-h { font-family:var(--font-serif); font-size:24px; color:var(--foreground);
  padding-bottom:12px; border-bottom:1px solid var(--border); }
.resp-num { font-family:var(--font-mono); font-size:12px; color:var(--faint); margin-right:8px; }
.resp-row { display:grid; grid-template-columns:210px 1fr; gap:20px; padding:13px 0; border-bottom:1px solid var(--border); }
.resp-k { font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--faint); padding-top:2px; }
.resp-v { font-family:var(--font-serif); font-size:17px; color:var(--foreground); line-height:1.5; white-space:pre-wrap; }
.resp-empty { padding:14px 0; font-size:13px; color:var(--faint); font-weight:300; }
@media (max-width:560px){ .resp-modal-in{padding:36px 24px;} .resp-row{grid-template-columns:1fr; gap:4px;} }
/* botão ✕ de excluir na linha do cliente */
.app-btn-x { margin-top:0; background:transparent; border:1px solid var(--border); color:var(--faint);
  width:40px; height:40px; padding:0; font-size:14px; line-height:1; cursor:pointer; flex-shrink:0;
  display:inline-flex; align-items:center; justify-content:center; transition:.18s; }
.app-btn-x:hover { color:var(--status-err); border-color:var(--status-err); }
/* botão perigo (confirmar exclusão) */
.app-btn.danger { background:var(--status-danger); color:var(--status-danger-fg); }
.app-btn.danger:hover { opacity:.88; }
/* modal de confirmação de exclusão */
.confirm-modal { position:fixed; inset:0; z-index:220; background:rgba(0,0,0,.6);
  display:flex; align-items:center; justify-content:center; padding:24px; }
.confirm-in { background:var(--background); border:1px solid var(--border); max-width:440px; width:100%;
  padding:34px 34px 30px; }
.confirm-h { font-family:var(--font-serif); font-size:26px; color:var(--foreground); margin-top:12px; line-height:1.15; }
.confirm-txt { font-size:14px; color:var(--muted-foreground); font-weight:300; line-height:1.6; margin-top:14px; }
.confirm-acts { display:flex; gap:12px; justify-content:flex-end; margin-top:28px; }
.confirm-acts .app-btn { margin-top:0; }
.confirm-status { font-size:13px; color:var(--muted-foreground); margin-top:14px; min-height:18px; text-align:right; }
.confirm-status.err { color:var(--status-err); }
/* badge do tipo de dossiê na linha do cliente */
.tipo-badge { font-family:var(--font-sans); font-size:10px; letter-spacing:.12em; text-transform:uppercase;
  color:var(--faint); border:1px solid var(--border); border-radius:999px; padding:2px 9px; margin-left:8px;
  vertical-align:middle; font-weight:400; }
/* modal Novo cliente (réplica do print) */
.nc-modal { position:fixed; inset:0; z-index:230; background:rgba(0,0,0,.6);
  display:flex; align-items:flex-start; justify-content:center; padding:40px 24px; overflow-y:auto; }
.nc-in { position:relative; background:var(--background); border:1px solid var(--border); max-width:520px; width:100%;
  padding:38px 40px 34px; }
.nc-x { position:absolute; top:22px; right:24px; background:none; border:none; color:var(--faint); font-size:18px; cursor:pointer; }
.nc-x:hover { color:var(--foreground); }
.nc-h { font-family:var(--font-serif); font-size:32px; color:var(--foreground); }
.nc-sub { font-size:14px; color:var(--muted-foreground); font-weight:300; margin-top:8px; }
.nc-label { display:block; font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--faint); margin:26px 0 12px; }
.nc-input { width:100%; background:transparent; border:none; border-bottom:1px solid var(--border);
  color:var(--foreground); padding:10px 0; font-family:var(--font-sans); font-size:17px; font-weight:300; }
.nc-input::placeholder { color:var(--faint); }
.nc-input:focus { outline:none; border-bottom-color:var(--foreground); }
.nc-cards { display:grid; gap:12px; }
.nc-cards.nc-3 { grid-template-columns:1fr 1fr 1fr; }
.nc-cards.nc-2 { grid-template-columns:1fr 1fr; }
.nc-card { text-align:left; background:transparent; border:1px solid var(--border); border-radius:8px;
  padding:16px; cursor:pointer; transition:border-color .15s, background .15s; }
.nc-card:hover { border-color:var(--muted-foreground); }
.nc-card.on { border-color:var(--foreground); background:var(--surface); }
.nc-card-t { font-size:15px; color:var(--foreground); font-weight:500; }
.nc-card-d { font-size:12px; color:var(--muted-foreground); font-weight:300; line-height:1.5; margin-top:6px; }
.nc-hint { font-size:12px; color:var(--muted-foreground); font-weight:300; line-height:1.6; margin-top:12px; }
.nc-hint b { color:var(--foreground); font-weight:500; }
.nc-go { width:100%; justify-content:center; margin-top:26px; }
.nc-status { font-size:13px; color:var(--muted-foreground); margin-top:12px; min-height:16px; }
.nc-status.err { color:var(--status-err); }
@media (max-width:560px){ .nc-cards.nc-3{grid-template-columns:1fr;} .nc-cards.nc-2{grid-template-columns:1fr;} }
/* modal "Cliente criado" — link/código com botão de copiar */
.cc-item { margin-top:22px; }
.cc-row { display:flex; align-items:center; gap:10px; margin-top:8px; background:var(--surface);
  border:1px solid var(--border); padding:12px 14px; }
.cc-val { flex:1; font-family:var(--font-mono); font-size:13px; color:var(--foreground);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cc-copy { flex-shrink:0; background:var(--foreground); color:var(--background); border:none;
  padding:9px 16px; font-size:11px; letter-spacing:.14em; text-transform:uppercase; cursor:pointer;
  transition:opacity .2s; }
.cc-copy:hover { opacity:.85; }
/* cor de texto FIXA (não herda var(--background)): a base .cc-copy usa
   color:var(--background), que troca de branco pra preto entre os temas —
   sem fixar aqui, o texto "Copiado!" sumiria no tema escuro (preto sobre
   fundo verde escuro-médio). */
.cc-copy.copied { background:var(--status-copied); color:var(--status-copied-fg); }
.cc-msg { width:100%; margin-top:26px; justify-content:center; }

/* ---------- login (Supabase Auth) ---------- */
.auth-gate { position:fixed; inset:0; z-index:9999; background:var(--background); display:flex;
  align-items:center; justify-content:center; padding:24px; }
.auth-box { width:100%; max-width:360px; }
.auth-eyebrow { font-family:var(--font-sans); font-size:10px; letter-spacing:.3em; text-transform:uppercase; color:var(--faint); margin-bottom:16px; }
.auth-h1 { font-family:var(--font-serif); font-size:32px; line-height:1.1; margin-bottom:28px; }
.auth-field { margin-bottom:16px; }
.auth-label { font-size:10px; letter-spacing:.24em; text-transform:uppercase; color:var(--faint); display:block; margin-bottom:8px; }
.auth-input { width:100%; background:var(--surface); border:1px solid var(--border); color:var(--foreground);
  padding:12px 14px; font-family:var(--font-sans); font-size:14px; font-weight:300; }
.auth-input:focus { outline:none; border-color:var(--foreground); }
.auth-btn { width:100%; margin-top:8px; justify-content:center; }
.auth-status { font-size:13px; color:var(--muted-foreground); margin-top:14px; min-height:16px; }
.auth-status.err { color:var(--status-err); }
/* z-index 150: acima do conteúdo e da sidebar (55-60), mas ABAIXO dos modais
   (resp-modal 200 / confirm 220 / nc 230) — antes era 9998 e os botões de conta
   ficavam POR CIMA dos modais, sobrepondo "Copiar respostas"/"✕" (bug visto em
   produção). O auth-gate (9999) continua cobrindo tudo, inclusive estes botões. */
.auth-logout { position:fixed; top:18px; right:18px; z-index:150; font-size:11px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--faint); background:none; border:1px solid var(--border);
  padding:8px 14px; cursor:pointer; }
.auth-logout:hover { color:var(--foreground); border-color:var(--foreground); }
/* ---------- toggle (auto-revisão por IA) ---------- */
.toggle-row { display:flex; align-items:center; gap:12px; cursor:pointer; user-select:none; }
.toggle-row input { position:absolute; opacity:0; width:0; height:0; }
.toggle-sw { width:38px; height:22px; border-radius:999px; background:var(--border); position:relative;
  flex-shrink:0; transition:background .2s; }
.toggle-sw::after { content:""; position:absolute; top:2px; left:2px; width:18px; height:18px; border-radius:50%;
  background:var(--background); transition:transform .2s; }
.toggle-row input:checked + .toggle-sw { background:var(--foreground); }
.toggle-row input:checked + .toggle-sw::after { transform:translateX(16px); }
.toggle-txt { font-size:13px; color:var(--muted-foreground); font-weight:300; }
.toggle-hint { color:var(--faint); font-size:12px; }
/* ---------- revisão pós-geração (editar antes de salvar) ---------- */
.revisao-list { list-style:none; margin:22px 0 0; padding:0; }
.revisao-item { display:flex; align-items:center; justify-content:space-between; gap:16px;
  padding:16px 18px; border:1px solid var(--border); margin-top:-1px; background:var(--surface); }
.revisao-item .ri-nome { font-family:var(--font-serif); font-size:17px; color:var(--foreground); }
.revisao-item .ri-meta { font-size:11px; letter-spacing:.08em; color:var(--faint); margin-top:3px; }
.revisao-item .ri-meta.edited { color:var(--status-warn); }
.revisao-item .ri-meta.falha { color:var(--status-err); }
.revisao-item .app-btn { margin-top:0; padding:10px 18px; }
.edit-modal-in { max-width:820px; }
.edit-json { min-height:50vh; font-family:var(--font-mono); font-size:12.5px; line-height:1.6; margin-top:18px; }
"""


def _auth_gate_js():
    # Login real via Supabase Auth (email/senha) — chamado no início de
    # _gerar_js()/_clientes_js(). Bloqueia a tela com um overlay até haver
    # sessão válida; expõe AUTH_TOKEN()/AUTH_HEADERS() para os RPCs _auth.
    return (
        r"""
<div id="auth-gate" class="auth-gate" style="display:none">
  <div class="auth-box">
    <div class="auth-eyebrow">Noeds · Equipe</div>
    <h1 class="auth-h1">Entrar</h1>
    <div class="auth-field">
      <label class="auth-label">E-mail</label>
      <input id="auth-email" class="auth-input" type="email" autocomplete="username">
    </div>
    <div class="auth-field">
      <label class="auth-label">Senha</label>
      <input id="auth-pass" class="auth-input" type="password" autocomplete="current-password">
    </div>
    <button id="auth-btn" class="app-btn auth-btn">Entrar</button>
    <div id="auth-status" class="auth-status"></div>
  </div>
</div>
<button id="auth-equipe" class="auth-logout" style="display:none; right:483px">Cadastrar equipe</button>
<button id="auth-pmi" class="auth-logout" style="display:none; right:354px">PMI padrão</button>
<button id="auth-prompt" class="auth-logout" style="display:none; right:225px">Prompt de geração</button>
<button id="auth-senha" class="auth-logout" style="display:none; right:96px">Trocar senha</button>
<button id="auth-logout" class="auth-logout" style="display:none">Sair</button>
<div id="pmi-modal" class="nc-modal" style="display:none">
  <div class="nc-in" style="max-width:720px">
    <button class="nc-x" id="pmi-x">×</button>
    <h2 class="nc-h" style="font-size:26px">PMI padrão (Plano de Marketing Inteligente)</h2>
    <p class="nc-sub">Este documento não é gerado por IA. Cole aqui o JSON final do PMI (visao_geral, 4 blocos, 7 motores, escala) — o mesmo conteúdo será usado em TODOS os clientes daqui em diante, sem regenerar. Deixe vazio e salve para voltar a gerar por IA a cada cliente.</p>
    <textarea id="pmi-texto" style="width:100%; min-height:360px; margin-top:14px; font-family:ui-monospace,monospace; font-size:12.5px; line-height:1.6; padding:14px; background:var(--surface-2); border:1px solid var(--border); color:var(--foreground); resize:vertical"></textarea>
    <div id="pmi-aviso" class="auth-status err" style="display:none; margin-top:8px"></div>
    <div style="display:flex; gap:10px; margin-top:14px; align-items:center; flex-wrap:wrap">
      <button id="pmi-salvar" class="app-btn">Salvar</button>
      <button id="pmi-limpar" class="app-btn ghost">Voltar a gerar por IA</button>
      <div id="pmi-status" class="auth-status" style="margin:0"></div>
    </div>
  </div>
</div>
<div id="prompt-modal" class="nc-modal" style="display:none">
  <div class="nc-in" style="max-width:720px">
    <button class="nc-x" id="prompt-x">×</button>
    <h2 class="nc-h" style="font-size:26px">Prompt de geração dos documentos</h2>
    <p class="nc-sub">Texto-base enviado à IA para cada um dos 9 documentos — os trechos entre chaves ({instruções deste documento}, {contexto da empresa} etc.) são preenchidos automaticamente por documento/cliente no momento da geração; mantenha-os no texto. Editável só por admin — vale para toda a equipe.</p>
    <textarea id="prompt-texto" style="width:100%; min-height:360px; margin-top:14px; font-family:ui-monospace,monospace; font-size:12.5px; line-height:1.6; padding:14px; background:var(--surface-2); border:1px solid var(--border); color:var(--foreground); resize:vertical"></textarea>
    <div id="prompt-aviso" class="auth-status err" style="display:none; margin-top:8px"></div>
    <div style="display:flex; gap:10px; margin-top:14px; align-items:center; flex-wrap:wrap">
      <button id="prompt-salvar" class="app-btn">Salvar</button>
      <button id="prompt-restaurar" class="app-btn ghost">Restaurar padrão</button>
      <div id="prompt-status" class="auth-status" style="margin:0"></div>
    </div>
  </div>
</div>
<div id="senha-modal" class="nc-modal" style="display:none">
  <div class="nc-in" style="max-width:420px">
    <button class="nc-x" id="senha-x">×</button>
    <h2 class="nc-h" style="font-size:26px">Trocar senha</h2>
    <p class="nc-sub">Confirme a senha atual e defina a nova.</p>
    <label class="nc-label">Senha atual</label>
    <input id="senha-atual" class="auth-input" type="password" autocomplete="current-password">
    <label class="nc-label">Nova senha</label>
    <input id="senha-nova" class="auth-input" type="password" autocomplete="new-password">
    <label class="nc-label">Confirmar nova senha</label>
    <input id="senha-confirma" class="auth-input" type="password" autocomplete="new-password">
    <button id="senha-salvar" class="app-btn" style="width:100%; justify-content:center">Salvar nova senha</button>
    <div id="senha-status" class="auth-status"></div>
  </div>
</div>
<div id="equipe-modal" class="nc-modal" style="display:none">
  <div class="nc-in" style="max-width:480px">
    <button class="nc-x" id="equipe-x">×</button>
    <h2 class="nc-h" style="font-size:26px">Cadastrar equipe</h2>
    <p class="nc-sub">Cria um login novo (e-mail e senha) para um colega acessar o painel. Só administradores veem esta tela.</p>
    <div id="equipe-lista" style="margin:16px 0 6px"></div>
    <label class="nc-label">Nome</label>
    <input id="equipe-nome" class="auth-input" type="text" autocomplete="name">
    <label class="nc-label">E-mail</label>
    <input id="equipe-email" class="auth-input" type="email" autocomplete="email">
    <label class="nc-label">Senha inicial</label>
    <input id="equipe-senha" class="auth-input" type="password" autocomplete="new-password">
    <p class="toggle-hint" style="margin-top:4px">Mínimo 6 caracteres. O colega pode trocar depois em "Trocar senha".</p>
    <label class="nc-label" style="margin-top:14px">Papel</label>
    <div class="nc-cards nc-2" id="equipe-papel-cards">
      <button type="button" class="nc-card on" data-papel="vendedor">
        <div class="nc-card-t">Vendedor</div>
        <div class="nc-card-d">Vê e copia links de clientes. Sem acesso a "Gerar", criar/excluir cliente ou gerenciar link.</div>
      </button>
      <button type="button" class="nc-card" data-papel="admin">
        <div class="nc-card-t">Admin</div>
        <div class="nc-card-d">Acesso total: gerar dossiês, criar/excluir clientes, gerenciar links e cadastrar equipe.</div>
      </button>
    </div>
    <button id="equipe-salvar" class="app-btn" style="width:100%; justify-content:center; margin-top:18px">Criar conta</button>
    <div id="equipe-status" class="auth-status"></div>
  </div>
</div>
<script>
(function(){
  // declarado aqui (não só no script principal que vem depois) porque este
  // IIFE roda ANTES dele, na carga inicial — carregarPapel() precisa da URL
  // disponível já na primeira execução síncrona, não só após um clique.
  var SUPABASE_URL=""" + f'"{SUPABASE_URL}"' + r""", SUPABASE_ANON=""" + f'"{SUPABASE_ANON}"' + r""";
  var SESSION_KEY="noeds_auth_session";
  function getSession(){ try{return JSON.parse(localStorage.getItem(SESSION_KEY)||"null");}catch(e){return null;} }
  function setSession(s){
    if(s){
      // expires_in vem em segundos a partir de AGORA (login/refresh) — guardamos o
      // instante absoluto de expiração p/ saber, sem chamar a rede, se está vencido.
      s._expiresAt = Date.now() + ((s.expires_in||3600)*1000);
      localStorage.setItem(SESSION_KEY, JSON.stringify(s));
    } else localStorage.removeItem(SESSION_KEY);
  }
  window.AUTH_TOKEN=function(){ var s=getSession(); return s&&s.access_token; };
  // access_token do Supabase expira em 1h (expires_in:3600) e nunca era renovado —
  // gerações longas (Claude/GPT-5-mini, vários minutos por documento) frequentemente
  // ultrapassam isso, e "Salvar e finalizar" no fim do processo levava 401. Renova
  // via refresh_token com 60s de folga antes de vencer, ou reativamente em qualquer 401.
  var _refreshing=null;
  async function refreshSession(){
    if(_refreshing) return _refreshing;
    var s=getSession();
    if(!s||!s.refresh_token){ return null; }
    _refreshing=(async function(){
      try{
        var r=await fetch(SUPABASE_URL+"/auth/v1/token?grant_type=refresh_token",{method:"POST",
          headers:{apikey:SUPABASE_ANON,"Content-Type":"application/json"},
          body:JSON.stringify({refresh_token:s.refresh_token})});
        var d=await r.json();
        if(!r.ok||!d.access_token){ setSession(null); return null; }
        setSession(d);
        return d;
      }catch(e){ return null; }
    })();
    var res=await _refreshing; _refreshing=null; return res;
  }
  window.ensureFreshSession=async function(){
    var s=getSession();
    if(!s||!s.access_token) return;
    if(!s._expiresAt || Date.now() > (s._expiresAt-60000)) await refreshSession();
  };
  window.AUTH_HEADERS=function(){
    var t=window.AUTH_TOKEN();
    return {apikey:SUPABASE_ANON, Authorization:"Bearer "+(t||SUPABASE_ANON), "Content-Type":"application/json"};
  };
  // versão assíncrona: garante token válido ANTES de montar os headers — usar nos
  // pontos que podem ocorrer minutos após o login (salvar, RPCs pós-geração longa).
  window.AUTH_HEADERS_FRESH=async function(){
    await window.ensureFreshSession();
    return window.AUTH_HEADERS();
  };
  window.MEU_PAPEL=null; // 'admin' | 'vendedor' — preenchido antes de onAuthReady rodar
  async function carregarPapel(){
    try{
      var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/get_meu_papel_auth",{method:"POST",headers:window.AUTH_HEADERS()});
      window.MEU_PAPEL=r.ok?(await r.json()):null;
    }catch(e){ window.MEU_PAPEL=null; }
  }
  function showGate(){ document.getElementById("auth-gate").style.display="flex";
    document.getElementById("auth-logout").style.display="none"; document.getElementById("auth-senha").style.display="none";
    document.getElementById("auth-prompt").style.display="none"; document.getElementById("auth-equipe").style.display="none"; }
  function hideGate(){ document.getElementById("auth-gate").style.display="none";
    document.getElementById("auth-logout").style.display="block"; document.getElementById("auth-senha").style.display="block";
    if(window.PROMPT_TEMPLATE_PADRAO) document.getElementById("auth-prompt").style.display="block";
    if(window.MEU_PAPEL==="admin") document.getElementById("auth-equipe").style.display="block"; }
  async function login(){
    var email=document.getElementById("auth-email").value.trim();
    var pass=document.getElementById("auth-pass").value;
    var st=document.getElementById("auth-status");
    if(!email||!pass){ st.className="auth-status err"; st.textContent="Preencha e-mail e senha."; return; }
    st.className="auth-status"; st.textContent="Entrando…";
    try{
      var r=await fetch(SUPABASE_URL+"/auth/v1/token?grant_type=password",{method:"POST",
        headers:{apikey:SUPABASE_ANON,"Content-Type":"application/json"},
        body:JSON.stringify({email:email,password:pass})});
      var d=await r.json();
      if(!r.ok||!d.access_token){ st.className="auth-status err"; st.textContent=(d.error_description||d.msg||"E-mail ou senha inválidos."); return; }
      setSession(d);
      await carregarPapel();
      if(window.PROMPT_TEMPLATE_PADRAO) await carregarPromptConfig();
      hideGate();
      if(window.onAuthReady) window.onAuthReady();
    }catch(e){ st.className="auth-status err"; st.textContent="Falha de conexão."; }
  }
  async function logout(){
    var s=getSession();
    try{ await fetch(SUPABASE_URL+"/auth/v1/logout",{method:"POST",
      headers:{apikey:SUPABASE_ANON,Authorization:"Bearer "+(s&&s.access_token||SUPABASE_ANON)}}); }catch(e){}
    setSession(null);
    location.reload();
  }
  async function carregarPromptConfig(){
    try{
      var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/get_config_auth",{method:"POST",headers:window.AUTH_HEADERS(),
        body:JSON.stringify({p_chave:"prompt_geracao"})});
      window.PROMPT_TEMPLATE_ATUAL=r.ok?(await r.json()):null;
    }catch(e){ window.PROMPT_TEMPLATE_ATUAL=null; }
  }
  function checarMarcadoresPrompt(texto){
    var faltando=(window.PROMPT_MARCADORES||[]).filter(function(m){return texto.indexOf(m)<0;});
    return faltando;
  }
  function abrirPromptGeracao(){
    document.getElementById("prompt-texto").value=window.PROMPT_TEMPLATE_ATUAL||window.PROMPT_TEMPLATE_PADRAO||"";
    var av=document.getElementById("prompt-aviso"); av.style.display="none"; av.textContent="";
    var st=document.getElementById("prompt-status"); st.className="auth-status"; st.textContent=
      window.PROMPT_TEMPLATE_ATUAL ? "Versão customizada em uso." : "Usando o texto padrão (nenhuma customização salva).";
    document.getElementById("prompt-modal").style.display="flex";
  }
  function fecharPromptGeracao(){ document.getElementById("prompt-modal").style.display="none"; }
  function validarPromptEdicao(){
    var texto=document.getElementById("prompt-texto").value;
    var faltando=checarMarcadoresPrompt(texto);
    var av=document.getElementById("prompt-aviso");
    if(faltando.length){
      av.style.display="block";
      av.textContent="Atenção: faltam os marcadores "+faltando.join(", ")+" — sem eles a geração ignora este texto e usa o padrão automaticamente.";
    } else { av.style.display="none"; av.textContent=""; }
    return faltando;
  }
  async function salvarPromptGeracao(){
    var texto=document.getElementById("prompt-texto").value;
    validarPromptEdicao(); // só avisa — salvar com marcador faltando é permitido (cai pro padrão na geração)
    var btn=document.getElementById("prompt-salvar"); var st=document.getElementById("prompt-status");
    btn.disabled=true; st.className="auth-status"; st.textContent="Salvando…";
    try{
      var h=await window.AUTH_HEADERS_FRESH();
      var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/set_config_auth",{method:"POST",headers:h,
        body:JSON.stringify({p_chave:"prompt_geracao", novo_valor:texto})});
      if(!r.ok){ var d=await r.json().catch(function(){return{};}); throw new Error(d.message||("Falha ao salvar ("+r.status+")")); }
      window.PROMPT_TEMPLATE_ATUAL=texto;
      st.className="auth-status"; st.textContent="Salvo ✓ — vale a partir da próxima geração.";
    }catch(e){ st.className="auth-status err"; st.textContent=e.message; }
    btn.disabled=false;
  }
  async function restaurarPromptGeracao(){
    if(!confirm("Restaurar o texto padrão? A customização salva será apagada.")) return;
    var btn=document.getElementById("prompt-restaurar"); var st=document.getElementById("prompt-status");
    btn.disabled=true; st.className="auth-status"; st.textContent="Restaurando…";
    try{
      var h=await window.AUTH_HEADERS_FRESH();
      var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/set_config_auth",{method:"POST",headers:h,
        body:JSON.stringify({p_chave:"prompt_geracao", novo_valor:null})});
      if(!r.ok){ var d=await r.json().catch(function(){return{};}); throw new Error(d.message||("Falha ao restaurar ("+r.status+")")); }
      window.PROMPT_TEMPLATE_ATUAL=null;
      document.getElementById("prompt-texto").value=window.PROMPT_TEMPLATE_PADRAO||"";
      document.getElementById("prompt-aviso").style.display="none";
      st.className="auth-status"; st.textContent="Restaurado ao padrão ✓";
    }catch(e){ st.className="auth-status err"; st.textContent=e.message; }
    btn.disabled=false;
  }
  function abrirTrocaSenha(){
    document.getElementById("senha-atual").value="";
    document.getElementById("senha-nova").value="";
    document.getElementById("senha-confirma").value="";
    var st=document.getElementById("senha-status"); st.className="auth-status"; st.textContent="";
    document.getElementById("senha-modal").style.display="flex";
  }
  function fecharTrocaSenha(){ document.getElementById("senha-modal").style.display="none"; }
  async function trocarSenha(){
    var atual=document.getElementById("senha-atual").value;
    var nova=document.getElementById("senha-nova").value;
    var confirma=document.getElementById("senha-confirma").value;
    var st=document.getElementById("senha-status");
    var s=getSession();
    if(!atual||!nova||!confirma){ st.className="auth-status err"; st.textContent="Preencha todos os campos."; return; }
    if(nova.length<6){ st.className="auth-status err"; st.textContent="A nova senha precisa ter pelo menos 6 caracteres."; return; }
    if(nova!==confirma){ st.className="auth-status err"; st.textContent="As senhas não coincidem."; return; }
    if(!s||!s.user||!s.user.email){ st.className="auth-status err"; st.textContent="Sessão inválida — saia e entre de novo."; return; }
    st.className="auth-status"; st.textContent="Confirmando senha atual…";
    try{
      // reautentica com a senha atual antes de trocar (evita que alguém com a
      // sessão aberta na tela troque a senha sem realmente saber a atual).
      var rConf=await fetch(SUPABASE_URL+"/auth/v1/token?grant_type=password",{method:"POST",
        headers:{apikey:SUPABASE_ANON,"Content-Type":"application/json"},
        body:JSON.stringify({email:s.user.email,password:atual})});
      var dConf=await rConf.json();
      if(!rConf.ok||!dConf.access_token){ st.className="auth-status err"; st.textContent="Senha atual incorreta."; return; }
      st.textContent="Salvando nova senha…";
      var r=await fetch(SUPABASE_URL+"/auth/v1/user",{method:"PUT",
        headers:{apikey:SUPABASE_ANON,Authorization:"Bearer "+dConf.access_token,"Content-Type":"application/json"},
        body:JSON.stringify({password:nova})});
      var d=await r.json();
      if(!r.ok){ st.className="auth-status err"; st.textContent=(d.msg||d.error_description||"Falha ao trocar a senha."); return; }
      setSession(dConf); // sessão renovada na reautenticação acima
      st.className="auth-status"; st.textContent="Senha alterada ✓";
      setTimeout(fecharTrocaSenha, 1200);
    }catch(e){ st.className="auth-status err"; st.textContent="Falha de conexão."; }
  }
  // ---- cadastro de equipe (só admin) ----
  var PAPEL_ESCOLHIDO="vendedor";
  async function carregarListaEquipe(){
    var box=document.getElementById("equipe-lista");
    box.innerHTML='<p class="toggle-hint">Carregando equipe atual…</p>';
    try{
      var h=await window.AUTH_HEADERS_FRESH();
      var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/listar_equipe_auth",{method:"POST",headers:h});
      if(!r.ok) throw new Error();
      var rows=await r.json();
      var papelTxt={admin:"Admin",vendedor:"Vendedor"};
      box.innerHTML='<p class="nc-label" style="margin-bottom:8px">Equipe atual (' + rows.length + ')</p>'
        + rows.map(function(m){
            return '<div style="display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid var(--border);font-size:13px">'
              +'<span style="color:var(--foreground)">'+ (m.nome||"—").replace(/[<>&]/g,function(c){return {"<":"&lt;",">":"&gt;","&":"&amp;"}[c];}) +'</span>'
              +'<span style="color:var(--faint)">'+ (papelTxt[m.papel]||m.papel) +'</span></div>';
          }).join("");
    }catch(e){ box.innerHTML='<p class="toggle-hint">Não foi possível carregar a lista da equipe.</p>'; }
  }
  function abrirEquipe(){
    document.getElementById("equipe-nome").value="";
    document.getElementById("equipe-email").value="";
    document.getElementById("equipe-senha").value="";
    PAPEL_ESCOLHIDO="vendedor";
    document.querySelectorAll("#equipe-papel-cards .nc-card").forEach(function(c){
      c.classList.toggle("on", c.dataset.papel==="vendedor");
    });
    var st=document.getElementById("equipe-status"); st.className="auth-status"; st.textContent="";
    document.getElementById("equipe-modal").style.display="flex";
    carregarListaEquipe();
  }
  function fecharEquipe(){ document.getElementById("equipe-modal").style.display="none"; }
  async function criarMembroEquipe(){
    var nome=document.getElementById("equipe-nome").value.trim();
    var email=document.getElementById("equipe-email").value.trim();
    var senha=document.getElementById("equipe-senha").value;
    var st=document.getElementById("equipe-status");
    if(!nome){ st.className="auth-status err"; st.textContent="Informe o nome."; return; }
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){ st.className="auth-status err"; st.textContent="E-mail inválido."; return; }
    if(senha.length<6){ st.className="auth-status err"; st.textContent="A senha precisa ter pelo menos 6 caracteres."; return; }
    var btn=document.getElementById("equipe-salvar");
    btn.disabled=true; st.className="auth-status"; st.textContent="Criando conta…";
    try{
      var h=await window.AUTH_HEADERS_FRESH();
      var r=await fetch(SUPABASE_URL+"/functions/v1/criar_membro_equipe",{method:"POST",headers:h,
        body:JSON.stringify({nome:nome,email:email,senha:senha,papel:PAPEL_ESCOLHIDO})});
      var d=await r.json().catch(function(){return{};});
      if(!r.ok){ st.className="auth-status err"; st.textContent=d.message||("Falha ao criar conta ("+r.status+")."); btn.disabled=false; return; }
      st.className="auth-status"; st.textContent="Conta criada ✓ — "+nome+" já pode entrar com o e-mail e senha definidos.";
      carregarListaEquipe();
      setTimeout(function(){ btn.disabled=false; }, 400);
    }catch(e){ st.className="auth-status err"; st.textContent="Falha de conexão."; btn.disabled=false; }
  }
  document.getElementById("auth-btn").addEventListener("click", login);
  document.getElementById("auth-pass").addEventListener("keydown", function(e){ if(e.key==="Enter") login(); });
  document.getElementById("auth-logout").addEventListener("click", logout);
  document.getElementById("auth-senha").addEventListener("click", abrirTrocaSenha);
  document.getElementById("senha-x").addEventListener("click", fecharTrocaSenha);
  document.getElementById("senha-modal").addEventListener("click", function(e){ if(e.target===this) fecharTrocaSenha(); });
  document.getElementById("senha-salvar").addEventListener("click", trocarSenha);
  document.getElementById("auth-prompt").addEventListener("click", abrirPromptGeracao);
  document.getElementById("prompt-x").addEventListener("click", fecharPromptGeracao);
  document.getElementById("prompt-modal").addEventListener("click", function(e){ if(e.target===this) fecharPromptGeracao(); });
  document.getElementById("prompt-texto").addEventListener("input", validarPromptEdicao);
  document.getElementById("prompt-salvar").addEventListener("click", salvarPromptGeracao);
  document.getElementById("prompt-restaurar").addEventListener("click", restaurarPromptGeracao);
  document.getElementById("auth-equipe").addEventListener("click", abrirEquipe);
  document.getElementById("equipe-x").addEventListener("click", fecharEquipe);
  document.getElementById("equipe-modal").addEventListener("click", function(e){ if(e.target===this) fecharEquipe(); });
  document.getElementById("equipe-papel-cards").addEventListener("click", function(e){
    var b=e.target.closest("[data-papel]"); if(!b) return;
    PAPEL_ESCOLHIDO=b.dataset.papel;
    this.querySelectorAll(".nc-card").forEach(function(c){ c.classList.toggle("on", c===b); });
  });
  document.getElementById("equipe-salvar").addEventListener("click", criarMembroEquipe);
  var s=getSession();
  if(s&&s.access_token){
    carregarPapel().then(function(){
      var p=window.PROMPT_TEMPLATE_PADRAO ? carregarPromptConfig() : Promise.resolve();
      p.then(function(){ hideGate(); if(window.onAuthReady) window.onAuthReady(); });
    });
  } else { showGate(); }
})();
</script>
"""
    )


def _gerar_js():
    fields_js = ",".join(f'"{k}"' for k, _ in DOSSIE_FIELDS)
    return (_auth_gate_js() + r"""
<script>
const SUPABASE_URL=""" + f'"{SUPABASE_URL}"' + r""", SUPABASE_ANON=""" + f'"{SUPABASE_ANON}"' + r""";
const FIELDS=[""" + fields_js + r"""];

const $=s=>document.querySelector(s);
function setStatus(msg,kind){var e=$("#status");e.innerHTML=msg;e.className="app-status"+(kind?" "+kind:"");}

// achata os 82 campos (7 seções aninhadas) num objeto chave->texto p/ os prompts dos 9 docs
const SEC_TITULOS={empresa:"Empresa",posicionamento:"Posicionamento",publico:"Público",
  oferta:"Oferta",comercial:"Comercial",marketing:"Marketing",crescimento:"Crescimento",
  comunicacao:"Comunicação & Marca"};
// vocabulário por tipo — mesmo dicionário do formulário (gen_form). Usado p/ dar rótulos
// legíveis à IA nas chaves cujo significado muda por tipo (funil comercial, história).
var TERMOS_CTX={
  clinica:{funil:["Leads/mês","Avaliações/mês","Comparecimentos/mês","Procedimentos vendidos/mês"],historia:"História da clínica"},
  servicos:{funil:["Leads/mês","Reuniões/mês","Reuniões realizadas/mês","Contratos/mês"],historia:"História da empresa"},
  produtos:{funil:["Leads/mês","Interesses/mês","Visitas à loja/mês","Pedidos/mês"],historia:"História da marca"}
};
// mapa chave->rótulo p/ campos cujo nome cru é críptico ou muda por tipo
function rotuloCampo(sid,k,voc){
  if(sid==="empresa"&&k==="historia") return voc.historia;
  if(sid==="comercial"){
    if(k==="leadsMes") return voc.funil[0];
    if(k==="agendamentosMes") return voc.funil[1];
    if(k==="comparecimentosMes") return voc.funil[2];
    if(k==="vendasMes") return voc.funil[3];
  }
  return k;
}
function montarCtxDeFormulario(dadosForm,modelo){
  var voc=TERMOS_CTX[modelo]||TERMOS_CTX.clinica;
  var ctx={clinica:(dadosForm.empresa&&dadosForm.empresa.nome)||""};
  Object.keys(SEC_TITULOS).forEach(function(sid){
    var vals=dadosForm[sid]||{};
    Object.keys(vals).forEach(function(k){
      var v=vals[k];
      if(sid==="oferta"&&k==="itens"&&Array.isArray(v)){
        var txt=v.filter(function(it){return it&&it.nome;}).map(function(it){
          return it.nome+(it.ticket?(" (ticket R$ "+it.ticket+")"):"");
        }).join("; ");
        if(txt) ctx[SEC_TITULOS[sid]+" - Ofertas"]=txt;
        return;
      }
      if(v==null||(""+v).trim()==="")return;
      ctx[SEC_TITULOS[sid]+" - "+rotuloCampo(sid,k,voc)]=v;
    });
  });
  return ctx;
}
// achata o formulário estruturado (7 seções aninhadas) no MESMO shape plano
// de 10 chaves que interpretar() extrai via IA do texto colado (DOSSIE_FIELDS
// / FIELDS) — é o formato que dossie_clientes.dados precisa ter, porque é o
// que RENDER_JS (build.py) lê pra substituir os placeholders [Nome da
// Clínica] etc. nas 9 páginas do dossiê. Sem isso, salvar() gravava o JSON
// aninhado bruto do formulário, e o cliente via os placeholders literais no
// link real (bug confirmado em produção: "Clínica Odonto X").
function achatarDadosDeFormulario(dadosForm){
  var emp=dadosForm.empresa||{}, pos=dadosForm.posicionamento||{}, pub=dadosForm.publico||{},
      ofe=dadosForm.oferta||{}, cre=dadosForm.crescimento||{};
  var primeiroTicket=(Array.isArray(ofe.itens)&&ofe.itens.length&&ofe.itens[0].ticket)||"";
  return {
    clinica: emp.nome||"",
    responsavel: emp.responsavel||"",
    especialidade: emp.segmento||"",
    cidade: emp.cidade||"",
    faturamento: cre.faturamento||"",
    ticket: primeiroTicket,
    principal_dor: pub.dores||"",
    objetivo: cre.objetivoPrincipal||"",
    publico: pub.clienteIdeal||pub.desejos||"",
    diferencial: pos.diferenciais||""
  };
}

// ---- provedores de IA (chave só no navegador, localStorage) ----
// a lista de modelos é buscada da API de cada provedor ao conectar (fetchModelos);
// FALLBACK_MODELS só é usado se a listagem falhar ou antes de conectar.
const FALLBACK_MODELS={
  gemini:[
    {id:"gemini-2.5-pro",label:"Gemini 2.5 Pro"},
    {id:"gemini-2.5-flash",label:"Gemini 2.5 Flash"},
    {id:"gemini-2.5-flash-lite",label:"Gemini 2.5 Flash-Lite"},
    {id:"gemini-2.5-flash-image",label:"Gemini 2.5 Flash Image"},
    {id:"gemini-2.0-flash",label:"Gemini 2.0 Flash"},
    {id:"gemini-2.0-flash-lite",label:"Gemini 2.0 Flash-Lite"},
    {id:"gemini-2.0-pro-exp",label:"Gemini 2.0 Pro (exp)"},
    {id:"gemini-1.5-pro",label:"Gemini 1.5 Pro"},
    {id:"gemini-1.5-flash",label:"Gemini 1.5 Flash"},
    {id:"gemini-1.5-flash-8b",label:"Gemini 1.5 Flash-8B"}
  ],
  openai:[
    {id:"gpt-5",label:"GPT-5"},
    {id:"gpt-5-mini",label:"GPT-5 mini"},
    {id:"gpt-5-nano",label:"GPT-5 nano"},
    {id:"gpt-4.1",label:"GPT-4.1"},
    {id:"gpt-4.1-mini",label:"GPT-4.1 mini"},
    {id:"gpt-4.1-nano",label:"GPT-4.1 nano"},
    {id:"gpt-4o",label:"GPT-4o"},
    {id:"gpt-4o-mini",label:"GPT-4o mini"},
    {id:"chatgpt-4o-latest",label:"ChatGPT-4o latest"},
    {id:"o1",label:"o1"},
    {id:"o1-mini",label:"o1-mini"},
    {id:"o1-pro",label:"o1-pro"},
    {id:"o3",label:"o3"},
    {id:"o3-mini",label:"o3-mini"},
    {id:"o3-pro",label:"o3-pro"},
    {id:"o4-mini",label:"o4-mini"}
  ],
  claude:[
    {id:"claude-opus-4-1-20250805",label:"Claude Opus 4.1"},
    {id:"claude-opus-4-20250514",label:"Claude Opus 4"},
    {id:"claude-sonnet-4-5-20250929",label:"Claude Sonnet 4.5"},
    {id:"claude-sonnet-4-20250514",label:"Claude Sonnet 4"},
    {id:"claude-haiku-4-5-20251001",label:"Claude Haiku 4.5"},
    {id:"claude-3-7-sonnet-20250219",label:"Claude 3.7 Sonnet"},
    {id:"claude-3-5-sonnet-20241022",label:"Claude 3.5 Sonnet"},
    {id:"claude-3-5-haiku-20241022",label:"Claude 3.5 Haiku"},
    {id:"claude-3-opus-20240229",label:"Claude 3 Opus"},
    {id:"claude-3-haiku-20240307",label:"Claude 3 Haiku"}
  ]
};
const PROVIDERS={
  gemini:{ nome:"Google Gemini", link:"https://aistudio.google.com/app/apikey",
    linkLabel:"Pegar chave no Google AI Studio", ph:"Cole aqui sua chave do Gemini (AIza…)",
    store:"gemini_key" },
  openai:{ nome:"OpenAI", link:"https://platform.openai.com/api-keys",
    linkLabel:"Pegar chave na OpenAI", ph:"Cole aqui sua chave da OpenAI (sk-…)",
    store:"openai_key" },
  claude:{ nome:"Anthropic Claude", link:"https://console.anthropic.com/settings/keys",
    linkLabel:"Pegar chave na Anthropic", ph:"Cole aqui sua chave da Anthropic (sk-ant-…)",
    store:"claude_key" }
};
var MODELOS_CACHE={}; // provider -> [{id,label}] já buscados nesta sessão

async function fetchModelos(provider,key){
  try{
    var __resultado=await fetchModelosImpl(provider,key);
    if(__resultado && __resultado.length) return __resultado;
    console.warn("fetchModelos: lista vazia p/ "+provider+", usando fallback");
  }catch(e){
    console.warn("fetchModelos falhou p/ "+provider+":", e);
    setStatus("Não foi possível listar todos os modelos da "+PROVIDERS[provider].nome+" ("+e.message+"). Mostrando lista reduzida — verifique a chave/permissões e reconecte.","err");
  }
  return FALLBACK_MODELS[provider]||[];
}
async function fetchModelosImpl(provider,key){
    if(provider==="openai"){
      // /v1/models não expõe capacidade (sem campo tipo "supports chat"); a única forma
      // confiável de saber se um modelo funciona aqui é o próprio prefixo oficial de família
      // usado pela OpenAI. Excluímos só famílias que a OpenAI documenta como NUNCA aceitando
      // chat/completions (a rota que esta ferramenta usa) — não é um chute por regex de nome.
      var NAO_CHAT=/^(text-embedding|whisper|tts|dall-e|omni-moderation|text-moderation|davinci|babbage|gpt-image)/i;
      var r=await fetch("https://api.openai.com/v1/models",{headers:{Authorization:"Bearer "+key}});
      if(!r.ok) throw new Error("http "+r.status);
      var data=await r.json();
      return (data.data||[])
        .map(function(m){return m.id;})
        .filter(function(id){return !NAO_CHAT.test(id);})
        .sort()
        .map(function(id){return {id:id,label:id};});
    }
    if(provider==="claude"){
      // /v1/models da Anthropic só lista modelos de mensagens/texto (não há embeddings
      // nem imagem nesse endpoint) — nenhum filtro de capacidade é necessário aqui.
      var all=[], url="https://api.anthropic.com/v1/models?limit=1000";
      while(url){
        var r=await fetch(url,{headers:{
          "x-api-key":key,"anthropic-version":"2023-06-01","anthropic-dangerous-direct-browser-access":"true"}});
        if(!r.ok) throw new Error("http "+r.status);
        var data=await r.json();
        all=all.concat(data.data||[]);
        url=(data.has_more&&data.last_id)
          ? "https://api.anthropic.com/v1/models?limit=1000&after_id="+encodeURIComponent(data.last_id)
          : null;
      }
      return all.map(function(m){return {id:m.id, label:m.display_name||m.id};});
    }
    if(provider==="gemini"){
      // supportedGenerationMethods é o campo de capacidade que a própria API expõe —
      // "generateContent" é o método usado por esta ferramenta; sem ele a chamada falha.
      var all=[], url="https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000&key="+encodeURIComponent(key);
      while(url){
        var r=await fetch(url);
        if(!r.ok) throw new Error("http "+r.status);
        var data=await r.json();
        all=all.concat(data.models||[]);
        url=data.nextPageToken
          ? "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000&pageToken="+encodeURIComponent(data.nextPageToken)+"&key="+encodeURIComponent(key)
          : null;
      }
      return all
        .filter(function(m){return (m.supportedGenerationMethods||[]).indexOf("generateContent")>=0;})
        .map(function(m){return {id:(m.name||"").replace(/^models\//,""), label:m.displayName||m.name};})
        .filter(function(m){return m.id;});
    }
}

function getProvider(){ return localStorage.getItem("ai_provider")||"gemini"; }
function setProvider(p){ localStorage.setItem("ai_provider",p); }
function getKeyFor(p){ return localStorage.getItem(PROVIDERS[p].store)||""; }
function getKey(){ return getKeyFor(getProvider()); }
// modelo escolhido por provedor (padrão = 1º do fallback)
function getModelFor(p){ return localStorage.getItem("ai_model_"+p)||(FALLBACK_MODELS[p][0]||{}).id; }
function setModelFor(p,m){ localStorage.setItem("ai_model_"+p,m); }
// ordem de tentativa: o escolhido primeiro, depois os demais (cache ou fallback) como fallback
function modelsInOrder(p){
  var chosen=getModelFor(p), all=(MODELOS_CACHE[p]||FALLBACK_MODELS[p]).map(function(m){return m.id;});
  return [chosen].concat(all.filter(function(id){return id!==chosen;}));
}

// atualiza o card conforme o provedor selecionado, buscando modelos reais ao conectar
async function refreshConn(){
  var p=getProvider(), cfg=PROVIDERS[p];
  document.querySelectorAll(".prov-tab").forEach(function(b){ b.classList.toggle("on", b.dataset.p===p); });
  $("#conn-title").textContent="Conexão · "+cfg.nome;
  $("#prov-link").href=cfg.link; $("#prov-link").textContent="↗ "+cfg.linkLabel;
  $("#gkey").placeholder=cfg.ph;
  var k=getKeyFor(p);
  $("#gkey").value=k||"";
  var sel=$("#model-sel");
  if(k){
    $("#conn-state").textContent="Conectado"; $("#conn-state").className="conn-on";
    if(!MODELOS_CACHE[p]){
      sel.innerHTML='<option>Carregando modelos…</option>';
      MODELOS_CACHE[p]=await fetchModelos(p,k);
    }
    sel.innerHTML="";
    MODELOS_CACHE[p].forEach(function(m){
      var o=document.createElement("option"); o.value=m.id; o.textContent=m.label; sel.appendChild(o);
    });
    sel.value=getModelFor(p);
  } else {
    $("#conn-state").textContent="Não conectado"; $("#conn-state").className="conn-off";
    sel.innerHTML="";
    FALLBACK_MODELS[p].forEach(function(m){
      var o=document.createElement("option"); o.value=m.id; o.textContent=m.label; sel.appendChild(o);
    });
  }
}
// troca de modelo
$("#model-sel").addEventListener("change",function(){
  setModelFor(getProvider(), this.value);
  setStatus("Modelo definido: "+this.options[this.selectedIndex].textContent,"ok");
});
// troca de provedor pelas abas
document.querySelectorAll(".prov-tab").forEach(function(b){
  b.addEventListener("click",function(){ setProvider(b.dataset.p); refreshConn(); setStatus(""); });
});
$("#salvar-key").addEventListener("click",function(){
  var p=getProvider(), k=$("#gkey").value.trim();
  if(!k){ localStorage.removeItem(PROVIDERS[p].store); refreshConn(); setStatus("Chave removida.","");return; }
  localStorage.setItem(PROVIDERS[p].store,k); refreshConn();
  setStatus("Conectado à "+PROVIDERS[p].nome+". Pode gerar.","ok");
});

function sleep(ms){return new Promise(function(r){setTimeout(r,ms);});}
// extrai segundos sugeridos do RetryInfo do erro 429 do Gemini, se houver
function retryDelaySec(je){
  try{ var ds=(je.error&&je.error.details)||[];
    for(var i=0;i<ds.length;i++){ if(/RetryInfo/.test(ds[i]["@type"]||"")){
      var m=(ds[i].retryDelay||"").match(/([0-9.]+)s/); if(m) return Math.ceil(parseFloat(m[1])); } } }catch(_){}
  return 0;
}

async function callGemini(model,prompt,key,temperature){
  var url="https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent?key="+encodeURIComponent(key);
  return fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({contents:[{parts:[{text:prompt}]}],
      generationConfig:{temperature:(temperature==null?0.2:temperature),responseMimeType:"application/json"}})});
}
async function callOpenAI(model,prompt,key,temperature){
  // modelos de raciocínio (gpt-5*, o1*, o3*, o4*) rejeitam "temperature" com 400
  // ("Only the default (1) value is supported") — só enviar em modelos clássicos.
  var SEM_TEMPERATURE=/^(gpt-5|o1|o3|o4)/i;
  var body={model:model, response_format:{type:"json_object"},
    messages:[{role:"user",content:prompt+"\n\nResponda em JSON."}]};
  if(!SEM_TEMPERATURE.test(model)) body.temperature=(temperature==null?0.2:temperature);
  return fetch("https://api.openai.com/v1/chat/completions",{method:"POST",
    headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},
    body:JSON.stringify(body)});
}
async function callClaude(model,prompt,key,temperature){
  // claude-3-opus e claude-3-haiku (legados) limitam output a 4096 tokens —
  // max_tokens:8192 fixo causava 400 nesses dois modelos, abortando a geração
  // inteira sem fallback (aiJSON só avança de modelo em 404/429, não em 400).
  var maxTokens=/^claude-3-(opus|haiku)-/i.test(model) ? 4096 : 8192;
  return fetch("https://api.anthropic.com/v1/messages",{method:"POST",
    headers:{"Content-Type":"application/json","x-api-key":key,
      "anthropic-version":"2023-06-01","anthropic-dangerous-direct-browser-access":"true"},
    body:JSON.stringify({model:model, max_tokens:maxTokens, temperature:(temperature==null?0.2:temperature),
      messages:[{role:"user",content:prompt+"\n\nResponda APENAS com JSON válido, sem markdown."}]})});
}
// extrai o texto JSON da resposta conforme o provedor
function extractText(provider,data){
  if(provider==="openai"){ return (((data.choices||[])[0]||{}).message||{}).content||"{}"; }
  if(provider==="claude"){ return (((data.content||[])[0]||{}).text)||"{}"; }
  return (((data.candidates||[])[0]||{}).content||{}).parts?.[0]?.text||"{}";
}
// extrai tokens de entrada/saída da resposta — cada provedor nomeia diferente.
function extractUsage(provider,data){
  if(provider==="openai"){
    var u=data.usage||{};
    return {entrada:u.prompt_tokens||0, saida:u.completion_tokens||0};
  }
  if(provider==="claude"){
    var u=data.usage||{};
    return {entrada:u.input_tokens||0, saida:u.output_tokens||0};
  }
  var u=data.usageMetadata||{};
  return {entrada:u.promptTokenCount||0, saida:u.candidatesTokenCount||0};
}
// contador acumulado de tokens da geração em andamento (zerado no início de cada "Gerar dossiê completo")
var _tokensGeracao={entrada:0, saida:0};

// núcleo reutilizável: manda um prompt ao provedor selecionado e devolve JSON,
// com fallback de modelo + retry em 429. onWait(msg) atualiza o status na espera.
async function aiJSON(prompt, onWait, temperature){
  var provider=getProvider(), cfg=PROVIDERS[provider], key=getKeyFor(provider);
  if(!key) throw new Error("Conecte sua chave da "+cfg.nome+" no card de conexão acima.");
  var MODELS=modelsInOrder(provider); // escolhido primeiro, resto como fallback
  var lastDetail="", quotaPerDay=false;
  for(var mi=0; mi<MODELS.length; mi++){
    var model=MODELS[mi];
    for(var attempt=0; attempt<3; attempt++){
      var r = provider==="openai" ? await callOpenAI(model,prompt,key,temperature)
            : provider==="claude" ? await callClaude(model,prompt,key,temperature)
            : await callGemini(model,prompt,key,temperature);
      if(r.ok){
        var data=await r.json();
        var uso=extractUsage(provider,data);
        _tokensGeracao.entrada+=uso.entrada; _tokensGeracao.saida+=uso.saida;
        var txt=extractText(provider,data);
        try{return JSON.parse(txt);}catch(e){var m=txt.match(/\{[\s\S]*\}/);return m?JSON.parse(m[0]):{};}
      }
      var detail=""; try{ var je=await r.json(); detail=(je.error&&je.error.message)||""; }catch(_){ je={}; }
      lastDetail=detail;
      // chave inválida / sem permissão (mensagens diferem por provedor)
      if(r.status===401 || (r.status===400&&/API key not valid|API_KEY_INVALID|Incorrect API key|invalid x-api-key/i.test(detail)))
        throw new Error("Chave da "+cfg.nome+" inválida. Reconecte com uma chave válida ("+cfg.linkLabel+").");
      if(r.status===403) throw new Error("Chave sem permissão na "+cfg.nome+". Verifique o painel do provedor.");
      if(r.status===429){
        // OpenAI: 429 pode ser 'insufficient_quota' (sem crédito) — não adianta esperar
        if(provider==="openai" && /insufficient_quota|exceeded your current quota/i.test(detail)){ quotaPerDay=true; break; }
        if(provider==="gemini" && /per day|PerDay|daily/i.test(detail)){ quotaPerDay=true; break; }
        var wait=retryDelaySec(je)|| (attempt+1)*8; // recuo: 8s, 16s, 24s
        if(attempt<2){ if(onWait) onWait("Limite atingido — aguardando "+wait+"s…"); await sleep(wait*1000); continue; }
        break; // esgotou tentativas neste modelo -> tenta próximo
      }
      if(r.status===404) break; // modelo indisponível -> tenta próximo
      throw new Error(cfg.nome+" falhou ("+r.status+")"+(detail?": "+detail:""));
    }
  }
  if(quotaPerDay){
    if(provider==="openai") throw new Error("Sem crédito/cota na OpenAI. Adicione créditos em platform.openai.com (Billing) ou use outro provedor.");
    throw new Error("Cota DIÁRIA gratuita do Gemini esgotada. Volte amanhã, use outra chave, ou ative billing no Google AI Studio.");
  }
  throw new Error("Limite da "+cfg.nome+" atingido (429) em todos os modelos. Aguarde 1–2 min e tente de novo."+(lastDetail?" · "+lastDetail:""));
}

// passo 1: extrai os 10 campos do diagnóstico colado
async function interpretar(texto){
  var prompt="Você estrutura respostas de formulário de clientes de uma consultoria estratégica para clínicas. "
    +"A partir do TEXTO, extraia os campos. Responda APENAS com JSON válido (sem markdown), uma chave por campo; "
    +"se faltar, use string vazia.\n\nCAMPOS: "+FIELDS.join(", ")+"\n\nTEXTO:\n"+texto;
  return aiJSON(prompt);
}

// --- ESPECIFICAÇÃO DOS 9 DOCUMENTOS ---
// cada doc: slug, nome exibido e o "molde" JSON que a IA deve devolver (descrição do formato).
const DOC_SPECS=""" + _doc_specs_json() + r""";
window.DOC_SPECS=DOC_SPECS; // acessado pelo modal "PMI padrão" (definido no IIFE de auth, fora deste script)

// valida a resposta da IA contra as contagens declaradas em spec (_counts,
// _nested_counts, _array_item_counts). Retorna null se ok, ou uma string
// descrevendo o 1º defeito encontrado (usada para pedir correção à IA).
function validarDoc(spec, r){
  if(!r || typeof r!=="object") return "resposta não é um objeto JSON.";
  var counts=spec._counts||{}, nested=spec._nested_counts||{}, arrItem=spec._array_item_counts||{};
  for(var k in counts){
    var v=r[k];
    if(!Array.isArray(v)) return "campo '"+k+"' deveria ser uma lista.";
    if(v.length!==counts[k]) return "campo '"+k+"' tem "+v.length+" itens, precisa ter exatamente "+counts[k]+".";
  }
  for(var nk in nested){
    var obj=r[nk];
    if(!obj || typeof obj!=="object") return "campo '"+nk+"' deveria ser um objeto.";
    for(var sub in nested[nk]){
      var sv=obj[sub];
      if(!Array.isArray(sv)) return "campo '"+nk+"."+sub+"' deveria ser uma lista.";
      if(sv.length!==nested[nk][sub]) return "campo '"+nk+"."+sub+"' tem "+sv.length+" itens, precisa ter exatamente "+nested[nk][sub]+".";
    }
  }
  for(var ak in arrItem){
    var arr=r[ak];
    if(!Array.isArray(arr)) return "campo '"+ak+"' deveria ser uma lista.";
    for(var i=0;i<arr.length;i++){
      var item=arr[i]||{};
      for(var field in arrItem[ak]){
        var fv=item[field];
        if(!Array.isArray(fv)) return "campo '"+ak+"["+i+"]."+field+"' deveria ser uma lista.";
        if(fv.length!==arrItem[ak][field]) return "campo '"+ak+"["+i+"]."+field+"' tem "+fv.length+" itens, precisa ter exatamente "+arrItem[ak][field]+".";
      }
    }
  }
  return null;
}
window.validarDoc=validarDoc; // acessado pelo modal "PMI padrão"

// texto-base do prompt, com marcadores {{...}} que _montarPromptDoc troca pelos
// valores reais (nome/instruções do documento, contexto do cliente etc.) na hora
// de gerar. É o texto exibido/editável no modal "Prompt de geração" — quando a
// equipe salva uma versão customizada (window.PROMPT_TEMPLATE_ATUAL), ela some no
// lugar deste padrão, mas os MESMOS marcadores continuam sendo procurados e
// substituídos, então a edição não quebra a geração desde que os marcadores
// continuem no texto.
var PROMPT_TEMPLATE_PADRAO=
  "Você é consultor estratégico sênior de uma consultoria de crescimento. Escreva o conteúdo REAL e ESPECÍFICO do "
  +"documento \"{{NOME_DOCUMENTO}}\" para a empresa abaixo, no segmento e realidade dela (NÃO use exemplos de estética "
  +"facial se a empresa for de outra área). Ignore qualquer conteúdo de cliente anterior — este documento é escrito do "
  +"zero, só com base nas informações da empresa abaixo.\n\n"
  +"COMO ESCREVER:\n"
  +"- Comunicação humana, simples e profissional. Escreva como uma consultoria real explicando o cenário do cliente, "
  +"não como um relatório automático.\n"
  +"- NÃO use travessão (—) em nenhuma frase. Use vírgula, ponto ou 'e' no lugar.\n"
  +"- NÃO use linguagem com cara de IA, frases genéricas ou termos técnicos sem necessidade.\n"
  +"- Frases diretas e curtas. Exemplos do tom esperado: 'Hoje o principal ponto de atenção está na conversão dos "
  +"leads em agendamentos.' / 'Existe oportunidade de melhorar o posicionamento da oferta para deixar mais claro o "
  +"valor do serviço.'\n"
  +"- Seja concreto: cite procedimentos/serviços plausíveis da área e dores reais do público. Cada frase deve dizer "
  +"algo útil sobre ESTA empresa, não uma generalidade que serviria para qualquer negócio.\n"
  +"- SEJA CURTO E ASSERTIVO: itens de lista com no máximo 140 caracteres; parágrafos com no máximo 2 frases; "
  +"frases com no máximo 20 palavras. Corte adjetivos e rodeios: cada item entrega UMA ideia.\n"
  +"- Ao apontar um problema, aponte junto a ação, no formato 'problema. Verbo de ação.' (ex.: 'Sem follow-up após "
  +"orçamento. Implantar sequência de 3 mensagens em 48h.'). NUNCA comece mais de 2 itens seguidos de uma mesma "
  +"lista com 'Não há' ou 'Não existe'.\n"
  +"- NÃO repita fatos já cobertos por outro documento do dossiê: cada documento tem papel próprio (Diagnóstico "
  +"mostra onde a empresa está; SWOT interpreta forças e riscos; Matriz BCG organiza o portfólio; Marketing e "
  +"Conteúdo dizem o que fazer; Playbook dá o script pronto; Certificado registra o que foi definido). Cite um "
  +"mesmo número no máximo 1 vez por documento, apenas quando essencial ao raciocínio.\n"
  +"- Não invente números, preços, cidade, faturamento, equipe ou volume de leads que não estejam no contexto abaixo. "
  +"Para qualquer dado que falte, escreva 'Não informado' ou 'Ponto a confirmar' em vez de supor um valor.\n\n"
  +"QUANDO FIZER SENTIDO PARA ESTE DOCUMENTO, conecte a análise aos motores da nossa entrega (não force nos "
  +"documentos onde não se aplica, ex. Matriz BCG): Geração de Demanda (como o cliente atrai leads hoje e como "
  +"vamos gerar mais oportunidades), Conversão Comercial (como os leads são atendidos, agendados e convertidos), "
  +"Indicadores (números que precisam ser acompanhados: leads, agendamentos, vendas, CPL, CPA, ROAS, taxa de "
  +"conversão), Reativação (base antiga, contatos parados, oportunidades perdidas), Positivo e Oferta (diferenciais, "
  +"promessa, percepção de valor, motivo para agir agora), Indicação (como gerar novas oportunidades via clientes "
  +"atuais) e Prova Social (depoimentos, resultados, avaliações, conteúdos que aumentam confiança).\n\n"
  +"INSTRUÇÕES ESPECÍFICAS DESTE DOCUMENTO:\n{{INSTRUCOES}}\n\n"
  +"{{EXEMPLO}}"
  +"EMPRESA (contexto):\n{{CONTEXTO_EMPRESA}}\n\n"
  +"Responda APENAS com um JSON válido (sem markdown, sem comentários) EXATAMENTE neste formato:\n"
  +"{{FORMATO_JSON}}\n"
  +"Regras: preencha todos os campos; listas com o nº de itens indicado; sem placeholders entre colchetes; sem "
  +"travessão em nenhum texto."
  +"{{CORRECAO}}";
// marcadores que _montarPromptDoc precisa encontrar no texto pra gerar
// corretamente — usado tanto na geração (fallback pro padrão se sumir do
// customizado) quanto no aviso de validação do modal de edição.
var PROMPT_MARCADORES=["{{NOME_DOCUMENTO}}","{{INSTRUCOES}}","{{CONTEXTO_EMPRESA}}","{{FORMATO_JSON}}"];
window.PROMPT_TEMPLATE_PADRAO=PROMPT_TEMPLATE_PADRAO;
window.PROMPT_MARCADORES=PROMPT_MARCADORES;
window.PROMPT_TEMPLATE_ATUAL=null; // preenchido por carregarPromptConfig() após login; null = usa o padrão

// passo 2: gera o conteúdo de UM documento (JSON estruturado), com o cliente como contexto
function _montarPromptDoc(spec, ctxTxt, correcao){
  var base=window.PROMPT_TEMPLATE_ATUAL||PROMPT_TEMPLATE_PADRAO;
  // customização perdeu marcador essencial (edição manual quebrou a estrutura) ->
  // cai pro padrão nesta geração, em vez de mandar um prompt incompleto à IA.
  if(PROMPT_MARCADORES.some(function(m){return base.indexOf(m)<0;})) base=PROMPT_TEMPLATE_PADRAO;
  var exemplo=spec._exemplo ? ("EXEMPLO DE NÍVEL DE QUALIDADE ESPERADO (empresa de OUTRO segmento — "
      +"use só como referência de profundidade, estrutura e tom; NÃO copie conteúdo nem termine "
      +"citando oficina/carros na resposta da empresa real abaixo):\n"+JSON.stringify(spec._exemplo)+"\n\n") : "";
  return base
    .split("{{NOME_DOCUMENTO}}").join(spec.nome)
    .split("{{INSTRUCOES}}").join(spec.instrucoes||"(nenhuma instrução específica para este documento)")
    .split("{{EXEMPLO}}").join(exemplo)
    .split("{{CONTEXTO_EMPRESA}}").join(ctxTxt)
    .split("{{FORMATO_JSON}}").join(JSON.stringify(spec.formato))
    .split("{{CORRECAO}}").join(correcao ? ("\n\nSUA RESPOSTA ANTERIOR TINHA UM DEFEITO: "+correcao+" Corrija e responda de novo só com o JSON.") : "");
}
async function gerarDoc(spec, ctx, onWait){
  // PMI (Plano de Marketing Inteligente, slug "marketing"): documento fixo, igual
  // pra todo cliente. Não passa pela IA — usa o conteúdo salvo em window.PMI_ATUAL
  // (colado 1 vez pelo botão "PMI padrão" ao lado de "Prompt de geração").
  if(spec.slug==="marketing" && window.PMI_ATUAL){
    if(onWait) onWait("Usando PMI padrão…");
    return window.PMI_ATUAL;
  }
  var ctxTxt=Object.keys(ctx).map(function(k){return "- "+k.replace(/_/g," ")+": "+(ctx[k]||"");}).join("\n");
  var temperature=spec.temperatura==null?0.2:spec.temperatura;
  var resultado=await aiJSON(_montarPromptDoc(spec, ctxTxt, null), onWait, temperature);
  var defeito=validarDoc(spec, resultado);
  if(defeito){
    if(onWait) onWait("Corrigindo estrutura da resposta…");
    resultado=await aiJSON(_montarPromptDoc(spec, ctxTxt, defeito), onWait, temperature);
    // 2ª tentativa: devolve o que veio mesmo se ainda tiver defeito residual
    // (evita loop infinito; melhor entregar algo do que travar a geração).
  }
  if(autoRevisaoAtiva()){
    if(onWait) onWait("Revisando conteúdo…");
    resultado=await revisarDoc(spec, resultado, ctxTxt, onWait);
  }
  return resultado;
}

// lê o toggle "Auto-revisão por IA" da tela (não persiste — decisão por geração).
function autoRevisaoAtiva(){
  var el=document.getElementById("auto-revisao");
  return !!(el && el.checked);
}

// passo opcional: 2ª chamada pedindo à IA para revisar o próprio resultado —
// trocar frases genéricas por algo específico da empresa, sem alterar a
// estrutura (mesmas chaves e contagens de itens). Se a resposta revisada
// vier com estrutura quebrada, mantém o resultado original (nunca piora).
function _montarPromptRevisao(spec, resultado, ctxTxt){
  return "Você é um editor sênior revisando o documento \""+spec.nome+"\" abaixo, escrito para a empresa a seguir. "
    +"Aponte e REESCREVA no próprio JSON qualquer frase genérica, vaga, ou que serviria para qualquer empresa do "
    +"segmento (não só esta). Troque por algo que só faz sentido para ESTA empresa, usando o contexto dela. "
    +"NÃO mude a estrutura do JSON: mesmas chaves, mesmo número de itens em cada lista, mesmos campos.\n\n"
    +"EMPRESA (contexto):\n"+ctxTxt+"\n\n"
    +"DOCUMENTO A REVISAR (JSON):\n"+JSON.stringify(resultado)+"\n\n"
    +"Responda APENAS com o JSON revisado, EXATAMENTE na mesma estrutura (mesmas chaves e contagens de itens).";
}
async function revisarDoc(spec, resultado, ctxTxt, onWait){
  try{
    var temperature=spec.temperatura==null?0.2:spec.temperatura;
    var revisado=await aiJSON(_montarPromptRevisao(spec, resultado, ctxTxt), onWait, temperature);
    var defeito=validarDoc(spec, revisado);
    if(defeito) return resultado; // revisão quebrou a estrutura -> descarta, fica com o original
    return revisado;
  }catch(e){
    return resultado; // falha na revisão nunca deve derrubar a geração do documento
  }
}

// painel de progresso: checklist dos 9 docs + contador de faltantes + tempo
var _t0=0;
function fmtTempo(s){ s=Math.max(0,Math.round(s)); var m=Math.floor(s/60); var r=s%60; return m?(m+"m "+("0"+r).slice(-2)+"s"):(r+"s"); }
function renderProgress(state, idxAtual, subMsg){
  // state[i]: 'ok' | 'falha' | 'fazendo' | 'aguardando'
  var feitos=state.filter(function(s){return s==="ok";}).length;
  var faltam=DOC_SPECS.length-feitos-state.filter(function(s){return s==="falha";}).length;
  var elapsed=_t0?( (Date.now()-_t0)/1000 ):0;
  // ETA: média por doc concluído × restantes
  var concluidos=feitos+state.filter(function(s){return s==="falha";}).length;
  var eta = concluidos? (elapsed/concluidos)*(DOC_SPECS.length-concluidos) : 0;
  var box=$("#progresso");
  var head='<div class="prog-head"><span class="prog-count">'+feitos+'/'+DOC_SPECS.length+' documentos</span>'
    +'<span class="prog-faltam">'+(faltam>0?("faltam "+faltam):"concluído")+'</span></div>'
    +'<div class="prog-bar"><div class="prog-fill" style="width:'+Math.round(feitos/DOC_SPECS.length*100)+'%"></div></div>'
    +'<div class="prog-tempo">decorrido '+fmtTempo(elapsed)+(eta>1?(' · restante ~'+fmtTempo(eta)):'')
    +' · '+(_tokensGeracao.entrada+_tokensGeracao.saida).toLocaleString('pt-BR')+' tokens'
    +' <span style="opacity:.65">('+_tokensGeracao.entrada.toLocaleString('pt-BR')+' entrada, '+_tokensGeracao.saida.toLocaleString('pt-BR')+' saída)</span></div>';
  var list='<ul class="prog-list">';
  for(var i=0;i<DOC_SPECS.length;i++){
    var st=state[i]||"aguardando", ic, cls;
    if(st==="ok"){ic="✓"; cls="ok";}
    else if(st==="falha"){ic="✕"; cls="falha";}
    else if(st==="fazendo"){ic='<span class="mini-spin"></span>'; cls="fazendo";}
    else {ic="·"; cls="wait";}
    list+='<li class="prog-item '+cls+'"><span class="pi-ic">'+ic+'</span>'
      +'<span class="pi-nome">'+DOC_SPECS[i].nome+'</span>'
      +(st==="fazendo"&&subMsg?('<span class="pi-sub">'+subMsg+'</span>'):'')+'</li>';
  }
  list+="</ul>";
  box.innerHTML=head+list; box.style.display="block";
}

// passo 2 (orquestra): gera os 9 documentos em sequência, com pausa entre eles
// gera 1 doc (índice i de DOC_SPECS), atualizando state/docs/falhas in-place.
// lança se for cota diária esgotada (sinaliza pra abortar o lote inteiro).
async function _gerarUm(i, spec, ctx, state, docs, falhas){
  state[i]="fazendo"; renderProgress(state,i,"iniciando…");
  try{
    docs[spec.slug]=await gerarDoc(spec, ctx, function(msg){ renderProgress(state, i, msg); });
    state[i]="ok";
  }catch(e){
    state[i]="falha";
    falhas.push({nome:spec.nome, motivo:e.message||"erro desconhecido"});
    if(/DIÁRIA/i.test(e.message)){ renderProgress(state,i,""); throw e; }
  }
  renderProgress(state,i,"");
}

// roda um lote de índices com concorrência limitada (evita estourar rate
// limit por minuto do provedor). Aborta o Promise.all se algum doc lançar
// (cota diária) — os demais em voo terminam, mas nenhum novo começa.
async function _gerarLote(indices, ctx, state, docs, falhas, concorrencia){
  var fila=indices.slice();
  async function worker(){
    while(fila.length){
      var i=fila.shift();
      await _gerarUm(i, DOC_SPECS[i], ctx, state, docs, falhas);
    }
  }
  var workers=[];
  for(var w=0; w<Math.min(concorrencia, indices.length); w++) workers.push(worker());
  await Promise.all(workers);
}

async function gerarTodos(ctx){
  var docs={}, falhas=[];
  var state=DOC_SPECS.map(function(){return "aguardando";});
  _t0=Date.now();
  _tokensGeracao={entrada:0, saida:0};
  renderProgress(state,-1,"");
  setStatus("");
  // certificado referencia semanticamente "os 7 documentos" — gerado por
  // último, depois que os demais (independentes entre si) já rodaram.
  var idxCertificado=DOC_SPECS.findIndex(function(s){return s.slug==="certificado";});
  var indicesIndependentes=DOC_SPECS.map(function(_,i){return i;}).filter(function(i){return i!==idxCertificado;});
  try{
    await _gerarLote(indicesIndependentes, ctx, state, docs, falhas, 3);
    if(idxCertificado>=0) await _gerarLote([idxCertificado], ctx, state, docs, falhas, 1);
  }catch(e){
    // cota diária esgotada — devolve parcial em vez de travar o usuário sem feedback
    throw Object.assign(new Error(e.message),{parcial:docs,falhas:falhas});
  }
  return {docs:docs, falhas:falhas};
}

function renderDados(d){
  var g=$("#dados"); g.innerHTML="";
  function escDados(s){return (s==null?"":(""+s)).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
  Object.keys(d).forEach(function(k){
    if(k==="clinica")return;
    var v=(d[k]||"").toString().trim()||"—";
    var cell=document.createElement("div");
    cell.innerHTML='<div class="k">'+escDados(k.replace(/_/g," "))+'</div><div class="v">'+escDados(v)+'</div>';
    g.appendChild(cell);
  });
  g.style.display="grid";
  window.__dados=d;
}

// dossie_clientes.dados (persistido e usado no preview/link real) precisa do
// shape PLANO (clinica/responsavel/cidade/...) que RENDER_JS lê pra
// preencher os placeholders — quando a origem é "form", window.__dados
// carrega o contexto rico pra revisão em tela (bom pra humano ler), não esse
// shape. Centraliza a escolha certa em um único lugar (salvar() e "Abrir
// dossiê" usavam o wrong shape do mesmo jeito antes desta correção).
function dadosParaPersistir(){
  return window.__ctxOrigem==="form" ? achatarDadosDeFormulario(window.__dadosFormOriginais||{}) : window.__dados;
}
async function salvar(documentos, forcar){
  var d=window.__dados; if(!d){return false;}
  // garante que a consulta de __versaoEsperada (disparada ao carregar o
  // cliente) já terminou antes de montar o payload — sem isso, clicar
  // "Salvar e finalizar" rápido demais poderia mandar p_versao_esperada
  // desatualizada e disparar um falso positivo de corrida.
  if(window.__versaoEsperadaPromise){ try{ await window.__versaoEsperadaPromise; }catch(e){} }
  var clinicaNome=(window.__dadosFormOriginais&&window.__dadosFormOriginais.empresa&&window.__dadosFormOriginais.empresa.nome)||d.clinica||"Sem nome";
  var dadosParaSalvar=dadosParaPersistir();
  var payload={
    p_clinica:clinicaNome, p_dados:dadosParaSalvar, p_documentos:documentos||{},
    p_respostas_brutas:$("#raw")?($("#raw").value||""):"",
    p_cliente_origem_id:window.__clienteOrigemId||null,
    // null na 1ª geração deste cliente. Se "forcar", envia undefined-como-null
    // de propósito (ignora a checagem) — usado quando o usuário confirma que
    // quer sobrescrever mesmo sabendo que outra aba já gerou por cima.
    p_versao_esperada:forcar?null:(window.__versaoEsperada||null)
  };
  if(forcar){
    // busca o created_at ATUAL antes de forçar, senão o forçar também colide
    // (a versão "esperada" continuaria desatualizada) — best effort: se
    // falhar, segue com null e deixa o servidor decidir de novo.
    try{
      var hh=window.AUTH_HEADERS();
      var rr=await fetch(SUPABASE_URL+"/rest/v1/rpc/get_clientes_auth",{method:"POST",headers:hh});
      var rows=rr.ok?await rr.json():[];
      var existente=(rows||[]).find(function(c){return c.cliente_origem_id===window.__clienteOrigemId;});
      payload.p_versao_esperada=existente?existente.created_at:null;
    }catch(e){}
  }
  // gerações longas (Claude, GPT-5-mini) passam facilmente de 1h — garante um
  // access_token válido (renova via refresh_token se preciso) antes de salvar.
  // salvar_dossie_auth faz upsert por cliente_origem_id: gerar de novo o
  // mesmo cliente atualiza a linha existente em vez de duplicar.
  var h=await window.AUTH_HEADERS_FRESH();
  var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/salvar_dossie_auth",{
    method:"POST", headers:h, body:JSON.stringify(payload)
  });
  if(r.status===401){
    // refresh_token também pode ter vencido (sessão muito antiga) — última
    // tentativa reautenticando de vez, em vez de só falhar com 401 cru.
    await window.ensureFreshSession();
    h=window.AUTH_HEADERS();
    r=await fetch(SUPABASE_URL+"/rest/v1/rpc/salvar_dossie_auth",{
      method:"POST", headers:h, body:JSON.stringify(payload)
    });
  }
  if(!r.ok){
    if(r.status===401) throw new Error("Sessão expirou. Clique em SAIR e entre novamente para salvar.");
    var corpoErro=await r.json().catch(function(){return{};});
    // 23503 = violação de FK: cliente_origem_id aponta pra um formulário que
    // já foi excluído do Banco de clientes (ex.: aba antiga reaberta depois
    // de excluir o formulário original) — mensagem específica em vez do
    // "Supabase recusou (409)" genérico.
    if(corpoErro.code==="23503") throw new Error("O formulário de origem deste cliente foi excluído do Banco de clientes. Recarregue a lista e comece a geração de novo a partir do cliente atual.");
    // P0002 = concurrent_generation: outra aba/pessoa já salvou uma geração
    // deste mesmo cliente depois que esta aba carregou — sinaliza pro
    // chamador (não é um erro genérico, precisa de decisão do usuário).
    if(corpoErro.code==="P0002"){ var eConc=new Error("concurrent_generation"); eConc.concurrent=true; throw eConc; }
    throw new Error("Supabase recusou ("+r.status+")"+(corpoErro.message?": "+corpoErro.message:"")+".");
  }
  var criado=await r.json();
  var clienteId=criado&&criado.id;
  window.__versaoEsperada=criado&&criado.created_at||null; // atualiza pra próxima chamada de salvar() nesta mesma aba
  // registra a versão no histórico (dossie_geracoes) — melhor-esforço: se
  // falhar, o dossiê já está salvo (documentos é o cache da versão atual),
  // só não fica no histórico dessa vez.
  if(clienteId){
    try{
      await fetch(SUPABASE_URL+"/rest/v1/rpc/criar_geracao_auth",{
        method:"POST", headers:window.AUTH_HEADERS(),
        body:JSON.stringify({p_cliente_id:clienteId, p_documentos:documentos||{}})
      });
    }catch(e){ /* histórico é best-effort, não bloqueia o fluxo principal */ }
  }
  return true;
}

// ---- fluxo vindo de "Gerar dossiê" no Banco de clientes (pula colar texto) ----
window.__ctxOrigem="texto";
window.__ctxPreCarregado=null;
window.__dadosFormOriginais=null;
window.__clienteOrigemId=null;
// created_at da geração já existente para este cliente (se houver) no
// momento em que esta aba carregou — enviado de volta em salvar() como
// "versão esperada", pra detectar se outra aba gerou por cima entre esse
// carregamento e este "Salvar e finalizar" (corrida entre abas).
window.__versaoEsperada=null;
(function(){
  var params=new URLSearchParams(location.search);
  var fromId=params.get("from");
  if(!fromId) return;
  var raw; try{ raw=JSON.parse(localStorage.getItem("dossie_para_gerar")||"null"); }catch(_){ raw=null; }
  if(!raw || raw.id!==fromId) return;
  window.__ctxOrigem="form";
  window.__clienteOrigemId=fromId;
  window.__dadosFormOriginais=raw.dados||{};
  window.__ctxPreCarregado=montarCtxDeFormulario(raw.dados||{}, raw.modelo||"clinica");
  $("#raw-card").style.display="none";
  $("#from-card").style.display="block";
  $("#from-nome").textContent=raw.clinica||"Cliente";
  var campos=Object.keys(window.__ctxPreCarregado).length;
  $("#from-resumo").textContent=campos+" campos carregados do formulário.";
  // best-effort: se falhar, __versaoEsperada fica null (mesmo comportamento
  // de "primeira geração") — não bloqueia o fluxo principal de gerar/salvar.
  // Guardada como promise (não só disparada) porque salvar() faz `await`
  // nela antes de montar o payload — sem isso, um "Salvar e finalizar"
  // clicado antes desta consulta terminar mandaria p_versao_esperada:null
  // mesmo já existindo uma linha, disparando um falso positivo de
  // "concurrent_generation" logo na primeira geração legítima do cliente.
  window.__versaoEsperadaPromise=window.AUTH_HEADERS_FRESH().then(function(h){
    return fetch(SUPABASE_URL+"/rest/v1/rpc/get_clientes_auth",{method:"POST",headers:h});
  }).then(function(r){ return r.ok?r.json():[]; }).then(function(rows){
    var existente=(rows||[]).find(function(c){return c.cliente_origem_id===fromId;});
    window.__versaoEsperada=existente?existente.created_at:null;
  }).catch(function(){});
})();

// ---- revisão pós-geração: lista os docs, permite editar (JSON) antes de salvar ----
window.__docsEditados={}; // slugs cujo conteúdo foi alterado manualmente na revisão
function escRevisao(s){return (s==null?"":(""+s)).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
function renderRevisao(docs, falhas){
  window.__docs=docs;
  var list=$("#revisao-list"); list.innerHTML="";
  DOC_SPECS.forEach(function(spec){
    var ok=!!docs[spec.slug];
    var falhaInfo=falhas.find(function(f){return f.nome===spec.nome;});
    var falhou=!!falhaInfo;
    var li=document.createElement("li");
    li.className="revisao-item";
    var metaTxt=falhou?("falhou na geração — "+falhaInfo.motivo):(window.__docsEditados[spec.slug]?"editado manualmente":"gerado");
    var metaCls=falhou?"falha":(window.__docsEditados[spec.slug]?"edited":"");
    li.innerHTML='<div><div class="ri-nome">'+spec.nome+'</div><div class="ri-meta '+metaCls+'">'+escRevisao(metaTxt)+'</div></div>';
    if(ok){
      var btn=document.createElement("button");
      btn.className="app-btn ghost"; btn.textContent="Editar";
      btn.addEventListener("click",function(){ abrirEdicao(spec); });
      li.appendChild(btn);
    }
    list.appendChild(li);
  });
  $("#revisao-card").style.display="block";
}

function abrirEdicao(spec){
  window.__editSlugAtual=spec.slug;
  $("#edit-titulo").textContent="Editar · "+spec.nome;
  $("#edit-json").value=JSON.stringify(window.__docs[spec.slug], null, 2);
  $("#edit-status").textContent=""; $("#edit-status").className="app-status";
  $("#edit-modal").style.display="flex";
}
function fecharEdicao(){ $("#edit-modal").style.display="none"; window.__editSlugAtual=null; }
$("#edit-close").addEventListener("click",fecharEdicao);
$("#edit-modal").addEventListener("click",function(e){ if(e.target===this) fecharEdicao(); });

$("#edit-salvar").addEventListener("click",function(){
  var slug=window.__editSlugAtual; if(!slug) return;
  var spec=DOC_SPECS.find(function(s){return s.slug===slug;});
  var parsed;
  try{ parsed=JSON.parse($("#edit-json").value); }
  catch(e){ $("#edit-status").className="app-status err"; $("#edit-status").textContent="JSON inválido: "+e.message; return; }
  var defeito=validarDoc(spec, parsed);
  if(defeito){ $("#edit-status").className="app-status err"; $("#edit-status").textContent="Estrutura inválida: "+defeito; return; }
  window.__docs[slug]=parsed;
  window.__docsEditados[slug]=true;
  fecharEdicao();
  renderRevisao(window.__docs, []);
});

// fluxo completo: (interpretar OU usar formulário) -> gerar os 9 docs -> revisar -> salvar -> abrir dossiê
$("#interpretar").addEventListener("click",async function(){
  var d;
  if(window.__ctxOrigem==="form"){
    d=window.__ctxPreCarregado;
  }else{
    var t=$("#raw").value.trim();
    if(t.length<20){setStatus("Cole as respostas do formulário primeiro.","err");return;}
  }
  this.disabled=true;
  window.__docsEditados={};
  $("#revisao-card").style.display="none";
  $("#abrir").style.display="none";
  var docs={}, falhas=[];
  try{
    if(window.__ctxOrigem!=="form"){
      setStatus('<span class="spinner"></span> Interpretando o diagnóstico…');
      d=await interpretar(t);
    }
    renderDados(d);
    var res=await gerarTodos(d);
    docs=res.docs; falhas=res.falhas;
  }catch(e){
    if(e.parcial){ docs=e.parcial; falhas=e.falhas||[]; }
    else { setStatus(e.message,"err"); this.disabled=false; return; }
  }
  var n=Object.keys(docs).length;
  var tokensTxt=(_tokensGeracao.entrada+_tokensGeracao.saida).toLocaleString('pt-BR')+" tokens ("
    +_tokensGeracao.entrada.toLocaleString('pt-BR')+" entrada, "+_tokensGeracao.saida.toLocaleString('pt-BR')+" saída)";
  if(falhas.length){
    var motivosUnicos=falhas.map(function(f){return f.motivo;}).filter(function(m,i,arr){return arr.indexOf(m)===i;});
    var detalheFalhas=motivosUnicos.length===1
      ? (falhas.map(function(f){return f.nome;}).join(", ")+" — "+motivosUnicos[0])
      : falhas.map(function(f){return f.nome+" ("+f.motivo+")";}).join("; ");
    setStatus("Gerados "+n+"/"+DOC_SPECS.length+". Faltaram: "+detalheFalhas+". Revise abaixo — você pode salvar assim mesmo e completar depois. · "+tokensTxt,"");
  }else{
    setStatus("Documentos gerados. Revise abaixo antes de salvar. · "+tokensTxt,"");
  }
  renderRevisao(docs, falhas);
  this.disabled=false;
});

$("#salvar-final").addEventListener("click",async function(){
  if(!window.__docs){return;}
  this.disabled=true;
  try{
    await salvar(window.__docs);
    var n=Object.keys(window.__docs).length;
    setStatus("Dossiê salvo ✓ ("+n+" documentos"+(Object.keys(window.__docsEditados).length?", "+Object.keys(window.__docsEditados).length+" editados manualmente":"")+").","ok");
    $("#abrir").style.display="inline-flex";
  }catch(e){
    if(e.concurrent){
      // outra aba/pessoa já salvou uma geração deste cliente enquanto esta
      // aba estava gerando — pergunta antes de sobrescrever, em vez de
      // fazer "last write wins" silencioso (o bug original desta correção).
      var querForcar=confirm("Outra pessoa (ou outra aba) já salvou uma geração mais recente deste cliente enquanto você gerava a sua.\n\nClique OK para SOBRESCREVER com a versão que você acabou de gerar, ou Cancelar para descartar a sua e manter a mais recente já salva.\n\nAmbas as versões ficam preservadas no histórico de gerações do cliente.");
      if(querForcar){
        try{
          await salvar(window.__docs, true);
          var n2=Object.keys(window.__docs).length;
          setStatus("Dossiê salvo ✓, sobrescrevendo a geração concorrente ("+n2+" documentos).","ok");
          $("#abrir").style.display="inline-flex";
        }catch(e2){ setStatus("Falha ao salvar: "+e2.message,"err"); }
      }else{
        setStatus("Não salvo — mantida a versão mais recente já salva por outra geração.","");
      }
    }
    else { setStatus("Falha ao salvar: "+e.message,"err"); }
  }
  this.disabled=false;
});

// abre o dossiê recém-gerado (guarda no localStorage e vai pra capa)
$("#abrir").addEventListener("click",function(){
  if(!window.__docs) return;
  // rev muda a cada "Abrir dossiê" — permite ao RENDER_JS avisar se uma aba
  // antiga (preview de outro cliente gerado antes) foi recarregada depois
  // que esta chave global foi sobrescrita por outra geração.
  localStorage.setItem("dossie_atual", JSON.stringify({dados:dadosParaPersistir(), documentos:window.__docs, rev:Date.now()}));
  location.href="index.html";
});

refreshConn();

// "Gerar" mexe com chaves de IA e geração dos documentos — só admin.
// vendedor é redirecionado para o Banco de clientes, que é o escopo dele.
window.onAuthReady=function(){
  if(window.MEU_PAPEL==="vendedor"){ location.href="clientes.html"; }
};
</script>
"""
    )


def _check_sec_labels_sync(sec_labels_dict):
    # Alerta (não bloqueia o build) se um campo existir em SECOES (gen_form.py)
    # mas faltar em sec_labels aqui — evita que um campo novo do formulário
    # suma silenciosamente da tela "Ver respostas" do painel por esquecimento
    # de espelhar. Ignora "itens" (bloco de ofertas, renderizado à parte).
    try:
        import gen_form
        for secao in gen_form.SECOES:
            sid = secao["id"]
            labels_campos = sec_labels_dict.get(sid, {}).get("campos", {})
            for campo in secao["campos"]:
                key, tipo = campo[0], campo[2]
                if key == "itens" or tipo == "nota":
                    continue
                if key not in labels_campos:
                    print(f"AVISO: campo '{key}' da seção '{sid}' (gen_form.SECOES) "
                          f"não está em sec_labels (gen_app._clientes_js) — vai faltar "
                          f"na tela 'Ver respostas' do painel.")
    except Exception as e:
        print(f"AVISO: não foi possível checar sincronia SECOES/sec_labels: {e}")


def _clientes_js():
    # rótulos das seções do formulário do cliente (para a leitura organizada)
    _sec_labels_dict = {
        "empresa": {"num": "01", "titulo": "Empresa", "campos": {
            "nome": "Nome da empresa", "cnpj": "CNPJ", "responsavel": "Responsável", "cargoResponsavel": "Quem responde",
            "email": "E-mail", "whatsapp": "WhatsApp", "segmento": "Segmento", "cidade": "Cidade",
            "estado": "Estado", "cep": "CEP", "cidadesAlcance": "Cidades a alcançar",
            "fundacao": "Ano de fundação", "colaboradores": "Colaboradores", "horario": "Horário",
            "historia": "História"}},
        "posicionamento": {"num": "02", "titulo": "Posicionamento", "campos": {
            "nivelPreco": "Posição de preço", "melhorQueConcorrencia": "Melhor que os concorrentes",
            "transformacao": "Transformação entregue", "porqueEscolher": "Por que escolhem",
            "promessa": "Promessa", "diferenciais": "Diferenciais", "valores": "Valores",
            "reputacao": "Reputação na região"}},
        "publico": {"num": "03", "titulo": "Público", "campos": {
            "faixaEtaria": "Faixa etária", "sexo": "Sexo predominante", "classe": "Classe social",
            "clienteIdeal": "Perfil ideal", "dores": "Dores", "desejos": "Desejos",
            "objecoes": "Objeções", "motivoCompra": "Motivo de compra",
            "origemPredominante": "Origem predominante"}},
        "oferta": {"num": "04", "titulo": "Oferta", "campos": {
            "servicoCarroChefe": "Carro-chefe", "servicoMaisVender": "Serviço que mais quer vender",
            "maisLucro": "Mais lucro", "maisRecorrencia": "Mais recorrência",
            "temEntrada": "Oferta de entrada", "recorrenciaModelo": "Modelo de recorrência",
            "focoNoventaDias": "Foco 90 dias"}},
        "comercial": {"num": "05", "titulo": "Comercial", "campos": {
            "quemAtende": "Quem atende", "qtdVendedores": "Qtd. vendedores", "crm": "CRM",
            "followUp": "Follow-up", "tempoResposta": "Tempo de resposta", "leadsMes": "Leads/mês",
            "agendamentosMes": "Agendamentos/mês", "comparecimentosMes": "Comparecimentos/mês",
            "vendasMes": "Vendas/mês", "taxaConversao": "Taxa de conversão", "noShow": "No-show",
            "objecoesComerciais": "Objeções comerciais", "comoChega": "Como chega",
            "processo": "Processo comercial"}},
        "marketing": {"num": "06", "titulo": "Marketing", "campos": {
            "instagram": "Instagram", "leadsDia": "Leads/dia", "gmn": "Google Meu Negócio",
            "site": "Site", "volumeClientes": "Clientes/mês", "baseContatosTotal": "Base — contatos",
            "baseClientesAtivos": "Base — ativos", "quantoInveste": "Investimento/mês", "canais": "Canais",
            "canalMaisLeads": "Canal + leads", "canalMaisFaturamento": "Canal + faturamento",
            "indicacaoForte": "Programa de indicação", "funcionou": "Funcionou",
            "naoFuncionou": "Não funcionou", "agencia": "Já teve agência", "naoGostou": "Não gostou",
            "conteudo": "Produz conteúdo", "fazReativacao": "Reativação", "vendeNovamente": "Revende p/ base",
            "principalConcorrente": "Concorrente", "dispostoGravar": "Disposto a gravar",
            "dispostoRedeAtiva": "Manter rede ativa", "mktObservacoes": "Observações"}},
        "crescimento": {"num": "07", "titulo": "Crescimento", "campos": {
            "faturamento": "Faturamento atual", "ticketMedio": "Ticket médio", "meta6m": "Meta 6 meses",
            "meta12m": "Meta 12 meses", "qtdClientes": "Qtd. desejada", "investirMkt": "Investir em mkt",
            "capacidadeMax": "Capacidade ociosa", "fila": "Fila de espera", "sazonalidade": "Sazonalidade",
            "melhoresMeses": "Melhores meses", "pioresMeses": "Piores meses",
            "objetivoPrincipal": "Objetivo principal", "impedeMeta": "O que impede a meta",
            "sucesso": "Definição de sucesso"}},
        "comunicacao": {"num": "08", "titulo": "Comunicação & Marca", "campos": {
            "tomVoz": "Tom de voz", "tomVozObs": "Tom de voz (detalhe)", "tratamento": "Tratamento",
            "restricoesCompliance": "Restrições / compliance", "quemAparece": "Quem aparece",
            "provaSocial": "Prova social", "provaSocialObs": "Prova social (detalhe)",
            "ameacasExternas": "Ameaças externas", "referenciasAdmira": "Referências que admira"}},
    }
    _check_sec_labels_sync(_sec_labels_dict)
    sec_labels = _json.dumps(_sec_labels_dict, ensure_ascii=False)
    return (_auth_gate_js() + r"""
<script>
const SUPABASE_URL=""" + f'"{SUPABASE_URL}"' + r""", SUPABASE_ANON=""" + f'"{SUPABASE_ANON}"' + r""";
const SEC=""" + sec_labels + r""";
const SEC_ORDER=["empresa","posicionamento","publico","oferta","comercial","marketing","crescimento","comunicacao"];
const $=s=>document.querySelector(s);
function esc(s){return (s==null?"":(""+s)).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
function formLink(id,tipo){return location.origin+location.pathname.replace(/[^/]*$/,"")+"dossie.html?c="+id+"&t="+(tipo||"clinica");}
// código de acesso: nome da empresa (normalizado, sem acento/espaço) + mês/ano atual.
// ex. "Lumi Estética" em julho/2026 -> "LUMI0726". Fácil de comunicar por telefone/WhatsApp.
function codigoDeAcesso(nomeEmpresa){
  var base=(nomeEmpresa||"").normalize("NFD").replace(/[̀-ͯ]/g,"") // remove acentos
    .toUpperCase().replace(/[^A-Z0-9]/g,""); // só letras/números
  base=(base||"CLIENTE").slice(0,10);
  var d=new Date();
  var mm=("0"+(d.getMonth()+1)).slice(-2), yy=(""+d.getFullYear()).slice(-2);
  return base+mm+yy;
}
var TIPOS_META={
  clinica:{rotulo:"Clínica",desc:"Negócios que atendem pacientes."},
  servicos:{rotulo:"Serviços",desc:"Negócios que vendem conhecimento ou execução."},
  produtos:{rotulo:"Produtos",desc:"Negócios que vendem produtos físicos ou digitais."}
};

// ---------- novo cliente: modal (Nome + Tipo de dossiê + Forma de preenchimento) ----------
function novoCliente(){
  var tipo="clinica", forma="enviar";
  var m=document.createElement("div"); m.className="nc-modal";
  function cards(obj,sel,attr){
    return Object.keys(obj).map(function(k){
      var o=obj[k], on=(k===sel)?" on":"";
      return '<button type="button" class="nc-card'+on+'" data-'+attr+'="'+k+'">'
        +'<div class="nc-card-t">'+esc(o.rotulo||o.t)+'</div>'
        +'<div class="nc-card-d">'+esc(o.desc||o.d)+'</div></button>';
    }).join("");
  }
  var formas={enviar:{t:"Enviar dossiê ao cliente",d:"O sistema gera o link de preenchimento."},
              interno:{t:"Preencher internamente",d:"A equipe Noeds responderá."}};
  m.innerHTML='<div class="nc-in">'
    +'<button class="nc-x" id="nc-x">✕</button>'
    +'<h2 class="nc-h">Novo cliente</h2>'
    +'<p class="nc-sub">Apenas o essencial. Demais dados serão coletados no dossiê.</p>'
    +'<label class="nc-label">Nome da empresa</label>'
    +'<input class="nc-input" id="nc-nome" placeholder="Ex.: Lumi" autocomplete="off">'
    +'<label class="nc-label">Tipo de dossiê</label>'
    +'<div class="nc-cards nc-3" id="nc-tipos">'+cards(TIPOS_META,tipo,"tipo")+'</div>'
    +'<p class="nc-hint">Define toda a experiência: formulário, vocabulário e exemplos. Termos como '
    +'<b>pacientes</b>, <b>procedimentos</b> e <b>procedimentos vendidos</b> são aplicados automaticamente.</p>'
    +'<label class="nc-label">Forma de preenchimento</label>'
    +'<div class="nc-cards nc-2" id="nc-formas">'+cards(formas,forma,"forma")+'</div>'
    +'<div class="nc-status" id="nc-status"></div>'
    +'<button class="app-btn nc-go" id="nc-go">Criar cliente</button>'
    +'</div>';
  document.body.appendChild(m);
  function close(){ m.remove(); }
  m.querySelector("#nc-x").onclick=close;
  m.addEventListener("click",function(e){ if(e.target===m) close(); });
  document.addEventListener("keydown",function esc0(e){ if(e.key==="Escape"){close();document.removeEventListener("keydown",esc0);} });
  m.querySelector("#nc-tipos").addEventListener("click",function(e){
    var b=e.target.closest("[data-tipo]"); if(!b)return; tipo=b.dataset.tipo;
    this.querySelectorAll(".nc-card").forEach(function(c){c.classList.toggle("on",c===b);});
    // atualizar o hint com o vocabulário do tipo
    var voc={clinica:["pacientes","procedimentos","procedimentos vendidos"],
             servicos:["clientes","serviços","contratos"],
             produtos:["compradores","produtos","pedidos"]}[tipo];
    m.querySelector(".nc-hint").innerHTML='Define toda a experiência: formulário, vocabulário e exemplos. Termos como '
      +'<b>'+voc[0]+'</b>, <b>'+voc[1]+'</b> e <b>'+voc[2]+'</b> são aplicados automaticamente.';
  });
  m.querySelector("#nc-formas").addEventListener("click",function(e){
    var b=e.target.closest("[data-forma]"); if(!b)return; forma=b.dataset.forma;
    this.querySelectorAll(".nc-card").forEach(function(c){c.classList.toggle("on",c===b);});
  });
  m.querySelector("#nc-go").onclick=async function(){
    var nome=(m.querySelector("#nc-nome").value||"").trim();
    var st=m.querySelector("#nc-status"); var btn=this;
    if(!nome){ st.className="nc-status err"; st.textContent="Informe o nome da empresa."; m.querySelector("#nc-nome").focus(); return; }
    var id="dossie-"+Math.random().toString(36).slice(2,10)+"-"+Math.random().toString(36).slice(2,7);
    var codigo=codigoDeAcesso(nome); // nome da empresa + mês/ano, ex. "LUMI0726"
    btn.disabled=true; st.className="nc-status"; st.textContent="Criando…";
    try{
      var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/upsert_resposta",{method:"POST",
        headers:{apikey:SUPABASE_ANON,Authorization:"Bearer "+SUPABASE_ANON,"Content-Type":"application/json"},
        body:JSON.stringify({rid:id,p_clinica:nome,p_responsavel:"",p_status:"nao-iniciado",p_progresso:0,p_dados:{},p_modelo:tipo,p_access_code:codigo})});
      if(!r.ok)throw new Error("Falha ao criar ("+r.status+").");
      var link=formLink(id,tipo);
      if(forma==="interno"){
        close(); carregar();
        location.href=link+"&equipe=1&cod="+encodeURIComponent(codigo);   // abre o formulário direto pra equipe
        return;
      }
      close(); carregar();
      mostrarClienteCriado(nome, link, codigo, TIPOS_META[tipo].rotulo);
    }catch(e){ btn.disabled=false; st.className="nc-status err"; st.textContent=e.message; }
  };
  m.querySelector("#nc-nome").focus();
}

// modal "Cliente criado": link + código com botão de copiar em cada linha,
// mais um botão que copia tudo já formatado pra colar direto no WhatsApp.
function mostrarClienteCriado(nome, link, codigo, rotulo){
  var mensagem="Olá! Aqui está o link para preencher o seu diagnóstico:\n"+link
    +"\n\nCódigo de acesso: "+codigo;
  var m=document.createElement("div");
  m.className="nc-modal";
  m.innerHTML=
    '<div class="nc-in">'
    +'<button class="nc-x" id="cc-x">×</button>'
    +'<h2 class="nc-h">Cliente criado</h2>'
    +'<p class="nc-sub">'+esc(nome)+' · '+esc(rotulo)+'. Envie o link e o código para o cliente preencher o dossiê.</p>'
    +'<div class="cc-item"><label class="nc-label" style="margin:0">Link do formulário</label>'
    +'<div class="cc-row"><span class="cc-val">'+esc(link)+'</span><button class="cc-copy" data-copy="link">Copiar</button></div></div>'
    +'<div class="cc-item"><label class="nc-label" style="margin:0">Código de acesso</label>'
    +'<div class="cc-row"><span class="cc-val">'+esc(codigo)+'</span><button class="cc-copy" data-copy="codigo">Copiar</button></div></div>'
    +'<button class="app-btn cc-msg" id="cc-msg">Copiar mensagem pronta p/ WhatsApp</button>'
    +'</div>';
  document.body.appendChild(m);
  function close(){ m.remove(); }
  m.querySelector("#cc-x").onclick=close;
  m.addEventListener("click",function(e){ if(e.target===m) close(); });
  function copiarBtn(btn, texto){
    navigator.clipboard.writeText(texto).then(function(){
      var original=btn.textContent;
      btn.textContent="Copiado ✓"; btn.classList.add("copied");
      setTimeout(function(){ btn.textContent=original; btn.classList.remove("copied"); },1600);
    }).catch(function(){});
  }
  m.querySelectorAll(".cc-copy").forEach(function(btn){
    btn.onclick=function(){ copiarBtn(btn, btn.dataset.copy==="link"?link:codigo); };
  });
  m.querySelector("#cc-msg").onclick=function(){ copiarBtn(this, mensagem); };
}

// ---------- listar respostas de formulário ----------
function gerarDossieDe(c){
  localStorage.setItem("dossie_para_gerar", JSON.stringify({id:c.id, clinica:c.clinica||"", dados:c.dados||{}, modelo:c.modelo||"clinica"}));
  location.href="gerar.html?from="+encodeURIComponent(c.id);
}

async function carregar(){
  var box=$("#lista"); box.innerHTML='<div class="app-status"><span class="spinner"></span> Carregando…</div>';
  try{
    var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/get_respostas_auth",{
      method:"POST", headers:await window.AUTH_HEADERS_FRESH()
    });
    if(!r.ok){throw new Error("Não foi possível ler ("+r.status+").");}
    var rows=await r.json();
    if(!Array.isArray(rows)){throw new Error((rows&&rows.message)?rows.message:"Resposta inesperada do banco.");}
    if(!rows.length){box.innerHTML='<div class="app-status">Nenhum cliente ainda. Clique em “Novo cliente” para gerar um link e enviar ao cliente.</div>';return;}
    box.innerHTML="";
    rows.forEach(function(c){
      var dt=(c.atualizado_em||c.created_at||"").slice(0,10);
      var stMap={"nao-iniciado":"Não iniciado","andamento":"Em preenchimento","concluido":"Concluído"};
      var stTxt=stMap[c.status]||c.status||"—";
      var row=document.createElement("div"); row.className="client-row";
      var tipoMeta=TIPOS_META[c.modelo]||TIPOS_META.clinica;
      var info=document.createElement("div");
      info.innerHTML='<div class="nm">'+esc(c.clinica||"Sem nome")+' <span class="tipo-badge">'+esc(tipoMeta.rotulo)+'</span></div>'
        +'<div class="meta">'+[stTxt+" · "+(c.progresso||0)+"%", c.responsavel, dt].filter(Boolean).map(esc).join(" · ")+'</div>';
      var acts=document.createElement("div"); acts.className="client-acts";
      var bVer=document.createElement("button"); bVer.className="app-btn"; bVer.textContent="Ver respostas";
      bVer.disabled=!(c.progresso>0);
      bVer.addEventListener("click",function(){ verRespostas(c); });
      var bLink=document.createElement("button"); bLink.className="app-btn ghost"; bLink.textContent="Copiar link";
      bLink.addEventListener("click",function(){
        var t=formLink(c.id,c.modelo)+"  ·  código: "+(c.access_code||"(sem código — registro antigo)");
        navigator.clipboard.writeText(t).then(function(){bLink.textContent="Copiado!";setTimeout(function(){bLink.textContent="Copiar link";},1500);});
      });
      var bGerar=document.createElement("button"); bGerar.className="app-btn"; bGerar.textContent="Gerar dossiê";
      bGerar.disabled=!(c.progresso>0);
      bGerar.addEventListener("click",function(){ gerarDossieDe(c); });
      acts.appendChild(bVer); acts.appendChild(bLink); acts.appendChild(bGerar);
      // registro legado (criado antes do código de acesso por cliente existir)
      // fica sem access_code — o formulário dele não abre nem salva mais
      // (bloqueado no servidor até ter um código). Botão só aparece nesse caso.
      if(!c.access_code && window.MEU_PAPEL!=="vendedor"){
        var bCod=document.createElement("button"); bCod.className="app-btn ghost"; bCod.textContent="Gerar código";
        bCod.title="Este cliente é antigo e não tem código de acesso — gere um para o link voltar a funcionar.";
        bCod.addEventListener("click",async function(){
          var novo=codigoDeAcesso(c.clinica||"cliente");
          bCod.disabled=true;
          try{
            var h=await window.AUTH_HEADERS_FRESH();
            var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/regenerar_access_code_auth",{method:"POST",headers:h,
              body:JSON.stringify({rid:c.id, novo_codigo:novo})});
            if(!r.ok) throw new Error("Falha ao gerar código ("+r.status+").");
            c.access_code=novo;
            carregar();
          }catch(e){ bCod.disabled=false; alert(e.message); }
        });
        acts.appendChild(bCod);
      }
      if(window.MEU_PAPEL!=="vendedor"){
        var bDel=document.createElement("button"); bDel.className="app-btn-x"; bDel.textContent="✕";
        bDel.title="Excluir formulário"; bDel.setAttribute("aria-label","Excluir formulário");
        bDel.addEventListener("click",function(){ confirmarExcluir(c); });
        acts.appendChild(bDel);
      }
      row.appendChild(info); row.appendChild(acts);
      box.appendChild(row);
    });
  }catch(e){box.innerHTML='<div class="app-status err">'+e.message+'</div>';}
}

// ---------- excluir formulário (com confirmação) ----------
function confirmarExcluir(c){
  confirmarExclusao({
    nome: c.clinica||"este cliente",
    eyebrow: "Excluir formulário",
    aviso: "Esta ação remove o formulário e todas as respostas deste cliente do banco. Não é possível desfazer.",
    rpc: "delete_resposta_auth", body: {rid:c.id}, aoConcluir: carregar
  });
}
// ---------- excluir dossiê gerado (com confirmação) ----------
function confirmarExcluirDossie(c){
  confirmarExclusao({
    nome: c.clinica||"este cliente",
    eyebrow: "Excluir dossiê gerado",
    aviso: "Esta ação remove o dossiê gerado (documentos, histórico de versões e link de compartilhamento, se houver) deste cliente. Não é possível desfazer.",
    rpc: "delete_cliente_auth", body: {cid:c.id}, aoConcluir: carregarDossies
  });
}
function confirmarExclusao(opts){
  var m=document.createElement("div"); m.className="confirm-modal";
  m.innerHTML='<div class="confirm-in">'
    +'<div class="app-eyebrow">'+esc(opts.eyebrow)+'</div>'
    +'<h3 class="confirm-h">Excluir “'+esc(opts.nome)+'”?</h3>'
    +'<p class="confirm-txt">'+esc(opts.aviso)+'</p>'
    +'<div class="confirm-acts">'
    +'<button class="app-btn ghost" id="cf-cancel">Cancelar</button>'
    +'<button class="app-btn danger" id="cf-ok">Sim, excluir</button>'
    +'</div><div class="confirm-status" id="cf-status"></div></div>';
  document.body.appendChild(m);
  function close(){ m.remove(); }
  m.querySelector("#cf-cancel").onclick=close;
  m.addEventListener("click",function(e){ if(e.target===m) close(); });
  document.addEventListener("keydown",function esc0(e){ if(e.key==="Escape"){close();document.removeEventListener("keydown",esc0);} });
  m.querySelector("#cf-ok").onclick=async function(){
    var st=m.querySelector("#cf-status"); var btn=this;
    btn.disabled=true; m.querySelector("#cf-cancel").disabled=true;
    st.textContent="Excluindo…";
    try{
      var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/"+opts.rpc,{method:"POST",
        headers:await window.AUTH_HEADERS_FRESH(),
        body:JSON.stringify(opts.body)});
      if(!r.ok)throw new Error("Falha ao excluir ("+r.status+").");
      close();
      opts.aoConcluir();
    }catch(e){ st.className="confirm-status err"; st.textContent=e.message;
      btn.disabled=false; m.querySelector("#cf-cancel").disabled=false; }
  };
}

// ---------- modal de leitura organizada por seção (formulário OU dossiê gerado) ----------
function ehFormatoSecoes(dados){
  return SEC_ORDER.some(function(sid){ return dados&&typeof dados[sid]==="object"&&dados[sid]!==null; });
}
function renderRespostasModal(clinica,dados){
  var d=dados||{};
  var texto="Cliente: "+(clinica||"Cliente")+"\n";
  var h='<div class="resp-modal-in"><button class="resp-close" id="resp-close">✕</button>'
    +'<button class="resp-close" id="resp-copiar" style="right:56px;font-size:13px;width:auto;padding:0 14px">Copiar respostas</button>'
    +'<div class="app-eyebrow">Respostas do cliente</div>'
    +'<h2 class="app-h1" style="margin-top:12px;font-size:36px">'+esc(clinica||"Cliente")+'</h2>';
  if(ehFormatoSecoes(d)){
    SEC_ORDER.forEach(function(sid){
      var meta=SEC[sid]; if(!meta)return;
      var vals=d[sid]||{};
      var rowsHtml="";
      var rowsTxt="";
      // ofertas (bloco especial)
      if(sid==="oferta"&&Array.isArray(vals.itens)&&vals.itens.length){
        vals.itens.forEach(function(it,i){
          if(!it||!(it.nome||it.ticket))return;
          var linha=(it.nome||"—")+(it.ticket?(" · ticket R$ "+it.ticket):"")
            +(it.margem?(" · margem "+it.margem):"")+(it.volume?(" · "+it.volume+"/mês"):"");
          rowsHtml+='<div class="resp-row"><div class="resp-k">Oferta '+(i+1)+'</div><div class="resp-v">'+esc(linha)+'</div></div>';
          rowsTxt+="Oferta "+(i+1)+": "+linha+"\n";
        });
      }
      Object.keys(meta.campos).forEach(function(fk){
        var v=vals[fk]; if(v==null||(""+v).trim()==="")return;
        rowsHtml+='<div class="resp-row"><div class="resp-k">'+esc(meta.campos[fk])+'</div><div class="resp-v">'+esc(v)+'</div></div>';
        rowsTxt+=meta.campos[fk]+": "+v+"\n";
      });
      if(!rowsHtml)rowsHtml='<div class="resp-empty">— sem respostas nesta seção —</div>';
      h+='<div class="resp-sec"><div class="resp-sec-h"><span class="resp-num">'+meta.num+'</span> '+esc(meta.titulo)+'</div>'+rowsHtml+'</div>';
      if(rowsTxt)texto+="\n"+meta.titulo.toUpperCase()+"\n"+rowsTxt;
    });
  }else{
    var rowsHtml="";
    Object.keys(d).forEach(function(k){
      if(k==="clinica")return;
      var v=d[k]; if(v==null||(""+v).trim()==="")return;
      rowsHtml+='<div class="resp-row"><div class="resp-k">'+esc(k.replace(/_/g," "))+'</div><div class="resp-v">'+esc(v)+'</div></div>';
      texto+=k.replace(/_/g," ")+": "+v+"\n";
    });
    h+='<div class="resp-sec">'+(rowsHtml||'<div class="resp-empty">— sem dados —</div>')+'</div>';
  }
  h+='</div>';
  var m=document.createElement("div"); m.className="resp-modal"; m.innerHTML=h;
  document.body.appendChild(m);
  m.querySelector("#resp-close").onclick=function(){m.remove();};
  m.addEventListener("click",function(e){if(e.target===m)m.remove();});
  var btnCopiar=m.querySelector("#resp-copiar");
  btnCopiar.onclick=function(){
    navigator.clipboard.writeText(texto.trim()).then(function(){
      var original=btnCopiar.textContent;
      btnCopiar.textContent="Copiado ✓";
      setTimeout(function(){ btnCopiar.textContent=original; },1600);
    }).catch(function(){});
  };
}
function verRespostas(c){ renderRespostasModal(c.clinica, c.dados); }

// ---------- compartilhamento exclusivo por cliente (dossiê gerado) ----------
async function setShareToken(clienteId, token){
  var h=await window.AUTH_HEADERS_FRESH(); h["Prefer"]="return=minimal";
  return fetch(SUPABASE_URL+"/rest/v1/rpc/set_share_token_auth",{
    method:"POST", headers:h,
    body:JSON.stringify({cliente_id:clienteId, novo_token:token})});
}
function slugify(s){
  return (s||"").normalize("NFD").replace(/[̀-ͯ]/g,"")
    .toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"").slice(0,16).replace(/-+$/,"");
}
function textoCompartilhar(c, link){
  return (c.clinica?c.clinica+" - ":"")+"Noeds: "+link;
}
function linkCompartilhado(token){
  return location.origin+location.pathname.replace(/[^/]*$/,"")+"?share="+token;
}
async function compartilhar(c, btn){
  if(c.share_token){
    var link=linkCompartilhado(c.share_token);
    var acao=confirm("Link já ativo:\n"+link+"\n\nOK = copiar de novo · Cancelar = revogar acesso");
    if(acao){ try{await navigator.clipboard.writeText(textoCompartilhar(c, link));}catch(e){} alert("Copiado."); }
    else { await revogar(c, btn); }
    return;
  }
  var rand=(crypto.randomUUID?crypto.randomUUID():(Date.now().toString(36)+Math.random().toString(36).slice(2)))
    .replace(/-/g,"").slice(0,12);
  var slug=slugify(c.clinica);
  var token=(slug?slug+"-":"")+rand;
  var r=await setShareToken(c.id, token);
  if(!r.ok){ alert("Falha ao gerar link ("+r.status+")."); return; }
  c.share_token=token;
  if(btn) btn.textContent="Gerenciar link";
  var link=linkCompartilhado(token);
  try{await navigator.clipboard.writeText(textoCompartilhar(c, link));}catch(e){}
  alert("Link exclusivo do cliente:\n"+link+"\n\n(Copiado para a área de transferência.)");
}
async function revogar(c, btn){
  var r=await setShareToken(c.id, null);
  if(!r.ok){ alert("Falha ao revogar ("+r.status+")."); return; }
  c.share_token=null;
  if(btn) btn.textContent="Compartilhar";
  alert("Acesso revogado.");
}

// ---------- listagem de dossiês já gerados (dossie_clientes) ----------
async function carregarDossies(){
  var box=$("#lista-dossies"); box.innerHTML='<div class="app-status"><span class="spinner"></span> Carregando…</div>';
  try{
    var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/get_clientes_auth",{
      method:"POST", headers:await window.AUTH_HEADERS_FRESH()
    });
    if(!r.ok){throw new Error("Não foi possível ler ("+r.status+").");}
    var rows=await r.json();
    if(!Array.isArray(rows)){throw new Error((rows&&rows.message)?rows.message:"Resposta inesperada do banco.");}
    if(!rows.length){box.innerHTML='<div class="app-status">Nenhum dossiê gerado ainda.</div>';return;}
    box.innerHTML="";
    rows.forEach(function(c){
      var nDocs=Object.keys(c.documentos||{}).length;
      var row=document.createElement("div"); row.className="client-row";
      var info=document.createElement("div");
      info.innerHTML='<div class="nm">'+esc(c.clinica||"Sem nome")+'</div>'
        +'<div class="meta">'+esc(nDocs+" documentos")+'</div>';
      var acts=document.createElement("div"); acts.className="client-acts";
      var bDados=document.createElement("button"); bDados.className="app-btn ghost"; bDados.textContent="Ver dados";
      bDados.addEventListener("click",function(){ renderRespostasModal(c.clinica, c.dados); });
      acts.appendChild(bDados);
      if(window.MEU_PAPEL!=="vendedor"){
        var bShare=document.createElement("button"); bShare.className="app-btn ghost";
        bShare.textContent=c.share_token?"Gerenciar link":"Compartilhar";
        bShare.addEventListener("click",function(){ compartilhar(c, bShare); });
        acts.appendChild(bShare);
        var bDelDossie=document.createElement("button"); bDelDossie.className="app-btn-x"; bDelDossie.textContent="✕";
        bDelDossie.title="Excluir dossiê gerado"; bDelDossie.setAttribute("aria-label","Excluir dossiê gerado");
        bDelDossie.addEventListener("click",function(){ confirmarExcluirDossie(c); });
        acts.appendChild(bDelDossie);
      }
      row.appendChild(info); row.appendChild(acts);
      box.appendChild(row);
    });
  }catch(e){box.innerHTML='<div class="app-status err">'+e.message+'</div>';}
}

$("#btn-novo")&&($("#btn-novo").onclick=novoCliente);
window.onAuthReady=function(){
  if(window.MEU_PAPEL==="vendedor"&&$("#btn-novo")) $("#btn-novo").style.display="none";
  carregar(); carregarDossies();
};
</script>
""")


def build(OUT, CSS, SIDEBAR_CSS, SIDEBAR_JS, sidebar_html, FONTS, PRINT_CSS, THEME_BOOT_JS=""):
    # ---- GERAR ----
    gerar_body = """
<p class="app-eyebrow">Ferramenta · Geração</p>
<h1 class="app-h1">Gerar dossiê</h1>
<p class="app-sub">Cole abaixo as respostas do formulário do cliente. A IA interpreta o texto,
estrutura os dados e prepara o dossiê personalizado. Revise antes de salvar.</p>

<div class="app-card conn-card">
  <div class="conn-head">
    <span id="conn-title" class="app-label" style="margin:0">Conexão · Google Gemini</span>
    <span id="conn-state" class="conn-off">Não conectado</span>
  </div>
  <div class="prov-tabs">
    <button class="prov-tab on" data-p="gemini">Gemini</button>
    <button class="prov-tab" data-p="openai">OpenAI</button>
    <button class="prov-tab" data-p="claude">Claude</button>
  </div>
  <p class="conn-hint">Escolha o provedor, conecte a chave dele e gere. A chave fica salva só neste
  navegador (não vai para o servidor). Pegue a sua em poucos segundos:</p>
  <a id="prov-link" class="app-btn ghost" href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener"
     style="margin-top:0">↗ Pegar chave no Google AI Studio</a>
  <div style="margin-top:16px; display:flex; gap:10px; flex-wrap:wrap; align-items:center">
    <input id="gkey" class="app-input" type="password" placeholder="Cole aqui sua chave do Gemini (AIza…)" style="flex:1; min-width:240px">
    <button id="salvar-key" class="app-btn" style="margin-top:0">Conectar</button>
  </div>
  <div class="model-row">
    <label class="app-label" for="model-sel" style="margin:0">Modelo</label>
    <select id="model-sel" class="app-input"></select>
  </div>
</div>

<div class="app-card" id="from-card" style="display:none">
  <p class="app-eyebrow">Origem · Formulário do cliente</p>
  <h2 class="app-h1" style="font-size:24px; margin-top:8px" id="from-nome"></h2>
  <p class="conn-hint" id="from-resumo"></p>
</div>

<div class="app-card" id="raw-card">
  <label class="app-label" for="raw">Respostas do formulário (texto livre)</label>
  <textarea id="raw" class="app-textarea" placeholder="Cole aqui as perguntas e respostas do cliente…"></textarea>
</div>

<div class="app-card">
  <label class="toggle-row" for="auto-revisao">
    <input id="auto-revisao" type="checkbox">
    <span class="toggle-sw"></span>
    <span class="toggle-txt">Auto-revisão por IA <span class="toggle-hint">(2ª passada corrigindo frases genéricas — dobra o custo de tokens, ~+1–2 min)</span></span>
  </label>
  <button id="interpretar" class="app-btn">Gerar dossiê completo</button>
  <p class="conn-hint" style="margin-top:14px">A IA lê o diagnóstico, gera os 9 documentos personalizados
  (um por vez, ~1–3 min) e salva o cliente. Mantenha esta aba aberta durante a geração.</p>
  <div id="status" class="app-status"></div>
  <div id="progresso" class="prog" style="display:none"></div>
  <div id="dados" class="app-grid" style="display:none"></div>
</div>

<div class="app-card" id="revisao-card" style="display:none">
  <p class="app-eyebrow">Revisão · Antes de salvar</p>
  <h2 class="app-h1" style="font-size:24px; margin-top:8px">Revisar documentos gerados</h2>
  <p class="conn-hint">Edite o que precisar antes de salvar — clique em um documento para abrir o conteúdo em JSON.
  A estrutura (nº de itens de cada lista) é validada automaticamente ao salvar a edição.</p>
  <ul id="revisao-list" class="revisao-list"></ul>
  <button id="salvar-final" class="app-btn">Salvar e finalizar</button>
  <button id="abrir" class="app-btn ghost" style="display:none">Abrir dossiê salvo →</button>
</div>

<div id="edit-modal" class="resp-modal" style="display:none">
  <div class="resp-modal-in edit-modal-in">
    <button class="resp-close" id="edit-close">×</button>
    <p class="app-eyebrow" id="edit-titulo">Documento</p>
    <textarea id="edit-json" class="app-textarea edit-json"></textarea>
    <div id="edit-status" class="app-status"></div>
    <button id="edit-salvar" class="app-btn">Salvar edição</button>
  </div>
</div>
"""
    (OUT / "gerar.html").write_text(
        _page("Gerar dossiê · Noeds", "gerar.html", gerar_body, CSS, SIDEBAR_CSS,
              SIDEBAR_JS, sidebar_html, FONTS, PRINT_CSS, extra_js=_gerar_js(), theme_boot_js=THEME_BOOT_JS),
        encoding="utf-8",
    )

    # ---- CLIENTES ----
    clientes_body = """
<p class="app-eyebrow">Ferramenta · Base</p>
<h1 class="app-h1">Banco de clientes</h1>
<p class="app-sub">Envie um link para o cliente preencher o dossiê — cada cliente tem seu próprio código de acesso,
gerado ao criar em “+ Novo cliente” (visível em “Copiar link”).
As respostas chegam aqui. Clique em “Ver respostas” para lê-las organizadas por seção.</p>
<div style="margin-top:26px; display:flex; align-items:center; gap:16px; flex-wrap:wrap">
  <button id="btn-novo" class="app-btn" style="margin-top:0">+ Novo cliente</button>
</div>
<div style="margin-top:28px" id="lista"></div>

<p class="app-eyebrow" style="margin-top:48px">Dossiês gerados</p>
<h2 class="app-h1" style="font-size:26px; margin-top:8px">Compartilhar com o cliente</h2>
<p class="app-sub">Gere um link exclusivo e somente-leitura para o cliente acompanhar o próprio dossiê.</p>
<div style="margin-top:20px" id="lista-dossies"></div>
"""
    (OUT / "clientes.html").write_text(
        _page("Banco de clientes · Noeds", "clientes.html", clientes_body, CSS, SIDEBAR_CSS,
              SIDEBAR_JS, sidebar_html, FONTS, PRINT_CSS, extra_js=_clientes_js(), theme_boot_js=THEME_BOOT_JS),
        encoding="utf-8",
    )
