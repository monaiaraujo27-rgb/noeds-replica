-- ============================================================
-- Reparo pontual de dado em produção: "Clínica Odonto X" foi gerada pelo
-- fluxo "Gerar dossiê" do Banco de clientes (gerar.html?from=<id>) antes da
-- correção do bug de shape (ver commit da varredura de segurança de
-- 2026-07-14). dossie_clientes.dados ficou salvo no formato aninhado bruto
-- do formulário ({empresa:{nome:...}, crescimento:{...}, ...}) em vez do
-- formato plano ({clinica, responsavel, cidade, ...}) que RENDER_JS espera
-- — o link real desse cliente (share_token já emitido) mostrava
-- literalmente "[Nome da Clínica]" etc. em vez dos dados reais.
--
-- Este é um reparo ÚNICO desse registro específico (id conhecido), não uma
-- migração de schema — não roda de novo para clientes futuros, que já são
-- salvos no formato certo pela correção em gen_app.py (achatarDadosDeFormulario).
-- ============================================================

update public.dossie_clientes
set dados = jsonb_build_object(
  'clinica', dados->'empresa'->>'nome',
  'responsavel', dados->'empresa'->>'responsavel',
  'especialidade', dados->'empresa'->>'segmento',
  'cidade', dados->'empresa'->>'cidade',
  'faturamento', dados->'crescimento'->>'faturamento',
  'ticket', dados->'oferta'->'itens'->0->>'ticket',
  'principal_dor', dados->'publico'->>'dores',
  'objetivo', dados->'crescimento'->>'objetivoPrincipal',
  'publico', coalesce(dados->'publico'->>'clienteIdeal', dados->'publico'->>'desejos'),
  'diferencial', dados->'posicionamento'->>'diferenciais'
)
where id = 'b7df2b61-39b5-468b-87cb-5fe861d935f3'
  and clinica = 'Clínica Odonto X'
  and dados ? 'empresa'; -- só aplica se ainda estiver no formato aninhado (idempotente)

-- pronto.
