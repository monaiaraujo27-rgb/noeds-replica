#!/usr/bin/env python3
"""
Gerador da réplica estática fiel de noeds-architect-suite.lovable.app
Estratégia: usa o HTML server-rendered REAL de cada rota (já baixado via curl),
remove apenas o badge da plataforma Lovable e os scripts de hidratação,
religa os links internos para arquivos .html locais e inlina o CSS real.
Nada de conteúdo é inventado - markup e texto vêm da fonte original.
"""
import re, os, html, pathlib

OUT = pathlib.Path(__file__).resolve().parent
# fontes versionadas em ./src (fallback p/ /tmp, que é volátil)
SRC = OUT / "src" if (OUT / "src" / "noeds.css").exists() else pathlib.Path("/tmp")
PAGES_SRC = SRC / "noeds_pages"
OUT.mkdir(exist_ok=True)

# slug -> arquivo de saída (índice é a home)
ROUTES = {
    "index": ("index.html", SRC / "noeds.html"),
    "diagnostico": ("diagnostico.html", PAGES_SRC / "diagnostico.html"),
    "swot": ("swot.html", PAGES_SRC / "swot.html"),
    "bcg": ("bcg.html", PAGES_SRC / "bcg.html"),
    "persona": ("persona.html", PAGES_SRC / "persona.html"),
    "marketing": ("marketing.html", PAGES_SRC / "marketing.html"),
    "conteudo": ("conteudo.html", PAGES_SRC / "conteudo.html"),
    "playbook": ("playbook.html", PAGES_SRC / "playbook.html"),
    "certificado": ("certificado.html", PAGES_SRC / "certificado.html"),
}

# mapa de href interno do original -> arquivo local
LINK_MAP = {
    "/": "index.html",
    "/diagnostico": "diagnostico.html",
    "/swot": "swot.html",
    "/bcg": "bcg.html",
    "/persona": "persona.html",
    "/marketing": "marketing.html",
    "/conteudo": "conteudo.html",
    "/playbook": "playbook.html",
    "/certificado": "certificado.html",
}

# ordem dos itens de navegação entre páginas (rótulo, arquivo)
NAV_PAGES = [
    ("Início", "index.html"),
    ("Diagnóstico", "diagnostico.html"),
    ("SWOT", "swot.html"),
    ("Matriz BCG", "bcg.html"),
    ("Persona", "persona.html"),
    ("Marketing", "marketing.html"),
    ("Conteúdo", "conteudo.html"),
    ("Playbook", "playbook.html"),
    ("Certificado", "certificado.html"),
]

# CSS real do site (baixado). Remove apenas as regras do badge da plataforma.
CSS = (SRC / "noeds.css").read_text(encoding="utf-8")
# tira o @font-face e as regras #lovable-badge* (pertencem à plataforma, não ao design)
CSS = re.sub(r"@font-face\s*\{[^}]*CameraPlainVariable[^}]*\}", "", CSS, flags=re.S)
CSS = re.sub(r"#lovable-badge[^{]*\{[^}]*\}", "", CSS)
CSS = re.sub(r"@media[^{]*\{\s*#lovable-badge[^@]*?\}\s*\}", "", CSS, flags=re.S)

# Tema claro do dossiê (camada aditiva, vem DEPOIS do CSS original na cascata -
# mesma especificidade de seletor, então a ordem decide). Padrão é claro
# (:root:not([data-theme="dark"])); [data-theme="dark"] restaura a paleta
# escura original do design (era o :root fixo antes do toggle existir). O
# atributo data-theme é setado no <html> por um script anti-FOUC (ver
# THEME_BOOT_JS) que roda antes de qualquer paint, lendo a preferência salva
# no localStorage de CADA navegador (não é sincronizado entre pessoas).
#
# PDF/impressão ficam sempre claros de propósito, independente do tema da
# tela - não remover esses dois blocos ao mexer no tema.
CSS += """
:root:not([data-theme="dark"]) {
  --background:#ffffff; --foreground:#1a1a1a; --surface:#f7f6f3; --surface-2:#efeee9;
  --border:#e2e0d9; --muted-foreground:#5c5b56; --faint:#8f8d85;
  --color-background:#ffffff; --color-foreground:#1a1a1a; --color-border:#e2e0d9;
}
/* body nunca tem o atributo data-theme (só o <html> tem, ver THEME_BOOT_JS)
   - "body:not([data-theme=dark])" seria sempre verdadeiro mesmo no escuro
   e brigaria com a regra escura abaixo. Usa "html:not(...) body" (ancestral)
   em vez de "body:not(...)" (o próprio elemento, que nunca tem o atributo). */
html:not([data-theme="dark"]), html:not([data-theme="dark"]) body { background:#ffffff !important; color:#1a1a1a !important; }
:root[data-theme="dark"] {
  --background:#000000; --foreground:#ffffff; --surface:#080808; --surface-2:#0e0e0e;
  --border:#151515; --muted-foreground:#a0a0a0; --faint:#707070;
  --color-background:#000000; --color-foreground:#ffffff; --color-border:#151515;
}
html[data-theme="dark"], html[data-theme="dark"] body { background:#000000 !important; color:#ffffff !important; }
/* PDF sempre claro (impressão/leitura formal), mesmo se a tela estiver no escuro. */
body.pdf-capturing #doc-print-area { background:#ffffff !important; color:#1a1a1a !important; }
/* o CSS original tem ::selection{color:#fff;background:#ffffff1f} (pensado pro
   tema escuro) - no claro isso é texto branco em fundo quase-branco, invisível
   ao selecionar. Redeclara os dois casos explicitamente. */
html:not([data-theme="dark"]) ::selection { color:#1a1a1a; background:#d8d4c4; }
html[data-theme="dark"] ::selection { color:#ffffff; background:#ffffff33; }
"""

# Fonts: o original carrega Cormorant Garamond + Inter via Google Fonts.
FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600'
    '&family=Inter:wght@300;400;500;600&display=swap">'
)

def get_title(src_html):
    m = re.search(r"<title>(.*?)</title>", src_html, re.S)
    return html.unescape(m.group(1).strip()) if m else "Noeds · Consultoria Estratégica"

def get_body(src_html):
    m = re.search(r"<body[^>]*>(.*)</body>", src_html, re.S)
    body = m.group(1) if m else src_html
    # remover scripts de hidratação / TSR
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    # remover o badge da plataforma Lovable (não faz parte do design do cliente)
    # obs: id="lovable-badge" pode vir em outra linha/depois de outros atributos
    # dentro da tag <aside ...>, por isso o [^>]*? antes de procurar o id
    body = re.sub(r'<aside(?:(?!id=)[^>])*?id="lovable-badge".*?</aside>', "", body, flags=re.S)
    # remover comentários de streaming RSC (<!--$--> etc.)
    body = re.sub(r"<!--/?\$[^>]*-->", "", body)
    body = re.sub(r"<!--\s*-->", "", body)
    return body

def relink(body):
    # converte href="/rota" -> href="rota.html"
    def repl(m):
        href = m.group(1)
        if href in LINK_MAP:
            return f'href="{LINK_MAP[href]}"'
        return m.group(0)
    return re.sub(r'href="(/[a-z]*)"', repl, body)

# ---------------------------------------------------------------------------
# MELHORIAS (camada aditiva - não altera o markup/design original)
#   1. Exportar PDF: botões "Baixar PDF"/"PDF" chamam window.print()
#   2. Navegação por capítulos: scroll suave + capítulo ativo (IntersectionObserver)
#   3. Gráficos: quadrante BCG + grade 2x2 SWOT (injetados via JS nas páginas certas)
# ---------------------------------------------------------------------------
PRINT_CSS = """
@media print {
  /* esconde navegação; expande o documento para a folha inteira */
  aside, .lg\\:ml-\\[300px\\] > div.sticky, [aria-label="Capítulos"] { display:none !important; }
  .lg\\:ml-\\[300px\\] { margin-left:0 !important; }
  html, body { background:#fff !important; color:#000 !important; }
  .bg-background, .bg-surface, .bg-surface-2 { background:#fff !important; }
  .text-foreground, h1, h2, h3, p, div, span, .serif { color:#000 !important; }
  .text-muted-foreground, .text-faint { color:#444 !important; }
  .border-border, .hairline, [class*="border"] { border-color:#ccc !important; background:#ccc !important; }
  .hairline { background:#ccc !important; }
  section, .doc-section { break-inside:avoid; page-break-inside:avoid; }
  a[href]::after { content:""; }
  @page { margin:18mm 16mm; }
}
/* destaque do capítulo ativo na navegação */
.noeds-chapter-active span:last-child { color:var(--foreground) !important; }
.noeds-chapter-active span:first-child { color:var(--muted-foreground) !important; }
html { scroll-behavior:smooth; }
/* gráficos injetados */
.noeds-chart { margin-top:2.5rem; }
.noeds-quad { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border);
  border:1px solid var(--border); aspect-ratio:1/1; max-width:560px; }
.noeds-quad > div { background:var(--surface); padding:1.25rem 1.5rem; display:flex; flex-direction:column; justify-content:space-between; }
.noeds-quad .q-tag { font-family:var(--font-sans); font-size:10px; letter-spacing:.28em; text-transform:uppercase; color:var(--faint); }
.noeds-quad .q-name { font-family:var(--font-serif); font-size:19px; margin-top:.4rem; line-height:1.2; }
.noeds-quad .q-meta { font-size:12px; color:var(--muted-foreground); margin-top:.75rem; font-weight:300; }
.noeds-axis { font-family:var(--font-sans); font-size:10px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint); }
.noeds-swot { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border); border:1px solid var(--border); }
.noeds-swot > div { background:var(--surface); padding:1.5rem 1.75rem; }
.noeds-swot .s-tag { font-family:var(--font-sans); font-size:10px; letter-spacing:.28em; text-transform:uppercase; }
.noeds-swot .s-body { font-size:13px; color:var(--muted-foreground); margin-top:.6rem; font-weight:300; line-height:1.7; }

/* ---- visuais nível 5 (camada aditiva; renderizados só quando há dossiê gerado) ---- */
:root { --nd-ok:#5a9a6d; --nd-warn:#c98a3a; --nd-err:#c0473f; }
html[data-theme="dark"] { --nd-ok:#7bbf8a; --nd-warn:#c98a3a; --nd-err:#e0726a; }
/* título/rótulo em DESTAQUE nos cards e blocos gerados (Meta 6 meses, Estratégia,
   Dores, situações de script…) - cor plena + peso médio, vence o .text-faint do
   eyebrow original via !important */
.nd-lab { font-family:var(--font-sans) !important; font-size:11px !important; letter-spacing:.22em !important;
  text-transform:uppercase; color:var(--foreground) !important; font-weight:500 !important; }
/* KPIs (indicadores do diagnóstico) */
.nd-kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--border); border:1px solid var(--border); margin-top:2rem; }
.nd-kpi { background:var(--surface); padding:1.25rem 1.4rem; }
.nd-kpi .k-label { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.22em; text-transform:uppercase; color:var(--foreground); min-height:2.6em; line-height:1.4; }
.nd-kpi .k-value { font-family:var(--font-serif); font-size:29px; line-height:1.1; margin-top:.45rem; letter-spacing:-.01em; }
.nd-kpi .k-note { font-size:11.5px; color:var(--muted-foreground); font-weight:300; margin-top:.55rem; line-height:1.5; }
.nd-chip { display:inline-block; font-family:var(--font-sans); font-size:9px; letter-spacing:.18em; text-transform:uppercase; color:var(--nd-warn); border:1px solid currentColor; padding:5px 10px; margin-top:.55rem; }
/* status por motor */
.nd-status-row { margin-top:1.4rem; display:flex; align-items:center; }
.nd-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--faint); }
.nd-dot.ok { background:var(--nd-ok); } .nd-dot.atencao { background:var(--nd-warn); } .nd-dot.critico { background:var(--nd-err); }
.nd-status-lbl { font-family:var(--font-sans); font-size:9px; letter-spacing:.24em; text-transform:uppercase; color:var(--muted-foreground); margin-left:9px; }
/* barra segmentada (alocação BCG / pesos dos pilares) */
.nd-bar { margin-top:2rem; }
.nd-bar .b-track { display:flex; height:10px; background:var(--surface-2); border:1px solid var(--border); }
.nd-bar .b-seg { height:100%; background:var(--foreground); }
.nd-bar .b-legend { display:flex; flex-wrap:wrap; gap:12px 22px; margin-top:12px; }
.nd-bar .b-item { font-family:var(--font-sans); font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted-foreground); display:flex; align-items:center; gap:7px; }
.nd-bar .b-swatch { width:9px; height:9px; display:inline-block; background:var(--foreground); }
/* bolha de chat (scripts do playbook) */
.nd-chat { margin-top:1.8rem; }
.nd-chat .c-tag { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.24em; text-transform:uppercase; color:var(--foreground); margin-bottom:10px; }
.nd-bubble { max-width:540px; background:var(--surface-2); border:1px solid var(--border); border-radius:14px 14px 14px 4px; padding:14px 18px; font-size:14px; line-height:1.7; font-weight:300; white-space:pre-line; }
.nd-copy { margin-top:9px; background:none; border:1px solid var(--border); color:var(--faint); font-family:var(--font-sans); font-size:9px; letter-spacing:.2em; text-transform:uppercase; padding:6px 13px; cursor:pointer; transition:color .2s, border-color .2s; }
.nd-copy:hover { color:var(--foreground); border-color:var(--foreground); }
/* par objeção -> resposta */
.nd-obj { margin-top:1.8rem; display:flex; flex-direction:column; }
.nd-obj .c-tag { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.24em; text-transform:uppercase; color:var(--foreground); margin-bottom:8px; }
.nd-obj .o-tag-r { align-self:flex-end; margin-top:12px; }
.nd-obj .o-cliente { align-self:flex-start; max-width:440px; background:var(--surface-2); border:1px solid var(--border); border-radius:14px 14px 14px 4px; padding:11px 16px; font-size:13.5px; font-weight:300; font-style:italic; color:var(--muted-foreground); }
.nd-obj .o-resposta { align-self:flex-end; max-width:540px; background:var(--foreground); color:var(--background); border-radius:14px 14px 4px 14px; padding:13px 18px; font-size:13.5px; line-height:1.65; font-weight:300; }
/* card de persona */
.nd-persona { border:1px solid var(--border); background:var(--surface); padding:1.75rem; margin-top:2rem; }
.nd-persona .p-head { display:flex; align-items:center; gap:16px; }
.nd-persona .p-mono { width:52px; height:52px; flex-shrink:0; border-radius:50%; border:1px solid var(--foreground); display:flex; align-items:center; justify-content:center; font-family:var(--font-serif); font-size:24px; }
.nd-persona .p-name { font-family:var(--font-serif); font-size:21px; line-height:1.2; }
.nd-persona .p-meta { font-family:var(--font-sans); font-size:10px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint); margin-top:5px; }
.nd-persona .p-quote { font-family:var(--font-serif); font-style:italic; font-size:18px; margin-top:1.2rem; line-height:1.4; }
.nd-persona .p-perfil { font-size:13px; font-weight:300; color:var(--muted-foreground); margin-top:.9rem; line-height:1.7; }
.nd-persona .p-cols { display:grid; grid-template-columns:1fr 1fr; gap:1.4rem; margin-top:1.4rem; }
.nd-persona .p-col-t { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.24em; text-transform:uppercase; color:var(--foreground); margin-bottom:.4rem; }
.nd-persona .p-item { font-size:13px; font-weight:300; color:var(--muted-foreground); line-height:1.55; padding:7px 0; border-bottom:1px solid var(--border); }
.nd-persona .p-gatilho { margin-top:1.3rem; border-left:2px solid var(--foreground); padding-left:14px; font-size:13.5px; font-weight:300; line-height:1.65; }
/* checklist (auditados, operação, ação da semana) */
.nd-check { margin-top:1.4rem; border-top:1px solid var(--border); }
.nd-check .c-row { display:flex; gap:14px; align-items:baseline; padding:11px 0; border-bottom:1px solid var(--border); }
.nd-check .c-row p { font-size:14px; font-weight:300; line-height:1.65; }
.nd-check .c-mark { color:var(--nd-ok); font-size:13px; flex-shrink:0; }
/* linha do tempo (marketing) */
.nd-timeline { display:flex; margin-top:2.2rem; }
.nd-timeline .t-step { flex:1; position:relative; }
.nd-timeline .t-step::before { content:""; position:absolute; top:5px; left:16px; right:0; height:1px; background:var(--border); }
.nd-timeline .t-step:last-child::before { display:none; }
.nd-timeline .t-node { width:11px; height:11px; border-radius:50%; border:1px solid var(--foreground); background:var(--background); position:relative; z-index:1; }
.nd-timeline .t-step.t-fill .t-node { background:var(--foreground); }
.nd-timeline .t-label { font-family:var(--font-sans); font-size:10.5px; font-weight:500; letter-spacing:.2em; text-transform:uppercase; color:var(--foreground); margin-top:11px; }
.nd-timeline .t-name { font-family:var(--font-serif); font-size:15px; margin-top:4px; line-height:1.3; padding-right:10px; }
/* selo (certificado) - hierarquia: rótulo pequeno em cima, NOME DA EMPRESA em
   destaque no centro, assinatura da consultoria discreta embaixo. Sem data. */
.nd-selo { width:186px; height:186px; border-radius:50%; border:1px solid var(--foreground); box-shadow:0 0 0 1px var(--border), 0 0 0 7px var(--surface), 0 0 0 8px var(--border); display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; margin:2.8rem auto 0; padding:20px; }
.nd-selo .s-e { font-family:var(--font-sans); font-size:8px; letter-spacing:.3em; text-transform:uppercase; color:var(--faint); }
.nd-selo .s-empresa { font-family:var(--font-serif); font-size:18px; line-height:1.15; margin:9px 2px; font-weight:500; }
.nd-selo .s-rule { width:26px; height:1px; background:var(--border); margin:2px auto; }
.nd-selo .s-by { font-family:var(--font-sans); font-size:8.5px; letter-spacing:.24em; text-transform:uppercase; color:var(--muted-foreground); margin-top:4px; }
.nd-selo .s-n { font-family:var(--font-serif); font-size:20px; margin:7px 0; }
/* rótulo destacado (SWOT) */
.nd-rlab { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.22em; text-transform:uppercase; color:var(--foreground); }
.nd-rbody { margin-top:3px; }
/* grade de fatos rótulo+texto (resumo do cliente / metas do diagnóstico) */
.nd-facts { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border); border:1px solid var(--border); margin-top:2rem; }
.nd-fact { background:var(--surface); padding:1.35rem 1.5rem; }
.nd-fact .f-label { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.22em; text-transform:uppercase; color:var(--foreground); }
.nd-fact .f-text { font-size:13.5px; font-weight:300; line-height:1.7; margin-top:.65rem; color:var(--foreground); }
/* grade de ideias (banco de conteúdo) */
.nd-ideas { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border); border:1px solid var(--border); margin-top:2rem; }
.nd-idea { background:var(--surface); padding:1.4rem 1.5rem; }
.nd-idea .i-top { display:flex; align-items:center; gap:8px; }
.nd-idea .i-num { font-family:var(--font-sans); font-size:10px; letter-spacing:.28em; color:var(--faint); }
.nd-tag { display:inline-block; font-family:var(--font-sans); font-size:8.5px; letter-spacing:.16em; text-transform:uppercase; color:var(--muted-foreground); border:1px solid var(--border); padding:4px 9px; }
.nd-idea .i-tema { font-family:var(--font-serif); font-size:17px; margin-top:.85rem; line-height:1.3; }
.nd-idea .i-gancho { font-style:italic; color:var(--muted-foreground); font-size:13.5px; margin-top:.6rem; font-weight:300; line-height:1.6; }
.nd-idea .i-dev { font-size:12.5px; color:var(--faint); margin-top:.6rem; font-weight:300; line-height:1.6; }
@media (max-width:640px){
  .nd-kpis { grid-template-columns:repeat(2,1fr); }
  .nd-ideas, .nd-facts, .nd-persona .p-cols { grid-template-columns:1fr; }
  .nd-timeline { flex-direction:column; gap:16px; }
  .nd-timeline .t-step::before { display:none; }
}
@media print {
  .nd-copy { display:none !important; }
  .nd-kpi, .nd-fact, .nd-persona, .nd-idea, .nd-bubble, .nd-obj .o-cliente { background:#fff !important; color:#000 !important; border-color:#ccc !important; }
  .nd-obj .o-resposta { background:#fff !important; color:#000 !important; border:1px solid #999 !important; }
  .nd-bar .b-seg, .nd-bar .b-swatch { background:#000 !important; }
  .nd-selo, .nd-timeline .t-node, .nd-persona .p-mono { border-color:#000 !important; }
}
"""

ENHANCE_JS = r"""
<script src="/src/vendor/html2canvas-pro.min.js"></script>
<script src="/src/vendor/jspdf.umd.min.js"></script>
<script>
(function(){
  // 1. PDF: qualquer botão com texto "Baixar PDF"/"PDF" gera um PDF real
  // (captura o DOM renderizado, preservando 100% do design) em vez de só
  // abrir a caixa de impressão do navegador. html2canvas-pro (não a lib
  // html2canvas original) porque o site usa cores CSS modernas (oklch/
  // color-mix via Tailwind v4) que a html2canvas clássica não sabe parsear
  // - só o fork -pro suporta. jsPDF monta o PDF a partir do canvas
  // capturado, paginando em A4 se o conteúdo for mais alto que 1 página.
  // Se alguma lib não carregar, cai de volta pro window.print() antigo.
  document.querySelectorAll('button').forEach(function(b){
    var t=(b.textContent||'').trim();
    if(t==='Baixar PDF'||t==='PDF'){
      b.style.cursor='pointer'; b.removeAttribute('disabled');
      b.addEventListener('click',async function(){
        if(typeof html2canvas==='undefined' || typeof window.jspdf==='undefined'){ window.print(); return; }
        var alvo=document.getElementById('doc-print-area')
          || document.querySelector('main section[id]')?.closest('main')
          || document.querySelector('main') || document.body;
        var nomeArq=(document.title||'dossie').replace(/[^\w\- ]+/g,'').trim()+'.pdf';
        var textoOrig=b.textContent; b.textContent='Gerando PDF…'; b.disabled=true;
        try{
          var canvas=await html2canvas(alvo,{scale:2,useCORS:true,backgroundColor:'#ffffff'});
          var jsPDF=window.jspdf.jsPDF;
          var margemMm=14, larguraA4=210, alturaA4=297;
          var larguraUtil=larguraA4-margemMm*2;
          var alturaUtilPx=canvas.width/larguraUtil*(alturaA4-margemMm*2);
          var pdf=new jsPDF({unit:'mm',format:'a4',orientation:'portrait'});
          var yCanvas=0, primeira=true;
          while(yCanvas<canvas.height){
            var fatia=document.createElement('canvas');
            fatia.width=canvas.width;
            fatia.height=Math.min(alturaUtilPx, canvas.height-yCanvas);
            fatia.getContext('2d').drawImage(canvas,0,yCanvas,canvas.width,fatia.height,0,0,canvas.width,fatia.height);
            var imgData=fatia.toDataURL('image/jpeg',0.95);
            var alturaMm=fatia.height*larguraUtil/canvas.width;
            if(!primeira) pdf.addPage();
            pdf.addImage(imgData,'JPEG',margemMm,margemMm,larguraUtil,alturaMm);
            yCanvas+=fatia.height; primeira=false;
          }
          pdf.save(nomeArq);
        }catch(e){ console.error('Falha ao gerar PDF, usando impressão do navegador:',e); window.print(); }
        finally{ b.textContent=textoOrig; b.disabled=false; }
      });
    }
  });

  // 2. Navegação por capítulos: liga o N-ésimo botão da sidebar à N-ésima <section>
  var sections=[].slice.call(document.querySelectorAll('#doc-print-area section[id], main section[id], section[id]'));
  // botões de capítulo (sidebar desktop)
  var navBtns=[].slice.call(document.querySelectorAll('nav button.group'));
  if(sections.length && navBtns.length){
    var n=Math.min(sections.length,navBtns.length);
    for(var i=0;i<n;i++){(function(idx){
      navBtns[idx].style.cursor='pointer';
      navBtns[idx].addEventListener('click',function(){
        sections[idx].scrollIntoView({behavior:'smooth',block:'start'});
      });
    })(i);}
    // capítulo ativo conforme rola
    if('IntersectionObserver' in window){
      var io=new IntersectionObserver(function(entries){
        entries.forEach(function(e){
          if(e.isIntersecting){
            var idx=sections.indexOf(e.target);
            navBtns.forEach(function(b){b.classList.remove('noeds-chapter-active');});
            if(navBtns[idx]) navBtns[idx].classList.add('noeds-chapter-active');
          }
        });
      },{rootMargin:'-20% 0px -70% 0px'});
      sections.forEach(function(s){io.observe(s);});
    }
  }

  // 3a. Gráfico quadrante na Matriz BCG (injeta após a 1ª seção "Leitura do Portfólio")
  var bcg=document.querySelector('#portfolio');
  if(bcg && !document.querySelector('.noeds-quad')){
    var box=bcg.querySelector('div.mt-10, div[class*="mt-1"]')||bcg;
    var wrap=document.createElement('div'); wrap.className='noeds-chart';
    wrap.innerHTML=''
      +'<div class="noeds-axis" style="margin-bottom:.6rem">Crescimento de mercado ↑ · Participação →</div>'
      +'<div class="noeds-quad">'
      +'<div><div><div class="q-tag">Estrela</div><div class="q-name">Alta escala</div></div><div class="q-meta">Maior fatia do investimento · 60%</div></div>'
      +'<div><div><div class="q-tag">Interrogação</div><div class="q-name">Validar</div></div><div class="q-meta">Teste de oferta/canal · 15%</div></div>'
      +'<div><div><div class="q-tag">Vaca Leiteira</div><div class="q-name">Sustentação</div></div><div class="q-meta">Caixa e recorrência · 25%</div></div>'
      +'<div><div><div class="q-tag">Abacaxi</div><div class="q-name">Revisar</div></div><div class="q-meta">Baixo retorno · reduzir</div></div>'
      +'</div>';
    box.appendChild(wrap);
  }

  // 3b. Grade 2x2 visual no SWOT (injeta no fim da 1ª seção "Forças")
  var swotFirst=document.querySelector('#forcas');
  var isSwot=/An[aá]lise SWOT/.test((document.querySelector('h1')||{}).textContent||'');
  if(isSwot && swotFirst && !document.querySelector('.noeds-swot')){
    var grid=document.createElement('div'); grid.className='noeds-chart';
    grid.innerHTML='<div class="noeds-swot">'
      +'<div><div class="s-tag" style="color:#cfcfcf">Forças</div><div class="s-body">Internas · positivas: o que já funciona e diferencia.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Fraquezas</div><div class="s-body">Internas · negativas: o que trava o crescimento.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Oportunidades</div><div class="s-body">Externas · positivas: o que pode ser aproveitado.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Ameaças</div><div class="s-body">Externas · negativas: o que precisa ser observado.</div></div>'
      +'</div>';
    swotFirst.appendChild(grid);
  }
})();
</script>
"""

# script anti-FOUC (Flash Of Unstyled Content): roda ANTES de qualquer CSS
# ser parseado, lendo a preferência de tema salva no localStorage deste
# navegador e já setando o atributo no <html> - sem isso, a página sempre
# pisca no tema claro (padrão) antes de trocar pro escuro escolhido.
# Compartilhado entre o dossiê (build.py TEMPLATE) e o painel interno
# (gen_app.py _page()); NÃO usado no formulário público (fora de escopo).
THEME_BOOT_JS = """<script>(function(){try{
  if(localStorage.getItem('noeds_theme')==='dark') document.documentElement.setAttribute('data-theme','dark');
}catch(e){}})();</script>"""

# ---------------------------------------------------------------------------
# SIDEBAR GLOBAL (camada aditiva)
#   - oculta por padrão, abre no botão ☰ (hambúrguer, canto superior esquerdo)
#   - itens: Gerar · Banco de clientes · (linha) · 9 páginas do dossiê
#   - injetada logo após <body> em TODAS as páginas
# ---------------------------------------------------------------------------
SIDEBAR_CSS = """
/* ---- sidebar global (camada aditiva, não faz parte do design original) ---- */
#ng-toggle { position:fixed; top:18px; left:18px; z-index:60; width:42px; height:42px;
  display:flex; flex-direction:column; align-items:center; justify-content:center; gap:5px;
  background:var(--surface,#111); border:1px solid var(--border,#262626); cursor:pointer;
  transition:border-color .25s, background .25s; }
#ng-toggle:hover { border-color:var(--foreground,#fff); }
#ng-toggle span { display:block; width:18px; height:1px; background:var(--muted-foreground,#aaa); transition:.3s; }
body.ng-open #ng-toggle span:nth-child(1){ transform:translateY(6px) rotate(45deg); }
body.ng-open #ng-toggle span:nth-child(2){ opacity:0; }
body.ng-open #ng-toggle span:nth-child(3){ transform:translateY(-6px) rotate(-45deg); }
#ng-overlay { position:fixed; inset:0; z-index:55; background:rgba(0,0,0,.55);
  opacity:0; pointer-events:none; transition:opacity .3s; }
body.ng-open #ng-overlay { opacity:1; pointer-events:auto; }
#ng-side { position:fixed; top:0; left:0; bottom:0; z-index:58; width:300px; max-width:84vw;
  background:var(--surface,#0e0e0e); border-right:1px solid var(--border,#262626);
  transform:translateX(-104%); transition:transform .32s cubic-bezier(.4,0,.2,1);
  display:flex; flex-direction:column; padding:84px 0 28px; overflow-y:auto; }
body.ng-open #ng-side { transform:translateX(0); }
#ng-side .ng-brand { padding:0 28px 22px; }
#ng-side .ng-brand .e { font-family:var(--font-sans,sans-serif); font-size:10px; letter-spacing:.3em;
  text-transform:uppercase; color:var(--faint,#666); }
#ng-side .ng-brand .n { font-family:var(--font-serif,serif); font-size:22px; color:var(--foreground,#fff); margin-top:6px; }
#ng-side .ng-sep { height:1px; background:var(--border,#262626); margin:8px 28px; }
#ng-side .ng-label { padding:14px 28px 6px; font-size:9px; letter-spacing:.28em; text-transform:uppercase; color:var(--faint,#666); }
#ng-side a.ng-item { display:flex; align-items:center; gap:12px; padding:13px 28px;
  color:var(--muted-foreground,#aaa); text-decoration:none; font-size:14px; font-weight:300;
  border-left:2px solid transparent; transition:color .2s, background .2s, border-color .2s; }
#ng-side a.ng-item:hover { color:var(--foreground,#fff); background:var(--surface-2,#161616); }
#ng-side a.ng-item.ng-active { color:var(--foreground,#fff); border-left-color:var(--foreground,#fff); }
#ng-side a.ng-item .ic { width:16px; text-align:center; opacity:.7; }
#ng-side a.ng-item.ng-primary { font-size:15px; color:var(--foreground,#eee); }
@media print { #ng-toggle, #ng-overlay, #ng-side, #ng-theme-toggle { display:none !important; } }
"""
SIDEBAR_CSS += """
body.dossie-share-mode #ng-toggle, body.dossie-share-mode #ng-side, body.dossie-share-mode #ng-overlay { display:none !important; }
body.ng-share-view .ng-team-only { display:none !important; }
"""
# botão de tema: elemento PRÓPRIO, fora de #ng-side de propósito - a regra
# acima esconde a sidebar inteira no modo "?share=" (link do cliente final),
# mas o toggle precisa continuar visível ali (é o cenário mais provável de
# alguém sem contexto do painel querer trocar de tema).
#
# Posição: canto SUPERIOR DIREITO (right:18px), longe do menu hambúrguer que
# fica à esquerda (left:18px) - assim nunca sobrepõe o menu, aberto ou fechado,
# durante scroll (é position:fixed). Nas páginas do DOSSIÊ (link do cliente) o
# topo-direito está livre, então o toggle ocupa right:18px. No PAINEL
# (.app-panel: gerar/clientes) o topo-direito tem até 5 botões de conta
# (.auth-logout, top:18px), então lá o toggle desce para top:64px pra não
# colidir. Detecta o painel pela classe .app-panel no <body>.
#
# Formato: switch de 2 zonas fixas (não é mais um botão único que alterna) -
# lua (premium/preto) na ponta esquerda, sol (creme) na direita, SEM texto
# (só ícone), com uma bolinha (thumb) que desliza para o lado escolhido.
# Clicar em qualquer ponta seleciona aquele tema diretamente (não faz toggle
# relativo ao estado atual).
SIDEBAR_CSS += """
#ng-theme-toggle { position:fixed; top:18px; right:18px; left:auto; z-index:60;
  display:flex; align-items:center; width:84px; height:42px; padding:0 4px;
  border-radius:21px; background:var(--surface,#111); border:1px solid var(--border,#262626);
  cursor:pointer; transition:border-color .25s; }
/* no painel (gerar/clientes) os botões de conta ocupam o topo-direito -
   desce o toggle pra linha de baixo, mantendo-o à direita e fora do menu. */
body.app-panel #ng-theme-toggle { top:64px; right:18px; }
#ng-theme-toggle:hover { border-color:var(--foreground,#fff); }
#ng-theme-toggle .ng-tt-lbl { flex:1; display:flex; align-items:center; justify-content:center;
  font-size:15px; line-height:1; color:var(--faint,#666); position:relative; z-index:2;
  transition:color .25s; background:none; border:none; padding:12px 0; cursor:pointer; }
#ng-theme-toggle .ng-tt-thumb { position:absolute; top:3px; left:3px; width:38px; height:34px;
  border-radius:17px; background:var(--foreground,#fff); z-index:1;
  transition:transform .28s cubic-bezier(.4,0,.2,1); }
#ng-theme-toggle[data-active="dark"] .ng-tt-lbl.ng-tt-dark,
#ng-theme-toggle[data-active="light"] .ng-tt-lbl.ng-tt-light { color:var(--background,#000); }
#ng-theme-toggle[data-active="light"] .ng-tt-thumb { transform:translateX(38px); }
@media (max-width:640px){
  /* telas estreitas: garante que o toggle não encoste na borda nem no menu */
  #ng-theme-toggle { top:14px; right:14px; }
  body.app-panel #ng-theme-toggle { top:60px; right:14px; }
}
"""

def sidebar_html(active_file):
    """gera a sidebar marcando o item ativo (active_file = nome do arquivo atual)."""
    items = []
    # itens de aplicação (primeiros)
    apps = [("Gerar", "gerar.html", "✎"), ("Banco de clientes", "clientes.html", "▤")]
    for label, file, ic in apps:
        cls = "ng-item ng-primary ng-team-only" + (" ng-active" if file == active_file else "")
        items.append(
            f'<a class="{cls}" href="{file}"><span class="ic">{ic}</span>{label}</a>'
        )
    nav = '<div class="ng-label">Dossiê</div>'
    pages = []
    for label, file in NAV_PAGES:
        cls = "ng-item" + (" ng-active" if file == active_file else "")
        pages.append(f'<a class="{cls}" href="{file}">{label}</a>')
    return (
        '<button id="ng-toggle" aria-label="Abrir menu"><span></span><span></span><span></span></button>'
        '<div id="ng-theme-toggle" role="radiogroup" aria-label="Tema do painel" data-active="dark">'
        '<div class="ng-tt-thumb"></div>'
        '<button type="button" class="ng-tt-lbl ng-tt-dark" data-theme-choice="dark" role="radio" aria-label="Tema Preto (premium)">&#9789;</button>'
        '<button type="button" class="ng-tt-lbl ng-tt-light" data-theme-choice="light" role="radio" aria-label="Tema Creme">&#9788;</button>'
        '</div>'
        '<div id="ng-overlay"></div>'
        '<nav id="ng-side" aria-label="Navegação global">'
        '<div class="ng-brand"><div class="e">Consultoria Estratégica</div><div class="n">Noeds</div></div>'
        + "".join(items)
        + '<div class="ng-sep ng-team-only"></div>'
        + nav
        + "".join(pages)
        + "</nav>"
    )

SIDEBAR_JS = r"""
<script>
(function(){
  var t=document.getElementById('ng-toggle'), o=document.getElementById('ng-overlay');
  function close(){document.body.classList.remove('ng-open');}
  function toggle(){document.body.classList.toggle('ng-open');}
  if(t)t.addEventListener('click',toggle);
  if(o)o.addEventListener('click',close);
  document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
  var shareToken=new URLSearchParams(location.search).get("share");
  if(shareToken){
    document.body.classList.add('ng-share-view');
    // propaga o token em QUALQUER link interno pra outra página do dossiê -
    // não só os da sidebar (#ng-side a.ng-item), mas também os "Abrir
    // Documento" da home (index.html) e afins. Sem isso, o cliente clicava
    // num link, o "?share=" se perdia, e a página seguinte caía no modo
    // "preview sem dados" (placeholders tipo [Nome da Clínica]) em vez de
    // mostrar o próprio dossiê.
    document.querySelectorAll('a[href]').forEach(function(a){
      var href=a.getAttribute('href');
      if(href && /^[a-z0-9_-]+\.html$/i.test(href)){
        a.setAttribute('href', href+"?share="+encodeURIComponent(shareToken));
      }
    });
  }
  // tema: preferência pessoal por navegador (localStorage, não sincronizada
  // entre pessoas nem entre painel/dossiê e o link do cliente final). O
  // atributo já foi setado no <html> pelo script anti-FOUC do <head>, se
  // aplicável - aqui só sincroniza a posição do switch e liga os cliques.
  // Switch de 2 zonas fixas: cada botão (Preto/Creme) seleciona aquele tema
  // diretamente, não alterna relativo ao estado atual (diferente do ícone
  // único de antes).
  var THEME_KEY='noeds_theme';
  var wrapT=document.getElementById('ng-theme-toggle');
  function aplicarTema(t){
    if(t==='dark') document.documentElement.setAttribute('data-theme','dark');
    else document.documentElement.removeAttribute('data-theme');
    if(wrapT) wrapT.setAttribute('data-active', t);
  }
  aplicarTema(localStorage.getItem(THEME_KEY)==='dark' ? 'dark' : 'light');
  if(wrapT) wrapT.querySelectorAll('[data-theme-choice]').forEach(function(b){
    b.addEventListener('click', function(){
      var novo = b.getAttribute('data-theme-choice');
      try{ localStorage.setItem(THEME_KEY, novo); }catch(e){}
      aplicarTema(novo);
    });
  });
})();
</script>
"""

# ---------------------------------------------------------------------------
# RENDER_JS - injeta o conteúdo do cliente (localStorage.dossie_atual) nas 9 páginas.
# Lê {dados, documentos}. Sem dados -> página fica no modelo. Camada aditiva.
# O conteúdo da IA segue o contrato de gen_app.py (DOC_SPECS); aqui reconstruímos
# o miolo de cada seção conhecida com as MESMAS classes do design.
# ---------------------------------------------------------------------------
RENDER_JS = r"""
<script>
(async function(){
  var SHARE_SUPABASE_URL="https://cvzaqqlagwueldpookdf.supabase.co";
  var SHARE_SUPABASE_ANON="sb_publishable_guPZajaIZW8_hABcLqIx1w_AD3EKh_o";
  var shareToken=new URLSearchParams(location.search).get("share");
  var raw=null, shareErro=false;
  // SKELETON: no link do cliente (?share=), o conteúdo real chega só depois do
  // fetch. Sem isso, o cliente veria por 1-3s o template com placeholders crus
  // ([Nome da Clínica], [nome]...) piscando antes da neutralização. Cobre a tela
  // com um overlay de carregamento até o render terminar (removido no finally).
  var skel=null;
  if(shareToken){
    skel=document.createElement("div");
    skel.id="ng-skeleton";
    skel.style.cssText="position:fixed;inset:0;z-index:9998;background:var(--background,#000);display:flex;align-items:center;justify-content:center";
    skel.innerHTML='<div style="width:26px;height:26px;border:2px solid var(--faint,#666);border-top-color:transparent;border-radius:50%;animation:ngspin .8s linear infinite"></div><style>@keyframes ngspin{to{transform:rotate(360deg)}}</style>';
    (document.body||document.documentElement).appendChild(skel);
  }
  var removerSkeleton=function(){ if(skel&&skel.parentNode){ skel.parentNode.removeChild(skel); skel=null; } };
  // rede de segurança: se algo travar antes do render terminar, não deixa o
  // cliente preso no spinner pra sempre - remove após 8s no pior caso.
  if(shareToken){ setTimeout(removerSkeleton, 8000); }
  if(shareToken){
    try{
      var r=await fetch(SHARE_SUPABASE_URL+"/rest/v1/rpc/get_dossie_by_share",{method:"POST",
        headers:{apikey:SHARE_SUPABASE_ANON,Authorization:"Bearer "+SHARE_SUPABASE_ANON,"Content-Type":"application/json"},
        body:JSON.stringify({token:shareToken})});
      var rows=r.ok?await r.json():[];
      if(Array.isArray(rows)&&rows.length){ raw={dados:rows[0].dados||{}, documentos:rows[0].documentos||{}}; }
      else { shareErro=true; }
    }catch(_){ shareErro=true; }
  } else {
    try{ raw=JSON.parse(localStorage.getItem("dossie_atual")||"null"); }catch(_){ raw=null; }
  }
  if(shareErro){
    document.body.innerHTML='<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:sans-serif;text-align:center;padding:24px"><div><p style="font-size:20px">Link inválido ou expirado.</p><p style="color:#888;margin-top:8px">Peça um novo link à equipe responsável.</p></div></div>';
    return;
  }
  if(shareToken){ document.body.classList.add("dossie-share-mode"); }
  if(!raw) return;
  var dados=raw.dados||{}, docs=raw.documentos||{};
  // preview interno (sem shareToken): dossie_atual é uma chave global, então
  // se a equipe gerar OUTRO cliente em outra aba, esta aba (se recarregada)
  // passa a ver o cliente novo sem aviso. sessionStorage é por aba: se essa
  // aba já tinha visto uma revisão diferente antes, o rev mudou por baixo
  // dela - mostra um aviso em vez de silenciosamente trocar de cliente.
  var trocouDeCliente=false;
  if(!shareToken && raw.rev){
    var revVista=sessionStorage.getItem("dossie_preview_rev");
    if(revVista && revVista!==(""+raw.rev)) trocouDeCliente=true;
    sessionStorage.setItem("dossie_preview_rev", ""+raw.rev);
  }

  // slug da página atual pelo arquivo
  var file=(location.pathname.split("/").pop()||"index.html").replace(/\.html$/,"")||"index";
  if(shareToken && dados.clinica){
    var PAGE_LABELS={"index":"","diagnostico":"Diagnóstico","swot":"SWOT","bcg":"Matriz BCG",
      "persona":"Persona","marketing":"Marketing","conteudo":"Conteúdo","playbook":"Playbook","certificado":"Certificado"};
    var pageLabel=PAGE_LABELS[file]||"";
    document.title=dados.clinica+(pageLabel?" - "+pageLabel:"")+" - Noeds";
  }
  function esc(s){return (s==null?"":(""+s)).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}

  // ---- classes do design (copiadas do markup original) ----
  var C={
    h2:"serif mt-6 text-[28px] leading-[1.1] tracking-tight sm:mt-8 sm:text-[32px] lg:text-[38px]",
    lead:"mt-4 max-w-2xl text-[15px] leading-[1.75] font-light text-muted-foreground sm:mt-5 sm:text-[16px] sm:leading-[1.8]",
    ul:"border-t border-border mt-8",
    li:"flex items-start gap-5 py-4 border-b border-border sm:gap-8 sm:py-5",
    num:"text-[10px] tracking-[0.32em] text-faint pt-1.5 w-6 shrink-0",
    liTxt:"text-[14px] leading-[1.75] font-light text-foreground/90 sm:text-[15px] sm:leading-[1.8]",
    eyebrow:"text-[10px] tracking-[0.32em] text-faint",
    para:"mt-5 text-[15px] leading-[1.8] font-light text-muted-foreground sm:text-[16px]",
    cardTitle:"serif text-[20px] leading-snug sm:text-[22px]",
    cardBody:"mt-3 text-[14px] leading-relaxed text-muted-foreground font-light"
  };
  function el(tag,cls,html){var e=document.createElement(tag); if(cls)e.className=cls; if(html!=null)e.innerHTML=html; return e;}
  function pad(i){return ("0"+(i+1)).slice(-2);}
  // lista numerada (ul/li) a partir de array de strings
  function numberedList(items){
    var ul=el("ul",C.ul);
    (items||[]).forEach(function(t,i){
      var li=el("li",C.li);
      li.appendChild(el("span",C.num,pad(i)));
      li.appendChild(el("p",C.liTxt,esc(t)));
      ul.appendChild(li);
    });
    return ul;
  }
  // bloco "eyebrow + título + corpo" (para cruzamentos, motores, pilares…)
  // eyebrow ganha .nd-lab (título em destaque, pedido do usuário)
  function block(eyebrow,title,body){
    var wrap=el("div","py-5 border-b border-border");
    if(eyebrow) wrap.appendChild(el("p",C.eyebrow+" nd-lab",esc(eyebrow)));
    if(title) wrap.appendChild(el("p","serif mt-3 text-[18px] sm:text-[20px]",esc(title)));
    if(body) wrap.appendChild(el("p","mt-2 "+C.cardBody,esc(body)));
    return wrap;
  }

  // ---- helpers visuais nível 5 (classes .nd-* definidas no CSS aditivo) ----
  // grade de KPIs; valor vazio/placeholder vira chip "Não informado"
  function statTiles(items){
    var wrap=el("div","nd-kpis");
    (items||[]).forEach(function(it){
      var t=el("div","nd-kpi");
      t.appendChild(el("p","k-label",esc(it.rotulo||"")));
      var v=(it.valor==null?"":""+it.valor).trim();
      if(!v || /^(n[aã]o informado|ponto a confirmar|a confirmar|-)$/i.test(v)) t.appendChild(el("span","nd-chip","Não informado"));
      else t.appendChild(el("p","k-value",esc(v)));
      if(it.nota) t.appendChild(el("p","k-note",esc(it.nota)));
      wrap.appendChild(t);
    });
    return wrap;
  }
  function pctFrom(s){ var m=/(\d{1,3})\s*%/.exec(s||""); return m?+m[1]:null; }
  // barra segmentada (tons de foreground com opacidade decrescente) + legenda
  function allocBar(segs){
    var ops=[".95",".6",".35",".18",".1"];
    var tot=segs.reduce(function(a,s){return a+(s.pct||0);},0)||100;
    var wrap=el("div","nd-bar"), track=el("div","b-track"), leg=el("div","b-legend");
    segs.forEach(function(s,i){
      var seg=el("div","b-seg"); seg.style.width=(100*(s.pct||0)/tot)+"%"; seg.style.opacity=ops[i]||".1";
      track.appendChild(seg);
      var it=el("span","b-item"); var sw=el("span","b-swatch"); sw.style.opacity=ops[i]||".1";
      it.appendChild(sw); it.appendChild(document.createTextNode((s.pct!=null?s.pct+"% · ":"")+(s.nome||"")));
      leg.appendChild(it);
    });
    wrap.appendChild(track); wrap.appendChild(leg); return wrap;
  }
  // status do motor (ok/atencao/critico) -> ponto colorido + rótulo
  function statusRow(st){
    var s=(""+(st||"")).toLowerCase(), n="";
    if(s.indexOf("crit")>=0) n="critico"; else if(s.indexOf("aten")>=0) n="atencao";
    else if(s.indexOf("ok")>=0||s.indexOf("saud")>=0) n="ok";
    if(!n) return null;
    var p=el("p","nd-status-row");
    p.innerHTML='<span class="nd-dot '+n+'"></span><span class="nd-status-lbl">'+({ok:"Saudável",atencao:"Atenção",critico:"Crítico"})[n]+"</span>";
    return p;
  }
  // bolha de chat com botão copiar (scripts prontos do playbook)
  function chatBubble(situacao,msg){
    var w=el("div","nd-chat");
    if(situacao) w.appendChild(el("p","c-tag",esc(situacao)));
    w.appendChild(el("div","nd-bubble",esc(msg||"")));
    var b=el("button","nd-copy","Copiar"); b.type="button";
    b.addEventListener("click",function(){
      var texto=msg||""; // preserva acentos e quebras de linha (writeText é fiel)
      var ok=function(){ b.textContent="Copiado ✓"; b.setAttribute("aria-live","polite");
        b.title="Conteúdo copiado com sucesso."; setTimeout(function(){b.textContent="Copiar"; b.title="";},1800); };
      var falhou=function(){ b.textContent="Não foi possível copiar"; b.title="Não foi possível copiar. Selecione o texto e copie manualmente.";
        setTimeout(function(){b.textContent="Copiar"; b.title="";},2600); };
      // fallback p/ navegador sem Clipboard API (ou http): usa execCommand.
      var fallback=function(){
        try{ var ta=document.createElement("textarea"); ta.value=texto;
          ta.style.cssText="position:fixed;top:-9999px;left:-9999px"; document.body.appendChild(ta);
          ta.focus(); ta.select(); var okc=document.execCommand("copy"); document.body.removeChild(ta);
          okc?ok():falhou();
        }catch(e){ falhou(); }
      };
      if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(texto).then(ok,fallback); }
      else fallback();
    });
    w.appendChild(b); return w;
  }
  // par "cliente diz -> você responde" (objeções)
  function objPair(o){
    var w=el("div","nd-obj");
    w.appendChild(el("p","c-tag","Cliente diz"));
    w.appendChild(el("div","o-cliente","“"+esc(o.objecao||"")+"”"));
    w.appendChild(el("p","c-tag o-tag-r","Você responde"));
    w.appendChild(el("div","o-resposta",esc(o.resposta||"")));
    return w;
  }
  // card de persona: monograma + meta + citação + colunas dores/desejos/objeções
  function personaCard(p){
    var card=el("div","nd-persona");
    var head=el("div","p-head");
    head.appendChild(el("div","p-mono",esc(((p.titulo||"?").trim().charAt(0)||"?").toUpperCase())));
    var ht=el("div","");
    ht.appendChild(el("p","p-name",esc(p.titulo||"")));
    if(p.servico) ht.appendChild(el("p","p-meta",esc(p.servico)));
    head.appendChild(ht); card.appendChild(head);
    if(p.frase) card.appendChild(el("p","p-quote","“"+esc(p.frase)+"”"));
    if(p.perfil) card.appendChild(el("p","p-perfil",esc(p.perfil)));
    var cols=el("div","p-cols");
    function col(title,items){ var c=el("div",""); c.appendChild(el("p","p-col-t",title));
      (items||[]).forEach(function(t){ c.appendChild(el("p","p-item",esc(t))); }); return c; }
    if(p.dores&&p.dores.length) cols.appendChild(col("Dores",p.dores));
    if(p.desejos&&p.desejos.length) cols.appendChild(col("Desejos",p.desejos));
    if(p.objecoes&&p.objecoes.length) cols.appendChild(col("Medos e objeções",p.objecoes));
    card.appendChild(cols);
    if(p.gatilho) card.appendChild(el("p","p-gatilho","<strong>Gatilho de decisão:</strong> "+esc(p.gatilho)));
    return card;
  }
  // checklist com ✓ (auditados, passos de operação, ação da semana)
  function checkList(items){
    var w=el("div","nd-check");
    (items||[]).forEach(function(t){
      var r=el("div","c-row"); r.appendChild(el("span","c-mark","✓")); r.appendChild(el("p","",esc(t)));
      w.appendChild(r);
    });
    return w;
  }
  // linha do tempo horizontal (fases do plano de marketing)
  function timeLine(steps){
    var w=el("div","nd-timeline");
    steps.forEach(function(s,i){
      var st=el("div","t-step"+(i===0?" t-fill":""));
      st.appendChild(el("div","t-node"));
      st.appendChild(el("p","t-label",esc(s.label||"Fase "+(i+1))));
      if(s.name) st.appendChild(el("p","t-name",esc(s.name)));
      w.appendChild(st);
    });
    return w;
  }
  // lista numerada com rótulo destacado ("Rótulo: explicação" -> 2 linhas)
  function labeledList(items){
    var ul=el("ul",C.ul);
    (items||[]).forEach(function(t,i){
      var li=el("li",C.li);
      li.appendChild(el("span",C.num,pad(i)));
      var box=el("div",""), ix=(t||"").indexOf(":");
      if(ix>2&&ix<70){
        box.appendChild(el("p","nd-rlab",esc(t.slice(0,ix))));
        box.appendChild(el("p",C.liTxt+" nd-rbody",esc(t.slice(ix+1).trim())));
      } else box.appendChild(el("p",C.liTxt,esc(t)));
      li.appendChild(box); ul.appendChild(li);
    });
    return ul;
  }
  // divide um parágrafo em frases (p/ virar checklist quando houver 2+)
  function frases(s){
    return ((""+(s||"")).match(/[^.!?]+[.!?]*/g)||[]).map(function(x){return x.trim();}).filter(Boolean);
  }
  // substitui o miolo de uma <section id> por novos nós (mantém o cabeçalho h2/lead se existir)
  function fillSection(id, builder){
    var sec=document.getElementById(id); if(!sec) return;
    // remove tudo após o parágrafo "lead" (mantém numeração, h2 e subtítulo)
    var keep=[]; var kids=[].slice.call(sec.children);
    var seenLead=false;
    for(var i=0;i<kids.length;i++){
      var k=kids[i], tag=k.tagName.toLowerCase();
      if(tag==="p"||tag==="h2"){ keep.push(k); if(tag==="p"&&/leading-\[1\.75\]/.test(k.className)) seenLead=true; }
      else break;
    }
    while(sec.children.length>keep.length) sec.removeChild(sec.lastChild);
    var frag=document.createDocumentFragment(); builder(frag);
    sec.appendChild(frag);
  }

  // ---- renderers por documento ----
  var R={
    diagnostico:function(d){
      // grade de cards rótulo+texto igualmente distribuídos (Resumo do Cliente,
      // Metas) - substitui as linhas rótulo/texto desalinhadas do layout antigo
      function factGrid(items){
        var wrap=el("div","nd-facts");
        (items||[]).forEach(function(it){
          var c=el("div","nd-fact");
          c.appendChild(el("p","f-label",esc(it.rotulo||"")));
          var txt=(it.texto==null?"":""+it.texto).trim();
          if(!txt || /^(n[aã]o informado|ponto a confirmar|a confirmar|-)$/i.test(txt)) c.appendChild(el("span","nd-chip","Não informado"));
          else c.appendChild(el("p","f-text",esc(txt)));
          wrap.appendChild(c);
        });
        return wrap;
      }
      fillSection("resumo",function(f){
        f.appendChild(factGrid(d.resumo_campos));
      });
      fillSection("indicadores",function(f){
        f.appendChild(statTiles(d.indicadores||[]));
      });
      var motores=["motor-demanda","motor-conversao","motor-controle","motor-reativacao","motor-posicionamento","motor-indicacao","motor-prova-social"];
      (d.motores||[]).forEach(function(m,i){
        if(i<motores.length) fillSection(motores[i],function(f){
          var st=statusRow(m.status); if(st) f.appendChild(st);
          f.appendChild(numberedList(m.itens||[]));
        });
      });
      fillSection("gargalo",function(f){ f.appendChild(numberedList(d.gargalo||[])); });
      fillSection("metas",function(f){
        f.appendChild(factGrid(d.metas));
        if(d.conclusao) f.appendChild(el("p",C.para+" mt-8",esc(d.conclusao)));
      });
    },
    swot:function(d){
      // grade 2x2 com os RÓTULOS REAIS de cada quadrante (substitui a versão
      // genérica injetada pelo ENHANCE_JS, que o fillSection de #forcas remove)
      function rotulos(items){
        return (items||[]).map(function(t){ var ix=(t||"").indexOf(":");
          return esc(ix>2&&ix<70 ? t.slice(0,ix) : (t||"").slice(0,42)); }).join(" · ");
      }
      function quadReal(){
        var wrap=el("div","noeds-chart");
        wrap.innerHTML='<div class="noeds-swot">'
          +'<div><div class="s-tag" style="color:var(--foreground)">Forças</div><div class="s-body">'+rotulos(d.forcas)+'</div></div>'
          +'<div><div class="s-tag" style="color:var(--foreground)">Fraquezas</div><div class="s-body">'+rotulos(d.fraquezas)+'</div></div>'
          +'<div><div class="s-tag" style="color:var(--foreground)">Oportunidades</div><div class="s-body">'+rotulos(d.oportunidades)+'</div></div>'
          +'<div><div class="s-tag" style="color:var(--foreground)">Ameaças</div><div class="s-body">'+rotulos(d.ameacas)+'</div></div>'
          +'</div>';
        return wrap;
      }
      fillSection("forcas",function(f){ f.appendChild(quadReal()); f.appendChild(labeledList(d.forcas)); });
      fillSection("fraquezas",function(f){ f.appendChild(labeledList(d.fraquezas)); });
      fillSection("oportunidades",function(f){ f.appendChild(labeledList(d.oportunidades)); });
      fillSection("ameacas",function(f){ f.appendChild(labeledList(d.ameacas)); });
      fillSection("cruzamentos",function(f){ (d.cruzamentos||[]).forEach(function(c){
        f.appendChild(block((c.titulo||"").replace(/\s+com\s+/i," × "),"",c.texto)); }); });
    },
    bcg:function(d){
      // percentuais de alocação por quadrante (parseados do rótulo "Estrela (60%)")
      var pct={};
      (d.alocacao||[]).forEach(function(a){ var p=pctFrom(a.rotulo), r=(a.rotulo||"").toLowerCase();
        if(r.indexOf("estrela")>=0) pct.estrela=p; else if(r.indexOf("vaca")>=0) pct.vaca=p;
        else if(r.indexOf("interroga")>=0) pct.interrogacao=p; });
      fillSection("portfolio",function(f){
        if(d.portfolio) f.appendChild(el("p",C.para,esc(d.portfolio)));
        // quadrante com os procedimentos REAIS (substitui o genérico do ENHANCE_JS,
        // removido pelo próprio fillSection). Sem procedimento real -> quadrante
        // OMITIDO (não mostra "A definir" nem placeholder), conforme a regra de
        // não exibir dado ausente ao cliente. "portfólio enxuto" no abacaxi conta
        // como ausência de procedimento abacaxi -> também omite.
        function nomeReal(obj){
          var n=((obj||{}).nome||"").trim();
          if(!n) return "";
          if(/^(portf[óo]lio enxuto|a definir|n[ãa]o informado|n\/a)$/i.test(n)) return "";
          return n;
        }
        function q(tag,obj,meta,p){
          var n=nomeReal(obj);
          if(!n) return ""; // sem procedimento real na fonte -> não renderiza este quadrante
          return '<div><div><div class="q-tag">'+tag+'</div><div class="q-name">'
          +esc(n)+'</div></div><div class="q-meta">'+meta+(p!=null?" · "+p+"%":"")+'</div></div>'; }
        var quads=q("Estrela",d.estrela,"Foco do investimento",pct.estrela)
          +q("Interrogação",d.interrogacao,"Validar demanda",pct.interrogacao)
          +q("Vaca Leiteira",d.vaca,"Caixa e recorrência",pct.vaca)
          +q("Abacaxi",d.abacaxi,"Revisar ou descontinuar",null);
        if(quads){
          var wrap=el("div","noeds-chart");
          wrap.innerHTML='<div class="noeds-axis" style="margin-bottom:.6rem">Crescimento de mercado ↑ · Participação →</div>'
            +'<div class="noeds-quad">'+quads+'</div>';
          f.appendChild(wrap);
        }
      });
      [["estrela",d.estrela],["vaca",d.vaca],["interrogacao",d.interrogacao],["abacaxi",d.abacaxi]].forEach(function(p){
        fillSection(p[0],function(f){ var q=p[1]||{};
          var n=(q.nome||"").trim();
          // quadrante sem procedimento real (vazio ou "portfólio enxuto"/"a definir"):
          // registra a ausência de forma neutra em vez de listar itens genéricos.
          if(!n || /^(portf[óo]lio enxuto|a definir|n[ãa]o informado|n\/a)$/i.test(n)){
            f.appendChild(el("p",C.para,"Sem procedimento classificado neste quadrante a partir do portfólio informado."));
            return;
          }
          f.appendChild(el("p","mt-5 serif text-[20px]",esc(n)));
          f.appendChild(numberedList(q.itens||[])); });
      });
      fillSection("alocacao",function(f){
        var segs=(d.alocacao||[]).map(function(a){ return {nome:(a.rotulo||"").replace(/\s*\([^)]*\)\s*/g,"").trim(), pct:pctFrom(a.rotulo)}; })
          .filter(function(s){ return s.pct!=null; });
        if(segs.length) f.appendChild(allocBar(segs));
        (d.alocacao||[]).forEach(function(a){ f.appendChild(block(a.rotulo,"",a.texto)); });
        if(d.conclusao) f.appendChild(el("p",C.para+" mt-8",esc(d.conclusao)));
      });
    },
    persona:function(d){
      fillSection("intro",function(f){ if(d.intro) f.appendChild(el("p",C.para,esc(d.intro))); });
      var ids=["persona-harmonizacao-facial","persona-estetica-avancada","persona-atendimento-geral"];
      (d.personas||[]).forEach(function(p,i){
        if(i<ids.length) fillSection(ids[i],function(f){
          f.appendChild(personaCard(p));
        });
      });
      fillSection("motivos",function(f){ f.appendChild(numberedList(d.motivos)); });
    },
    marketing:function(d){
      fillSection("visao-geral",function(f){
        if(d.visao_geral) f.appendChild(el("p",C.para,esc(d.visao_geral)));
        // linha do tempo das fases (título "Primeiros 38 dias · Fundação" -> etapa + nome)
        var steps=(d.blocos||[]).map(function(b,i){
          var t=b.titulo||"", m=/^(.*?)\s*·\s*(.+)$/.exec(t);
          return m?{label:m[1],name:m[2]}:{label:"Fase "+(i+1),name:t};
        });
        if(steps.length){ steps.push({label:"Depois",name:"Escala"}); f.appendChild(timeLine(steps)); }
      });
      var ids=["primeiros-38","metodologia-trafego","recuperacao-base","primeiros-90"];
      (d.blocos||[]).forEach(function(b,i){
        if(i<ids.length) fillSection(ids[i],function(f){
          if(b.titulo) f.appendChild(el("p","mt-5 serif text-[20px]",esc(b.titulo)));
          if(b.estrategia) f.appendChild(block("Estratégia","",b.estrategia));
          if(b.operacao){
            // schema novo manda lista de passos; dossiês antigos têm string única
            var wop=el("div","py-5 border-b border-border");
            wop.appendChild(el("p",C.eyebrow+" nd-lab","Operação"));
            if(Array.isArray(b.operacao)) wop.appendChild(checkList(b.operacao));
            else wop.appendChild(el("p","mt-2 "+C.cardBody,esc(b.operacao)));
            f.appendChild(wop);
          }
          if(b.resultado){
            var wr=el("div","py-5 border-b border-border");
            wr.appendChild(el("p",C.eyebrow+" nd-lab","Resultado Esperado"));
            wr.appendChild(el("p","serif mt-3 text-[18px] leading-snug",esc(b.resultado)));
            f.appendChild(wr);
          }
        });
      });
      fillSection("motores",function(f){ (d.motores||[]).forEach(function(m){ f.appendChild(block(m.rotulo,"",m.texto)); }); });
      fillSection("caminho-escala",function(f){ if(d.escala) f.appendChild(el("p",C.para,esc(d.escala))); });
    },
    conteudo:function(d){
      fillSection("porque",function(f){ if(d.porque) f.appendChild(el("p",C.para,esc(d.porque))); });
      fillSection("pilares",function(f){
        var segs=(d.pilares||[]).map(function(p){ return {nome:p.nome,pct:pctFrom(p.peso)}; })
          .filter(function(s){ return s.pct!=null; });
        if(segs.length) f.appendChild(allocBar(segs));
        (d.pilares||[]).forEach(function(p){ f.appendChild(block((p.peso?p.peso+" · ":"")+p.nome,"",p.texto)); });
      });
      fillSection("banco",function(f){
        var grid=el("div","nd-ideas");
        (d.banco||[]).forEach(function(b,i){
          var card=el("div","nd-idea");
          var top=el("p","i-top");
          top.innerHTML='<span class="i-num">'+pad(i)+'</span>'
            +(b.pilar?'<span class="nd-tag">'+esc(b.pilar)+'</span>':"")
            +(b.formato?'<span class="nd-tag">'+esc(b.formato)+'</span>':"");
          card.appendChild(top);
          if(b.tema) card.appendChild(el("p","i-tema",esc(b.tema)));
          if(b.gancho) card.appendChild(el("p","i-gancho",esc(b.gancho)));
          if(b.desenvolvimento) card.appendChild(el("p","i-dev",esc(b.desenvolvimento)));
          grid.appendChild(card);
        }); f.appendChild(grid);
      });
      fillSection("acao",function(f){
        if(!d.acao) return;
        var passos=frases(d.acao);
        if(passos.length>1) f.appendChild(checkList(passos));
        else f.appendChild(el("p",C.para,esc(d.acao)));
      });
    },
    playbook:function(d){
      fillSection("fundamentos",function(f){
        // "Regra curta. Justificativa." -> regra em serif destacada + corpo abaixo
        var ul=el("ul",C.ul);
        (d.fundamentos||[]).forEach(function(t,i){
          var li=el("li",C.li);
          li.appendChild(el("span",C.num,pad(i)));
          var box=el("div",""), m=/^([^.!?]{8,80}[.!?])\s+(.+)$/.exec(t||"");
          if(m){
            box.appendChild(el("p","serif text-[17px] leading-snug",esc(m[1])));
            box.appendChild(el("p","mt-1 "+C.cardBody,esc(m[2])));
          } else box.appendChild(el("p",C.liTxt,esc(t)));
          li.appendChild(box); ul.appendChild(li);
        });
        f.appendChild(ul);
      });
      fillSection("biblioteca",function(f){ (d.scripts||[]).forEach(function(s){ f.appendChild(chatBubble(s.situacao,s.mensagem)); }); });
      fillSection("objecoes-gerais",function(f){ (d.objecoes||[]).forEach(function(o){ f.appendChild(objPair(o)); }); });
    },
    certificado:function(d){
      fillSection("resumo",function(f){
        if(d.resumo) f.appendChild(el("p",C.para,esc(d.resumo)));
        // selo: destaca o NOME REAL DA EMPRESA auditada (não a consultoria).
        // SEM data de criação (removida a pedido: certificado não carimba data).
        var selo=el("div","nd-selo");
        selo.appendChild(el("p","s-e","Ciclo concluído"));
        var nomeEmpresa=(dados.clinica||"").trim();
        if(nomeEmpresa){
          selo.appendChild(el("p","s-empresa",esc(nomeEmpresa)));
          selo.appendChild(el("div","s-rule"));
          selo.appendChild(el("p","s-by","por Noeds"));
        } else {
          // sem nome da empresa na fonte: não inventa - mostra só a assinatura.
          selo.appendChild(el("p","s-n","Noeds"));
        }
        f.appendChild(selo);
      });
      fillSection("auditados",function(f){ f.appendChild(checkList(d.auditados)); });
      fillSection("conformidade",function(f){ (d.conformidade||[]).forEach(function(c){ f.appendChild(block(c.area,"",c.escopo)); }); });
      fillSection("proximo",function(f){
        if(!d.proximo) return;
        var marcos=frases(d.proximo);
        if(marcos.length>1) f.appendChild(numberedList(marcos));
        else f.appendChild(el("p",C.para,esc(d.proximo)));
      });
    }
  };

  // ---- 1) substitui placeholders globais ([Nome da Clínica] etc.) em TODA página ----
  var PH={
    "Nome da Clínica":dados.clinica, "Nome do Responsável":dados.responsavel,
    "Nome do responsável comercial":dados.responsavel, "Nicho da Clínica":dados.especialidade,
    "Cidade":dados.cidade, "Faturamento Atual":dados.faturamento, "Meta de Faturamento":dados.objetivo,
    "Principal Diferencial":dados.diferencial, "Principal Gargalo":dados.principal_dor
  };
  // sinônimos p/ resolver placeholder residual não-global (ex. "[Nome]" solto num
  // script do playbook) sem expor o colchete cru ao cliente. Chave = miolo em
  // minúsculas; valor = função que devolve o texto final (ou "" p/ apagar o campo).
  var PH_RESIDUAL=[
    [/^nome( do cliente| completo)?$/i, function(){ return dados.responsavel||dados.clinica||""; }],
    [/^clínica|^cl[ií]nica|^empresa|^nome da empresa$/i, function(){ return dados.clinica||""; }],
    [/^cidade$/i, function(){ return dados.cidade||""; }],
    [/^respons[áa]vel/i, function(){ return dados.responsavel||""; }]
  ];
  // seções "Prompt para a IA" / "prompt pronto" são TEMPLATES que o cliente vai
  // COPIAR e preencher em outra ferramenta - ali os colchetes ([Procedimento
  // Principal], [COLE AQUI O DOCUMENTO PERSONA]) são marcadores legítimos do
  // prompt, não dado faltando. Essas subárvores são ISENTAS da limpeza. Detecta
  // pelo cabeçalho .eyebrow do bloco (ex.: "Prompt para a IA").
  function ehBlocoPromptModelo(node){
    for(var el=(node.nodeType===1?node:node.parentElement), up=0; el && up<8; el=el.parentElement, up++){
      var eb=el.querySelector&&el.querySelector(".eyebrow");
      if(eb && /prompt (para a ia|pronto|modelo|de ia)/i.test(eb.textContent||"")) return true;
    }
    return false;
  }
  function neutralizarPlaceholders(root){
    (function walk(node){
      if(node.nodeType===3){
        var t=node.nodeValue;
        if(t.indexOf("[")>=0){
          if(ehBlocoPromptModelo(node)) return; // isenta prompt-modelo
          node.nodeValue=t.replace(/\[([^\]\[]{2,60})\]/g,function(m,key){
            for(var k in PH){ if(PH[k]&&new RegExp("^"+k,"i").test(key)) return PH[k]; }
            // não casou com placeholder global conhecido: tenta sinônimo residual...
            var kk=key.trim();
            for(var i=0;i<PH_RESIDUAL.length;i++){
              if(PH_RESIDUAL[i][0].test(kk)){ var v=PH_RESIDUAL[i][1](); if(v) return v; }
            }
            // ...e, como último recurso, remove o marcador SÓ se ele tiver "cara
            // de campo a preencher": começa com letra/underscore E NÃO contém
            // dígito nem o símbolo de moeda "R$". Assim apaga "[Nome]",
            // "[endereço]", "[confirmar convênios]" (placeholders) mas PRESERVA
            // valores legítimos como "[R$ 30]", "[1]", "[2024]". Importante:
            // testa "R$" como PAR (moeda), nunca a letra "R" isolada - senão
            // qualquer palavra com R (ex. PERSONA, PROCEDIMENTO) escaparia da
            // limpeza. O que não casar fica como está.
            if(/^[A-Za-zÀ-ÿ_]/.test(kk) && !/[0-9]|R\$/.test(kk)) return "";
            return m;
          }).replace(/\s{2,}/g," ").replace(/\s+([,.;:!?])/g,"$1");
        }
      } else if(node.nodeType===1 && !/SCRIPT|STYLE/.test(node.tagName)){
        for(var c=node.firstChild;c;c=c.nextSibling) walk(c);
      }
    })(root);
  }
  neutralizarPlaceholders(document.body);
  // o <title> (aba do navegador) não está em document.body, então o walk não o
  // alcança - resolve os placeholders dele à parte pra não aparecer "[Nome da
  // Clínica]" no título da aba.
  if(document.title && document.title.indexOf("[")>=0){
    document.title=document.title.replace(/\[([^\]\[]{2,60})\]/g,function(m,key){
      for(var k in PH){ if(PH[k]&&new RegExp("^"+k,"i").test(key)) return PH[k]; }
      return dados.clinica||m;
    });
  }

  // ---- 2) injeta o conteúdo do documento atual ----
  if(R[file] && docs[file]){ try{ R[file](docs[file]); }catch(e){ console.warn("render",file,e); } }
  // 2b) o conteúdo injetado por R[file] NÃO passou pelo walk acima (ele roda
  // antes da injeção). Alguns docs (ex. playbook) trazem scripts com "[Nome]",
  // "[dia]" etc. vindos da IA, e o template estático ainda tem seções próprias
  // com placeholders. Roda a neutralização DE NOVO sobre a página toda, agora
  // com o conteúdo final montado - garante que nenhum colchete cru chegue ao
  // cliente (regra: placeholder nunca visível).
  neutralizarPlaceholders(document.body);

  // conteúdo final já montado e limpo -> pode revelar (tira o skeleton do share)
  removerSkeleton();

  // ---- 3) religa os botões de copiar ESTÁTICOS do template ----
  // O template das páginas (playbook, conteúdo, persona) já vem com dezenas de
  // botões "Copiar mensagem"/"Copiar persona" no HTML, mas SEM handler de clique
  // - só os botões criados pelo próprio RENDER_JS (chatBubble) copiavam. Aqui a
  // gente varre todos os botões de copiar da página e liga o comportamento
  // (clipboard + fallback execCommand + feedback visual e acessível). Idempotente:
  // marca cada botão com data-copy-ligado pra nunca ligar 2x.
  (function ligarCopiasEstaticas(){
    // acha o texto que ESTE botão deve copiar, por proximidade no DOM:
    // 1) irmão/descendente com .whitespace-pre-line (scripts prontos), senão
    // 2) o bloco/card ancestral mais próximo (persona), usando seu texto visível.
    function textoDoBotao(btn){
      // 1) scripts prontos ("Copiar mensagem"): a mensagem está no
      // .whitespace-pre-line dentro do mesmo bloco-card do botão.
      var cont=btn.parentElement;
      for(var up=0; up<4 && cont; up++){
        var pre=cont.querySelector(".whitespace-pre-line");
        if(pre) return pre.innerText;
        cont=cont.parentElement;
      }
      // 2) "Copiar persona": o botão fica num header (só nome + botão); o
      // conteúdo da persona são os elementos irmãos desse header, dentro do card
      // pai. Sobe até o ancestral que tenha conteúdo bem maior que o header,
      // clona, remove header(s)/botão(ões) e usa o texto restante.
      var header=btn.parentElement; // div "nome + botão"
      var card=header?header.parentElement:null; // card da persona inteira
      if(card){
        var clone=card.cloneNode(true);
        clone.querySelectorAll("button").forEach(function(x){ x.remove(); });
        var t=(clone.innerText||"").replace(/\n{3,}/g,"\n\n").trim();
        // só usa se sobrou conteúdo real (mais que o próprio nome do header)
        if(t && t.length>40) return t;
      }
      // 3) último recurso: texto do bloco imediato sem o botão.
      var box=btn.parentElement;
      if(box){ var c2=box.cloneNode(true); c2.querySelectorAll("button").forEach(function(x){x.remove();});
        var t2=(c2.innerText||"").trim(); if(t2) return t2; }
      return "";
    }
    function ligar(btn){
      if(btn.getAttribute("data-copy-ligado")) return;
      btn.setAttribute("data-copy-ligado","1");
      var rotuloOriginal=btn.getAttribute("aria-label")||"Copiar";
      btn.addEventListener("click",function(){
        var texto=textoDoBotao(btn);
        var restaura=function(){ btn.setAttribute("aria-label",rotuloOriginal); btn.title=""; };
        var ok=function(){ btn.setAttribute("aria-label","Copiado"); btn.title="Conteúdo copiado com sucesso.";
          setTimeout(restaura,1800); };
        var falhou=function(){ btn.setAttribute("aria-label","Não foi possível copiar");
          btn.title="Não foi possível copiar. Selecione o texto e copie manualmente."; setTimeout(restaura,2600); };
        if(!texto){ falhou(); return; }
        var fallback=function(){
          try{ var ta=document.createElement("textarea"); ta.value=texto;
            ta.style.cssText="position:fixed;top:-9999px;left:-9999px"; document.body.appendChild(ta);
            ta.focus(); ta.select(); var okc=document.execCommand("copy"); document.body.removeChild(ta);
            okc?ok():falhou();
          }catch(e){ falhou(); }
        };
        if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(texto).then(ok,fallback); }
        else fallback();
      });
    }
    // pega todo botão cujo aria-label começa com "Copiar" (Copiar mensagem,
    // Copiar persona, etc.) e ainda não é um .nd-copy (esses já têm handler).
    document.querySelectorAll('button[aria-label^="Copiar"]').forEach(function(btn){
      if(btn.classList.contains("nd-copy")) return;
      ligar(btn);
    });
  })();

  // banner discreto indicando dossiê do cliente
  var b=document.createElement("div");
  b.style.cssText="position:fixed;bottom:0;left:0;right:0;z-index:50;background:var(--surface,#111);border-top:1px solid var(--border,#262626);padding:8px 16px 8px 72px;font-size:11px;letter-spacing:.1em;color:var(--muted-foreground,#aaa);display:flex;gap:14px;align-items:center;justify-content:space-between";
  b.innerHTML='<span>DOSSIÊ · '+esc(dados.clinica||"Cliente")+(trocouDeCliente?' · <span style="color:#e8a33d">esta aba mostrava outro cliente antes. Confira se é o dossiê certo</span>':'')+'</span>';
  if(!shareToken){
    var x=document.createElement("button"); x.textContent="Sair do dossiê";
    x.style.cssText="background:none;border:1px solid var(--border,#333);color:inherit;padding:5px 12px;cursor:pointer;font-size:10px;letter-spacing:.2em;text-transform:uppercase";
    x.onclick=function(){ localStorage.removeItem("dossie_atual"); location.reload(); };
    b.appendChild(x);
  }
  document.body.appendChild(b);
})();
</script>
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="Consultoria estratégica proprietária Noeds.">
{theme_boot_js}
{fonts}
<style>{css}
{print_css}
{sidebar_css}</style>
</head>
<body>
{sidebar}
{body}
{enhance_js}
{sidebar_js}
{render_js}
</body>
</html>
"""

for slug, (outname, srcpath) in ROUTES.items():
    raw = srcpath.read_text(encoding="utf-8")
    body = relink(get_body(raw))
    doc = TEMPLATE.format(
        title=get_title(raw),
        theme_boot_js=THEME_BOOT_JS,
        fonts=FONTS_LINK,
        css=CSS,
        print_css=PRINT_CSS,
        sidebar_css=SIDEBAR_CSS,
        sidebar=sidebar_html(outname),
        body=body,
        enhance_js=ENHANCE_JS,
        sidebar_js=SIDEBAR_JS,
        render_js=RENDER_JS,
    )
    (OUT / outname).write_text(doc, encoding="utf-8")
    print(f"{outname:22s} <- {srcpath.name:18s} ({len(doc):>7d} B)")

# ---------------------------------------------------------------------------
# Páginas-app (Gerar + Banco de clientes) - geradas por gen_app.py
# ---------------------------------------------------------------------------
try:
    import gen_app
    gen_app.build(OUT, CSS, SIDEBAR_CSS, SIDEBAR_JS, sidebar_html, FONTS_LINK, PRINT_CSS, THEME_BOOT_JS)
    print("gerar.html / clientes.html   <- gen_app.py")
except Exception as e:
    print("aviso: páginas-app não geradas:", e)

# ---------------------------------------------------------------------------
# Formulário público do cliente (dossie.html) - gerado por gen_form.py.
# Página SEM sidebar: é o link que o cliente recebe (código MKT@2026).
# ---------------------------------------------------------------------------
def _page_public(title, body, extra_js="", extra_css=""):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{FONTS_LINK}
<style>{CSS}
{extra_css}</style>
</head>
<body>
{body}
{extra_js}
</body>
</html>
"""

# Página dedicada do FORMULÁRIO - tema CLARO idêntico aos originais NOEDS.
# NÃO injeta o CSS dark do site (o extra_css do gen_form define seu próprio :root claro).
# Fontes: Instrument Serif (serif) + Work Sans (corpo) + JetBrains Mono (eyebrow).
FORM_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1'
    '&family=Work+Sans:wght@300;400;500;600'
    '&family=JetBrains+Mono:wght@400;500&display=swap">'
)

def _page_form(title, body, extra_js="", extra_css=""):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{FORM_FONTS}
<style>{extra_css}</style>
</head>
<body>
{body}
{extra_js}
</body>
</html>
"""

try:
    import gen_form
    gen_form.build(OUT, CSS, FORM_FONTS, _page_form)
    print("dossie.html                  <- gen_form.py (tema claro, 3 tipos)")
except Exception as e:
    print("aviso: formulário público não gerado:", e)

print("\nOK. Réplica gerada em", OUT)
