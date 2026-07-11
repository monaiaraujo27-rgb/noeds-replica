-- ============================================================
-- Level 3 do roadmap: autenticação multi-usuário real (Supabase Auth).
--
-- Tabela de perfil da equipe. RLS: cada membro lê o próprio registro.
-- Escopo de visibilidade decidido no roadmap: TODO membro autenticado
-- vê todos os clientes/respostas (mesmo comportamento do token único
-- anterior) — segmentação por dono fica para extensão futura, só se o
-- uso real da equipe mostrar necessidade.
-- ============================================================

create table if not exists public.team_members (
  id uuid primary key references auth.users(id) on delete cascade,
  nome text not null default '',
  papel text not null default 'vendedor' check (papel in ('admin', 'vendedor')),
  created_at timestamptz not null default now()
);

alter table public.team_members enable row level security;

drop policy if exists "self read" on public.team_members;
create policy "self read"
  on public.team_members for select
  using (auth.uid() = id);

-- primeiro usuário (criado via Admin API) marcado como admin.
insert into public.team_members (id, nome, papel)
values ('20d9ba3c-af14-4ff8-b71b-40ea1f15e5f2', 'Monai', 'admin')
on conflict (id) do update set papel = 'admin';

-- pronto.
