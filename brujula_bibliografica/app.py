"""Interfaz local para priorizar la revisión de artículos bibliográficos."""

from __future__ import annotations

import base64
from collections import Counter
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from analytics import ANALYTICS_VERSION, overview, reason_group
from core import csv_bytes, load_table
from flow_graph import flow_svg
from keyword_graph import keyword_graph_svg
from project_report import FILES, SCOPUS_LOGO, WOS_LOGO, project_summary
from resources import article_resource


PROJECT_RESULTS = FILES["analyzed"]
LEVELS = ("Alta", "Media", "Baja", "Sin resumen")
OBJECTIVE_HELP = (
    "Caracterizar las bases de datos utilizadas, su frecuencia y sus condiciones de acceso, especialmente los recursos públicos.",
    "Clasificar las técnicas de preparación y aumento de imágenes según su propósito y frecuencia.",
    "Identificar los modelos de aprendizaje automático y profundo para clasificación, sus enfoques de entrenamiento y su frecuencia.",
    "Resumir métricas, procedimientos de validación, resultados y limitaciones metodológicas.",
)
RECOMMENDATION_HELP = (
    "Alta: mayor prioridad temática. Media: relación con mama y termografía que requiere comprobar alcance. "
    "Baja: afinidad limitada, revisión o retractación. Sin resumen: no hay texto suficiente para valorar."
)
CHART_CHOICES = ("Tarjetas", "Barras", "Puntos", "Anillo")
CHART_DEFAULTS = {
    "evidence_datasets": "Barras",
    "evidence_access": "Tarjetas",
    "evidence_preparation": "Puntos",
    "evidence_models": "Barras",
    "evidence_classification": "Barras",
    "evidence_tools": "Puntos",
    "evidence_metrics": "Tarjetas",
    "evidence_limitations": "Puntos",
}


@st.cache_data(show_spinner=False)
def cached_load(filename: str, contents: bytes):
    return load_table(filename, contents)


@st.cache_data(show_spinner="Resumiendo la evidencia de los resúmenes...")
def cached_overview(rows: list[dict[str, object]], method_version: str):
    return overview(rows)


@st.cache_data(show_spinner=False)
def cached_project_summary(file_state: tuple[tuple[str, int, int], ...]):
    return project_summary()


def download_file(label: str, path: Path, key: str) -> None:
    mime = ("text/csv" if path.suffix == ".csv" else
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if path.suffix == ".xlsx" else "application/vnd.ms-excel")
    st.download_button(label, path.read_bytes(), file_name=path.name,
                       mime=mime, key=key, use_container_width=True)


def evidence_chart(title: str, mentions: dict[str, list[int]],
                   records: list[dict[str, str]], key: str, note: str = "") -> None:
    st.markdown(f"#### {title}")
    if note:
        st.caption(note)
    visible = [(name, indices) for name, indices in mentions.items() if indices]
    if not visible:
        st.info("No hay menciones explícitas en los registros seleccionados.")
        return
    summary = pd.DataFrame([
        {"Categoría": name, "Artículos": len(indices),
         "% de seleccionados": round(100 * len(indices) / len(records), 1)}
        for name, indices in visible
    ]).sort_values("Artículos", ascending=False)
    chart_control, filter_control = st.columns([2.2, 1], vertical_alignment="bottom")
    with chart_control:
        chart_type = st.selectbox("Visualización", CHART_CHOICES,
                                  index=CHART_CHOICES.index(CHART_DEFAULTS.get(key, "Barras")),
                                  key=f"{key}_chart")
    with filter_control:
        with st.popover("Filtrar categorías", use_container_width=True):
            selected_categories = st.multiselect(
                "Categorías visibles en la gráfica", summary["Categoría"].tolist(),
                default=summary["Categoría"].tolist(), key=f"{key}_categories")
    chart_data = summary[summary["Categoría"].isin(selected_categories)]
    if chart_data.empty:
        st.info("Selecciona al menos una categoría para mostrar la gráfica.")
    elif chart_type == "Tarjetas":
        cards = []
        for _, item in chart_data.iterrows():
            name = escape(str(item["Categoría"]))
            count = int(item["Artículos"])
            percent = float(item["% de seleccionados"])
            cards.append(f'<div class="evidence-card"><div class="evidence-card-title">{name}</div>'
                         f'<div class="evidence-card-count">{count} <span>artículos · {percent:.1f} %</span></div>'
                         f'<div class="evidence-meter"><div style="width:{max(2, min(100, percent)):.1f}%"></div></div></div>')
        st.markdown('<div class="evidence-cards">' + ''.join(cards) + '</div>',
                    unsafe_allow_html=True)
    else:
        tooltip = [alt.Tooltip("Categoría:N"), alt.Tooltip("Artículos:Q"),
                   alt.Tooltip("% de seleccionados:Q", format=".1f")]
        base = alt.Chart(chart_data).encode(tooltip=tooltip)
        height = max(210, min(590, 37 * len(chart_data)))
        if chart_type == "Barras":
            graph = base.mark_bar(cornerRadiusEnd=5, color="#43b9a2").encode(
                x=alt.X("Artículos:Q", title="Artículos"),
                y=alt.Y("Categoría:N", sort="-x", title=None,
                        axis=alt.Axis(labelLimit=220))).properties(height=height)
        elif chart_type == "Puntos":
            stems = base.mark_bar(size=2, color="#6a9cb3").encode(
                x=alt.X("Artículos:Q", title="Artículos"),
                y=alt.Y("Categoría:N", sort="-x", title=None,
                        axis=alt.Axis(labelLimit=220)))
            dots = base.mark_circle(size=150, color="#e9854c").encode(
                x="Artículos:Q", y=alt.Y("Categoría:N", sort="-x"))
            graph = (stems + dots).properties(height=height)
        else:
            graph = base.mark_arc(innerRadius=72, outerRadius=125).encode(
                theta=alt.Theta("Artículos:Q"),
                color=alt.Color("Categoría:N", legend=alt.Legend(orient="bottom")))
            graph = graph.properties(height=340)
            st.caption("El anillo reparte menciones entre categorías; un artículo puede aparecer en varias.")
        st.altair_chart(graph, width="stretch")
    st.dataframe(summary, hide_index=True, width="stretch", height=min(350, 35 * (len(summary) + 1)))
    with st.expander("Ver los artículos detrás de cada conteo"):
        chosen = st.selectbox("Categoría", summary["Categoría"].tolist(), key=key)
        indices = mentions[chosen]
        st.dataframe(pd.DataFrame([
            {"Recurso": records[i]["resource"], "Título": records[i]["title"]} for i in indices
        ]), hide_index=True, width="stretch", height=300,
            column_config={"Recurso": st.column_config.LinkColumn(display_text="Abrir ↗", width=105)})


def objective_heading(number: int, label: str) -> None:
    st.markdown(f'<div class="objective-heading"><span>OBJETIVO {number} · {escape(label.upper())}</span>'
                f'<p>{escape(OBJECTIVE_HELP[number - 1])}</p></div>', unsafe_allow_html=True)


def score_table(results: list[dict[str, object]]) -> pd.DataFrame:
    columns = {
        "titulo_analisis": "Título",
        "puntaje_general": "Puntaje general",
        "nivel_recomendacion": "Recomendación",
        "afinidad_O1": "Objetivo 1",
        "afinidad_O2": "Objetivo 2",
        "afinidad_O3": "Objetivo 3",
        "afinidad_O4": "Objetivo 4",
        "objetivo_mayor_afinidad": "Mayor afinidad",
    }
    table = pd.DataFrame(results, columns=list(columns))
    table.insert(0, "Recurso", [article_resource(row) for row in results])
    for field in ("puntaje_general", "afinidad_O1", "afinidad_O2", "afinidad_O3", "afinidad_O4"):
        table[field] = pd.to_numeric(table[field], errors="coerce").fillna(0.0)
    return table[["Recurso", *columns]].rename(columns=columns)


@st.dialog("Artículos de este motivo", width="large")
def show_reason_articles(reason: str, selected_rows: list[dict[str, object]]) -> None:
    matching = [row for row in selected_rows if reason_group(row) == reason]
    st.markdown(f"**Motivo:** {reason}")
    st.caption(f"{len(matching)} artículos dentro de los niveles de recomendación seleccionados.")
    st.dataframe(score_table(matching), hide_index=True, width="stretch", height=420,
                 column_config={"Recurso": st.column_config.LinkColumn(display_text="Abrir ↗", width=105)})
    st.download_button("↓ Exportar estos artículos CSV", csv_bytes(matching),
                       file_name="articulos_del_motivo.csv", mime="text/csv",
                       type="primary", use_container_width=True)


def render_home() -> None:
    file_state = tuple((name, path.stat().st_mtime_ns, path.stat().st_size)
                       for name, path in FILES.items())
    summary = cached_project_summary(file_state)
    scopus_src = f"data:image/png;base64,{base64.b64encode(SCOPUS_LOGO.read_bytes()).decode()}"
    wos_src = f"data:image/png;base64,{base64.b64encode(WOS_LOGO.read_bytes()).decode()}"
    flow_wide = f"data:image/svg+xml;base64,{base64.b64encode(flow_svg(summary).encode('utf-8')).decode()}"
    flow_narrow = f"data:image/svg+xml;base64,{base64.b64encode(flow_svg(summary, narrow=True).encode('utf-8')).decode()}"

    st.markdown(f"""
    <div class="research-header">
      <div class="report-kicker">REVISIÓN SISTEMÁTICA EN DESARROLLO · UTPL</div>
      <h1>Inteligencia artificial para la clasificación del cáncer de mama mediante termografía</h1>
      <p>El artículo científico plantea una revisión sistemática guiada por PRISMA 2020. Examina
      <b>bases de datos</b>, <b>preparación de imágenes</b>, <b>modelos de aprendizaje automático y profundo</b>
      y <b>evaluación de resultados</b>; también contempla las implementaciones de software como tema complementario.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<h2 class="report-section">Fuentes de datos</h2>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        with st.container(key="source_scopus"):
            st.markdown(f'<div class="source-inner"><div class="logo-plaque"><img src="{scopus_src}" alt="Scopus"></div>'
                        f'<div><div class="source-name">Scopus</div><div class="source-detail">{summary["scopus"]} registros · SC1.csv</div>'
                        '<div class="source-download">Descargar archivo ↓</div></div></div>',
                        unsafe_allow_html=True)
            download_file("↓ Descargar archivo Scopus", FILES["scopus"], "dl_scopus")
    with right:
        with st.container(key="source_wos"):
            st.markdown(f'<div class="source-inner"><div class="logo-plaque"><img src="{wos_src}" alt="Web of Science"></div>'
                        f'<div><div class="source-name">Web of Science</div><div class="source-detail">{summary["wos"]} registros · WS1.xls</div>'
                        '<div class="source-download">Descargar archivo ↓</div></div></div>',
                        unsafe_allow_html=True)
            download_file("↓ Descargar archivo Web of Science", FILES["wos"], "dl_wos")

    st.markdown(f"""
    <picture class="flow-graphic">
      <source media="(max-width: 700px)" srcset="{flow_narrow}">
      <img src="{flow_wide}" alt="Flujo: {summary['scopus']} registros de Scopus y {summary['wos']} de Web of Science; se retiran {summary['pairs_fused']} duplicados y {summary['screened_out']} registros fuera del tema. Quedan {summary['final_rows']} artículos.">
    </picture>
    """, unsafe_allow_html=True)
    st.caption(f"Tras deduplicar quedaron {summary['deduplicated_rows']} registros. Se apartaron {summary['screened_out']} que no cumplen el filtro textual de termografía mamaria; los {summary['final_rows']} restantes pasan al análisis de objetivos.")

    with st.container(key="dataset_card"):
        st.markdown(f"""
        <div class="dataset-content">
          <div class="dataset-icon">▦</div>
          <div><div class="dataset-eyebrow">BASE LISTA PARA EXPLORAR</div>
          <h2>Dataset final filtrado</h2>
          <p>{summary['final_rows']} artículos · {summary['final_columns']} columnas bibliográficas.<br>
          El análisis añade {summary['analysis_columns']} columnas de puntajes y recomendaciones: {summary['analyzed_columns']} en total.</p></div>
        </div>
        """, unsafe_allow_html=True)
        download_col, start_col = st.columns(2)
        with download_col:
            download_file(f"↓ Descargar dataset final ({summary['final_rows']})", FILES["final"], "dl_final")
        with start_col:
            if st.button("Comenzar análisis →", type="primary", use_container_width=True):
                st.session_state["view"] = "results"
                st.rerun()


st.set_page_config(page_title="Brújula Bibliográfica", layout="wide")
if st.session_state.get("chart_defaults_version") != 2:
    for chart_key, default_view in CHART_DEFAULTS.items():
        st.session_state[f"{chart_key}_chart"] = default_view
    st.session_state["chart_defaults_version"] = 2
st.markdown("""
<style>
.stApp {background:light-dark(#e9f0f2,#0a121a) !important;}
.block-container {max-width:1080px; margin:1.1rem auto 2rem; padding:1.6rem 2rem 2.2rem !important;
  background:light-dark(#ffffff,#111f29); border:1px solid light-dark(#ccdce0,#29404a);
  border-radius:24px; box-shadow:0 18px 50px light-dark(rgba(31,64,75,.11),rgba(0,0,0,.25));}
.research-header {padding:.35rem 0 1rem; border-bottom:1px solid light-dark(#cbdde0,#34515a);}
.report-kicker,.dataset-eyebrow {font-size:.71rem; font-weight:800; letter-spacing:.12em;
  color:light-dark(#087b71,#79dbc8);}
.research-header h1 {font-size:clamp(1.7rem,3.2vw,2.25rem); line-height:1.16; font-weight:650;
  margin:.55rem 0 .75rem; max-width:930px;}
.research-header p {font-size:1rem; line-height:1.52; margin:0; max-width:900px; opacity:.86;}
.report-section {font-size:1.18rem; margin:1.3rem 0 .45rem;}
.st-key-source_scopus,.st-key-source_wos {position:relative; border-radius:16px; padding:.8rem;
  min-height:91px; border:1px solid light-dark(#dfbca5,#76523e); cursor:pointer;
  box-shadow:0 5px 15px light-dark(rgba(31,64,75,.07),rgba(0,0,0,.12));
  transition:transform .15s ease,border-color .15s ease,box-shadow .15s ease;}
.st-key-source_scopus {background:linear-gradient(110deg,light-dark(#fff0e4,#3e2d29),light-dark(#fff9f3,#292c30));}
.st-key-source_wos {background:linear-gradient(110deg,light-dark(#eaf1ff,#213a50),light-dark(#f7f9ff,#242f3b));
  border-color:light-dark(#b8ccec,#4b7496);}
.st-key-source_scopus:hover,.st-key-source_wos:hover {transform:translateY(-2px);border-color:#69c9bd;}
.st-key-source_scopus:focus-within,.st-key-source_wos:focus-within {outline:2px solid #69c9bd;}
.source-inner {display:flex; align-items:center; gap:.85rem;}
.logo-plaque {background:#fff; border-radius:10px; width:128px; height:48px; display:flex;
  justify-content:center; align-items:center; flex:none; padding:7px;}
.logo-plaque img {max-width:100%; max-height:100%; object-fit:contain;}
.source-name {font-size:1.05rem; font-weight:750; line-height:1.1;}
.source-detail {font-size:.76rem; opacity:.75; margin-top:.25rem;}
.source-download {font-size:.75rem; font-weight:700; color:light-dark(#087b71,#79dbca); margin-top:.35rem;}
.st-key-source_scopus .st-key-dl_scopus,.st-key-source_wos .st-key-dl_wos {
  position:absolute !important; inset:0 !important; width:100% !important; height:100% !important; z-index:2;}
.st-key-source_scopus [data-testid="stDownloadButton"],.st-key-source_wos [data-testid="stDownloadButton"] {
  width:100%; height:100%;}
.st-key-source_scopus button,.st-key-source_wos button {position:absolute; inset:0; width:100%; height:100%;
  opacity:0; z-index:2; cursor:pointer;}
.flow-graphic {display:block; margin:1rem 0;}
.flow-graphic img {display:block; width:100%; height:auto; border-radius:17px;}
.st-key-dataset_card {background:linear-gradient(120deg,light-dark(#e5f6f0,#173e40),light-dark(#f3fbf7,#203a3b));
  border:1px solid light-dark(#9fcfc1,#548e85); border-radius:19px; padding:1.1rem 1.25rem;
  box-shadow:0 9px 24px light-dark(rgba(31,100,81,.10),rgba(0,0,0,.16));}
.dataset-content {display:flex; align-items:flex-start; gap:.9rem; margin-bottom:.65rem;}
.dataset-icon {display:grid; place-items:center; width:48px; height:48px; flex:none; border-radius:12px;
  background:#38a48e; color:white; font-size:1.65rem;}
.dataset-eyebrow {color:light-dark(#087b71,#79dbc8)}.dataset-content h2 {font-size:1.35rem; margin:.2rem 0 .3rem;}
.dataset-content p {font-size:.9rem; opacity:.8; line-height:1.4; margin:0;}
.st-key-results_header {position:relative; margin:.55rem 0 1.15rem; padding:1.15rem 1.35rem;
  border-left:4px solid #3eb39e; border-radius:0 15px 15px 0;
  background:linear-gradient(110deg,light-dark(#e4f5f0,#193d41),light-dark(#f1f7fc,#1d3440));
  border-top:1px solid light-dark(#c7e4dc,#315b59);
  border-right:1px solid light-dark(#c7e4dc,#315b59);
  border-bottom:1px solid light-dark(#c7e4dc,#315b59);}
.results-kicker {font-size:.7rem; font-weight:800; letter-spacing:.14em; color:light-dark(#087b71,#7bdfcb);}
.results-heading h1 {font-size:clamp(1.7rem,3vw,2.25rem); line-height:1.16; margin:.3rem 0 .5rem; padding-right:170px;}
.results-heading p {font-size:.96rem; line-height:1.5; margin:0; opacity:.9;}
.st-key-results_header .st-key-back_to_report {position:absolute; top:.9rem; right:1.1rem; width:158px; z-index:2;}
.st-key-back_to_report button {font-size:.82rem; white-space:normal;}
button[kind="primary"] {background:#2fa88f !important; border-color:#2fa88f !important; color:#fff !important;}
button[kind="primary"]:hover {background:#238e79 !important; border-color:#238e79 !important;}
.st-key-export_results {display:flex; justify-content:flex-end; margin-left:auto !important;}
.st-key-export_results button {background:#e9854c !important; border-color:#e9854c !important;
  color:#fff !important; font-weight:750 !important; font-size:.84rem !important; white-space:nowrap;}
.st-key-export_results button:hover {background:#d9733d !important; border-color:#d9733d !important;}
.keyword-network {overflow-x:auto; border-radius:18px; border:1px solid light-dark(#b6d6d0,#43736b);}
.keyword-network img {display:block; width:100%; min-width:800px; height:auto;}
.evidence-cards {display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.7rem; margin:.7rem 0 1rem;}
.evidence-card {padding:.85rem 1rem; border-radius:13px; border:1px solid rgba(107,201,189,.3);
  background:linear-gradient(135deg,light-dark(#e5f4f2,#20484a),light-dark(#f2f7fb,#233947));
  border-color:light-dark(#bfd9d8,#497473);}
.evidence-card-title {font-size:.86rem; font-weight:700; min-height:2.15rem; line-height:1.25;}
.evidence-card-count {font-size:1.55rem; font-weight:800; color:light-dark(#075d58,#dff9ef); margin:.3rem 0 .5rem;}
.evidence-card-count span {font-size:.75rem; font-weight:500; color:light-dark(#41656a,#b8d6d2);}
.evidence-meter {height:6px; border-radius:9px; background:rgba(133,184,186,.19); overflow:hidden;}
.evidence-meter div {height:100%; border-radius:9px; background:#55c9ae;}
.objective-heading {border-left:4px solid #e9854c; padding:.7rem 1rem; margin:.45rem 0 1rem;
  border-radius:0 12px 12px 0; background:rgba(233,133,76,.12);}
.objective-heading span {font-size:.72rem; font-weight:800; letter-spacing:.11em;
  color:light-dark(#a34d22,#ffc091);}
.objective-heading p {font-size:.94rem; line-height:1.45; margin:.32rem 0 0;}
.st-key-scope_hint {border:1px solid light-dark(#b6d8d4,#356c69); border-radius:12px;
  background:light-dark(#ecf8f6,#193b3e); padding:.35rem .7rem; margin-bottom:.8rem;}
.st-key-scope_hint p {font-size:.87rem; margin:.35rem 0;}
.st-key-dismiss_scope button {border:none !important; background:transparent !important;
  font-size:1.2rem !important; padding:0 .25rem !important; min-height:1.5rem;}
@media (max-width:700px) {
  .block-container {margin:.5rem .3rem 1rem; padding:1rem !important; border-radius:17px;}
  .research-header h1 {font-size:1.72rem;}
  .research-header p {font-size:.92rem;}
  .st-key-source_scopus,.st-key-source_wos {min-height:74px;}
  .st-key-results_header {padding:.9rem 1rem;}.results-heading p {font-size:.9rem;}
  .results-heading h1 {padding-right:0; margin-top:1.2rem;}
  .st-key-results_header .st-key-back_to_report {top:.55rem; right:.8rem; width:139px;}
}
</style>
""", unsafe_allow_html=True)

if st.session_state.get("view", "home") == "home":
    render_home()
    st.stop()

with st.container(key="results_header"):
    st.markdown("""
    <div class="results-heading">
      <div class="results-kicker">ARTÍCULOS DE LA REVISIÓN</div>
      <h1>Resultados del análisis</h1>
      <p>Los títulos, resúmenes y palabras clave se compararon con el tema y los cuatro objetivos de la investigación.
      La <b>recomendación general</b> agrupa los artículos en afinidad alta, media o baja.
      Los <b>puntajes por objetivo</b> ayudan a identificar qué trabajos pueden aportar a cada pregunta de investigación.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("← Volver al informe", key="back_to_report"):
        st.session_state["view"] = "home"
        st.rerun()
contents = PROJECT_RESULTS.read_bytes()
source_hash = str(PROJECT_RESULTS.stat().st_mtime_ns)
try:
    headers, rows = cached_load(PROJECT_RESULTS.name, contents)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
results = rows

counts = Counter(row["nivel_recomendacion"] for row in results)
if st.session_state.get("level_source_hash") != source_hash:
    st.session_state["level_source_hash"] = source_hash
    for label in LEVELS:
        st.session_state[f"show_level_{label}"] = True
st.markdown("**Selecciona los niveles de recomendación que quieres consultar**")
level_controls = st.columns(4)
selected_levels = []
for box, label in zip(level_controls, LEVELS):
    key = f"show_level_{label}"
    if key not in st.session_state:
        st.session_state[key] = True
    count = counts.get(label, 0)
    if box.checkbox(f"{label} · {count} ({count / len(results) * 100:.1f} %)", key=key):
        selected_levels.append(label)

selected_rows = [row for row in results if row["nivel_recomendacion"] in selected_levels]
sort_tab, analyze_tab = st.tabs(["Tabla de resultados", "Análisis de resultados"])

with sort_tab:
    filtered = sorted(selected_rows,
                      key=lambda row: float(row["puntaje_general"] or 0), reverse=True)
    instructions, export_area = st.columns([4, 1.5], vertical_alignment="bottom")
    with instructions:
        st.caption(f"{len(filtered)} artículos. Haz clic en un encabezado para ordenar; repite el clic para invertir el orden.")
    with export_area:
        st.download_button("↓ Exportar resultados CSV",
                           csv_bytes(filtered) if filtered else b"",
                           file_name="analisis_seleccionado.csv", mime="text/csv",
                           disabled=not filtered, type="primary", key="export_results")
    table = score_table(filtered) if filtered else score_table(results[:0])
    selection = st.dataframe(table, hide_index=True, width="stretch", height=560,
                 on_select="rerun", selection_mode="single-row",
                 column_config={
                     "Recurso": st.column_config.LinkColumn(display_text="Abrir ↗", width=105),
                     "Título": st.column_config.TextColumn(width=310),
                     "Puntaje general": st.column_config.NumberColumn(format="%.1f %%", width=115,
                          help="Prioridad de lectura calculada a partir de afinidad temática y señales del título y resumen."),
                     "Recomendación": st.column_config.TextColumn(width=120, help=RECOMMENDATION_HELP),
                     **{f"Objetivo {i}": st.column_config.NumberColumn(format="%.1f %%", width=95,
                          help=OBJECTIVE_HELP[i - 1])
                        for i in range(1, 5)},
                     "Mayor afinidad": st.column_config.TextColumn(width=115,
                          help="Objetivo con el puntaje de afinidad más alto para este artículo."),
                 })
    picked_indices = selection.selection.rows
    if picked_indices and picked_indices[0] < len(filtered):
        picked = filtered[picked_indices[0]]
        st.markdown(f"**{picked['titulo_analisis']}** · [Abrir recurso ↗]({article_resource(picked)})")
        st.write(f"Recomendación: **{picked['nivel_recomendacion']}** · Motivo: {picked['motivo_recomendacion']}")

with analyze_tab:
    if not selected_rows:
        st.info("Marca al menos una categoría de recomendación para analizar resultados.")
    else:
        report = cached_overview(selected_rows, ANALYTICS_VERSION)
        records = report["records"]
        analyzed_count = ("todos los artículos seleccionados" if len(records) == len(results)
                          else f"{len(records)} artículos seleccionados")
        st.caption(f"Menciones detectadas en título, resumen y palabras clave de {analyzed_count}. Un artículo puede aparecer en varias categorías. Estos conteos no sustituyen la extracción manual del texto completo.")
        network = report["keyword_network"]
        with st.expander("Palabras clave más frecuentes", expanded=True):
            if network["nodes"]:
                graphic = keyword_graph_svg(network)
                graphic_src = base64.b64encode(graphic.encode("utf-8")).decode("ascii")
                st.markdown(f'<div class="keyword-network"><img src="data:image/svg+xml;base64,{graphic_src}" alt="Red de palabras clave frecuentes y sus conexiones"></div>',
                            unsafe_allow_html=True)
                st.caption("Cada nodo indica cuántos artículos contienen la palabra clave. Una línea conecta términos que aparecen juntos en al menos dos registros; cuanto más gruesa, mayor coocurrencia. La conexión no implica que sean sinónimos.")
            else:
                st.info("Los registros seleccionados no contienen palabras clave separadas por punto y coma.")
        with st.expander("Motivos de la recomendación general"):
            reasons = report["reasons"]
            if reasons:
                st.caption("Selecciona un motivo para ver sus artículos y exportarlos en CSV.")
                reason_table = pd.DataFrame([
                    {"Motivo": reason, "Artículos": count,
                     "% de seleccionados": round(100 * count / len(records), 1)}
                    for reason, count in reasons
                ])
                reason_selection = st.dataframe(reason_table, hide_index=True,
                                                width="stretch", height=320,
                                                on_select="rerun", selection_mode="single-row",
                                                key=f"reason_table_{source_hash}_{'_'.join(selected_levels)}")
                picked_reasons = reason_selection.selection.rows
                if picked_reasons:
                    selected_reason = reasons[picked_reasons[0]][0]
                    marker = (source_hash, tuple(selected_levels), selected_reason)
                    if st.session_state.get("reason_dialog_marker") != marker:
                        st.session_state["reason_dialog_marker"] = marker
                        show_reason_articles(selected_reason, selected_rows)
                else:
                    st.session_state.pop("reason_dialog_marker", None)
            else:
                st.info("El archivo no contiene motivos de recomendación.")
        objective_tabs = st.tabs(["Objetivo 1 · Datos", "Objetivo 2 · Estrategias",
                                  "Objetivo 3 · Modelos", "Objetivo 4 · Evaluación",
                                  "Objetivo 5 · Multimodal", "Objetivo 6 · XAI",
                                  "Objetivo 7 · Software"])
        with objective_tabs[0]:
            objective_heading(1, "Datos")
            if st.session_state.get("show_scope_hint", True):
                with st.container(key="scope_hint"):
                    hint_text, dismiss = st.columns([12, 1], vertical_alignment="center")
                    with hint_text:
                        st.markdown("Se analizan los registros que superaron el filtro textual de termografía mamaria. Mencionar otra tecnología no excluye un artículo que también cumpla ese criterio.")
                    with dismiss:
                        if st.button("×", key="dismiss_scope", help="Cerrar este aviso"):
                            st.session_state["show_scope_hint"] = False
                            st.rerun()
            evidence_chart("Bases de datos nombradas", report["datasets"], records,
                           "evidence_datasets",
                           "Lista de nombres reconocidos; el conteo es de artículos que los mencionan, no de bases únicas ni de uso confirmado.")
            evidence_chart("Disponibilidad de los datos mencionada", report["access"], records,
                           "evidence_access",
                           "Una mención pública o restringida no prueba las condiciones de acceso de cada base. «No indicado» significa que no aparece una afirmación explícita en los campos disponibles.")
        with objective_tabs[1]:
            objective_heading(2, "Estrategias")
            evidence_chart("Preparación y aumento de imágenes", report["preparation"], records,
                           "evidence_preparation",
                           "Las categorías se superponen: un artículo puede mencionar varias estrategias.")
        with objective_tabs[2]:
            objective_heading(3, "Modelos")
            evidence_chart("Modelos y familias de IA mencionados", report["models"], records,
                           "evidence_models",
                           "Una mención puede corresponder al método propio, una comparación o antecedentes; verifica el texto completo antes de atribuir uso.")
            evidence_chart("Tipos de clasificación mencionados", report["classification"], records,
                           "evidence_classification")
            evidence_chart("Herramientas de implementación mencionadas", report["tools"], records,
                           "evidence_tools")
        with objective_tabs[3]:
            objective_heading(4, "Evaluación")
            evidence_chart("Métricas de evaluación mencionadas", report["metrics"], records,
                           "evidence_metrics")
            evidence_chart("Limitaciones metodológicas mencionadas", report["limitations"], records,
                           "evidence_limitations",
                           "Se cuentan limitaciones expresadas en los campos disponibles; la ausencia de mención no implica ausencia del problema.")
            st.markdown("#### Métricas mencionadas por artículo")
            st.caption("✓ indica que la métrica aparece en el título, resumen o palabras clave. Una mención no confirma que el estudio la haya utilizado.")
            metric_sets = {name: set(indices) for name, indices in report["metrics"].items()}
            metric_rows = [
                {"Recurso": record["resource"], "Título": record["title"],
                 **{name: index in indices for name, indices in metric_sets.items()}}
                for index, record in enumerate(records)
            ]
            st.dataframe(pd.DataFrame(metric_rows), hide_index=True,
                         width="stretch", height=520,
                         column_config={
                             "Recurso": st.column_config.LinkColumn(display_text="Abrir ↗", width=105),
                             "Título": st.column_config.TextColumn(width="large"),
                             **{name: st.column_config.CheckboxColumn(width="small") for name in metric_sets},
                         })
        for upcoming, name in zip(objective_tabs[4:], ("Multimodal", "XAI", "Software")):
            with upcoming:
                st.markdown(f"### {name}")
                st.info("Próximamente")
