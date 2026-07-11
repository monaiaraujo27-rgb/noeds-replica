# Migrations — projeto Supabase "SETUP" (ref `cvzaqqlagwueldpookdf`)

Estas migrations, em ordem de timestamp no nome do arquivo, são a **fonte de verdade** do schema em produção. Aplique com:

```
supabase db query --linked --file supabase/migrations/<arquivo>.sql
```

(CLI já linkada ao projeto "SETUP", sem senha necessária — workdir da CLI é `~`, não o cwd do shell, então use caminho absoluto se rodar de outro diretório).

Não existem mais arquivos `.sql` soltos na raiz do projeto (`supabase_dossie.sql`, `supabase_respostas.sql`, `supabase_clientes_share.sql` foram removidos em 2026-07-11) — eram cópias históricas que já haviam ficado desatualizadas em relação ao schema real (não refletiam RPCs como `upsert_resposta`, `delete_resposta`, nem o token girado na correção de segurança da mesma data). Qualquer alteração de schema daqui para frente deve entrar como uma nova migration numerada aqui, nunca como edição solta.
