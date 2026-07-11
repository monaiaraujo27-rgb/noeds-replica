drop policy if exists "insert dossie open" on public.dossie_clientes;
-- cria uma policy por role explicitamente (evita o problema de PUBLIC vs anon)
create policy "ins anon" on public.dossie_clientes for insert to anon with check (char_length(coalesce(clinica,''))>0);
create policy "ins auth" on public.dossie_clientes for insert to authenticated with check (char_length(coalesce(clinica,''))>0);
grant insert, select on table public.dossie_clientes to anon, authenticated;
notify pgrst, 'reload schema';
