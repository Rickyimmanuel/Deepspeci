"""
DeepSpeci Streamlit UI
Workspace-driven — all settings configurable from the UI.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import streamlit as st

from config.loader import get_config, reload_config
from config.workspace import (
    load_workspace,
    save_workspace,
    add_provider,
    remove_provider,
    set_active_provider,
    list_provider_names,
    get_active_provider,
    get_providers,
    save_jira_config,
    get_jira_config,
    save_confluence_config,
    get_confluence_config,
)
from models.domain import AnalyzeRequest, InputSource, LLMProvider
from api.orchestrator import Orchestrator
from services.normalizer import DocumentNormalizer
from services.output import OutputService
from services.audit import AuditLogger

# ---------- Page config ----------
st.set_page_config(
    page_title="DeepSpeci — Requirement Quality Analysis",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =====================================================================
# SIDEBAR — Workspace Settings
# =====================================================================
with st.sidebar:
    st.title("🔍 DeepSpeci")
    cfg = get_config()
    st.caption(f"v{cfg.version} · {cfg.environment}")

    # =========== LLM Configuration ===========
    st.divider()
    st.subheader("🤖 LLM Configuration")

    ws = load_workspace()
    provider_names = list_provider_names(ws)
    active = get_active_provider(ws)
    active_idx = provider_names.index(active) if active in provider_names else 0

    selected_provider = st.selectbox(
        "Active Provider",
        provider_names,
        index=active_idx,
        help="Selected provider is used for all analyses.",
    )

    # Status indicator for active provider
    if selected_provider == "mock":
        st.caption("⚠️ Using mock adapter (demo only)")
    else:
        providers_config = get_providers(ws)
        if selected_provider in providers_config:
            p = providers_config[selected_provider]
            has_key = bool(p.get("api_key"))
            has_url = bool(p.get("base_url"))
            if has_key and has_url:
                st.caption(f"✅ Configured — {p.get('model_name', 'default')}")
            elif has_url:
                st.caption("⚠️ API key missing")
            else:
                st.caption("❌ Not configured")
        else:
            st.caption("❌ Not configured — add below")

    # Activate provider
    if selected_provider != active:
        set_active_provider(selected_provider)
        reload_config()

    # Add new provider
    with st.expander("➕ Add / Edit Provider"):
        prov_name = st.text_input("Provider Name", placeholder="e.g. kimi, openai, copilot")
        prov_url = st.text_input("Base URL", placeholder="https://api.openai.com/v1/chat/completions")
        prov_key = st.text_input("API Key", type="password", placeholder="sk-...")
        prov_model = st.text_input("Model Name", value="gpt-4o")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save Provider", use_container_width=True):
                if prov_name:
                    add_provider(prov_name, prov_url, prov_key, prov_model)
                    set_active_provider(prov_name)
                    reload_config()
                    st.success(f"✅ Saved & activated: {prov_name}")
                    st.rerun()
                else:
                    st.warning("Provider name required")
        with c2:
            if st.button("🔌 Test LLM", use_container_width=True):
                if prov_url and prov_key:
                    import httpx
                    try:
                        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {prov_key}"}
                        payload = {"model": prov_model, "messages": [{"role": "user", "content": "Reply with: OK"}], "max_tokens": 10}
                        r = httpx.post(prov_url, headers=headers, json=payload, timeout=15)
                        r.raise_for_status()
                        reply = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                        st.success(f"✅ Connected — reply: {reply.strip()}")
                    except Exception as exc:
                        st.error(f"❌ {exc}")
                else:
                    st.warning("URL and API key required")

    # Remove provider
    removable = [p for p in provider_names if p != "mock"]
    if removable:
        with st.expander("🗑️ Remove Provider"):
            to_remove = st.selectbox("Select provider", removable, key="rem_prov")
            if st.button("Remove", use_container_width=True):
                remove_provider(to_remove)
                reload_config()
                st.success(f"Removed: {to_remove}")
                st.rerun()

    # =========== Jira Configuration ===========
    st.divider()
    st.subheader("🔗 Jira Configuration")

    jira_ws = get_jira_config(ws)
    jira_status = "✅ Connected" if jira_ws.get("url") and jira_ws.get("api_token") else "❌ Not configured"
    st.caption(jira_status)

    with st.expander("Configure Jira"):
        j_url = st.text_input("Jira Base URL", value=jira_ws.get("url", ""), placeholder="https://your-org.atlassian.net")
        j_email = st.text_input("Jira Email", value=jira_ws.get("email", ""))
        j_token = st.text_input("Jira API Token", type="password", value=jira_ws.get("api_token", ""))
        j_proj = st.text_input("Project Key (optional)", value=jira_ws.get("project_key", ""))

        jc1, jc2 = st.columns(2)
        with jc1:
            if st.button("💾 Save Jira", use_container_width=True):
                save_jira_config(j_url, j_email, j_token, j_proj)
                reload_config()
                st.success("✅ Jira config saved")
                st.rerun()
        with jc2:
            if st.button("🔌 Test Jira", use_container_width=True):
                if j_url and j_token:
                    import httpx
                    try:
                        r = httpx.get(
                            f"{j_url.rstrip('/')}/rest/api/3/myself",
                            auth=(j_email, j_token),
                            headers={"Accept": "application/json"},
                            timeout=15,
                        )
                        r.raise_for_status()
                        name = r.json().get("displayName", "OK")
                        st.success(f"✅ Connected as {name}")
                    except Exception as exc:
                        st.error(f"❌ {exc}")
                else:
                    st.warning("URL and token required")

    # =========== Confluence Configuration ===========
    st.divider()
    st.subheader("📄 Confluence Configuration")

    conf_ws = get_confluence_config(ws)
    conf_status = "✅ Connected" if conf_ws.get("url") and conf_ws.get("api_token") else "❌ Not configured"
    st.caption(conf_status)

    with st.expander("Configure Confluence"):
        c_url = st.text_input("Confluence URL", value=conf_ws.get("url", ""), placeholder="https://your-org.atlassian.net")
        c_email = st.text_input("Confluence Email", value=conf_ws.get("email", ""))
        c_token = st.text_input("Confluence API Token", type="password", value=conf_ws.get("api_token", ""))
        c_space = st.text_input("Space Key", value=conf_ws.get("space_key", ""))

        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("💾 Save Confluence", use_container_width=True):
                save_confluence_config(c_url, c_email, c_token, c_space)
                reload_config()
                st.success("✅ Confluence config saved")
                st.rerun()
        with cc2:
            if st.button("🔌 Test Confluence", use_container_width=True):
                if c_url and c_token:
                    import httpx
                    try:
                        url = f"{c_url.rstrip('/')}/wiki/rest/api/space"
                        if c_space:
                            url += f"/{c_space}"
                        r = httpx.get(url, auth=(c_email, c_token), headers={"Accept": "application/json"}, timeout=15)
                        r.raise_for_status()
                        st.success("✅ Connected")
                    except Exception as exc:
                        st.error(f"❌ {exc}")
                else:
                    st.warning("URL and token required")

    # =========== Recent Runs ===========
    st.divider()
    st.subheader("📋 Recent Runs")
    audit = AuditLogger()
    for e in audit.read_entries(5):
        st.caption(f"• {e.get('timestamp','')[:19]} {e.get('status','')} ({e.get('llm_provider','')})")
    if not audit.read_entries(1):
        st.caption("No runs yet.")


# =====================================================================
# MAIN AREA
# =====================================================================
st.title("🔍 DeepSpeci")
st.markdown("Analyse requirements for **ambiguities**, **completeness**, **consistency**, and **enriched stories**.")

tab_text, tab_file, tab_jira, tab_conf = st.tabs(
    ["📝 Text", "📎 File Upload", "🔗 Jira", "📄 Confluence"]
)

with tab_text:
    text_input = st.text_area("Paste requirements", height=220,
                               placeholder="As a user I want to …")

with tab_file:
    uploaded = st.file_uploader("Upload doc", type=["txt", "md", "pdf", "docx", "png", "jpg", "jpeg"])

with tab_jira:
    jira_key = st.text_input("Jira issue key", placeholder="PROJ-123")

with tab_conf:
    conf_id = st.text_input("Confluence page ID", placeholder="123456")

st.divider()
active_prov = get_active_provider() or "mock"
st.caption(f"Active provider: **{active_prov}**")
run_btn = st.button("🚀 Analyse", type="primary", use_container_width=True)

if run_btn:
    orchestrator = Orchestrator()
    normalizer = DocumentNormalizer()
    report = None
    error_msg = None

    with st.spinner(f"Running analysis with **{active_prov}** …"):
        try:
            if text_input and text_input.strip():
                req = AnalyzeRequest(source=InputSource.MANUAL_TEXT, text=text_input)
                report = run_async(orchestrator.run_analysis(req))

            elif uploaded is not None:
                data = uploaded.read()
                docs = run_async(normalizer.from_file_bytes(data, uploaded.name))
                report = run_async(orchestrator.run_analysis_on_doc(docs[0]))

            elif jira_key and jira_key.strip():
                req = AnalyzeRequest(source=InputSource.JIRA, jira_issue_key=jira_key.strip())
                report = run_async(orchestrator.run_analysis(req))

            elif conf_id and conf_id.strip():
                req = AnalyzeRequest(source=InputSource.CONFLUENCE, confluence_page_id=conf_id.strip())
                report = run_async(orchestrator.run_analysis(req))
            else:
                st.warning("⚠️ Provide input in one of the tabs above.")
        except Exception as exc:
            error_msg = str(exc)

    if error_msg:
        st.error(f"❌ {error_msg}")

    if report:
        st.success(f"✅ Analysis complete — **{report.status.value}** (provider: {report.llm_provider.value})")

        if report.summary:
            st.subheader("📊 Summary")
            st.info(report.summary)

        t1, t2, t3, t4 = st.tabs(["Ambiguities", "Completeness", "Consistency", "Enriched Stories"])

        with t1:
            if report.ambiguities:
                for a in report.ambiguities:
                    with st.expander(f"📌 {a.location}"):
                        st.write(f"**Issue:** {a.description}")
                        st.write(f"**Suggestion:** {a.suggestion}")
            else:
                st.write("✅ No ambiguities detected.")

        with t2:
            if report.completeness_gaps:
                for g in report.completeness_gaps:
                    with st.expander(f"📌 {g.missing_aspect}"):
                        st.write(f"**Description:** {g.description}")
                        st.write(f"**Recommendation:** {g.recommendation}")
            else:
                st.write("✅ No completeness gaps found.")

        with t3:
            if report.consistency_warnings:
                for w in report.consistency_warnings:
                    with st.expander(f"⚠️ {w.conflict}"):
                        st.write(f"**Description:** {w.description}")
                        st.write(f"**Suggestion:** {w.suggestion}")
            else:
                st.write("✅ No consistency warnings.")

        with t4:
            if report.enriched_stories:
                for i, s in enumerate(report.enriched_stories, 1):
                    with st.expander(f"📖 Story {i}"):
                        st.write(f"**Original:** {s.original}")
                        st.write(f"**Enriched:** {s.enriched}")
                        if s.acceptance_criteria:
                            st.write("**Acceptance Criteria:**")
                            for ac in s.acceptance_criteria:
                                st.write(f"  • {ac}")
            else:
                st.write("No stories to enrich.")

        # ----- Actions -----
        st.divider()
        st.subheader("📤 Export")
        output = OutputService()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("⬇️ JSON", data=output.to_json(report),
                               file_name=f"report_{report.report_id[:8]}.json",
                               mime="application/json", use_container_width=True)
        with c2:
            st.download_button("⬇️ Markdown", data=output.to_markdown(report),
                               file_name=f"report_{report.report_id[:8]}.md",
                               mime="text/markdown", use_container_width=True)
        with c3:
            push_key = st.text_input("Jira key", key="push_jira")
            if st.button("🔗 Push to Jira", use_container_width=True) and push_key:
                try:
                    run_async(output.push_to_jira(push_key, report))
                    st.success(f"Pushed to {push_key}")
                except Exception as exc:
                    st.error(str(exc))

        with st.expander("🔎 Raw JSON"):
            st.json(report.model_dump(mode="json"))

        if report.error:
            st.error(f"⚠️ Error: {report.error}")
