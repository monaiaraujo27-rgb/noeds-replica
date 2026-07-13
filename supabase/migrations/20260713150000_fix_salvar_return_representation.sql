-- ============================================================
-- Corrige erro real em produção: "Salvar e finalizar" falhava com
-- 403 "permission denied for table dossie_clientes" (código 42501).
--
-- Causa: no Level 4.6 (versionamento), salvar() em gen_app.py passou a
-- usar "Prefer: return=representation" no INSERT em dossie_clientes,
-- porque agora precisa do id da linha criada para chamar a RPC
-- criar_geracao_auth (histórico de gerações). Mas a auditoria de
-- segurança anterior (20260711150000_fix_audit_findings.sql) revogou
-- SELECT de anon/authenticated na tabela — na época o INSERT usava
-- "return=minimal" e não precisava de SELECT, então revogar era seguro.
-- Ninguém re-concedeu o SELECT quando o INSERT passou a pedir a linha
-- de volta, e o PostgREST não consegue satisfazer return=representation
-- sem SELECT — o INSERT em si funciona, mas a resposta falha com 403.
--
-- Correção: GRANT SELECT só para "authenticated" (não para "anon" — o
-- formulário público continua sem poder ler a tabela) + policy de
-- SELECT restrita a membros da equipe (team_members), mesmo padrão de
-- autorização já usado nos RPCs _auth do projeto.
-- ============================================================

grant select on table public.dossie_clientes to authenticated;

drop policy if exists "team select dossie" on public.dossie_clientes;
create policy "team select dossie"
  on public.dossie_clientes for select to authenticated
  using ( exists (select 1 from public.team_members where id = auth.uid()) );

-- pronto.
