#!/usr/bin/env python3
"""Generates a standalone FigJam-style HTML visual board from scrum-spec documents.

Reads map.md and all spec.md files in a docs directory (e.g. scrum-spec/) and renders
an interactive, complete visual board with native 2-finger trackpad panning,
pinch-to-zoom, role-based views (PO, Dev, QA), and fully readable specs on-canvas.

Usage:
  python3 -I board.py [folder] [--output board.html] [--open]

Zero dependencies. Read-only on source Markdown. Python 3.10+.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from specdoc import parse, questions_from, section_lines

MARKER = "<!-- scrum-spec"


def mermaid_label(text: str) -> str:
    text = " ".join(text.split())
    return text.replace("\\", "").replace('"', "'").replace("#", " ").replace("-->", "→")


def mermaid_state(acs: list[dict[str, str]]) -> str:
    """One transition per AC/EC row. Given and Then stay separate states; rows are not merged."""
    if not acs:
        return ""
    lines = ["stateDiagram-v2", "    direction LR"]
    seen: dict[str, int] = {}
    for ac in acs:
        code = re.sub(r"[^A-Za-z0-9]", "", ac.get("code", "")) or "AC"
        count = seen.get(code, 0)
        seen[code] = count + 1
        ident = code if count == 0 else f"{code}_{count}"
        given = mermaid_label(ac.get("given", "")) or " "
        when = mermaid_label(ac.get("when", "")) or " "
        then_ = mermaid_label(ac.get("then", "")) or " "
        lines.append(f'    state "{given}" as {ident}_given')
        lines.append(f'    state "{then_}" as {ident}_then')
        lines.append(f"    {ident}_given --> {ident}_then: {when}")
    return "\n".join(lines)


def state_flow_html(acs: list[dict[str, str]]) -> str:
    diagram = mermaid_state(acs)
    if not diagram:
        return ""
    return (
        '<div class="spec-block"><div class="spec-block-title">State flow</div>'
        f'<pre class="state-flow">{html.escape(diagram)}</pre></div>'
    )


class StorySpec:
    def __init__(self, slug: str, path: Path):
        self.slug = slug
        self.path = path
        self.ticket = slug
        self.story_text = ""
        self.in_scope: list[str] = []
        self.out_scope: list[str] = []
        self.source = ""
        self.rules: list[str] = []
        self.approve = "❌ waiting for PO"
        self.acs: list[dict[str, str]] = []
        self.questions: list[dict] = []
        self.decisions: list[str] = []
        self.test_accounts = ""
        self.test_data = ""
        self.do_not_report = ""
        self.watch_out = ""
        self.test_steps: list[tuple[str, list[str]]] = []
        self.size_signal = ""
        self.steps_ref = ""

    @classmethod
    def load(cls, path: Path) -> StorySpec | None:
        text = path.read_text(encoding="utf-8")
        if not text.startswith(MARKER):
            return None

        slug = path.parent.name
        spec = cls(slug, path)
        sections, tables = parse(text.splitlines())

        for line in section_lines(sections, ""):
            if line.startswith("# "):
                spec.slug = line[2:].strip()
                break

        in_in_scope = False
        in_out_scope = False
        for line in section_lines(sections, "Story"):
            s = line.strip()
            if s.startswith("- **Ticket:**"):
                spec.ticket = s.split(":", 1)[1].strip()
            elif s.startswith("- **Story:**"):
                spec.story_text = s.split(":", 1)[1].strip()
            elif s.startswith("- **Source:**"):
                spec.source = s.split(":", 1)[1].strip()
            elif s.startswith("- **In scope:**"):
                in_in_scope, in_out_scope = True, False
            elif s.startswith("- **Out of scope:**"):
                in_in_scope, in_out_scope = False, True
            elif s.startswith("- **"):
                in_in_scope, in_out_scope = False, False
            elif in_in_scope and s.startswith("- "):
                spec.in_scope.append(s[2:].strip())
            elif in_out_scope and s.startswith("- "):
                spec.out_scope.append(s[2:].strip())

        for line in section_lines(sections, "Rules"):
            s = line.strip()
            if s.startswith("- **") or (s.startswith("- ") and not s.startswith("- (none")):
                spec.rules.append(s[2:].strip())

        # Acceptance Criteria
        for line in section_lines(sections, "Acceptance Criteria"):
            s = line.strip()
            if s.startswith("**approve:**"):
                spec.approve = s.split("**approve:**", 1)[1].strip()

        for sec_name, _header, rows in tables:
            if sec_name == "Acceptance Criteria":
                for _, row in rows:
                    if len(row) >= 4:
                        spec.acs.append({"code": row[0], "given": row[1], "when": row[2], "then": row[3]})
        spec.questions = questions_from(tables)

        for line in section_lines(sections, "Decisions"):
            s = line.strip()
            if s.startswith("- **D") or (s.startswith("- ") and "·" in s):
                spec.decisions.append(s[2:].strip())

        # Test steps
        test_sec = section_lines(sections, "Test steps")
        current_test_group = ""
        current_steps: list[str] = []
        for line in test_sec:
            s = line.strip()
            if s.startswith("- **Accounts:**"):
                spec.test_accounts = s.split(":", 1)[1].strip()
            elif s.startswith("- **Data to prepare:**"):
                spec.test_data = s.split(":", 1)[1].strip()
            elif s.startswith("- **Do not report:**"):
                spec.do_not_report = s.split(":", 1)[1].strip()
            elif s.startswith("### Watch out"):
                current_test_group = "Watch out"
            elif s.startswith("### "):
                if current_test_group:
                    spec.test_steps.append((current_test_group, current_steps))
                current_test_group = s[4:].strip()
                current_steps = []
            elif current_test_group == "Watch out" and (s.startswith("1. ") or s.startswith("- ")):
                spec.watch_out = s.split(" ", 1)[1].strip()
            elif current_test_group and (re.match(r"^\d+\.\s+", s) or s.startswith("- ")):
                current_steps.append(s)

        if current_test_group and current_test_group != "Watch out":
            spec.test_steps.append((current_test_group, current_steps))

        return spec


class StoryMap:
    def __init__(self, flow: str, path: Path):
        self.flow = flow
        self.path = path
        self.approve = "❌ waiting for PO"
        self.steps: list[tuple[str, str, str]] = []  # [(step_num, title, actor_source)]
        self.stories_map: dict[str, dict[str, str]] = {}  # {slug: {steps, can, size}}
        self.not_now: list[str] = []
        self.questions: list[dict] = []
        self.decisions: list[str] = []

    @classmethod
    def load(cls, path: Path) -> StoryMap | None:
        text = path.read_text(encoding="utf-8")
        if not text.startswith(MARKER):
            return None

        flow = path.parent.name
        sections, tables = parse(text.splitlines())

        for line in section_lines(sections, ""):
            if line.startswith("# ") and "·" in line:
                flow = line[2:].split("·", 1)[1].strip()

        smap = cls(flow, path)

        for line in section_lines(sections, ""):
            if "**approve:**" in line:
                smap.approve = line.split("**approve:**", 1)[1].strip()

        for line in section_lines(sections, "Steps"):
            s = line.strip()
            m = re.match(r"^(\d+)\.\s+(.*?)(?:\s+[—-]\s+(.*))?$", s)
            if m:
                step_no = f"Step {m.group(1)}"
                title = m.group(2).strip()
                meta = m.group(3).strip() if m.group(3) else ""
                smap.steps.append((step_no, title, meta))

        # Stories table
        for sec_name, _header, rows in tables:
            if sec_name == "Stories":
                for _, row in rows:
                    if len(row) >= 4:
                        slug = row[0].replace("`", "").strip()
                        smap.stories_map[slug] = {"steps": row[1].strip(), "can": row[2].strip(), "size": row[3].strip()}
        smap.questions = questions_from(tables)

        for line in section_lines(sections, "Not now"):
            s = line.strip()
            if s.startswith("- ") and not s.startswith("- (none"):
                smap.not_now.append(s[2:].strip())

        # Decisions
        for line in section_lines(sections, "Decisions"):
            s = line.strip()
            if s.startswith("- **D") or (s.startswith("- ") and "·" in s):
                smap.decisions.append(s[2:].strip())

        return smap


def discover(root: Path) -> tuple[list[StoryMap], list[StorySpec]]:
    maps: list[StoryMap] = []
    specs: list[StorySpec] = []

    for path in sorted(root.rglob("*.md")):
        if path.name == "map.md":
            m = StoryMap.load(path)
            if m:
                maps.append(m)
        elif path.name == "spec.md":
            s = StorySpec.load(path)
            if s:
                specs.append(s)

    # Correlate map details into specs
    for smap in maps:
        for slug, meta in smap.stories_map.items():
            for sp in specs:
                if sp.slug == slug:
                    sp.steps_ref = meta.get("steps", "")
                    if not sp.size_signal:
                        sp.size_signal = meta.get("size", "")

    return maps, specs


def render_html(maps: list[StoryMap], specs: list[StorySpec], title: str = "Scrum Spec Board") -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Combine all steps from all maps, or synthesise from stories
    all_steps: list[tuple[str, str, str]] = []
    for sm in maps:
        all_steps.extend(sm.steps)

    # Aggregate global open questions
    all_questions: list[dict[str, str]] = []
    for sm in maps:
        for q in sm.questions:
            all_questions.append({**q, "from": sm.flow})
    for sp in specs:
        for q in sp.questions:
            all_questions.append({**q, "from": sp.ticket or sp.slug})

    # Aggregate decisions
    all_decisions: list[str] = []
    for sm in maps:
        all_decisions.extend(sm.decisions)
    for sp in specs:
        all_decisions.extend(sp.decisions)
    # Deduplicate decisions while preserving order
    unique_decisions: list[str] = list(dict.fromkeys(all_decisions))

    # Aggregate Not Now
    all_not_now: list[str] = []
    for sm in maps:
        all_not_now.extend(sm.not_now)

    # Render Steps HTML
    steps_html = ""
    if all_steps:
        items = []
        for i, (num, stitle, meta) in enumerate(all_steps):
            arrow = '<span class="step-arrow">→</span>' if i > 0 else ""
            meta_tag = f'<span class="step-actor">👤 {html.escape(meta)}</span>' if meta else ""
            items.append(f"""
              {arrow}
              <div class="step-card">
                <span class="step-num">{html.escape(num)}</span>
                <div class="step-title">{html.escape(stitle)}</div>
                {meta_tag}
              </div>
            """)
        steps_html = f"""
        <div class="fig-section">
          <span class="section-label">🗺️ User Journey · Steps</span>
          <div class="steps-row">
            {"".join(items)}
          </div>
        </div>
        """

    # Render Stories HTML
    stories_html = []
    for sp in specs:
        is_approved = sp.approve.startswith("✅")
        card_class = "card-approved" if is_approved else "card-waiting"
        stamp_class = "approved" if is_approved else "waiting"
        stamp_text = html.escape(sp.approve)

        # Status badge
        blocking_q = [q for q in sp.questions if q.get("blocking")]
        if blocking_q:
            sub_status = f'<span style="font-size: 11px; color: #dc2626; font-weight: 700;">⚠️ {len(blocking_q)} BLOCKER QUESTION</span>'
        elif is_approved:
            sub_status = '<span style="font-size: 11px; color: #16a34a; font-weight: 700;">🚀 READY FOR SPRINT</span>'
        else:
            sub_status = '<span style="font-size: 11px; color: #ca8a04; font-weight: 600;">⏳ IN REFINEMENT</span>'

        steps_tag = f'<span class="card-steps-tag">Steps {html.escape(sp.steps_ref)}</span>' if sp.steps_ref else ""

        # Scope HTML
        scope_in_html = ""
        if sp.in_scope:
            scope_in_html = f"""
              <div class="scope-row">
                <span class="tag-scope-in">IN SCOPE</span>
                <span>{html.escape(" · ".join(sp.in_scope))}</span>
              </div>
            """
        scope_out_html = ""
        if sp.out_scope:
            scope_out_html = f"""
              <div class="scope-row">
                <span class="tag-scope-out">OUT OF SCOPE</span>
                <span>{html.escape(" · ".join(sp.out_scope))}</span>
              </div>
            """
        scope_block = ""
        if scope_in_html or scope_out_html:
            scope_block = f"""
            <div class="spec-block">
              <div class="spec-block-title">🎯 Scope</div>
              <div class="scope-box">
                {scope_in_html}
                {scope_out_html}
              </div>
            </div>
            """

        # Rules HTML
        rules_block = ""
        if sp.rules:
            items = "".join(f"<li>{html.escape(r)}</li>" for r in sp.rules)
            rules_block = f"""
            <div class="spec-block section-rules">
              <div class="spec-block-title">📜 Business Rules</div>
              <ul class="rules-list">
                {items}
              </ul>
            </div>
            """

        # Acceptance Criteria HTML
        acs_block = ""
        if sp.acs:
            ac_rows = []
            for ac in sp.acs:
                code_cls = "badge-ec" if ac["code"].startswith("EC") else "badge-ac"
                ac_rows.append(f"""
                  <tr>
                    <td><span class="{code_cls}">{html.escape(ac['code'])}</span></td>
                    <td>{html.escape(ac['given'])}</td>
                    <td>{html.escape(ac['when'])}</td>
                    <td><strong>{html.escape(ac['then'])}</strong></td>
                  </tr>
                """)
            acs_block = f"""
            <div class="spec-block">
              <div class="spec-block-title">🎯 Acceptance Criteria ({len(sp.acs)} Criteria)</div>
              <table class="ac-table">
                <thead>
                  <tr>
                    <th style="width: 44px;">#</th>
                    <th>Given</th>
                    <th>When</th>
                    <th>Then</th>
                  </tr>
                </thead>
                <tbody>
                  {"".join(ac_rows)}
                </tbody>
              </table>
            </div>
            """
            acs_block += state_flow_html(sp.acs)

        # QA Handoff HTML
        qa_block = ""
        if sp.test_accounts or sp.test_data or sp.watch_out or sp.do_not_report:
            items = []
            if sp.test_accounts:
                items.append(f"• <strong>Accounts:</strong> {html.escape(sp.test_accounts)}")
            if sp.test_data:
                items.append(f"• <strong>Prepare:</strong> {html.escape(sp.test_data)}")
            if sp.do_not_report:
                items.append(f"• <strong>Do not report:</strong> {html.escape(sp.do_not_report)}")

            watch_html = ""
            if sp.watch_out:
                watch_html = f"""
                <div class="qa-alert">
                  ⚠️ <strong>Watch out:</strong> {html.escape(sp.watch_out)}
                </div>
                """

            qa_block = f"""
            <div class="spec-block section-qa">
              <div class="spec-block-title">🧪 Tester Handoff (Test Steps)</div>
              <div class="qa-box">
                <div class="qa-title">👤 Test Accounts & Data</div>
                <div class="qa-row">
                  {"<br>".join(items)}
                </div>
                {watch_html}
              </div>
            </div>
            """

        # Footer Source paths
        paths_html = ""
        if sp.source:
            # find paths
            found = re.findall(r"`([^`]+)`", sp.source) or [p.strip() for p in sp.source.split("·") if "/" in p]
            if found:
                p_tags = "".join(f'<span class="code-path">{html.escape(p.strip())}</span> ' for p in found)
                paths_html = f"<div>📂 {p_tags}</div>"

        size_html = f"<div>🔍 <strong>Size:</strong> {html.escape(sp.size_signal)}</div>" if sp.size_signal else ""

        stories_html.append(f"""
        <div class="spec-card {card_class}">
          <div class="card-top">
            <div class="card-head-row">
              <div class="card-id-block">
                <span class="badge-ticket">{html.escape(sp.ticket)}</span>
                <span class="card-slug">{html.escape(sp.slug)}</span>
              </div>
              {steps_tag}
            </div>

            <div class="card-head-row">
              <span class="status-stamp {stamp_class}">{stamp_text}</span>
              {sub_status}
            </div>

            <div class="story-statement">
              {html.escape(sp.story_text)}
            </div>
          </div>

          <div class="card-content">
            {scope_block}
            {rules_block}
            {acs_block}
            {qa_block}
          </div>

          <div class="card-footer">
            {size_html}
            {paths_html}
          </div>
        </div>
        """)

    # Column 3: Questions, Decisions, Not Now
    q_stickies = []
    for q in all_questions:
        is_blocker = bool(q.get("blocking"))
        tag_html = '<span class="tag-blocker">🚫 BLOCKS ' + html.escape(str(q.get("blocks", "")).upper()) + '</span>' if is_blocker else f'<span class="tag-later">{html.escape(q.get("blocks", "later"))}</span>'
        ans_html = f'<div style="font-size: 11px; margin-top: 4px; color: #15803d;"><strong>Answer:</strong> {html.escape(q["answer"])}</div>' if q.get("answer") else ""

        q_stickies.append(f"""
        <div class="sticky-note pink">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <span class="note-id">{html.escape(q['id'])} · {html.escape(q.get('from', ''))}</span>
            {tag_html}
          </div>
          <p style="font-size: 13.5px; line-height: 1.5; font-weight: 500;">
            "{html.escape(q['question'])}"
          </p>
          <div style="font-size: 12px; background: rgba(255,255,255,0.7); padding: 8px 10px; border-radius: 6px;">
            👤 <strong>Ask:</strong> {html.escape(q.get('ask', ''))}
            {ans_html}
          </div>
        </div>
        """)

    decisions_html = ""
    if unique_decisions:
        d_items = "".join(f"• {html.escape(d)}<br>" for d in unique_decisions)
        decisions_html = f"""
        <div class="sticky-note yellow-mini">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <span class="note-id">⚡ Decisions Log</span>
            <span style="font-size: 11px; font-weight: 700; background: #fef08a; padding: 2px 6px; border-radius: 4px;">Audited</span>
          </div>
          <div style="font-size: 12.5px; line-height: 1.6;">
            {d_items}
          </div>
        </div>
        """

    not_now_html = ""
    if all_not_now:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in all_not_now)
        not_now_html = f"""
        <div class="sticky-note gray">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <span class="note-id">📦 Not Now (Scope Cut)</span>
          </div>
          <ul style="font-size: 12.5px; padding-left: 18px; line-height: 1.7; color: #475569;">
            {items}
          </ul>
        </div>
        """

    flow_badge = html.escape(maps[0].flow) if maps else "scrum-spec"
    col3_html = "".join(q_stickies) + decisions_html + not_now_html

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} · {flow_badge}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-canvas: #f8f9fa;
      --dot-color: #cbd5e1;
      --text-main: #0f172a;
      --text-muted: #64748b;
      
      --sticky-yellow: #fefce8;
      --sticky-yellow-border: #fef08a;
      --sticky-blue: #eff6ff;
      --sticky-blue-border: #bfdbfe;
      --sticky-pink: #fff1f2;
      --sticky-pink-border: #fecdd3;
      --sticky-gray: #f8fafc;
      --sticky-gray-border: #e2e8f0;

      --section-border: #cbd5e1;
      --section-bg: rgba(255, 255, 255, 0.85);
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }}

    html, body {{
      width: 100%;
      height: 100%;
      background-color: var(--bg-canvas);
      background-image: radial-gradient(var(--dot-color) 1.5px, transparent 1.5px);
      background-size: 24px 24px;
      background-attachment: local;
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      overflow: auto;
      -webkit-overflow-scrolling: touch;
      overscroll-behavior: contain;
    }}

    #zoom-wrapper {{
      transform-origin: 0 0;
      min-width: 2400px;
      min-height: 1600px;
      padding: 110px 120px 240px 120px;
      display: inline-flex;
      flex-direction: column;
      gap: 36px;
      will-change: transform;
    }}

    .top-bar {{
      position: fixed;
      top: 16px;
      left: 20px;
      right: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 1000;
      pointer-events: none;
    }}

    .brand-pill {{
      pointer-events: auto;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(12px);
      padding: 8px 18px;
      border-radius: 9999px;
      box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08);
      border: 1px solid rgba(0,0,0,0.08);
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .brand-title {{
      font-weight: 700;
      font-size: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .tag-flow {{
      background: #eff6ff;
      color: #2563eb;
      padding: 3px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
    }}

    .meta-time {{
      font-size: 11px;
      color: #64748b;
      margin-left: 4px;
    }}

    .center-controls {{
      pointer-events: auto;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(12px);
      padding: 4px;
      border-radius: 9999px;
      box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08);
      border: 1px solid rgba(0,0,0,0.08);
      display: flex;
      align-items: center;
      gap: 4px;
    }}

    .role-btn {{
      background: none;
      border: none;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      color: #64748b;
      cursor: pointer;
      transition: all 0.15s;
    }}

    .role-btn:hover {{
      background: #f1f5f9;
      color: #0f172a;
    }}

    .role-btn.active {{
      background: #0f172a;
      color: white;
    }}

    .zoom-controls {{
      pointer-events: auto;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(12px);
      padding: 4px;
      border-radius: 9999px;
      box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08);
      border: 1px solid rgba(0,0,0,0.08);
      display: flex;
      align-items: center;
      gap: 2px;
    }}

    .zoom-btn {{
      background: none;
      border: none;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      font-weight: 600;
      color: #475569;
      transition: all 0.15s;
    }}

    .zoom-btn:hover {{
      background: #f1f5f9;
      color: #0f172a;
    }}

    .zoom-level {{
      font-size: 12px;
      font-weight: 600;
      padding: 0 6px;
      min-width: 44px;
      text-align: center;
      color: #475569;
    }}

    .fig-section {{
      background: var(--section-bg);
      border: 2px dashed var(--section-border);
      border-radius: 28px;
      padding: 28px 32px 34px 32px;
      position: relative;
      box-shadow: 0 10px 35px rgba(0,0,0,0.02);
    }}

    .section-label {{
      position: absolute;
      top: -15px;
      left: 32px;
      background: #1e293b;
      color: white;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 5px 14px;
      border-radius: 9999px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.18);
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .steps-row {{
      display: flex;
      align-items: center;
      gap: 20px;
    }}

    .step-card {{
      background: var(--sticky-blue);
      border: 1.5px solid var(--sticky-blue-border);
      border-radius: 14px;
      padding: 16px 18px;
      width: 250px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.04);
      display: flex;
      flex-direction: column;
      gap: 6px;
      transform: rotate(-0.5deg);
    }}

    .step-num {{
      font-family: 'Caveat', cursive;
      font-size: 22px;
      font-weight: 700;
      color: #2563eb;
    }}

    .step-title {{
      font-size: 14px;
      font-weight: 700;
      color: #1e3a8a;
    }}

    .step-actor {{
      font-size: 11px;
      color: #3b82f6;
      font-weight: 600;
      background: rgba(255,255,255,0.85);
      padding: 3px 8px;
      border-radius: 6px;
      align-self: flex-start;
      margin-top: 4px;
    }}

    .step-arrow {{
      font-size: 22px;
      color: #94a3b8;
      font-weight: 700;
    }}

    .board-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(540px, 1fr)) 440px;
      gap: 32px;
      align-items: start;
    }}

    .status-stamp {{
      font-family: 'Caveat', cursive;
      font-size: 17px;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      white-space: nowrap;
    }}

    .status-stamp.approved {{
      background: #dcfce7;
      color: #15803d;
      border: 2px dashed #16a34a;
      transform: rotate(-1.5deg);
    }}

    .status-stamp.waiting {{
      background: #fee2e2;
      color: #b91c1c;
      border: 2px dashed #dc2626;
      transform: rotate(2deg);
    }}

    .spec-card {{
      background: #ffffff;
      border: 2px solid #e2e8f0;
      border-radius: 20px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.06), 0 2px 6px rgba(0,0,0,0.04);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      position: relative;
    }}

    .spec-card.card-approved {{
      border-top: 6px solid #22c55e;
    }}

    .spec-card.card-waiting {{
      border-top: 6px solid #ef4444;
    }}

    .card-top {{
      padding: 20px 22px 16px 22px;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .card-head-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }}

    .card-id-block {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .badge-ticket {{
      background: #1e293b;
      color: white;
      font-size: 12px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
    }}

    .card-slug {{
      font-size: 18px;
      font-weight: 700;
      color: #0f172a;
    }}

    .card-steps-tag {{
      font-size: 11px;
      font-weight: 600;
      background: #e0e7ff;
      color: #3730a3;
      padding: 2px 8px;
      border-radius: 9999px;
    }}

    .story-statement {{
      font-size: 14px;
      line-height: 1.5;
      color: #1e293b;
      background: #fefce8;
      border-left: 4px solid #eab308;
      padding: 10px 14px;
      border-radius: 0 8px 8px 0;
    }}

    .card-content {{
      padding: 18px 22px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}

    .spec-block {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .spec-block-title {{
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #64748b;
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .scope-box {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 12.5px;
      background: #f8fafc;
      padding: 10px 14px;
      border-radius: 10px;
      border: 1px solid #e2e8f0;
    }}

    .scope-row {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      line-height: 1.45;
    }}

    .tag-scope-in {{
      background: #dcfce7;
      color: #15803d;
      font-size: 10.5px;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 4px;
      white-space: nowrap;
    }}

    .tag-scope-out {{
      background: #f1f5f9;
      color: #64748b;
      font-size: 10.5px;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 4px;
      white-space: nowrap;
    }}

    .rules-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .rules-list li {{
      font-size: 12.5px;
      line-height: 1.45;
      padding: 6px 10px;
      background: #f1f5f9;
      border-radius: 6px;
      color: #334155;
    }}

    .ac-table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 12px;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      overflow: hidden;
    }}

    .ac-table th {{
      background: #f1f5f9;
      color: #475569;
      font-weight: 600;
      text-align: left;
      padding: 7px 10px;
      border-bottom: 1px solid #e2e8f0;
      font-size: 11px;
    }}

    .ac-table td {{
      padding: 8px 10px;
      border-bottom: 1px solid #f1f5f9;
      line-height: 1.4;
      vertical-align: top;
      color: #334155;
    }}

    .ac-table tr:last-child td {{
      border-bottom: none;
    }}

    .state-flow {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px;
      line-height: 1.45;
      white-space: pre-wrap;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 10px 12px;
      color: #334155;
    }}

    .badge-ac {{
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
      font-size: 11px;
      color: #2563eb;
    }}

    .badge-ec {{
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
      font-size: 11px;
      color: #d97706;
    }}

    .qa-box {{
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      border-radius: 10px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      font-size: 12.5px;
      color: #166534;
    }}

    .qa-title {{
      font-weight: 700;
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
      color: #15803d;
    }}

    .qa-row {{
      line-height: 1.45;
    }}

    .qa-alert {{
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 6px;
      padding: 6px 10px;
      color: #991b1b;
      font-size: 11.5px;
      margin-top: 4px;
    }}

    .card-footer {{
      padding: 12px 22px;
      background: #f8fafc;
      border-top: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: #64748b;
    }}

    .code-path {{
      font-family: 'JetBrains Mono', monospace;
      background: #e2e8f0;
      padding: 1px 5px;
      border-radius: 4px;
      font-size: 10.5px;
      color: #334155;
    }}

    .sticky-note {{
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 6px 18px rgba(0,0,0,0.06);
      display: flex;
      flex-direction: column;
      gap: 12px;
      position: relative;
      margin-bottom: 24px;
    }}

    .sticky-note.pink {{
      background: var(--sticky-pink);
      border: 1.5px solid var(--sticky-pink-border);
      color: #881337;
      transform: rotate(-1deg);
    }}

    .sticky-note.gray {{
      background: var(--sticky-gray);
      border: 1.5px solid var(--sticky-gray-border);
      color: #334155;
    }}

    .sticky-note.yellow-mini {{
      background: #fef9c3;
      border: 1.5px solid #fef08a;
      color: #713f12;
      transform: rotate(1deg);
    }}

    .note-id {{
      font-family: 'Caveat', cursive;
      font-size: 24px;
      font-weight: 700;
    }}

    .tag-blocker {{
      background: #fee2e2;
      color: #b91c1c;
      border: 1px solid #f87171;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 700;
    }}

    .tag-later {{
      background: #f1f5f9;
      color: #64748b;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
    }}

    body.filter-po .spec-block.section-qa,
    body.filter-po .card-footer {{
      opacity: 0.25;
    }}

    body.filter-dev .spec-block.section-qa {{
      opacity: 0.25;
    }}

    body.filter-tester .spec-block.section-rules,
    body.filter-tester .scope-box,
    body.filter-tester .card-footer {{
      opacity: 0.25;
    }}

    .helper-bar {{
      position: fixed;
      bottom: 16px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(15, 23, 42, 0.9);
      color: white;
      padding: 8px 20px;
      border-radius: 9999px;
      font-size: 12px;
      pointer-events: none;
      backdrop-filter: blur(8px);
      box-shadow: 0 4px 20px rgba(0,0,0,0.2);
      display: flex;
      align-items: center;
      gap: 12px;
      z-index: 1000;
    }}
  </style>
</head>
<body>

  <div class="top-bar">
    <div class="brand-pill">
      <span style="font-size: 20px;">📋</span>
      <span class="brand-title">Story Map <span class="tag-flow">{flow_badge}</span></span>
      <span class="meta-time">Generated {now_str}</span>
    </div>

    <div class="center-controls">
      <button class="role-btn active" onclick="setRole('all', this)">All Specs</button>
      <button class="role-btn" onclick="setRole('po', this)">PO View</button>
      <button class="role-btn" onclick="setRole('dev', this)">Dev View</button>
      <button class="role-btn" onclick="setRole('tester', this)">QA / Tester View</button>
    </div>

    <div class="zoom-controls">
      <button class="zoom-btn" id="zoomOut" title="Zoom Out">-</button>
      <span class="zoom-level" id="zoomLevel">100%</span>
      <button class="zoom-btn" id="zoomIn" title="Zoom In">+</button>
      <button class="zoom-btn" id="zoomReset" title="Reset (100%)">↺</button>
    </div>
  </div>

  <div id="zoom-wrapper">
    {steps_html}

    <div class="fig-section">
      <span class="section-label">📌 Sprint Backlog · Complete Stories & Spec</span>
      <div class="board-grid">
        {"".join(stories_html)}
        <div>
          {col3_html}
        </div>
      </div>
    </div>
  </div>

  <div class="helper-bar">
    <span>✨ <strong>Pinch trackpad with 2 fingers</strong> to zoom</span>
    <span>•</span>
    <span><strong>Two-finger scroll</strong> to pan the canvas</span>
  </div>

  <script>
    const wrapper = document.getElementById('zoom-wrapper');
    let currentZoom = 1.0;

    function zoomAt(clientX, clientY, targetZoom) {{
      const newZoom = Math.min(Math.max(targetZoom, 0.35), 2.2);
      if (Math.abs(newZoom - currentZoom) < 0.001) return;

      const scrollX = window.scrollX || document.documentElement.scrollLeft;
      const scrollY = window.scrollY || document.documentElement.scrollTop;

      const contentX = (scrollX + clientX) / currentZoom;
      const contentY = (scrollY + clientY) / currentZoom;

      currentZoom = newZoom;
      wrapper.style.transform = `scale(${{currentZoom}})`;
      
      const dotSize = Math.max(12, Math.round(24 * currentZoom));
      document.body.style.backgroundSize = `${{dotSize}}px ${{dotSize}}px`;
      document.getElementById('zoomLevel').innerText = `${{Math.round(currentZoom * 100)}}%`;

      const newScrollX = contentX * currentZoom - clientX;
      const newScrollY = contentY * currentZoom - clientY;
      window.scrollTo(newScrollX, newScrollY);
    }}

    window.addEventListener('wheel', (e) => {{
      if (e.ctrlKey || e.metaKey) {{
        e.preventDefault();
        const factor = Math.exp(-e.deltaY * 0.012);
        zoomAt(e.clientX, e.clientY, currentZoom * factor);
      }}
    }}, {{ passive: false }});

    let gestureStartZoom = 1.0;
    window.addEventListener('gesturestart', (e) => {{
      e.preventDefault();
      gestureStartZoom = currentZoom;
    }});

    window.addEventListener('gesturechange', (e) => {{
      e.preventDefault();
      zoomAt(e.clientX, e.clientY, gestureStartZoom * e.scale);
    }});

    window.addEventListener('gestureend', (e) => {{
      e.preventDefault();
    }});

    function zoomButton(factor) {{
      const centerX = window.innerWidth / 2;
      const centerY = window.innerHeight / 2;
      zoomAt(centerX, centerY, currentZoom * factor);
    }}

    document.getElementById('zoomIn').onclick = () => zoomButton(1.2);
    document.getElementById('zoomOut').onclick = () => zoomButton(1 / 1.2);
    document.getElementById('zoomReset').onclick = () => {{
      const centerX = window.innerWidth / 2;
      const centerY = window.innerHeight / 2;
      zoomAt(centerX, centerY, 1.0);
    }};

    function setRole(role, btn) {{
      document.querySelectorAll('.role-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.body.className = '';
      if (role !== 'all') {{
        document.body.classList.add(`filter-${{role}}`);
      }}
    }}
  </script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a FigJam-style HTML board from scrum-spec documents.")
    parser.add_argument("folder", nargs="?", default="scrum-spec", help="Folder containing scrum-spec docs (default: scrum-spec)")
    parser.add_argument("-o", "--output", help="Path to write board.html (default: <folder>/board.html)")
    parser.add_argument("--open", action="store_true", help="Open the generated board in the default browser")
    parser.add_argument("--title", default="Story Map & Sprint Board", help="Title for the board")

    args = parser.parse_args(argv)
    target_dir = Path(args.folder).resolve()

    if not target_dir.exists():
        # Fall back to current dir if folder doesn't exist
        if Path("scrum-spec").exists():
            target_dir = Path("scrum-spec").resolve()
        else:
            target_dir = Path(".").resolve()

    maps, specs = discover(target_dir)

    if not maps and not specs:
        print(f"Warning: No valid scrum-spec documents (map.md or spec.md) found under {target_dir}", file=sys.stderr)

    out_path = Path(args.output).resolve() if args.output else target_dir / "board.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = render_html(maps, specs, title=args.title)
    out_path.write_text(html_content, encoding="utf-8")

    print(f"✅ Board generated: {out_path} ({len(specs)} stories, {len(maps)} story maps)")

    if args.open:
        webbrowser.open(out_path.as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
