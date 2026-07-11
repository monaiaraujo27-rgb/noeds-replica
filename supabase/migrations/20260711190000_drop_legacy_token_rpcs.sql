-- ============================================================
-- Encerra a última brecha do esquema de token: os RPCs antigos
-- (get_clientes, get_respostas, delete_resposta, set_share_token) ainda
-- funcionavam com o token dossie_c70b8dae... mesmo depois do client migrar
-- 100% para os RPCs _auth (Level 3, Supabase Auth). Como o token já ficou
-- exposto em versões anteriores do HTML público, mantê-los vivos era uma
-- porta residual para quem guardou o valor antigo. Confirmado via grep que
-- nenhum código atual (gen_app.py) chama mais essas 4 funções pelo nome
-- antigo — seguro remover.
-- ============================================================

drop function if exists public.get_clientes(text);
drop function if exists public.get_respostas(text);
drop function if exists public.delete_resposta(text, text);
drop function if exists public.set_share_token(uuid, text, text);

-- pronto.
