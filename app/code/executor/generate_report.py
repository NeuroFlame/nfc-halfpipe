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
.bar-inner{background:rgba(99,102,241,.2);border-radius:3px;height:7px;min-width:2px}
canvas{border-radius:6px}"""

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
    connectivity = global_results.get("connectivity", {})
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
    if connectivity:
        active_modes.append("atlas_connectivity")
    if voxelwise:
        active_modes.append("voxelwise_maps")

    sidebar_sections = [("sec-overview", "Site Overview"), ("sec-qc", "Quality Control")]
    if roi:
        sidebar_sections.append(("sec-roi", "ROI Values"))
    if connectivity:
        sidebar_sections.append(("sec-connectivity", "Connectivity"))
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
    connectivity_html = _build_connectivity_section(connectivity) if connectivity else ""
    voxelwise_html = _build_voxelwise_section(voxelwise) if voxelwise else ""

    roi_block = (
        "<div class='section' id='sec-roi'>"
        "<div class='section-title'>ROI Values</div>"
        + roi_html + "</div>"
    ) if roi else ""

    connectivity_block = (
        "<div class='section' id='sec-connectivity'>"
        "<div class='section-title'>Atlas Connectivity</div>"
        + connectivity_html + "</div>"
    ) if connectivity else ""

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
        connectivity_block,
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


def _resolve_networks(key: str, n_parcels: int):
    """
    Return the per-parcel network label list for a known atlas, or None.

    Priority:
      1. Exact key match (e.g. "connectivity_atlas-Schaefer200")
      2. Atlas name substring in key  (e.g. "neuromark_atlas-NeuroMark1")
      3. Parcel count fallback         (200 → Schaefer, 53 → NeuroMark)
    """
    if key in _PARCEL_NETWORKS:
        return _PARCEL_NETWORKS[key]
    # Substring match on atlas identifier embedded in the key
    if "Schaefer200" in key and n_parcels == 200:
        return _SCHAEFER_200_7NET
    if ("NeuroMark1" in key or "NeuroMark_1" in key) and n_parcels == 53:
        return _NEUROMARK_1_0_DOMAINS
    # Parcel-count fallback (less precise — only triggers for the exactly matching sizes)
    return _PARCEL_NETWORKS.get(n_parcels)


def _build_connectivity_section(connectivity: dict) -> str:
    """
    Render federated connectivity matrices as annotated interactive Canvas heatmaps.

    Each atlas card shows:
      - KPI stats (parcels, sites, subjects, mean off-diagonal r)
      - Blue→white→red heatmap with 12px colored network-annotation bands on the
        left and top axes (for known atlases: Schaefer 200-parcel 17-network and
        NeuroMark 1.0 53-component)
      - A network legend row below the heatmap

    Works for any matrix size; annotation bands appear only when the atlas is
    recognised by key name (atlas-Schaefer200, atlas-NeuroMark1) or parcel count.
    """
    import json

    matrices = connectivity.get("matrices", {})
    if not matrices:
        return "<p style='color:var(--text3);font-size:.85rem'>No connectivity data available.</p>"

    # ------------------------------------------------------------------ #
    # Shared JS: heatmap + annotation bands                               #
    # ------------------------------------------------------------------ #
    _JS_HEATMAP = """\
var _NET_COLORS={
  'Visual':'#781286','Somatomotor':'#4169e1','DorsAttn':'#00760e',
  'SalVentAttn':'#c43aff','Limbic':'#dcf8a4','Frontoparietal':'#e69422',
  'Default':'#cd3c14','Default Mode':'#cd3c14',
  'SubCortical':'#4d4d4d','Auditory':'#e84d8a','SensoriMotor':'#2166ac',
  'CogCtrl':'#1b7837','DMN':'#d6604d','Cerebellar':'#4dac26'
};
function _netColor(name){return _NET_COLORS[name]||'#94a3b8';}
function _getBlocks(nets){
  var blocks=[];var cur=nets[0];var s=0;
  for(var i=1;i<nets.length;i++){
    if(nets[i]!==cur){blocks.push({n:cur,s:s,e:i-1});cur=nets[i];s=i;}
  }
  blocks.push({n:cur,s:s,e:nets.length-1});
  return blocks;
}
function drawHeatmap(canvasId,data,networks){
  var canvas=document.getElementById(canvasId);
  if(!canvas)return;
  var n=data.length;
  var maxPx=400;
  var cell=Math.max(1,Math.floor(maxPx/n));
  var BAND=networks?12:0;
  canvas.width=BAND+n*cell;
  canvas.height=BAND+n*cell;
  if(n*cell<=maxPx)canvas.style.imageRendering='pixelated';
  var ctx=canvas.getContext('2d');
  // Draw matrix
  for(var i=0;i<n;i++){
    for(var j=0;j<n;j++){
      ctx.fillStyle=corrColor(data[i][j]);
      ctx.fillRect(BAND+j*cell,BAND+i*cell,cell,cell);
    }
  }
  if(!networks)return;
  // Draw annotation bands
  var blocks=_getBlocks(networks);
  blocks.forEach(function(b){
    var color=_netColor(b.n);
    var start=b.s*cell;
    var len=(b.e-b.s+1)*cell;
    // Left band (row axis)
    ctx.fillStyle=color;
    ctx.fillRect(0,BAND+start,BAND-1,len);
    // Top band (column axis)
    ctx.fillRect(BAND+start,0,len,BAND-1);
    // Network label in left band (rotated) if block is wide enough
    var blockPx=(b.e-b.s+1)*cell;
    if(blockPx>=18){
      ctx.save();
      ctx.translate(BAND-2,BAND+start+blockPx/2);
      ctx.rotate(-Math.PI/2);
      ctx.fillStyle='rgba(0,0,0,0.75)';
      ctx.font='bold '+(Math.min(9,blockPx/3))+'px sans-serif';
      ctx.textAlign='center';
      ctx.textBaseline='middle';
      var lbl=b.n.length>9?b.n.slice(0,8)+'…':b.n;
      ctx.fillText(lbl,0,0);
      ctx.restore();
    }
  });
  // Hairline separators between blocks
  ctx.strokeStyle='rgba(0,0,0,0.25)';
  ctx.lineWidth=1;
  blocks.forEach(function(b){
    if(b.s===0)return;
    var pos=BAND+b.s*cell-0.5;
    ctx.beginPath();ctx.moveTo(BAND,pos);ctx.lineTo(BAND+n*cell,pos);ctx.stroke();
    ctx.beginPath();ctx.moveTo(pos,BAND);ctx.lineTo(pos,BAND+n*cell);ctx.stroke();
  });
}
function corrColor(r){
  r=Math.max(-1,Math.min(1,isNaN(r)?0:r));
  var t=(r+1)/2;
  var r1,g1,b1,r2,g2,b2,f;
  if(t<=0.5){r1=37;g1=99;b1=235;r2=248;g2=250;b2=252;f=t*2;}
  else{r1=248;g1=250;b1=252;r2=220;g2=38;b2=38;f=(t-0.5)*2;}
  return'rgb('+Math.round(r1+(r2-r1)*f)+','+Math.round(g1+(g2-g1)*f)+','+Math.round(b1+(b2-b1)*f)+')';
}
"""

    cards = []
    heatmap_calls = []

    for idx, (key, entry) in enumerate(sorted(matrices.items())):
        n_parcels = entry.get("n_parcels", 0)
        n_sites   = entry.get("n_sites", "—")
        n_subjects = entry.get("total_subjects", "—")
        matrix = entry.get("mean_correlation_matrix", [])

        # Mean off-diagonal r
        mean_offdiag = None
        if matrix:
            total, count = 0.0, 0
            n = len(matrix)
            for i in range(n):
                for j in range(n):
                    if i != j and isinstance(matrix[i][j], (int, float)):
                        total += matrix[i][j]
                        count += 1
            if count > 0:
                mean_offdiag = round(total / count, 4)

        canvas_id = "heatmap_" + str(idx)

        # Look up network labels for known atlases
        nets = _resolve_networks(key, n_parcels)
        nets_json = json.dumps(nets, separators=(",", ":")) if nets else "null"

        compact = [[round(v, 4) if isinstance(v, float) else v for v in row] for row in matrix]
        matrix_json = json.dumps(compact, separators=(",", ":"))

        kpi_row = (
            "<div class='kpi-row'>"
            + _kpi("Parcels", str(n_parcels or "—"))
            + _kpi("Sites", str(n_sites))
            + _kpi("Subjects", str(n_subjects))
            + (_kpi("Mean Off-Diagonal r", "{:.4f}".format(mean_offdiag)) if mean_offdiag is not None else "")
            + "</div>"
        )

        # Correlation gradient legend
        corr_legend = (
            "<div style='display:flex;align-items:center;gap:.5rem;margin-top:.5rem;font-size:.72rem;color:var(--text3)'>"
            "<span style='display:inline-block;width:40px;height:9px;"
            "background:linear-gradient(to right,#2563eb,#f8fafc,#dc2626);border-radius:3px'></span>"
            "<span>−1.0</span><span style='flex:1;text-align:center'>correlation</span><span>+1.0</span>"
            "</div>"
        )

        # Network legend chips
        net_legend = ""
        if nets:
            seen: list = []
            for name in nets:
                if name not in seen:
                    seen.append(name)
            chips = "".join(
                "<span style='display:inline-flex;align-items:center;gap:.3rem;font-size:.7rem;"
                "background:var(--chip-bg);border:1px solid var(--border);border-radius:999px;"
                "padding:.15rem .55rem'>"
                "<span style='display:inline-block;width:8px;height:8px;border-radius:50%;"
                "background:" + _NETWORK_COLORS.get(nm, "#94a3b8") + "'></span>"
                + _esc(nm)
                + "</span>"
                for nm in seen
            )
            net_legend = (
                "<div style='display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.65rem'>"
                + chips + "</div>"
            )

        card = (
            "<div class='stat-card' style='margin-bottom:1rem'>"
            "<div class='stat-card-header'>"
            "<span class='stat-card-title'>" + _esc(str(key)) + "</span>"
            "<span style='font-size:.75rem;color:var(--text3)'>"
            + str(n_parcels or "—") + " × " + str(n_parcels or "—") + " correlation matrix</span>"
            "</div>"
            "<div style='padding:.85rem 1.2rem'>"
            + kpi_row
            + "<div style='overflow-x:auto;margin-top:.75rem'>"
            "<canvas id='" + canvas_id + "' style='max-width:100%;display:block;"
            "border:1px solid var(--border);border-radius:6px'>"
            "Your browser does not support canvas.</canvas>"
            "</div>"
            + corr_legend
            + net_legend
            + "</div></div>"
        )
        cards.append(card)
        heatmap_calls.append(
            "drawHeatmap('" + canvas_id + "'," + matrix_json + "," + nets_json + ");"
        )

    script = (
        "<script>"
        + _JS_HEATMAP
        + "window.addEventListener('load',function(){"
        + "".join(heatmap_calls)
        + "});</script>"
    )
    return "".join(cards) + script


# ------------------------------------------------------------------ #
# Atlas network label tables                                          #
# ------------------------------------------------------------------ #

_NETWORK_COLORS = {
    # Schaefer 17-network → 7-network colours (Yeo-convention)
    "Visual":         "#781286",
    "Somatomotor":    "#4169e1",
    "DorsAttn":       "#00760e",
    "SalVentAttn":    "#c43aff",
    "Limbic":         "#dcf8a4",
    "Frontoparietal": "#e69422",
    "Default":        "#cd3c14",
    "Default Mode":   "#cd3c14",
    # NeuroMark 1.0 domain colours
    "SubCortical":    "#4d4d4d",
    "Auditory":       "#e84d8a",
    "SensoriMotor":   "#2166ac",
    "CogCtrl":        "#1b7837",
    "DMN":            "#d6604d",
    "Cerebellar":     "#4dac26",
}

# Schaefer 2018 200-parcel 17-network → 7 broad networks
# Derived from the templateflow MNI6Asym dseg.tsv (index 1-200 in order)
_SCHAEFER_200_7NET = (
    ["Visual"] * 12
    + ["Somatomotor"] * 16
    + ["DorsAttn"] * 11
    + ["SalVentAttn"] * 11
    + ["Limbic"] * 6
    + ["Frontoparietal"] * 18
    + ["Default"] * 26
    # RH
    + ["Visual"] * 12
    + ["Somatomotor"] * 18
    + ["DorsAttn"] * 11
    + ["SalVentAttn"] * 15
    + ["Limbic"] * 8
    + ["Frontoparietal"] * 19
    + ["Default"] * 17
)

# NeuroMark fMRI 1.0 — 53 components in 7 functional domains
# Du et al. (2020) NeuroImage:Clinical 28:102375
_NEUROMARK_1_0_DOMAINS = (
    ["SubCortical"] * 5
    + ["Auditory"] * 3
    + ["SensoriMotor"] * 8
    + ["Visual"] * 10
    + ["CogCtrl"] * 13
    + ["DMN"] * 9
    + ["Cerebellar"] * 5
)

# Lookup: atlas key (from connectivity matrices dict) → parcel network list
# Also keyed by n_parcels as integer fallback
_PARCEL_NETWORKS: dict = {
    # Schaefer 200-parcel — exact key emitted by HALFpipe
    "connectivity_atlas-Schaefer200": _SCHAEFER_200_7NET,
    # NeuroMark — feature name is "neuromark", atlas tag is "NeuroMark1"
    # so HALFpipe produces key "neuromark_atlas-NeuroMark1"
    "neuromark_atlas-NeuroMark1":     _NEUROMARK_1_0_DOMAINS,
    "neuromark_atlas-NeuroMark1.0":   _NEUROMARK_1_0_DOMAINS,
    # Also cover a user who named the feature "connectivity"
    "connectivity_atlas-NeuroMark1":  _NEUROMARK_1_0_DOMAINS,
    "connectivity_atlas-NeuroMark1.0": _NEUROMARK_1_0_DOMAINS,
    # Integer fallback (parcel count is unique for each atlas)
    200: _SCHAEFER_200_7NET,
    53:  _NEUROMARK_1_0_DOMAINS,
}


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
