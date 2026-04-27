import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"

GREEN = "#1e8e3e"
AMBER = "#f9ab00"
RED = "#d93025"
BLUE = "#1a73e8"
LIGHT_GRAY = "#f8f9fa"
BORDER = "#dadce0"
TEXT = "#202124"
MUTED = "#5f6368"

THRESHOLDS = {
    "lcp_ms":         {"good": 2500,  "poor": 4000,  "unit": "ms",   "lower": True,  "label": "LCP"},
    "fcp_ms":         {"good": 1800,  "poor": 3000,  "unit": "ms",   "lower": True,  "label": "FCP"},
    "tbt_ms":         {"good": 200,   "poor": 600,   "unit": "ms",   "lower": True,  "label": "TBT"},
    "speed_index_ms": {"good": 3400,  "poor": 5800,  "unit": "ms",   "lower": True,  "label": "Speed Index"},
    "cls":            {"good": 0.1,   "poor": 0.25,  "unit": "",     "lower": True,  "label": "CLS"},
    "score":          {"good": 90,    "poor": 50,    "unit": "/100", "lower": False, "label": "Score"},
}


def load_json_safe(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def metric_color(value, t: dict) -> str:
    if value is None:
        return MUTED
    if t["lower"]:
        if value <= t["good"]:
            return GREEN
        if value <= t["poor"]:
            return AMBER
        return RED
    else:
        if value >= t["good"]:
            return GREEN
        if value >= t["poor"]:
            return AMBER
        return RED


def metric_rating(value, t: dict) -> str:
    if value is None:
        return "N/A"
    if t["lower"]:
        if value <= t["good"]:
            return "Good"
        if value <= t["poor"]:
            return "Needs Work"
        return "Poor"
    else:
        if value >= t["good"]:
            return "Good"
        if value >= t["poor"]:
            return "Needs Work"
        return "Poor"


def fmt_ms(val) -> str:
    if val is None:
        return "N/A"
    if val >= 1000:
        return f"{val/1000:.2f}s"
    return f"{val:.0f}ms"


def fmt_val(key: str, val) -> str:
    if val is None:
        return "N/A"
    if key == "cls":
        return f"{val:.3f}"
    if key in ("lcp_ms", "fcp_ms", "tbt_ms", "speed_index_ms"):
        return fmt_ms(val)
    return str(val)


def build_improvements(perf, uptime, links) -> list[dict]:
    items = []

    if uptime:
        if not uptime.get("is_up"):
            err = uptime.get("error") or f"HTTP {uptime.get('status_code')}"
            items.append({"priority": 1, "metric": "Uptime", "current": "DOWN",
                          "target": "Site reachable", "tip": f"Site is unreachable: {err}"})
        elif uptime.get("response_time_ms", 0) > 3000:
            items.append({"priority": 3, "metric": "Response Time",
                          "current": fmt_ms(uptime["response_time_ms"]),
                          "target": "< 1000ms",
                          "tip": "Slow server response. Check hosting, enable caching, or use a CDN."})

    if perf:
        for strategy in ("mobile", "desktop"):
            s = perf.get(strategy, {})
            if s.get("error"):
                continue
            vitals = s.get("vitals", {})
            scores = s.get("scores", {})
            label = strategy.capitalize()

            for key, t in THRESHOLDS.items():
                if key == "score":
                    continue
                val = vitals.get(key)
                if val is None:
                    continue
                if t["lower"] and val > t["poor"]:
                    tips = {
                        "lcp_ms": "Optimize largest image/text block: compress images, use lazy loading, preload key resources.",
                        "fcp_ms": "Reduce render-blocking resources and server response time.",
                        "tbt_ms": "Break up long JavaScript tasks; defer non-critical scripts.",
                        "speed_index_ms": "Prioritize above-the-fold content; reduce CSS/JS blocking.",
                        "cls": "Set explicit width/height on images and embeds; avoid injecting content above existing DOM.",
                    }
                    items.append({"priority": 2, "metric": f"{t['label']} ({label})",
                                  "current": fmt_val(key, val),
                                  "target": f"< {fmt_val(key, t['good'])}",
                                  "tip": tips.get(key, "Optimize this metric.")})
                elif t["lower"] and val > t["good"]:
                    items.append({"priority": 3, "metric": f"{t['label']} ({label})",
                                  "current": fmt_val(key, val),
                                  "target": f"< {fmt_val(key, t['good'])}",
                                  "tip": f"{t['label']} needs improvement on {label}."})

            score_tips = {
                "seo": "Add meta description, title tag, structured data, and ensure all images have alt text.",
                "accessibility": "Fix contrast issues, add ARIA labels, ensure keyboard navigability.",
                "best_practices": "Fix mixed content, use HTTPS, update deprecated APIs.",
            }
            for cat, tip in score_tips.items():
                val = scores.get(cat)
                if val is None:
                    continue
                t = THRESHOLDS["score"]
                if val < t["poor"]:
                    items.append({"priority": 5, "metric": f"{cat.replace('_', ' ').title()} ({label})",
                                  "current": f"{val}/100", "target": "≥ 90", "tip": tip})
                elif val < t["good"]:
                    items.append({"priority": 6, "metric": f"{cat.replace('_', ' ').title()} ({label})",
                                  "current": f"{val}/100", "target": "≥ 90", "tip": tip})

    if links and links.get("broken_count", 0) > 0:
        items.append({"priority": 4, "metric": "Broken Links",
                      "current": f"{links['broken_count']} broken",
                      "target": "0 broken",
                      "tip": "Fix or remove broken links to preserve SEO equity and user experience."})

    items.sort(key=lambda x: x["priority"])
    # Deduplicate by metric name keeping highest priority
    seen = {}
    for item in items:
        if item["metric"] not in seen:
            seen[item["metric"]] = item
    return list(seen.values())


def row(label, value, color=TEXT, bold=False):
    weight = "font-weight:600;" if bold else ""
    return (f'<tr><td style="padding:8px 12px;border-bottom:1px solid {BORDER};color:{MUTED};'
            f'font-size:13px;">{label}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid {BORDER};color:{color};'
            f'font-size:13px;{weight}">{value}</td></tr>')


def badge(text, color):
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
            f'background:{color};color:#fff;font-size:11px;font-weight:600;">{text}</span>')


def section_header(title):
    return (f'<tr><td colspan="2" style="padding:16px 12px 8px;background:{LIGHT_GRAY};'
            f'font-size:14px;font-weight:700;color:{TEXT};border-bottom:2px solid {BORDER};">'
            f'{title}</td></tr>')


def render_uptime(uptime) -> str:
    if not uptime:
        return unavailable_section("Uptime")
    is_up = uptime.get("is_up", False)
    color = GREEN if is_up else RED
    status_text = "UP" if is_up else "DOWN"
    rows = [
        section_header("Uptime & Availability"),
        row("Status", badge(status_text, color), bold=True),
        row("Status Code", uptime.get("status_code") or uptime.get("error", "N/A")),
        row("Response Time", fmt_ms(uptime.get("response_time_ms"))),
        row("Final URL", uptime.get("final_url") or uptime.get("url", "N/A")),
        row("Checked At", uptime.get("checked_at", "N/A")),
    ]
    if uptime.get("error"):
        rows.append(row("Error", uptime["error"], color=RED))
    return "".join(rows)


def render_vitals(strategy_data, label) -> str:
    if not strategy_data or strategy_data.get("error"):
        err = (strategy_data or {}).get("error", "unavailable")
        return (f'<tr><td colspan="2" style="padding:8px 12px;color:{RED};font-size:13px;">'
                f'{label} data unavailable: {err}</td></tr>')

    vitals = strategy_data.get("vitals", {})
    rows = [section_header(f"Core Web Vitals — {label}")]
    order = ["lcp_ms", "fcp_ms", "tbt_ms", "speed_index_ms", "cls"]
    for key in order:
        t = THRESHOLDS[key]
        val = vitals.get(key)
        color = metric_color(val, t)
        rating = metric_rating(val, t)
        display = f'{fmt_val(key, val)} &nbsp; {badge(rating, color)}'
        rows.append(row(t["label"], display))
    return "".join(rows)


def render_scores(perf) -> str:
    if not perf:
        return unavailable_section("Lighthouse Scores")

    cat_labels = {"performance": "Performance", "seo": "SEO",
                  "accessibility": "Accessibility", "best_practices": "Best Practices"}
    rows = [section_header("Lighthouse Scores")]

    header = (f'<tr>'
              f'<td style="padding:8px 12px;font-size:13px;font-weight:600;color:{MUTED};'
              f'border-bottom:1px solid {BORDER};">Category</td>'
              f'<td style="padding:8px 12px;font-size:13px;font-weight:600;color:{MUTED};'
              f'border-bottom:1px solid {BORDER};">Mobile</td>'
              f'<td style="padding:8px 12px;font-size:13px;font-weight:600;color:{MUTED};'
              f'border-bottom:1px solid {BORDER};">Desktop</td>'
              f'</tr>')
    rows.append(header)

    t = THRESHOLDS["score"]
    for cat, label in cat_labels.items():
        m_val = (perf.get("mobile") or {}).get("scores", {}).get(cat)
        d_val = (perf.get("desktop") or {}).get("scores", {}).get(cat)
        m_disp = f'{badge(str(m_val), metric_color(m_val, t))}' if m_val is not None else "N/A"
        d_disp = f'{badge(str(d_val), metric_color(d_val, t))}' if d_val is not None else "N/A"
        rows.append(
            f'<tr>'
            f'<td style="padding:8px 12px;border-bottom:1px solid {BORDER};font-size:13px;">{label}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid {BORDER};">{m_disp}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid {BORDER};">{d_disp}</td>'
            f'</tr>'
        )
    return "".join(rows)


def render_links(links) -> str:
    if not links:
        return unavailable_section("Broken Links")

    broken = [l for l in links.get("links", []) if not l["ok"]]
    total_checked = links.get("links_checked", 0)
    total_found = links.get("total_links_found", 0)
    broken_count = links.get("broken_count", 0)

    summary_color = GREEN if broken_count == 0 else RED
    summary = f'{badge(f"{broken_count} broken", summary_color)} of {total_checked} checked ({total_found} found)'
    rows = [
        section_header("Broken Links"),
        (f'<tr><td colspan="2" style="padding:8px 12px;font-size:13px;border-bottom:1px solid {BORDER};">'
         f'{summary}</td></tr>'),
    ]

    if broken:
        rows.append(
            f'<tr>'
            f'<td style="padding:6px 12px;font-size:12px;font-weight:600;color:{MUTED};'
            f'border-bottom:1px solid {BORDER};">URL</td>'
            f'<td style="padding:6px 12px;font-size:12px;font-weight:600;color:{MUTED};'
            f'border-bottom:1px solid {BORDER};">Status</td>'
            f'</tr>'
        )
        for link in broken[:20]:
            status = link.get("status_code") or link.get("error", "error")
            url = link["url"]
            display_url = url if len(url) <= 70 else url[:67] + "..."
            rows.append(
                f'<tr>'
                f'<td style="padding:6px 12px;font-size:12px;color:{TEXT};'
                f'border-bottom:1px solid {BORDER};word-break:break-all;">{display_url}</td>'
                f'<td style="padding:6px 12px;font-size:12px;color:{RED};'
                f'border-bottom:1px solid {BORDER};">{status}</td>'
                f'</tr>'
            )
        if len(broken) > 20:
            rows.append(
                f'<tr><td colspan="2" style="padding:8px 12px;font-size:12px;color:{MUTED};">'
                f'...and {len(broken) - 20} more broken links.</td></tr>'
            )
    return "".join(rows)


def render_improvements(improvements) -> str:
    if not improvements:
        return (f'<tr><td colspan="2" style="padding:12px;background:#e6f4ea;color:{GREEN};'
                f'font-size:13px;font-weight:600;border-radius:4px;">'
                f'No improvements needed — everything looks great!</td></tr>')

    priority_colors = {1: RED, 2: RED, 3: AMBER, 4: AMBER, 5: AMBER, 6: MUTED}
    rows = [section_header(f"Top Improvements ({len(improvements)} found)")]
    for i, item in enumerate(improvements, 1):
        color = priority_colors.get(item["priority"], MUTED)
        rows.append(
            f'<tr><td colspan="2" style="padding:10px 12px;border-bottom:1px solid {BORDER};">'
            f'<div style="display:table;width:100%;">'
            f'<span style="font-size:13px;font-weight:600;color:{TEXT};">{i}. {item["metric"]}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:12px;color:{color};">{item["current"]} → {item["target"]}</span>'
            f'<br><span style="font-size:12px;color:{MUTED};margin-top:3px;display:block;">'
            f'{item["tip"]}</span>'
            f'</div>'
            f'</td></tr>'
        )
    return "".join(rows)


def render_action_plan(perf, uptime, links) -> str:
    actions = []  # list of {title, color, steps: [str]}

    # --- Uptime ---
    if uptime:
        rt = uptime.get("response_time_ms")
        if not uptime.get("is_up"):
            actions.append({
                "title": "Site is Down — Restore Availability",
                "color": RED,
                "steps": [
                    f"Error: {uptime.get('error') or uptime.get('status_code')}",
                    "Check your hosting provider's status page for outages",
                    "Verify DNS is resolving correctly with <code>dig your-domain.com</code>",
                    "Check server error logs and restart the web server if needed",
                    "Set up uptime monitoring alerts (e.g. UptimeRobot, Betterstack) so you know instantly",
                ]
            })
        elif rt and rt > 3000:
            actions.append({
                "title": f"Slow Server Response — {fmt_ms(rt)} (target: &lt; 1000ms)",
                "color": AMBER,
                "steps": [
                    "Enable server-side caching (Redis, Varnish, or full-page cache in your CMS)",
                    "Add a CDN (Cloudflare free tier is a quick win — routes traffic to nearest edge node)",
                    "Review database queries — slow queries are a common cause of high TTFB",
                    "Check if your hosting plan is CPU/memory throttled; upgrade if needed",
                ]
            })

    # --- Mobile vitals ---
    if perf:
        mobile = perf.get("mobile") or {}
        desktop = perf.get("desktop") or {}
        m_vitals = mobile.get("vitals", {})
        d_vitals = desktop.get("vitals", {})
        m_scores = mobile.get("scores", {})
        d_scores = desktop.get("scores", {})

        lcp_m = m_vitals.get("lcp_ms")
        if lcp_m and lcp_m > THRESHOLDS["lcp_ms"]["poor"]:
            actions.append({
                "title": f"Fix Mobile LCP — {fmt_ms(lcp_m)} (target: &lt; 2.5s)",
                "color": RED,
                "steps": [
                    "Find the LCP element: open Chrome DevTools → Lighthouse → click the LCP node in the report",
                    "If it's a hero image: convert to WebP format (saves 25–35% file size vs JPG)",
                    "Add <code>fetchpriority=\"high\"</code> and <code>loading=\"eager\"</code> attributes to that image tag",
                    "Preload it in your <code>&lt;head&gt;</code>: <code>&lt;link rel=\"preload\" as=\"image\" href=\"hero.webp\"&gt;</code>",
                    "If it's a text block: ensure the font is preloaded and not render-blocking",
                    "Check your hosting is geographically close to your main audience — use a CDN if not",
                ]
            })
        elif lcp_m and lcp_m > THRESHOLDS["lcp_ms"]["good"]:
            actions.append({
                "title": f"Improve Mobile LCP — {fmt_ms(lcp_m)} (target: &lt; 2.5s)",
                "color": AMBER,
                "steps": [
                    "Compress the LCP image and serve in WebP format",
                    "Ensure the LCP resource is not lazy-loaded — remove <code>loading=\"lazy\"</code> from it",
                    "Preload the LCP image in <code>&lt;head&gt;</code> with <code>&lt;link rel=\"preload\"&gt;</code>",
                ]
            })

        si_m = m_vitals.get("speed_index_ms")
        if si_m and si_m > THRESHOLDS["speed_index_ms"]["poor"]:
            actions.append({
                "title": f"Fix Mobile Speed Index — {fmt_ms(si_m)} (target: &lt; 3.4s)",
                "color": RED,
                "steps": [
                    "Inline your critical (above-the-fold) CSS directly in <code>&lt;style&gt;</code> tags in <code>&lt;head&gt;</code>",
                    "Move all non-critical <code>&lt;script&gt;</code> tags to bottom of <code>&lt;body&gt;</code> or add <code>defer</code>/<code>async</code>",
                    "Eliminate render-blocking resources: in Chrome DevTools → Coverage, find unused CSS/JS loaded on initial page",
                    "Lazy-load all images below the fold with <code>loading=\"lazy\"</code>",
                    "Enable Gzip/Brotli compression on your web server for HTML, CSS, and JS files",
                ]
            })
        elif si_m and si_m > THRESHOLDS["speed_index_ms"]["good"]:
            actions.append({
                "title": f"Improve Mobile Speed Index — {fmt_ms(si_m)} (target: &lt; 3.4s)",
                "color": AMBER,
                "steps": [
                    "Defer non-critical JavaScript with the <code>defer</code> attribute",
                    "Lazy-load below-the-fold images with <code>loading=\"lazy\"</code>",
                    "Minify CSS and JS files if not already done",
                ]
            })

        fcp_m = m_vitals.get("fcp_ms")
        if fcp_m and fcp_m > THRESHOLDS["fcp_ms"]["good"]:
            label = "Fix" if fcp_m > THRESHOLDS["fcp_ms"]["poor"] else "Improve"
            actions.append({
                "title": f"{label} Mobile FCP — {fmt_ms(fcp_m)} (target: &lt; 1.8s)",
                "color": RED if fcp_m > THRESHOLDS["fcp_ms"]["poor"] else AMBER,
                "steps": [
                    "Reduce server response time (TTFB) — enable caching and use a CDN",
                    "Remove or defer render-blocking <code>&lt;link rel=\"stylesheet\"&gt;</code> for non-critical CSS",
                    "Inline the minimal CSS needed to paint the first visible content",
                    "Avoid chained critical requests — preload key fonts and resources",
                ]
            })

        cls_m = m_vitals.get("cls")
        if cls_m and cls_m > THRESHOLDS["cls"]["good"]:
            label = "Fix" if cls_m > THRESHOLDS["cls"]["poor"] else "Fix"
            actions.append({
                "title": f"Fix Mobile Layout Shift (CLS) — {cls_m:.3f} (target: &lt; 0.1)",
                "color": RED if cls_m > THRESHOLDS["cls"]["poor"] else AMBER,
                "steps": [
                    "Add explicit <code>width</code> and <code>height</code> attributes to every <code>&lt;img&gt;</code> and <code>&lt;video&gt;</code> tag",
                    "Reserve space for ads, embeds, and iframes with fixed dimensions or aspect-ratio CSS",
                    "Avoid inserting content (banners, cookie bars, popups) above existing page content after load",
                    "Preload custom fonts to prevent invisible-text flash causing reflow: <code>&lt;link rel=\"preload\" as=\"font\"&gt;</code>",
                    "Use <code>font-display: optional</code> or <code>swap</code> in your CSS @font-face rules",
                ]
            })

        # --- Desktop vitals ---
        tbt_d = d_vitals.get("tbt_ms")
        if tbt_d and tbt_d > THRESHOLDS["tbt_ms"]["poor"]:
            actions.append({
                "title": f"Fix Desktop TBT (JavaScript Blocking) — {fmt_ms(tbt_d)} (target: &lt; 200ms)",
                "color": RED,
                "steps": [
                    "Open Chrome DevTools → Performance tab → record a page load → find tasks &gt; 50ms (shown in red)",
                    "Open DevTools → Coverage tab — find JS files with high unused byte percentage; defer or remove them",
                    "Audit third-party scripts (chat widgets, analytics, A/B testing tools) — each one blocks the main thread",
                    "Load non-essential third-party scripts with <code>async</code> or delay them until after user interaction",
                    "If using a tag manager (GTM), audit its tags — remove unused ones and set triggers to fire after page load",
                    "Break up long synchronous JS functions using <code>setTimeout(fn, 0)</code> or the Scheduler API",
                ]
            })
        elif tbt_d and tbt_d > THRESHOLDS["tbt_ms"]["good"]:
            actions.append({
                "title": f"Improve Desktop TBT — {fmt_ms(tbt_d)} (target: &lt; 200ms)",
                "color": AMBER,
                "steps": [
                    "Defer non-critical JavaScript with the <code>defer</code> attribute",
                    "Lazy-load third-party widgets (live chat, social embeds) until user scrolls to them",
                    "Minify and tree-shake your JavaScript bundles",
                ]
            })

        lcp_d = d_vitals.get("lcp_ms")
        if lcp_d and lcp_d > THRESHOLDS["lcp_ms"]["good"]:
            actions.append({
                "title": f"Improve Desktop LCP — {fmt_ms(lcp_d)} (target: &lt; 2.5s)",
                "color": RED if lcp_d > THRESHOLDS["lcp_ms"]["poor"] else AMBER,
                "steps": [
                    "Preload the hero image: <code>&lt;link rel=\"preload\" as=\"image\" href=\"hero.webp\"&gt;</code>",
                    "Serve images in WebP or AVIF format",
                    "Ensure hero image is not lazy-loaded",
                ]
            })

        # Lighthouse scores
        score_actions = {
            "seo": {
                "title": "Improve SEO Score",
                "steps": [
                    "Add a unique, descriptive <code>&lt;meta name=\"description\"&gt;</code> tag (150–160 chars) to every page",
                    "Ensure every page has a unique <code>&lt;title&gt;</code> tag (50–60 chars)",
                    "Add <code>alt</code> text to all images — describe the image content clearly",
                    "Add structured data (JSON-LD) for your business type (e.g. LocalBusiness, Product, FAQPage)",
                    "Submit an XML sitemap to Google Search Console",
                    "Ensure <code>&lt;meta name=\"robots\"&gt;</code> is not accidentally blocking indexing",
                ]
            },
            "accessibility": {
                "title": "Improve Accessibility Score",
                "steps": [
                    "Check color contrast — text must meet 4.5:1 ratio (use WebAIM Contrast Checker)",
                    "Add <code>aria-label</code> to icon-only buttons and links",
                    "Ensure all form inputs have associated <code>&lt;label&gt;</code> elements",
                    "Make sure the page is navigable by keyboard (Tab key) with a visible focus indicator",
                    "Add <code>lang=\"en\"</code> attribute to your <code>&lt;html&gt;</code> tag",
                ]
            },
            "best_practices": {
                "title": "Improve Best Practices Score",
                "steps": [
                    "Ensure all resources load over HTTPS — fix any mixed content warnings",
                    "Update or remove deprecated JavaScript APIs flagged in the Console",
                    "Set appropriate security headers: <code>X-Content-Type-Options</code>, <code>X-Frame-Options</code>",
                    "Ensure images have correct aspect ratios and are not distorted",
                ]
            },
        }
        for strategy_label, s_vitals, s_scores in [("Mobile", m_vitals, m_scores), ("Desktop", d_vitals, d_scores)]:
            for cat, action_def in score_actions.items():
                val = s_scores.get(cat)
                if val is None or val >= 90:
                    continue
                color = RED if val < 50 else AMBER
                actions.append({
                    "title": f"{action_def['title']} ({strategy_label}) — {val}/100",
                    "color": color,
                    "steps": action_def["steps"],
                })

    # --- Broken links ---
    if links and links.get("broken_count", 0) > 0:
        broken_urls = [l["url"] for l in links.get("links", []) if not l["ok"]][:5]
        url_list = [f"<code>{u}</code>" for u in broken_urls]
        if links["broken_count"] > 5:
            url_list.append(f"...and {links['broken_count'] - 5} more (see Broken Links section above)")
        actions.append({
            "title": f"Fix {links['broken_count']} Broken Link{'s' if links['broken_count'] > 1 else ''}",
            "color": AMBER,
            "steps": [
                "Broken links hurt SEO and user experience — fix or remove each one:",
                *url_list,
                "Use a permanent redirect (301) if the page has moved to a new URL",
                "If the page no longer exists, remove the link from your site",
            ]
        })

    if not actions:
        return ""

    # Build HTML
    items_html = ""
    for i, action in enumerate(actions, 1):
        steps_html = "".join(
            f'<tr><td style="padding:3px 0 3px 16px;font-size:13px;color:{TEXT};">'
            f'<span style="color:{MUTED};">{j}.</span>&nbsp;{step}</td></tr>'
            for j, step in enumerate(action["steps"], 1)
        )
        items_html += f'''
<tr><td style="padding:14px 0 6px;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td style="padding:0 0 6px;">
      <span style="display:inline-block;background:{action["color"]};color:#fff;
        font-size:11px;font-weight:700;padding:2px 8px;border-radius:3px;
        margin-right:8px;">{i}</span>
      <span style="font-size:13px;font-weight:700;color:{TEXT};">{action["title"]}</span>
    </td></tr>
    {steps_html}
  </table>
</td></tr>
<tr><td style="border-bottom:1px solid {BORDER};padding:0;font-size:0;">&nbsp;</td></tr>'''

    return f'''<tr><td style="padding:20px 20px 0;border-top:2px solid {BORDER};">
  <p style="margin:0 0 4px;font-size:16px;font-weight:700;color:{TEXT};">Action Plan</p>
  <p style="margin:0 0 16px;font-size:12px;color:{MUTED};">Step-by-step fixes for every issue found today, in priority order.</p>
  <table width="100%" cellpadding="0" cellspacing="0">
    {items_html}
  </table>
</td></tr>'''


def unavailable_section(title) -> str:
    return (f'<tr><td colspan="2" style="padding:10px 12px;color:{MUTED};font-size:13px;">'
            f'{title}: data unavailable</td></tr>')


def render_summary(perf, uptime, links, improvements) -> str:
    urgent, watch, good = [], [], []

    # Uptime
    if uptime:
        rt = uptime.get("response_time_ms")
        if not uptime.get("is_up"):
            urgent.append(f"Site is <strong>DOWN</strong> — {uptime.get('error') or uptime.get('status_code')}")
        elif rt and rt > 3000:
            watch.append(f"Slow server response ({fmt_ms(rt)}) — consider CDN or caching")
        else:
            good.append(f"Site is UP ({fmt_ms(rt)} response)")

    # Core Web Vitals
    if perf:
        vital_tips = {
            "lcp_ms": "Compress hero image, add preload hint",
            "fcp_ms": "Remove render-blocking resources",
            "tbt_ms": "Defer non-critical JavaScript",
            "speed_index_ms": "Inline critical CSS, defer JS",
            "cls": "Set explicit image dimensions",
        }
        for strategy in ("mobile", "desktop"):
            s = perf.get(strategy) or {}
            if s.get("error"):
                continue
            label = strategy.capitalize()
            vitals = s.get("vitals", {})
            scores = s.get("scores", {})

            for key, t in THRESHOLDS.items():
                if key == "score":
                    continue
                val = vitals.get(key)
                if val is None:
                    continue
                display = fmt_val(key, val)
                name = t["label"]
                if t["lower"] and val > t["poor"]:
                    urgent.append(f"<strong>{name} ({label})</strong> is {display} — {vital_tips.get(key, 'optimize')}")
                elif t["lower"] and val > t["good"]:
                    watch.append(f"{name} ({label}) needs work: {display} (target &lt; {fmt_val(key, t['good'])})")
                else:
                    good.append(f"{name} ({label}) is good: {display}")

            perf_score = scores.get("performance")
            if perf_score is not None:
                if perf_score < 50:
                    urgent.append(f"<strong>Performance score ({label})</strong> is {perf_score}/100")
                elif perf_score < 90:
                    watch.append(f"Performance score ({label}): {perf_score}/100 (target ≥ 90)")
                else:
                    good.append(f"Performance score ({label}): {perf_score}/100")

    # Broken links
    if links:
        broken = links.get("broken_count", 0)
        checked = links.get("links_checked", 0)
        if broken > 0:
            watch.append(f"{broken} broken link{'s' if broken > 1 else ''} found out of {checked} checked")
        else:
            good.append(f"No broken links ({checked} checked)")

    def bullet_list(items, color):
        if not items:
            return ""
        rows = "".join(
            f'<tr><td style="padding:3px 0;font-size:13px;color:{TEXT};">'
            f'<span style="color:{color};font-weight:700;">&#9679;</span>&nbsp;{item}</td></tr>'
            for item in items
        )
        return f'<table width="100%" cellpadding="0" cellspacing="0">{rows}</table>'

    parts = []
    if urgent:
        parts.append(
            f'<p style="margin:0 0 6px;font-size:12px;font-weight:700;color:{RED};'
            f'text-transform:uppercase;letter-spacing:0.5px;">Needs Immediate Attention</p>'
            + bullet_list(urgent, RED)
        )
    if watch:
        if parts:
            parts.append('<div style="height:12px;"></div>')
        parts.append(
            f'<p style="margin:0 0 6px;font-size:12px;font-weight:700;color:{AMBER};'
            f'text-transform:uppercase;letter-spacing:0.5px;">Worth Improving</p>'
            + bullet_list(watch, AMBER)
        )
    if good:
        if parts:
            parts.append('<div style="height:12px;"></div>')
        parts.append(
            f'<p style="margin:0 0 6px;font-size:12px;font-weight:700;color:{GREEN};'
            f'text-transform:uppercase;letter-spacing:0.5px;">Looking Good</p>'
            + bullet_list(good, GREEN)
        )

    if not parts:
        return ""

    inner = "".join(parts)
    return f'''<tr><td style="padding:16px 20px;border-bottom:1px solid {BORDER};">
  <p style="margin:0 0 12px;font-size:15px;font-weight:700;color:{TEXT};">Summary</p>
  {inner}
</td></tr>'''


def overall_status(uptime, perf, links) -> tuple[str, str]:
    if uptime and not uptime.get("is_up"):
        return "DOWN", RED
    poor_count = 0
    if perf:
        for strategy in ("mobile", "desktop"):
            s = perf.get(strategy, {})
            for key, t in THRESHOLDS.items():
                if key == "score":
                    continue
                val = (s.get("vitals") or {}).get(key)
                if val is not None and t["lower"] and val > t["poor"]:
                    poor_count += 1
    if poor_count >= 3:
        return "Needs Attention", RED
    if poor_count >= 1 or (links and links.get("broken_count", 0) > 0):
        return "Needs Improvement", AMBER
    return "Healthy", GREEN


def build_html_email(perf, uptime, links) -> str:
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")
    site = (uptime or {}).get("url") or (perf or {}).get("mobile", {}).get("url", "Your Website")
    status_text, status_color = overall_status(uptime, perf, links)
    improvements = build_improvements(perf, uptime, links)
    subject = f"[{now}] amigosim.com performance"

    summary_html = render_summary(perf, uptime, links, improvements)
    action_plan_html = render_action_plan(perf, uptime, links)
    uptime_html = render_uptime(uptime)
    mobile_html = render_vitals((perf or {}).get("mobile"), "Mobile") if perf else unavailable_section("Core Web Vitals — Mobile")
    desktop_html = render_vitals((perf or {}).get("desktop"), "Desktop") if perf else unavailable_section("Core Web Vitals — Desktop")
    scores_html = render_scores(perf)
    links_html = render_links(links)
    improvements_html = render_improvements(improvements)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{subject}</title></head>
<body style="margin:0;padding:0;background:#f1f3f4;font-family:-apple-system,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f3f4;padding:20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;border:1px solid {BORDER};">

  <!-- Header -->
  <tr><td style="background:{BLUE};padding:24px 20px;">
    <p style="margin:0;color:#ffffff;font-size:20px;font-weight:700;">{site}</p>
    <p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px;">Performance Report &mdash; {now}</p>
  </td></tr>

  <!-- Overall status -->
  <tr><td style="padding:16px 20px;background:{LIGHT_GRAY};border-bottom:1px solid {BORDER};">
    <span style="font-size:14px;color:{MUTED};">Overall Status: </span>
    <span style="font-size:14px;font-weight:700;color:{status_color};">{status_text}</span>
  </td></tr>

  <!-- Summary -->
  {summary_html}

  <!-- Data sections -->
  <tr><td style="padding:0 8px;">
  <table width="100%" cellpadding="0" cellspacing="0">
    {uptime_html}
    {mobile_html}
    {desktop_html}
    {scores_html}
    {links_html}
    {improvements_html}
  </table>
  </td></tr>

  <!-- Action Plan -->
  {action_plan_html}

  <!-- Footer -->
  <tr><td style="padding:16px 20px;background:{LIGHT_GRAY};border-top:1px solid {BORDER};">
    <p style="margin:0;font-size:11px;color:{MUTED};text-align:center;">
      Generated by WAT Performance Monitor &mdash; {now}
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def main():
    TMP.mkdir(exist_ok=True)

    perf = load_json_safe(TMP / "performance_data.json")
    uptime = load_json_safe(TMP / "uptime_data.json")
    links = load_json_safe(TMP / "broken_links_data.json")

    if perf is None and uptime is None and links is None:
        html = ("""<!DOCTYPE html><html><body>
<p style="color:#d93025;font-family:Arial,sans-serif;">
All data collection failed. Check .tmp/run.log for details.</p>
</body></html>""")
        out = TMP / "email_body.html"
        out.write_text(html)
        print("WARNING: All data unavailable — wrote fallback email", file=sys.stderr)
        sys.exit(1)

    html = build_html_email(perf, uptime, links)
    out = TMP / "email_body.html"
    out.write_text(html)
    print(f"Report generated: {out}")
    sys.exit(0)


if __name__ == "__main__":
    main()
