// Cadastro de equipe pelo painel interno (gerar.html/clientes.html).
//
// Criar uma conta de login (email/senha) exige a Admin API do Supabase
// (auth.admin.createUser), que só funciona com a service_role key — essa
// key nunca pode ir para o client/HTML público. Por isso isso é uma Edge
// Function (roda server-side, a key fica só aqui como secret do projeto),
// nunca uma RPC Postgres comum.
//
// Autorização: só admin pode chamar. A checagem NUNCA confia em nada vindo
// do corpo da requisição — o uid do chamador é extraído validando o JWT do
// header Authorization (o próprio access_token de sessão do admin logado,
// mesmo token usado nas chamadas *_auth normais), e só então consultamos
// team_members pra confirmar o papel.
import "@supabase/functions-js/edge-runtime.d.ts"
import { createClient } from "@supabase/supabase-js"

// SUPABASE_URL é injetada automaticamente pelo runtime (prefixo SUPABASE_ é
// reservado). A service_role key NÃO pode usar esse prefixo em secrets
// customizados — por isso o nome PROJECT_SERVICE_ROLE_KEY, setado manualmente
// via `supabase secrets set`.
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!
const SERVICE_ROLE_KEY = Deno.env.get("PROJECT_SERVICE_ROLE_KEY")!

// Edge Functions rodam num domínio distinto do PostgREST (mesmo projeto,
// mas /functions/v1/ não herda a config de CORS de /rest/v1/) — sem estes
// headers em TODA resposta (incluindo o preflight OPTIONS), o navegador
// bloqueia a chamada do painel (noeds-replica.vercel.app) com erro de CORS
// antes mesmo do POST chegar à function.
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  })
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS })
  }
  if (req.method !== "POST") {
    return jsonResponse({ message: "method not allowed" }, 405)
  }

  const authHeader = req.headers.get("Authorization") || ""
  const jwt = authHeader.replace(/^Bearer\s+/i, "")
  if (!jwt) {
    return jsonResponse({ message: "unauthorized" }, 401)
  }

  // client com service_role: único capaz de validar qualquer JWT de
  // usuário e de chamar a Admin API (createUser/deleteUser).
  const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY)

  const { data: userData, error: userErr } = await admin.auth.getUser(jwt)
  if (userErr || !userData?.user) {
    return jsonResponse({ message: "unauthorized" }, 401)
  }
  const chamadorId = userData.user.id

  // única fonte de verdade de autorização: papel do CHAMADOR (extraído do
  // JWT validado acima), nunca algo vindo do body da requisição.
  const { data: chamadorRow, error: papelErr } = await admin
    .from("team_members")
    .select("papel")
    .eq("id", chamadorId)
    .maybeSingle()
  if (papelErr || !chamadorRow || chamadorRow.papel !== "admin") {
    return jsonResponse({ message: "unauthorized" }, 403)
  }

  let body: { nome?: string; email?: string; senha?: string; papel?: string }
  try {
    body = await req.json()
  } catch {
    return jsonResponse({ message: "corpo inválido" }, 400)
  }

  const nome = (body.nome || "").trim()
  const email = (body.email || "").trim().toLowerCase()
  const senha = body.senha || ""
  const papel = body.papel || ""

  if (!nome) return jsonResponse({ message: "informe o nome" }, 400)
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return jsonResponse({ message: "e-mail inválido" }, 400)
  }
  if (senha.length < 6) {
    return jsonResponse({ message: "senha precisa de pelo menos 6 caracteres" }, 400)
  }
  if (papel !== "admin" && papel !== "vendedor") {
    return jsonResponse({ message: "papel inválido" }, 400)
  }

  // email_confirm:true porque o painel não tem fluxo de confirmação por
  // e-mail — login já funciona só com email/senha, sem verificação prévia.
  const { data: created, error: createErr } = await admin.auth.admin.createUser({
    email,
    password: senha,
    email_confirm: true,
  })
  if (createErr || !created?.user) {
    const msg = (createErr?.message || "").toLowerCase()
    if (msg.includes("already") || msg.includes("registered") || msg.includes("exists")) {
      return jsonResponse({ message: "este e-mail já está cadastrado na equipe", code: "email_exists" }, 409)
    }
    console.error("createUser falhou:", createErr)
    return jsonResponse({ message: "falha ao criar conta" }, 500)
  }

  const novoId = created.user.id
  const { error: insertErr } = await admin
    .from("team_members")
    .insert({ id: novoId, nome, papel })

  if (insertErr) {
    // rollback: sem isso, o usuário existiria em auth.users mas sem papel
    // — conseguiria logar, mas get_meu_papel_auth() sempre falharia.
    console.error("insert team_members falhou, revertendo createUser:", insertErr)
    await admin.auth.admin.deleteUser(novoId)
    return jsonResponse({ message: "falha ao registrar o membro da equipe" }, 500)
  }

  return jsonResponse({ id: novoId, nome, email, papel })
})
