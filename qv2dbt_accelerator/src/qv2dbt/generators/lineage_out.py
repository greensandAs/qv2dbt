"""Lineage deliverables: JSON graph, Mermaid diagrams, interactive HTML.

All three are derived from the :class:`Lineage` produced by ``lineage.py``.
"""
from __future__ import annotations

import json
import re

from ..lineage import Lineage
from ..models import QvScript

_ROLE_ORDER = ["source", "staging", "intermediate", "mart", "mapping"]


def _nid(name: str) -> str:
    return "n_" + re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_")


# ---------------------------------------------------------------------------
# JSON graph
# ---------------------------------------------------------------------------

def build_json(script: QvScript, lin: Lineage) -> dict:
    return {
        "script": script.name,
        "nodes": {
            "sources": lin.sources,
            "tables": lin.tables,
        },
        "table_edges": [{"from": u, "to": d} for u, d in lin.table_edges],
        "columns": [
            {
                "table": c.table,
                "column": c.column,
                "layer": c.layer,
                "mapping_type": c.mapping_type,
                "direct_deps": [
                    {"upstream": d.upstream, "column": d.column,
                     "external": d.external} for d in c.direct_deps
                ],
                "ultimate_sources": [{"table": a, "column": b}
                                     for a, b in c.ultimate_sources],
                "qlikview": c.qlik_expr,
                "snowflake": c.snowflake_sql,
                "notes": c.notes,
            }
            for c in lin.columns
        ],
    }


def write_json(script: QvScript, lin: Lineage, path: str) -> dict:
    data = build_json(script, lin)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return data


# ---------------------------------------------------------------------------
# Mermaid
# ---------------------------------------------------------------------------

def build_mermaid_tables(script: QvScript, lin: Lineage) -> str:
    lines = ["flowchart LR"]
    # group nodes into subgraphs by role
    groups: dict[str, list[tuple[str, str]]] = {r: [] for r in _ROLE_ORDER}
    for sid, meta in lin.sources.items():
        label = sid.split("source:")[-1]
        groups["source"].append((sid, f"{label}\\n({meta.get('kind','')})"))
    for name, meta in lin.tables.items():
        groups.get(meta["role"], groups["intermediate"]).append((name, name))
    for role in _ROLE_ORDER:
        nodes = groups.get(role) or []
        if not nodes:
            continue
        lines.append(f"  subgraph {role.upper()}")
        for real, label in nodes:
            lines.append(f'    {_nid(real)}["{label}"]')
        lines.append("  end")
    for u, d in lin.table_edges:
        lines.append(f"  {_nid(u)} --> {_nid(d)}")
    lines += [
        "  classDef source fill:#DDEBF7,stroke:#2E75B6;",
        "  classDef mart fill:#FCE4D6,stroke:#C55A11;",
    ]
    src_ids = " ".join(_nid(s) for s in lin.sources) or ""
    mart_ids = " ".join(_nid(n) for n, m in lin.tables.items()
                        if m["role"] == "mart")
    if src_ids:
        lines.append(f"  class {src_ids} source;")
    if mart_ids:
        lines.append(f"  class {mart_ids} mart;")
    return "\n".join(lines)


def build_mermaid_columns(mart: str, lin: Lineage) -> str:
    lines = ["flowchart LR"]
    cols = lin.for_table(mart)
    seen_src = set()
    for c in cols:
        tgt = _nid(f"{mart}.{c.column}")
        lines.append(f'  {tgt}["{c.column}"]')
        for a, b in c.ultimate_sources:
            sid = _nid(f"{a}.{b}")
            if sid not in seen_src:
                lines.append(f'  {sid}(["{a}.{b}"])')
                seen_src.add(sid)
            lines.append(f"  {sid} --> {tgt}")
    return "\n".join(lines)


def write_mermaid(script: QvScript, lin: Lineage, mmd_path: str,
                  md_path: str) -> None:
    overview = build_mermaid_tables(script, lin)
    with open(mmd_path, "w", encoding="utf-8") as fh:
        fh.write(overview + "\n")
    marts = [n for n, m in lin.tables.items() if m["role"] == "mart"]
    parts = [f"# Lineage — {script.name}\n",
             "## Table-level lineage\n", "```mermaid", overview, "```\n"]
    for mart in marts:
        parts += [f"## Column lineage — {mart}\n", "```mermaid",
                  build_mermaid_columns(mart, lin), "```\n"]
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))


# ---------------------------------------------------------------------------
# Interactive HTML explorer
# ---------------------------------------------------------------------------

def write_html(script: QvScript, lin: Lineage, data: dict, path: str) -> None:
    payload = json.dumps(data)
    html = _HTML_TEMPLATE.replace("__TITLE__", script.name)\
                         .replace("__DATA__", payload)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lineage Explorer — __TITLE__</title>
<style>
  :root{--src:#2E75B6;--stg:#548235;--int:#BF9000;--mart:#C55A11;--map:#7030A0;
        --bg:#f7f8fa;--pane:#fff;--line:#e3e6ea;--txt:#1f2733;--mut:#6b7280;}
  *{box-sizing:border-box} body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
    color:var(--txt);background:var(--bg)}
  header{padding:14px 18px;background:var(--pane);border-bottom:1px solid var(--line)}
  header h1{font-size:16px;margin:0} header .sub{color:var(--mut);font-size:12px}
  .wrap{display:flex;height:calc(100vh - 56px)}
  .side{width:340px;border-right:1px solid var(--line);background:var(--pane);
    overflow:auto;padding:10px}
  .main{flex:1;overflow:auto;padding:18px}
  input,select{width:100%;padding:8px;border:1px solid var(--line);border-radius:8px;
    margin-bottom:8px;font-size:13px}
  .grp{margin:6px 0} .grp>.h{font-weight:600;font-size:11px;text-transform:uppercase;
    color:var(--mut);letter-spacing:.04em;margin:8px 2px}
  .tbl{margin:4px 0} .tbl>.tn{font-weight:600;cursor:pointer;padding:3px 6px;border-radius:6px}
  .tbl>.tn:hover{background:#eef2f7}
  .col{padding:3px 6px 3px 20px;cursor:pointer;border-radius:6px;color:#374151}
  .col:hover{background:#eef2f7} .col.active{background:#dbeafe;font-weight:600}
  .pill{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11px;
    color:#fff;margin-left:6px}
  .role-source{background:var(--src)}.role-staging{background:var(--stg)}
  .role-intermediate{background:var(--int)}.role-mart{background:var(--mart)}
  .role-mapping{background:var(--map)}
  .mt{background:#374151}
  .card{background:var(--pane);border:1px solid var(--line);border-radius:12px;
    padding:16px;margin-bottom:14px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
  .card h2{margin:0 0 4px;font-size:16px} .muted{color:var(--mut)}
  code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
  pre{background:#0f172a;color:#e2e8f0;padding:10px 12px;border-radius:8px;overflow:auto}
  .kv{display:grid;grid-template-columns:130px 1fr;gap:6px 12px;margin:8px 0}
  .kv .k{color:var(--mut)}
  ul.tree{list-style:none;margin:6px 0;padding-left:14px;border-left:2px solid var(--line)}
  ul.tree li{margin:3px 0}
  .node{padding:2px 8px;border-radius:6px;background:#eef2f7;display:inline-block}
  .node.src{background:#e7f0fb;color:#1d4e89;font-weight:600}
  .empty{color:var(--mut);padding:40px;text-align:center}
  .note{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;padding:6px 10px;
    border-radius:8px;font-size:12.5px;margin-top:8px}
</style></head><body>
<header><h1>Column Lineage Explorer</h1>
  <div class="sub">__TITLE__ · pick a column to trace it back to source</div></header>
<div class="wrap">
  <div class="side">
    <input id="q" placeholder="Filter tables / columns…">
    <select id="layerf">
      <option value="">All layers</option>
      <option value="staging">staging</option>
      <option value="intermediate">intermediate</option>
      <option value="mart">mart</option>
    </select>
    <div id="list"></div>
  </div>
  <div class="main"><div id="detail" class="empty">Select a column on the left.</div></div>
</div>
<script>
const DATA = __DATA__;
const cols = DATA.columns;
const idx = {};
cols.forEach(c => idx[(c.table+'||'+c.column).toLowerCase()] = c);
const tableRole = {}; Object.entries(DATA.nodes.tables).forEach(([k,v])=>tableRole[k]=v.role);

function group(){
  const g={};
  cols.forEach(c=>{ (g[c.table]=g[c.table]||{layer:c.layer,cols:[]}).cols.push(c); });
  return g;
}
function render(){
  const q=document.getElementById('q').value.toLowerCase();
  const lf=document.getElementById('layerf').value;
  const g=group(); const host=document.getElementById('list'); host.innerHTML='';
  const order=['mart','intermediate','staging'];
  const byLayer={}; Object.entries(g).forEach(([t,o])=>{(byLayer[o.layer]=byLayer[o.layer]||[]).push([t,o]);});
  order.forEach(layer=>{
    if(lf && lf!==layer) return;
    const items=(byLayer[layer]||[]).sort((a,b)=>a[0].localeCompare(b[0]));
    let shown=[];
    items.forEach(([t,o])=>{
      const cs=o.cols.filter(c=>!q || t.toLowerCase().includes(q) || c.column.toLowerCase().includes(q));
      if(!cs.length) return;
      shown.push([t,o,cs]);
    });
    if(!shown.length) return;
    const grp=document.createElement('div'); grp.className='grp';
    grp.innerHTML=`<div class="h">${layer}</div>`;
    shown.forEach(([t,o,cs])=>{
      const d=document.createElement('div'); d.className='tbl';
      const tn=document.createElement('div'); tn.className='tn';
      tn.innerHTML=`${t}<span class="pill role-${o.layer}">${o.layer}</span>`;
      d.appendChild(tn);
      cs.forEach(c=>{
        const cd=document.createElement('div'); cd.className='col';
        cd.textContent=c.column; cd.dataset.key=(t+'||'+c.column).toLowerCase();
        cd.onclick=()=>select(cd.dataset.key,cd);
        d.appendChild(cd);
      });
      grp.appendChild(d);
    });
    host.appendChild(grp);
  });
}
function tree(key,seen){
  seen=seen||new Set(); if(seen.has(key)) return '<li class="muted">…cycle…</li>'; seen.add(key);
  const c=idx[key]; if(!c) return '';
  let html='';
  c.direct_deps.forEach(d=>{
    if(d.external){
      html+=`<li><span class="node src">${d.upstream.replace('source:','')}.${d.column}</span></li>`;
    }else{
      const ck=(d.upstream+'||'+d.column).toLowerCase();
      const child=idx[ck];
      const role=tableRole[d.upstream]||'';
      html+=`<li><span class="node">${d.upstream}.${d.column}`+
            (role?`<span class="pill role-${role}">${role}</span>`:'')+`</span>`;
      if(child){ html+=`<ul class="tree">${tree(ck,new Set(seen))}</ul>`; }
      html+='</li>';
    }
  });
  return html;
}
function select(key,el){
  document.querySelectorAll('.col.active').forEach(x=>x.classList.remove('active'));
  if(el) el.classList.add('active');
  const c=idx[key]; const host=document.getElementById('detail'); host.className='';
  const us=c.ultimate_sources.map(s=>`${s.table}.${s.column}`).join(' , ')||'—';
  host.innerHTML=`
    <div class="card">
      <h2>${c.table}.<b>${c.column}</b> <span class="pill mt">${c.mapping_type}</span>
        <span class="pill role-${c.layer}">${c.layer}</span></h2>
      <div class="kv">
        <div class="k">Ultimate source(s)</div><div>${us}</div>
        <div class="k">QlikView logic</div><div><code>${esc(c.qlikview)||'—'}</code></div>
      </div>
      <div class="k muted">Snowflake SQL</div>
      <pre>${esc(c.snowflake)||'—'}</pre>
      ${c.notes && c.notes.length?`<div class="note">⚠ ${c.notes.map(esc).join('<br>')}</div>`:''}
    </div>
    <div class="card">
      <h2>Upstream lineage</h2>
      <div class="node">${c.table}.${c.column}</div>
      <ul class="tree">${tree(key)||'<li class="muted">reads directly from source</li>'}</ul>
    </div>`;
}
function esc(s){return (s||'').replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));}
document.getElementById('q').oninput=render;
document.getElementById('layerf').onchange=render;
render();
</script></body></html>
"""


def generate(script: QvScript, lin: Lineage, out) -> dict:
    """out: dict with keys json, mmd, md, html (paths)."""
    data = write_json(script, lin, out["json"])
    write_mermaid(script, lin, out["mmd"], out["md"])
    write_html(script, lin, data, out["html"])
    return data
