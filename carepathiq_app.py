import streamlit as st
import urllib.request
import urllib.parse
import json
import time
from openai import OpenAI
import streamlit.components.v1 as components

st.set_page_config(page_title="CarePathIQ", layout="wide", page_icon="🏥")

st.title("🏥 CarePathIQ — Clinical Pathway Agent")
st.markdown("A multi-phase UI to build evidence-based clinical pathways.")

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

st.sidebar.markdown('---')
st.sidebar.write('CarePathIQ — minimal Streamlit implementation')
