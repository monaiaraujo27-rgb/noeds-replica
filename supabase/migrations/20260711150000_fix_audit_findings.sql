-- ============================================================
-- Correções da auditoria de segurança pós-Fase-0 (2026-07-11).
--
-- Achado ALTO: GRANT SELECT residual em dossie_clientes para anon/authenticated
-- (migrations 20260630165000_grants.sql e 20260630168000_policy_allroles.sql).
-- Hoje é inofensivo — não existe nenhuma policy "for select" na tabela, então
-- RLS default-deny bloqueia leitura mesmo com o grant. Mas é uma bomba-relógio:
-- se uma policy de SELECT for criada no futuro (o mesmo tipo de erro que
-- gerou a policy "anon update resposta" já corrigida na Fase 0), o grant já
-- pronto tornaria TODA a tabela (dados, documentos, respostas_brutas,
-- share_token) legível sem token algum. O INSERT real do app já usa
-- "Prefer: return=minimal" (confirmado em gen_app.py:781) — não depende de
-- SELECT para funcionar. Revogado por defesa em profundidade.
-- ============================================================

revoke select on table public.dossie_clientes from anon, authenticated;

-- pronto.
