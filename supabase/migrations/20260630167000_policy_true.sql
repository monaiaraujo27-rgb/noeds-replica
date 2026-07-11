drop policy if exists "insert dossie public" on public.dossie_clientes;
create policy "insert dossie open" on public.dossie_clientes
  for insert to anon with check (true);
notify pgrst, 'reload schema';
