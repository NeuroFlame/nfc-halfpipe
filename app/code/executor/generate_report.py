"""Generate a static HTML results report for the HALFpipe federated analysis."""

_CSS = """\
:root{
  --bg:#ffffff;--bg3:#f1f5f9;--border:#e2e8f0;
  --text:#0f172a;--text2:#334155;--text3:#64748b;
  --header-bg:linear-gradient(135deg,#e0e9ff 0%,#f8fafc 100%);
  --header-border:#e2e8f0;
  --chip-bg:#f1f5f9;--chip-color:#475569;--chip-b:#6366f1;
  --card-bg:#ffffff;--th-bg:#f8fafc;
}
[data-theme="dark"]{
  --bg:#0f172a;--bg3:#0f172a;--border:#334155;
  --text:#e2e8f0;--text2:#cbd5e1;--text3:#64748b;
  --header-bg:linear-gradient(135deg,#1e1b4b 0%,#0f172a 100%);
  --header-border:#334155;
  --chip-bg:#1e293b;--chip-color:#94a3b8;--chip-b:#a5b4fc;
  --card-bg:#1e293b;--th-bg:#161f30;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:background .2s,color .2s;margin:1rem 0}
button{font-family:inherit}
.theme-toggle{position:fixed;top:2rem;right:1.25rem;z-index:999;background:var(--card-bg);border:1px solid var(--border);border-radius:999px;padding:.35rem .85rem;font-size:.8rem;font-weight:600;color:var(--text2);cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.theme-toggle:hover{background:var(--bg3)}
.page-header{background:var(--header-bg);border-bottom:1px solid var(--header-border);padding:2rem 2.5rem;padding-right:8rem}
.page-header h1{font-size:1.7rem;font-weight:700;color:var(--text);letter-spacing:-.02em}
.page-header p{color:var(--text3);margin-top:.35rem;font-size:.93rem}
.chips{display:flex;gap:.6rem;margin-top:1rem;flex-wrap:wrap}
.chip{background:var(--chip-bg);border:1px solid var(--border);border-radius:999px;padding:.25rem .75rem;font-size:.78rem;color:var(--chip-color)}
.chip b{color:var(--chip-b)}
.container{max-width:1400px;margin:0 auto;padding:2rem 0}
.section{margin-bottom:3rem}
.section-title{font-size:.82rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text3);margin-bottom:1.1rem;padding-bottom:.5rem;border-bottom:1px solid var(--border)}
.kpi-row{display:flex;gap:.75rem;margin-bottom:1.2rem;flex-wrap:wrap}
.kpi-card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:.9rem 1.2rem;flex:1;min-width:140px}
.kpi-label{font-size:.72rem;color:var(--text3);text-transform:uppercase;letter-spacing:.07em}
.kpi-value{font-size:1.6rem;font-weight:700;color:var(--text);font-family:monospace}
.stat-card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:1rem}
.stat-card-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.stat-card-header{padding:.75rem 1rem;border-bottom:1px solid var(--border);display:flex;align-items:center}
.stat-card-title{font-weight:700;color:var(--text);font-size:.9rem;flex:1}
table.stat-table{width:100%;border-collapse:collapse;font-size:.8rem}
table.stat-table th{color:var(--text3);font-weight:600;padding:.45rem .85rem;text-align:right;background:var(--th-bg)}
table.stat-table th:first-child{text-align:left}
table.stat-table td{padding:.42rem .85rem;border-top:1px solid var(--border);text-align:right}
table.stat-table td:first-child{text-align:left}
.layout{display:flex;align-items:flex-start;padding:1.5rem 2rem 0}
.sidebar{width:190px;flex-shrink:0;position:sticky;top:1.5rem;max-height:calc(100vh - 3rem);overflow-y:auto;margin-right:1.5rem;transition:width .2s,opacity .2s,margin .2s}
.sidebar.hidden{width:0;opacity:0;overflow:hidden;margin-right:0;pointer-events:none}
.sidebar-inner{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:.6rem .5rem}
.sidebar-header{display:flex;align-items:center;justify-content:space-between;padding:.2rem .3rem .45rem;border-bottom:1px solid var(--border);margin-bottom:.4rem}
.sidebar-label{font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text3)}
.sidebar-toggle{background:none;border:none;cursor:pointer;font-size:.75rem;color:var(--text3);padding:.15rem .35rem;border-radius:5px}
.sidebar-toggle:hover{background:var(--bg3);color:var(--text)}
.main-content{flex:1;min-width:0}
.sidebar-peek{position:fixed;left:0;top:50%;transform:translateY(-50%);background:var(--card-bg);border:1px solid var(--border);border-left:none;border-radius:0 8px 8px 0;padding:.55rem .35rem;cursor:pointer;font-size:.72rem;color:var(--text3);display:none;z-index:200;writing-mode:vertical-rl}
.sidebar-peek.visible{display:block}
.nav-item{display:block;width:100%;padding:.4rem .65rem;border-radius:7px;font-size:.78rem;color:var(--text3);cursor:pointer;border:none;background:none;text-align:left;transition:background .12s,color .12s}
.nav-item:hover{background:var(--bg3);color:var(--text)}
.nav-item.active{background:rgba(99,102,241,.13);color:#6366f1;font-weight:600}
[data-theme="dark"] .nav-item.active{background:rgba(165,180,252,.1);color:#a5b4fc}
.tabs{display:flex;gap:.4rem;margin-bottom:1rem;flex-wrap:wrap}
.tab-btn{padding:.3rem .8rem;border-radius:999px;border:1px solid var(--border);font-size:.78rem;cursor:pointer;background:var(--chip-bg);color:var(--chip-color)}
.tab-btn.active{background:rgba(99,102,241,.13);color:#6366f1;border-color:#6366f1;font-weight:600}
[data-theme="dark"] .tab-btn.active{background:rgba(165,180,252,.1);color:#a5b4fc;border-color:#a5b4fc}
.bar-cell{width:160px;padding:0 .85rem}
.bar-inner{background:rgba(99,102,241,.2);border-radius:3px;height:7px;min-width:2px}"""

_JS = """\
function toggleTheme(){
  var d=document.documentElement;
  var isDark=d.getAttribute('data-theme')==='dark';
  d.setAttribute('data-theme',isDark?'light':'dark');
  document.getElementById('themeBtn').textContent=isDark?'🌙 Dark mode':'☀️ Light mode';
}
function toggleSidebar(){
  var s=document.getElementById('sidebar');
  var p=document.getElementById('sidebarPeek');
  var hidden=s.classList.toggle('hidden');
  p.classList.toggle('visible',hidden);
}
function switchTab(btn,panelId){
  document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.remove('active');});
  document.querySelectorAll('.tab-panel').forEach(function(p){p.style.display='none';});
  btn.classList.add('active');
  document.getElementById(panelId).style.display='';
}
var navItems=document.querySelectorAll('.nav-item[data-sec]');
var observer=new IntersectionObserver(function(entries){
  entries.forEach(function(e){
    if(e.isIntersecting){
      navItems.forEach(function(n){n.classList.remove('active');});
      var btn=document.querySelector('.nav-item[data-sec="'+e.target.id+'"]');
      if(btn)btn.classList.add('active');
    }
  });
},{rootMargin:'-40% 0px -40% 0px'});
document.querySelectorAll('.section[id]').forEach(function(s){observer.observe(s);});"""


def generate_html_report(site_name: str, global_results: dict) -> str:
    """
    Build a self-contained HTML report string from aggregated results.

    Parameters
    ----------
    site_name : str
        The NVFlare client name (e.g. "site1").
    global_results : dict
        The federated aggregation output from HALFpipeAggregator.aggregate().

    Returns
    -------
    str
        Complete, self-contained HTML document.
    """
    qc = global_results.get("qc_metadata", {})
    roi = global_results.get("roi_values", {})
    voxelwise = global_results.get("voxelwise_maps", {})

    total_subjects = qc.get("total_subjects", 0)
    n_sites = qc.get("n_sites", 0)
    mean_fd = qc.get("mean_mean_fd")
    mean_fd_perc = qc.get("mean_mean_fd_perc")
    site_summaries = qc.get("site_summaries", {})

    active_modes = []
    if qc:
        active_modes.append("qc_metadata")
    if roi:
        active_modes.append("roi_values")
    if voxelwise:
        active_modes.append("voxelwise_maps")

    sidebar_sections = [("sec-overview", "Site Overview"), ("sec-qc", "Quality Control")]
    if roi:
        sidebar_sections.append(("sec-roi", "ROI Values"))
    if voxelwise:
        sidebar_sections.append(("sec-voxelwise", "Voxelwise Maps"))

    sidebar_items = "".join(
        "<button class='nav-item' data-sec='" + sid + "' "
        "onclick=\"document.getElementById('" + sid + "').scrollIntoView({behavior:'smooth',block:'start'})\">"
        + _esc(label) + "</button>\n"
        for sid, label in sidebar_sections
    )

    chips_html = (
        "<div class='chip'>Site <b>" + _esc(site_name) + "</b></div>"
        + "<div class='chip'>Subjects <b>" + str(total_subjects) + "</b></div>"
        + "<div class='chip'>Sites <b>" + str(n_sites) + "</b></div>"
        + "".join("<div class='chip'>Mode <b>" + _esc(m) + "</b></div>" for m in active_modes)
    )

    fd_val = "{:.3f}".format(mean_fd) if mean_fd is not None else "—"
    fd_perc_val = "{:.1f}%".format(mean_fd_perc) if mean_fd_perc is not None else "—"
    fd_color = (
        "#dc2626" if mean_fd is not None and mean_fd > 0.5
        else "#16a34a" if mean_fd is not None and mean_fd <= 0.3
        else "#d97706"
    )

    kpi_cards = (
        "<div class='kpi-row'>"
        + _kpi("Total Subjects", str(total_subjects))
        + _kpi("Participating Sites", str(n_sites))
        + _kpi("Mean Framewise Displacement", fd_val, color=fd_color)
        + _kpi("FD % &gt; 0.5 mm", fd_perc_val)
        + "</div>"
    )

    qc_table_html = _build_qc_table(site_summaries)
    roi_html = _build_roi_section(roi) if roi else ""
    voxelwise_html = _build_voxelwise_section(voxelwise) if voxelwise else ""

    roi_block = (
        "<div class='section' id='sec-roi'>"
        "<div class='section-title'>ROI Values</div>"
        + roi_html + "</div>"
    ) if roi else ""

    voxelwise_block = (
        "<div class='section' id='sec-voxelwise'>"
        "<div class='section-title'>Voxelwise Maps</div>"
        + voxelwise_html + "</div>"
    ) if voxelwise else ""

    site_name_esc = _esc(site_name)
    n_sites_str = str(n_sites)

    parts = [
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n",
        "<meta charset='UTF-8'/>\n",
        "<meta name='viewport' content='width=device-width,initial-scale=1.0'/>\n",
        "<title>HALFpipe Federated fMRI — " + site_name_esc + "</title>\n",
        "<style>\n",
        _CSS,
        "\n</style>\n</head>\n<body>\n",
        "<button class='theme-toggle' onclick='toggleTheme()' id='themeBtn'>&#127769; Dark mode</button>\n",
        "<div class='layout'>",
        "<aside class='sidebar' id='sidebar'><div class='sidebar-inner'>",
        "<div class='sidebar-header'><span class='sidebar-label'>Sections</span>",
        "<button class='sidebar-toggle' onclick='toggleSidebar()'>&#x2715;</button></div>\n",
        sidebar_items,
        "</div></aside>",
        "<button class='sidebar-peek' id='sidebarPeek' onclick='toggleSidebar()'>Sections</button>",
        "<div class='main-content'>",
        "<div class='page-header'>",
        "<h1>HALFpipe Federated fMRI Analysis — " + site_name_esc + "</h1>",
        "<p>Federated fMRI preprocessing and feature extraction across "
        + n_sites_str + " participating sites</p>",
        "<div class='chips'>" + chips_html + "</div>",
        "</div>",  # page-header
        "<div class='container'>",
        "<div class='section' id='sec-overview'>",
        "<div class='section-title'>Site Overview</div>",
        kpi_cards,
        "</div>",
        "<div class='section' id='sec-qc'>",
        "<div class='section-title'>Quality Control</div>",
        qc_table_html,
        "</div>",
        roi_block,
        voxelwise_block,
        "</div>",  # container
        "</div>",  # main-content
        "</div>",  # layout
        "\n<script>\n",
        _JS,
        "\n</script>\n</body>\n</html>",
    ]
    return "".join(parts)


# ------------------------------------------------------------------ #
# HTML component builders                                              #
# ------------------------------------------------------------------ #

def _kpi(label: str, value: str, color: str = "var(--text)") -> str:
    return (
        "<div class='kpi-card'>"
        "<div class='kpi-label'>" + label + "</div>"
        "<div class='kpi-value' style='color:" + color + "'>" + value + "</div>"
        "</div>"
    )


def _build_qc_table(site_summaries: dict) -> str:
    if not site_summaries:
        return "<p style='color:var(--text3);font-size:.85rem'>No per-site QC data available.</p>"

    rows = ""
    for site in sorted(site_summaries):
        stats = site_summaries[site]
        n = stats.get("n_subjects", "—")
        fd = stats.get("mean_fd")
        fd_perc = stats.get("mean_fd_perc")
        fd_color = (
            "#dc2626" if fd is not None and fd > 0.5
            else "#16a34a" if fd is not None and fd <= 0.3
            else "#d97706"
        )
        fd_str = "<span style='font-family:monospace;color:" + fd_color + "'>{:.3f}</span>".format(fd) if fd is not None else "—"
        fd_perc_str = "{:.1f}%".format(fd_perc) if fd_perc is not None else "—"
        rows += (
            "<tr>"
            "<td>" + _esc(str(site)) + "</td>"
            "<td>" + str(n) + "</td>"
            "<td>" + fd_str + "</td>"
            "<td style='font-family:monospace'>" + fd_perc_str + "</td>"
            "</tr>"
        )

    return (
        "<div class='stat-card'><div class='stat-card-scroll'>"
        "<table class='stat-table'>"
        "<thead><tr>"
        "<th>Site</th><th>N Subjects</th><th>Mean FD (mm)</th><th>FD %</th>"
        "</tr></thead>"
        "<tbody>" + rows + "</tbody>"
        "</table></div></div>"
    )


def _build_roi_section(roi: dict) -> str:
    features = {k: v for k, v in roi.items() if not k.startswith("_") and isinstance(v, dict)}
    if not features:
        return "<p style='color:var(--text3);font-size:.85rem'>No ROI data available.</p>"

    tabs_html = ""
    panels_html = ""
    first = True
    for feature_name, parcels in sorted(features.items()):
        active_cls = " active" if first else ""
        display_style = "" if first else " style='display:none'"
        panel_id = "tab-" + feature_name
        tabs_html += (
            "<button class='tab-btn" + active_cls + "' "
            "onclick='switchTab(this,\"" + panel_id + "\")'>"
            + _esc(feature_name) + "</button>"
        )
        panels_html += (
            "<div class='tab-panel' id='" + panel_id + "'" + display_style + ">"
            + _build_roi_table(feature_name, parcels)
            + "</div>"
        )
        first = False

    return "<div class='tabs'>" + tabs_html + "</div>" + panels_html


def _build_roi_table(feature_name: str, parcels: dict) -> str:
    if not parcels:
        return ""

    values = [v for v in parcels.values() if isinstance(v, (int, float)) and v is not None]
    max_val = max(abs(v) for v in values) if values else 1.0

    rows = ""
    for parcel in sorted(parcels):
        val = parcels[parcel]
        if val is None:
            continue
        bar_pct = int(abs(val) / max_val * 100) if max_val else 0
        rows += (
            "<tr>"
            "<td>" + _esc(str(parcel)) + "</td>"
            "<td style='font-family:monospace'>{:.4f}</td>".format(val)
            + "<td class='bar-cell'>"
            "<div class='bar-inner' style='width:" + str(bar_pct) + "%'></div>"
            "</td>"
            "</tr>"
        )

    return (
        "<div class='stat-card'>"
        "<div class='stat-card-header'>"
        "<span class='stat-card-title'>" + _esc(feature_name) + " — parcel means</span>"
        "</div>"
        "<div class='stat-card-scroll'>"
        "<table class='stat-table'>"
        "<thead><tr>"
        "<th>Parcel</th><th>Mean Value</th><th>Distribution</th>"
        "</tr></thead>"
        "<tbody>" + rows + "</tbody>"
        "</table></div></div>"
    )


def _build_voxelwise_section(voxelwise: dict) -> str:
    n_sites = voxelwise.get("n_sites", "—")
    total_subjects = voxelwise.get("total_subjects", "—")

    if "meta_maps" in voxelwise:
        map_keys = list(voxelwise["meta_maps"].keys())
        note = "Meta-analysis maps produced ({} sites, {} subjects). Maps are in the output directory.".format(
            n_sites, total_subjects
        )
    else:
        map_keys = voxelwise.get("available_map_keys", [])
        note = "nibabel not available; maps were not combined. Individual site maps are in the output directory."

    if not map_keys:
        return "<p style='color:var(--text3);font-size:.85rem'>No voxelwise map data available.</p>"

    items = "".join("<li style='padding:.25rem 0'>" + _esc(str(k)) + "</li>" for k in map_keys)
    return (
        "<div class='stat-card'>"
        "<div class='stat-card-header'>"
        "<span class='stat-card-title'>Available map keys</span>"
        "<span style='font-size:.75rem;color:var(--text3)'>" + str(n_sites) + " sites · " + str(total_subjects) + " subjects</span>"
        "</div>"
        "<div style='padding:.85rem 1.2rem'>"
        "<p style='font-size:.8rem;color:var(--text3);margin-bottom:.65rem'>" + _esc(note) + "</p>"
        "<ul style='padding-left:1.2rem;color:var(--text2);font-size:.85rem;font-family:monospace'>"
        + items + "</ul></div></div>"
    )


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
