-- remove objetos de diagnóstico
drop trigger if exists t_trace on public.dossie_clientes;
drop function if exists public.trace_ins();
drop table if exists public.ins_trace;
drop function if exists public.whoami();
drop function if exists public.list_pol();
drop function if exists public.rls_state();
-- consolida policies de insert (mantém anon+authenticated, remove duplicatas antigas)
drop policy if exists "ins anon" on public.dossie_clientes;
drop policy if exists "ins auth" on public.dossie_clientes;
create policy "ins anon" on public.dossie_clientes for insert to anon with check (char_length(coalesce(clinica,''))>0);
create policy "ins auth" on public.dossie_clientes for insert to authenticated with check (char_length(coalesce(clinica,''))>0);
-- limpa linhas de teste
delete from public.dossie_clientes where clinica in ('Trace','Clínica Teste','Clínica Real');
notify pgrst, 'reload schema';
