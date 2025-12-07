import streamlit as st
import urllib.request
import urllib.parse
import json
import time
from openai import OpenAI
import streamlit.components.v1 as components

st.set_page_config(page_title="CarePathIQ", layout="wide", page_icon="🏥")

st.title("Clinical Pathway Agent")
st.markdown("A multi-phase, conversational assistant to build evidence-based clinical pathways.")

# --- Conversational dialogue library (restored from CLI prompts) ---
dialogue = {
    "intro": "Hello! I'm your Clinical Pathway Agent. I'm here to help you transform your clinical expertise and evidence-based medicine into a robust clinical pathway.",
    "phase_1_start": "Let's kick things off with the Scope. I'll ask you a few questions to frame the problem accurately.",
    "phase_2_intro": "Great job on the scope. Now, let's look at the science. We need to make sure our pathway is evidence-based. Ready to evaluate some evidence?",
    "phase_3_intro": "Now let's map out the logic. We need to ensure every decision point is clear and supported by the evidence we just gathered.",
    "phase_4_intro": "A pathway only works if people actually use it. Let's simulate the workflow.",
    "phase_5_intro": "We're in the home stretch. Now we need to operationalize this—turning a paper document into a live clinical tool.",
    "step_verification": "I've finished gathering inputs for this section. Please review the summary preview above.",
    "approval_request": ">> Do you approve this section? (Type 'YES' to proceed, anything else to abort): ",
    "locked": "Section approved. Updating Documentation...",
    "summary_generated": "The formal summary has been saved to '{filename}'."
}

# --- API key input (UI-first template) ---
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")
use_llm = False
client = None
if openai_api_key:
    try:
        client = OpenAI(api_key=openai_api_key)
        use_llm = True
        st.sidebar.success("LLM connected")
    except Exception as e:
        st.sidebar.error(f"LLM init error: {e}")

# Initialize session state pathway_data
if 'pathway_data' not in st.session_state:
    st.session_state.pathway_data = {
        'scope': {},
        'evidence': [],
        'logic': {},
        'testing': {},
        'operations': {},
        'mermaid': ''
    }

# Conversational assistant state
if 'assistant_messages' not in st.session_state:
    st.session_state.assistant_messages = [
        {'role': 'assistant', 'content': 'Hello — I can help you build a clinical pathway. Ask me for phase guidance or type a question.'}
    ]

def append_assistant_message(role, content):
    st.session_state.assistant_messages.append({'role': role, 'content': content})
# Assistant panel moved below after helper functions are defined

def summarize_pathway():
    """Return a concise summary (LLM-assisted if key present) of `st.session_state.pathway_data`.

    Includes: scope, evidence bank (top 5), and mermaid code (if any).
    """
    data = st.session_state.pathway_data
    scope = data.get('scope', {})
    sb = []
    sb.append('Summary of Clinical Pathway:')
    cond = scope.get('condition') or 'Not specified'
    sb.append(f"- Condition: {cond}")
    sb.append(f"- Population: {scope.get('population','Not specified')}")
    sb.append(f"- Setting: {scope.get('setting','Not specified')}")
    objectives = scope.get('objectives', [])
    if objectives:
        sb.append('- Objectives:')
        for o in objectives:
            sb.append(f"  - {o}")
    else:
        sb.append('- Objectives: None specified')

    evidence = data.get('evidence', [])
    if evidence:
        sb.append(f"- Evidence bank ({len(evidence)} items), top entries:")
        for e in evidence[:5]:
            point = e.get('point','')
            cite = e.get('citation','')
            ver = e.get('verification','')
            sb.append(f"  - {point} — {cite} — {ver}")
    else:
        sb.append('- Evidence bank: empty')

    mermaid = data.get('mermaid','').strip()
    if mermaid:
        sb.append('- Mermaid flowchart code included (trimmed):')
        sb.append('\n'.join(mermaid.splitlines()[:20]))
    else:
        sb.append('- Mermaid flowchart: none')

    plaintext = '\n'.join(sb)

    # If LLM available, ask it to rewrite/condense the summary
    if client:
        prompt = (
            "Please produce a concise, user-facing summary of the clinical pathway data below. "
            "Keep it to 4-6 short bullet points and highlight any missing information.\n\n" + plaintext
        )
        llm_reply = ask_assistant(prompt, context='You are a concise clinical pathway assistant.')
        # If LLM returned something meaningful, prefer it
        if llm_reply and not llm_reply.startswith('LLM error'):
            return llm_reply

    return plaintext


# ------------------- Conversational Phase Runner -------------------
if 'current_phase' not in st.session_state:
    st.session_state.current_phase = 1

def append_phase_message(msg):
    append_assistant_message('assistant', msg)

def propose_structure_from_scope():
    condition = st.session_state.pathway_data.get('scope', {}).get('condition','the condition')
    return [
        {"type": "Start Node", "name": f"Patient presents with {condition}"},
        {"type": "Decision Node", "name": "Risk Stratification / Severity Assessment"},
        {"type": "Note", "name": "Clinical Risk Score Details (e.g., Calculator)"},
        {"type": "Process Step", "name": "Initial Medical Management"},
        {"type": "End Node", "name": "Disposition (Admit vs. Discharge)"}
    ]

def auto_run_phase_2():
    """Automatically search PubMed for proposed decision elements and save evidence."""
    data = st.session_state.pathway_data
    condition = data.get('scope', {}).get('condition', 'Clinical')
    elements = propose_structure_from_scope()
    evidence_bank = []
    append_phase_message(f"Running automated PubMed searches for {len(elements)} elements...")
    for item in elements:
        point = item['name']
        query = f"({condition}) AND ({point}) AND (Guideline[pt] OR Systematic Review[pt])"
        results = search_pubmed(query, retmax=2)
        if results:
            chosen = results[0]
            evidence_bank.append({'id': chosen, 'decision_point': point, 'element_type': item['type']})
            append_phase_message(f"Found evidence for '{point}': {chosen}")
        else:
            append_phase_message(f"No API hits for '{point}', please add manual citation.")
            evidence_bank.append({'id': 'MANUAL_REQUIRED', 'decision_point': point, 'element_type': item['type']})
    data.setdefault('evidence', {})
    data['evidence']['studies'] = evidence_bank
    st.session_state.pathway_data = data
    append_phase_message('Evidence bank updated with automated search results.')

def auto_run_phase_3():
    """Generate mermaid flowchart from evidence nodes."""
    data = st.session_state.pathway_data
    studies = data.get('evidence', {}).get('studies', [])
    nodes = [s.get('decision_point') for s in studies if s.get('decision_point')]
    entry = data.get('logic', {}).get('entry') or (st.session_state.pathway_data.get('scope',{}).get('condition','Entry'))
    exit_pt = data.get('logic', {}).get('endpoints') or 'Disposition'
    if not nodes:
        append_phase_message('No decision nodes available to generate flowchart. Add evidence first.')
        return
    code = generate_mermaid(entry, nodes, exit_pt)
    st.session_state.pathway_data['mermaid'] = code
    append_phase_message('Mermaid flowchart generated from evidence nodes.')

def run_phase(phase):
    if phase == 1:
        # Use the conversational prompt from dialogue
        append_phase_message(dialogue.get('phase_1_start'))
    elif phase == 2:
        append_phase_message(dialogue.get('phase_2_intro'))
        auto_run_phase_2()
    elif phase == 3:
        append_phase_message(dialogue.get('phase_3_intro'))
        auto_run_phase_3()
    elif phase == 4:
        append_phase_message(dialogue.get('phase_4_intro'))
    elif phase == 5:
        append_phase_message(dialogue.get('phase_5_intro'))


def search_pubmed(query, retmax=3):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search_params = {'db': 'pubmed', 'term': query, 'retmode': 'json', 'retmax': retmax}
    try:
        url = base_url + "esearch.fcgi?" + urllib.parse.urlencode(search_params)
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            id_list = data.get('esearchresult', {}).get('idlist', [])
        if not id_list:
            return []
        summary_params = {'db': 'pubmed', 'id': ','.join(id_list), 'retmode': 'json'}
        url = base_url + "esummary.fcgi?" + urllib.parse.urlencode(summary_params)
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            result = data.get('result', {})
            citations = []
            for uid in id_list:
                if uid in result:
                    item = result[uid]
                    title = item.get('title', 'No Title').replace("&lt;i&gt;", "").replace("&lt;/i&gt;", "")
                    authors = item.get('authors', [])
                    first_author = authors[0]['name'] if authors else 'Unknown'
                    pub_date = item.get('pubdate', 'No Date')[:4]
                    source = item.get('source', 'Journal')
                    citations.append(f"{first_author} et al. ({pub_date}). {title}. {source}.")
            return citations
    except Exception as e:
        return [f"Error fetching PubMed data: {e}"]

def ask_assistant(prompt, context=''):
    if not client:
        return 'Analysis unavailable (No Key)'
    full = f"{context}\n\nTask: {prompt}"
    try:
        stream = client.chat.completions.create(model='gpt-3.5-turbo', messages=[{'role':'user','content':full}], stream=False)
        # Depending on SDK, adapt:
        if hasattr(stream, 'choices'):
            return stream.choices[0].message.content
        return getattr(stream, 'text', str(stream))
    except Exception as e:
        return f'LLM error: {e}'

def generate_mermaid(entry, nodes, exit_point):
    if not client:
        return 'graph TD; A[No LLM]-->B[Manual]'
    prompt = f"Create a Mermaid.js flowchart (graph TD) for Entry: {entry} Nodes: {nodes} Exit: {exit_point}. Output only raw graph TD code."
    return ask_assistant(prompt, context='You are a clinical pathway visual designer.').replace('```mermaid','').replace('```','').strip()

# Assistant chat panel (placed after helper functions so dependencies exist)
with st.expander('Assistant — conversational help', expanded=True):
    for msg in st.session_state.assistant_messages:
        try:
            st.chat_message(msg['role']).write(msg['content'])
        except Exception:
            st.write(f"**{msg['role'].title()}:** {msg['content']}")

    user_q = st.chat_input('Ask the assistant about the workflow or the current phase')
    if user_q:
        append_assistant_message('user', user_q)
        if 'summarize' in user_q.lower() or 'summary' in user_q.lower():
            try:
                summary = summarize_pathway()
            except Exception as e:
                summary = f'Error generating summary: {e}'
            append_assistant_message('assistant', summary)
        else:
            reply = ask_assistant(user_q)
            append_assistant_message('assistant', reply)

    if st.button('Summarize current pathway'):
        try:
            summary = summarize_pathway()
        except Exception as e:
            summary = f'Error generating summary: {e}'
        append_assistant_message('assistant', summary)

# --- UI Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Scope & Charter","2. Evidence Appraisal","3. Logic & Visuals","4. User Testing","5. Final Report"])

with tab1:
    st.header("Phase 1 — Scope & Charter")
    with st.form('scope_form'):
        cond = st.text_input('Clinical Condition', value=st.session_state.pathway_data['scope'].get('condition',''))
        pop = st.text_input('Target Population', value=st.session_state.pathway_data['scope'].get('population',''))
        setting = st.text_input('Care Setting', value=st.session_state.pathway_data['scope'].get('setting',''))
        problem = st.text_area('Problem Statement', value=st.session_state.pathway_data['scope'].get('problem',''))
        objectives = st.text_area('SMART Objectives', value='\n'.join(st.session_state.pathway_data['scope'].get('objectives',[])))
        if st.form_submit_button('Save Charter'):
            st.session_state.pathway_data['scope'] = {'condition':cond,'population':pop,'setting':setting,'problem':problem,'objectives':[o for o in objectives.split('\n') if o.strip()]}
            st.success('Scope saved')
        # Phase controls
        if st.form_submit_button('Auto-run Phase 1 (Guidance)'):
            run_phase(1)
        if st.form_submit_button('Get guidance (Assistant)'):
            append_phase_message(dialogue.get('phase_1_start'))
        if st.form_submit_button('Next: Go to Phase 2'):
            st.session_state.current_phase = 2
            run_phase(2)

with tab2:
    st.header('Phase 2 — Rapid Evidence Appraisal')
    node = st.text_input('Decision Node / Clinical Question')
    if st.button('Search PubMed & Verify') and node:
        condition = st.session_state.pathway_data['scope'].get('condition','Clinical')
        query = f"({condition}) AND ({node}) AND (Guideline[pt] OR Systematic Review[pt])"
        cites = search_pubmed(query)
        if cites:
            st.write('Top results:')
            for i,c in enumerate(cites,1):
                st.write(f"{i}. {c}")
            sel = st.number_input('Select # to use as citation (0 to enter manual)', min_value=0, max_value=len(cites), value=1)
            if sel==0:
                citation = st.text_input('Manual citation')
            else:
                citation = cites[int(sel)-1]
            verification = ask_assistant(f"Does the citation '{citation}' support the decision '{node}'? Answer 'Verified' or 'Warning' with one-line rationale.") if client else 'Manual — no LLM'
            entry = {'point':node,'citation':citation,'verification':verification}
            st.session_state.pathway_data['evidence'].append(entry)
            st.success('Evidence saved')
        else:
            st.warning('No citations found — try manual entry')

    # Phase controls
    if st.button('Auto-run Phase 2 (Automated Evidence Search)'):
        run_phase(2)
    if st.button('Get guidance (Assistant)'):
        append_phase_message(dialogue.get('phase_2_intro'))
    if st.button('Next: Go to Phase 3'):
        st.session_state.current_phase = 3
        run_phase(3)

    if st.session_state.pathway_data['evidence']:
        st.markdown('### Evidence Bank')
        for i,e in enumerate(st.session_state.pathway_data['evidence']):
            with st.expander(f"{i+1}. {e['point']}"):
                st.write(f"**Citation:** {e['citation']}")
                st.info(f"**Verification:** {e['verification']}")

with tab3:
    st.header('Phase 3 — Logic & Visuals')
    col1,col2 = st.columns(2)
    entry_pt = col1.text_input('Entry Trigger', value=st.session_state.pathway_data['logic'].get('entry','Triage'))
    exit_pt = col2.text_input('Exit/Disposition', value=st.session_state.pathway_data['logic'].get('endpoints','Disposition'))
    if st.button('Generate Flowchart'):
        nodes = [e['point'] for e in st.session_state.pathway_data['evidence']]
        if not nodes:
            st.error('Add evidence nodes first (Tab 2)')
        else:
            code = generate_mermaid(entry_pt, nodes, exit_pt)
            st.session_state.pathway_data['mermaid'] = code
            st.session_state.pathway_data['logic'] = {'entry':entry_pt,'endpoints':exit_pt,'nodes':nodes}
            st.success('Mermaid generated')

    # Phase controls
    if st.button('Auto-run Phase 3 (Generate from Evidence)'):
        run_phase(3)
    if st.button('Get guidance (Assistant)'):
        append_phase_message(dialogue.get('phase_3_intro'))
    if st.button('Next: Go to Phase 4'):
        st.session_state.current_phase = 4
        run_phase(4)

    if st.session_state.pathway_data.get('mermaid'):
        mermaid_html = f"""
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        <div class="mermaid">{st.session_state.pathway_data['mermaid']}</div>
        """
        st.write('### Interactive Flowchart')
        components.html(mermaid_html, height=500, scrolling=True)

with tab4:
    st.header('Phase 4 — User Testing')
    heur = st.text_area('Heuristic Issues Found', value=st.session_state.pathway_data['testing'].get('issues',''))
    mitig = st.text_area('Mitigation Plan', value=st.session_state.pathway_data['testing'].get('mitigation',''))
    if st.button('Save Testing'):
        st.session_state.pathway_data['testing'] = {'issues':heur,'mitigation':mitig,'status':'Saved'}
        st.success('Testing feedback saved')

    # Phase controls
    if st.button('Auto-run Phase 4 (Testing Guidance)'):
        run_phase(4)
    if st.button('Get guidance (Assistant)'):
        append_phase_message(dialogue.get('phase_4_intro'))
    if st.button('Next: Go to Phase 5'):
        st.session_state.current_phase = 5
        run_phase(5)

with tab5:
    st.header('Phase 5 — Final Report')
    if st.button('Compile Final Report'):
        data = st.session_state.pathway_data
        scope = data.get('scope',{})
        md = f"# Clinical Pathway: {scope.get('condition','Draft')}\n\n"
        md += f"## 1. Project Charter\n{scope.get('problem','')}\n\n"
        md += "## 2. Evidence Appraisal\n| Decision | Citation | Verification |\n|---|---|---|\n"
        for e in data.get('evidence',[]):
            md += f"| {e['point']} | {e['citation']} | {e['verification']} |\n"
        md += f"\n## 3. Visual Logic\n```mermaid\n{data.get('mermaid','')}\n```\n"
        md += f"\n## 4. User Testing\n{data.get('testing',{})}\n"
        st.markdown('### Preview')
        st.markdown(md)
        st.download_button('Download Report (MD)', data=md, file_name='clinical_pathway.md', mime='text/markdown')
    if st.button('Auto-run Phase 5 (Compile & Summary)'):
        run_phase(5)
    if st.button('Get guidance (Assistant)'):
        append_phase_message(dialogue.get('phase_5_intro'))

st.sidebar.markdown('---')
st.sidebar.write('CarePathIQ — minimal Streamlit implementation')

# Detailed checklist UI in the sidebar
if 'checklist_overrides' not in st.session_state:
    st.session_state.checklist_overrides = {}

def get_default_checks():
    data = st.session_state.pathway_data
    scope = data.get('scope', {})
    logic = data.get('logic', {})
    return [
        bool(scope.get('condition')),
        bool(scope.get('problem')),
        bool(scope.get('objectives')),
        bool(data.get('evidence')),
        bool(logic.get('nodes')),
        bool(data.get('mermaid','').strip()),
    ]

check_labels = [
    'Scope — Condition defined',
    'Scope — Problem statement written',
    'Scope — SMART objectives documented',
    'Evidence — At least one citation added',
    'Logic — Decision nodes defined',
    'Visuals — Mermaid flowchart generated',
]

defaults = get_default_checks()
checked_count = 0
checkbox_keys = []
st.sidebar.markdown('**Progress Checklist**')
for i,label in enumerate(check_labels, start=1):
    key = f'check_{i}'
    checkbox_keys.append(key)
    default = st.session_state.checklist_overrides.get(key, defaults[i-1])
    val = st.sidebar.checkbox(label, value=default, key=key)
    # Store overrides when the user changes a checkbox
    if val != defaults[i-1]:
        st.session_state.checklist_overrides[key] = val
    else:
        # remove override if it matches default
        st.session_state.checklist_overrides.pop(key, None)
    if val:
        checked_count += 1

total_checks = len(check_labels)
percent = int((checked_count / total_checks) * 100) if total_checks else 0
st.sidebar.metric('Progress', f'{percent}%')
st.sidebar.progress(percent)
st.sidebar.write(f'{checked_count}/{total_checks} sections complete')

