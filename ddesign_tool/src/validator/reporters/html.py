"""
validator/reporters/html.py — HTML 可视化报告
"""

from __future__ import annotations

import os
from typing import List

from _logging import get_logger

from ..engine import ModReport, ValidationReport

_log = get_logger(__name__)
_SEVERITY_CLASS = {0: "error", 1: "fail", 2: "warn", 3: "pass"}
_SEVERITY_LABEL = {0: "ERROR", 1: "FAIL", 2: "WARN", 3: "PASS"}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mod Validator Report</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:#1e1e1e;color:#d4d4d4;padding:20px}}
h1{{color:#fff;margin-bottom:5px}}
.summary{{display:flex;gap:20px;margin:20px 0;flex-wrap:wrap}}
.summary-card{{background:#2d2d2d;border-radius:8px;padding:16px 24px;min-width:120px}}
.summary-card .num{{font-size:28px;font-weight:bold}}
.summary-card .label{{font-size:12px;color:#888;margin-top:4px}}
.progress-bar{{background:#333;border-radius:4px;height:24px;overflow:hidden;margin:10px 0}}
.mod-card{{background:#2d2d2d;border-radius:8px;margin:12px 0;overflow:hidden}}
.mod-header{{padding:12px 16px;display:flex;justify-content:space-between;align-items:center;cursor:pointer}}
.mod-header.healthy{{border-left:4px solid #4caf50}}
.mod-header.unhealthy{{border-left:4px solid #f44336}}
.mod-name{{font-weight:bold;font-size:15px}}
.mod-stats{{font-size:13px;color:#888}}
.result-list{{padding:0 16px 12px}}
.result-row{{display:flex;align-items:flex-start;gap:10px;padding:6px 0;border-top:1px solid #333;font-size:13px}}
.result-icon{{width:60px;text-align:center;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:bold;flex-shrink:0}}
.result-icon.pass{{background:#1b3a1b;color:#4caf50}}
.result-icon.warn{{background:#3a3510;color:#ff9800}}
.result-icon.fail{{background:#3a1b1b;color:#f44336}}
.result-icon.error{{background:#3a1b1b;color:#f44336}}
.result-detail{{white-space:pre-wrap;font-family:Consolas,monospace;font-size:12px;color:#888;margin-top:4px;margin-left:70px}}
.filter-bar{{display:flex;gap:8px;margin:10px 0}}
.filter-btn{{background:#333;border:none;color:#aaa;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:13px}}
.filter-btn.active{{background:#007acc;color:#fff}}
.timestamp{{color:#666;font-size:12px}}
</style>
</head>
<body>
<h1>Mod Validator Report</h1>
<p class="timestamp">Generated: {timestamp}</p>

<div class="filter-bar">
  <button class="filter-btn active" onclick="filter('all')">All ({total_checks})</button>
  <button class="filter-btn" onclick="filter('fail')">Fail/Error ({total_fail})</button>
  <button class="filter-btn" onclick="filter('warn')">Warn ({total_warn})</button>
</div>

<div class="summary">
  <div class="summary-card"><div class="num" style="color:#4caf50">{healthy_mods}</div><div class="label">Healthy Mods</div></div>
  <div class="summary-card"><div class="num" style="color:#f44336">{unhealthy_mods}</div><div class="label">Issues</div></div>
  <div class="summary-card"><div class="num">{total_checks}</div><div class="label">Total Checks</div></div>
  <div class="summary-card"><div class="num">{duration_ms:.0f}ms</div><div class="label">Duration</div></div>
</div>

<div class="progress-bar">
  <div style="width:{pass_pct}%;background:#4caf50;height:100%;float:left"></div>
  <div style="width:{warn_pct}%;background:#ff9800;height:100%;float:left"></div>
  <div style="width:{fail_pct}%;background:#f44336;height:100%;float:left"></div>
</div>

{mod_cards}

<script>
function filter(type) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.mod-card').forEach(card => {{
    if (type === 'all') {{ card.style.display = ''; return; }}
    const hasIssue = card.querySelector('.result-icon.' + type);
    card.style.display = hasIssue ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


class HTMLReporter:
    """HTML 可视化报告生成器"""

    def save(self, reports: List[ModReport], filepath: str):
        """保存 HTML 报告"""
        from datetime import datetime

        total = ValidationReport(reports=reports, total_mods=len(reports))
        for r in reports:
            total.healthy_mods += 1 if r.healthy else 0
            total.total_checks += r.total
            total.total_passed += r.passed
            total.total_warnings += r.warnings
            total.total_failures += r.failures
            total.total_errors += r.errors

        unhealthy = total.total_mods - total.healthy_mods
        total_fail = total.total_failures + total.total_errors
        total_issues = total.total_checks

        if total_issues > 0:
            pass_pct = total.total_passed / total_issues * 100
            warn_pct = total.total_warnings / total_issues * 100
            fail_pct = total_fail / total_issues * 100
        else:
            pass_pct = warn_pct = fail_pct = 0

        mod_cards = "\n".join(self._render_mod_card(r) for r in reports)

        html = HTML_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_checks=total.total_checks,
            total_fail=total_fail,
            total_warn=total.total_warnings,
            healthy_mods=total.healthy_mods,
            unhealthy_mods=unhealthy,
            duration_ms=total.duration_ms,
            pass_pct=pass_pct,
            warn_pct=warn_pct,
            fail_pct=fail_pct,
            mod_cards=mod_cards,
        )

        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

    def _render_mod_card(self, r: ModReport) -> str:
        status_class = "healthy" if r.healthy else "unhealthy"
        status_text = "PASS" if r.healthy else "ISSUES"
        stats = (
            f"P:{r.passed} "
            f"<span style='color:#ff9800'>W:{r.warnings}</span> "
            f"<span style='color:#f44336'>F:{r.failures} E:{r.errors}</span>"
        )

        results_html = ""
        for rr in r.results:
            cls = _SEVERITY_CLASS.get(rr.severity, "warn")
            lbl = _SEVERITY_LABEL.get(rr.severity, "???")
            detail_html = ""
            if rr.detail:
                detail_html = (
                    f'<div class="result-detail">' f"{self._escape(rr.detail)}</div>"
                )
            results_html += (
                f'<div class="result-row">'
                f'<span class="result-icon {cls}">{lbl}</span>'
                f"<span>{self._escape(rr.name)}: {self._escape(rr.message)}"
                f' <span style="color:#666">{rr.duration_ms:.0f}ms</span></span>'
                f"</div>{detail_html}"
            )

        return (
            f'<div class="mod-card">'
            f'<div class="mod-header {status_class}" '
            f'onclick="this.nextElementSibling.style.display='
            f"this.nextElementSibling.style.display=='none'?'block':'none'\">"
            f'<div><span class="mod-name">{self._escape(r.mod_name)}</span> '
            f'<span style="color:#888">({r.node_type})</span> '
            f'<span style="color:#888">{r.duration_ms:.0f}ms</span></div>'
            f'<div class="mod-stats">{stats} '
            f'<span style="color:{ "#4caf50" if r.healthy else "#f44336" }">'
            f"{status_text}</span></div>"
            f"</div>"
            f'<div class="result-list">{results_html}</div>'
            f"</div>"
        )

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
