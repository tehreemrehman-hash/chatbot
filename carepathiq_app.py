import streamlit as st
print("--- RELOADING APP WITH NEW THEME ---")
import urllib.request
import urllib.parse
import json
import time
from openai import OpenAI
import streamlit.components.v1 as components

st.set_page_config(page_title="CarePathIQ", layout="wide", page_icon="🏥")

# Force button color with CSS injection
st.markdown("""
<style>
div.stButton > button:first-child {
    background-color: #1D0200 !important;
    color: white !important;
    border-color: #1D0200 !important;
}
div.stButton > button:first-child:hover {
    background-color: #3a0400 !important;
    border-color: #3a0400 !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Clinical Pathway Agent")
# st.markdown("A multi-phase, conversational Clinical Pathway Agent to build evidence-based clinical pathways.")

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

# Sidebar onboarding for API key (quick steps + test button)
with st.sidebar.expander("How to get & test your OpenAI API key", expanded=False):
    st.markdown(
        """
        1. Go to https://platform.openai.com/account/api-keys and sign in.
        2. Click **Create new secret key** and copy the key (it is shown only once).
        3. Paste the key into the **OpenAI API Key** field above.

        You can also store the key locally in `./.streamlit/secrets.toml` like:

        ```toml
        OPENAI_API_KEY = "sk-..."
        ```

        After setting an environment variable or `secrets.toml`, restart the app so Streamlit picks it up.
        """
    )
    # Test API key button: performs a lightweight call to verify connectivity
    if st.button("Test API Key", key="test_openai_key"):
        if not openai_api_key:
            st.warning("No API key provided — paste it into the field above first.")
        else:
            if not client:
                try:
                    client = OpenAI(api_key=openai_api_key)
                    use_llm = True
                except Exception as e:
                    st.error(f"Could not initialize client: {e}")
                    client = None
            if client:
                try:
                    # lightweight test: ask the model for a 1-word reply
                    resp = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": "Reply with the single word: READY"}],
                        temperature=0,
                        stream=False,
                    )
                    # extract text safely
                    text = None
                    if hasattr(resp, 'choices') and len(resp.choices) > 0:
                        try:
                            text = resp.choices[0].message.content
                        except Exception:
                            text = getattr(resp.choices[0], 'text', None)
                    if not text:
                        text = getattr(resp, 'text', str(resp))
                    if "READY" in str(text):
                        st.success("API key is valid and responded as expected.")
                    else:
                        st.warning(f"Received a response but it did not match expectations: {text}")
                except Exception as e:
                    if "429" in str(e) or "insufficient_quota" in str(e):
                        st.error("API Key Registered, but Quota Exceeded (Error 429). Please check your OpenAI billing/credits.")
                    else:
                        st.error(f"API key test failed: {e}")

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
        {'role': 'assistant', 'content': dialogue.get('intro')}
    ]

# Agent started flag (shows landing / starter page until user begins)
if 'started' not in st.session_state:
    st.session_state.started = False

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
            # Normalize to canonical evidence item
            evidence_bank.append({'point': point, 'citation': chosen, 'verification': 'Auto-imported'})
            append_phase_message(f"Found evidence for '{point}': {chosen}")
        else:
            append_phase_message(f"No API hits for '{point}', please add manual citation.")
            evidence_bank.append({'point': point, 'citation': 'MANUAL_REQUIRED', 'verification': ''})
    # Normalize evidence as a list of {'point','citation','verification'}
    data.setdefault('evidence', [])
    data['evidence'].extend(evidence_bank)
    st.session_state.pathway_data = data
    append_phase_message('Evidence bank updated with automated search results.')

def auto_run_phase_3():
    """Generate mermaid flowchart from evidence nodes."""
    data = st.session_state.pathway_data
    studies = data.get('evidence', [])
    nodes = [s.get('point') for s in studies if s.get('point')]
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

# Clinical Pathway Agent chat panel (placed after helper functions so dependencies exist)
def get_conversation_questions(phase: int):
    if phase == 1:
        return [
            {'key': 'scope.condition', 'prompt': 'What is the clinical condition? (e.g., Acute Chest Pain)'},
            {'key': 'scope.population', 'prompt': 'Who is the target population? (e.g., Adults > 18 with chest pain)'},
            {'key': 'scope.setting', 'prompt': 'What is the care setting? (e.g., Emergency Department)'},
            {'key': 'scope.problem', 'prompt': 'Write a brief problem statement.'},
            {'key': 'scope.objectives', 'prompt': 'List SMART objectives (one per line).'},
        ]
    if phase == 2:
        return [
            {'key': 'evidence.nodes', 'prompt': 'List key decision nodes or clinical questions (comma separated).'},
        ]
    if phase == 3:
        return [
            {'key': 'logic.entry', 'prompt': 'What is the entry trigger (how does a patient enter the pathway)?'},
            {'key': 'logic.endpoints', 'prompt': 'What are the possible exit/disposition endpoints?'},
        ]
    if phase == 4:
        return [
            {'key': 'testing.issues', 'prompt': 'Describe any heuristic or usability issues found.'},
            {'key': 'testing.mitigation', 'prompt': 'Describe proposed mitigations.'},
        ]
    if phase == 5:
        return [
            {'key': 'operations.notes', 'prompt': 'Any final operational notes or implementation constraints?'},
        ]
    return []

def start_conversation(phase: int):
    st.session_state.conversation = {
        'phase': phase,
        'questions': get_conversation_questions(phase),
        'index': 0,
        'active': True
    }
    # For Phase 1, use the specific intro text requested
    if phase == 1:
        intro = dialogue.get('phase_1_start')
    else:
        intro = dialogue.get(f'phase_{phase}_intro') or 'Starting conversation for this phase.'
    
    append_assistant_message('assistant', intro)

def save_answer_to_pathway(key: str, answer: str):
    parts = key.split('.')
    target = st.session_state.pathway_data
    for p in parts[:-1]:
        if p not in target or not isinstance(target[p], dict):
            target[p] = {}
        target = target[p]
    last = parts[-1]
    # Special handling for lists
    if last == 'objectives':
        target[last] = [a.strip() for a in answer.splitlines() if a.strip()]
    elif last in ('nodes', 'evidence_nodes') or key.startswith('evidence'):
        # Normalize evidence nodes into the canonical evidence list
        nodes = [a.strip() for a in answer.replace(';',',').split(',') if a.strip()]
        # Ensure top-level evidence is a list
        st.session_state.pathway_data.setdefault('evidence', [])
        for n in nodes:
            # Avoid duplicating an existing point
            exists = any(e.get('point') == n for e in st.session_state.pathway_data['evidence'])
            if not exists:
                st.session_state.pathway_data['evidence'].append({'point': n, 'citation': '', 'verification': ''})
        # Also mirror into nested target if appropriate
        target[last] = nodes
    else:
        target[last] = answer
    st.session_state.pathway_data = st.session_state.pathway_data

def handle_conversation_response(response: str):
    conv = st.session_state.get('conversation')
    if not conv or not conv.get('active'):
        return
    q = conv['questions'][conv['index']]
    save_answer_to_pathway(q['key'], response)
    # Do NOT append "Saved: ..." message to keep chat clean
    
    conv['index'] += 1
    if conv['index'] >= len(conv['questions']):
        conv['active'] = False
        append_assistant_message('assistant', 'Section complete. Review saved inputs in the phase tab.')
    else:
        # Clear history to show only the most recent question
        if len(st.session_state.assistant_messages) > 0:
            intro = st.session_state.assistant_messages[0]
            st.session_state.assistant_messages = [intro]
        
        # If LLM is active, generate a context-specific transition/prompt for the next question
        if client:
            next_q = conv['questions'][conv['index']]
            # Construct a prompt for the LLM
            prompt_text = (
                f"The user just answered '{response}' to the previous question about '{q['key']}'. "
                f"The next question is about '{next_q['key']}' and the standard prompt is '{next_q['prompt']}'. "
                "Please generate a conversational transition and ask the next question naturally. "
                "If relevant, offer a brief context-specific suggestion based on their previous answer."
            )
            try:
                dynamic_prompt = ask_assistant(prompt_text, context="You are a helpful Clinical Pathway Agent.")
                # Update the prompt in the conversation state so it displays correctly
                conv['questions'][conv['index']]['prompt'] = dynamic_prompt
            except Exception:
                pass # Fallback to standard prompt if LLM fails
            
    st.session_state.conversation = conv

    # UI polish: store a short-lived confirmation and clear the current answer widget
    phase = conv.get('phase')
    idx = conv.get('index') - 1
    st.session_state['conv_last_saved'] = {
        'phase': phase,
        'index': idx,
        'msg': f"Saved answer for question {idx+1} of phase {phase}"
    }
    # clear the textarea for the question we just answered (if present)
    key = f'conv_answer_{phase}_{idx}'
    if key in st.session_state:
        try:
            st.session_state[key] = ''
        except Exception:
            pass
    # also ensure the next answer textarea is empty so user can type fresh
    next_idx = conv.get('index')
    next_key = f'conv_answer_{phase}_{next_idx}'
    if next_key in st.session_state:
        try:
            st.session_state[next_key] = ''
        except Exception:
            pass

# Landing / starter page: require API key then show onboarding instructions
if not st.session_state.started:
    if not openai_api_key:
        # st.info("OpenAI API key required to enable LLM features")
        st.markdown("""
        I'm your Clinical Pathway Agent. I'm here to help you transform your clinical expertise and evidence-based medicine into a robust clinical pathway.
        
        To get started, input your OpenAI API key in the sidebar. If you don't have one, you can obtain one [here](https://platform.openai.com/account/api-keys).
        """)
        
        if st.button("Continue without API Key (Demo Mode)"):
            st.session_state.started = True
            st.rerun()
        
        st.stop()
    else:
        # User has entered a key (or we are in a state where we can proceed)
        # Show a simple start button without redundant text
        if st.button('Start Clinical Pathway Agent', key='start_agent'):
            st.session_state.started = True
            # Start Phase 1 conversation immediately
            start_conversation(1)
            st.rerun()

if st.session_state.started:
    with st.expander('Clinical Pathway Agent — conversational help', expanded=True):
        # Render conversation history using Streamlit's chat components
        for msg in st.session_state.assistant_messages:
            role = msg.get('role', 'assistant')
            content = msg.get('content', '')
            if role == 'assistant':
                with st.chat_message('assistant'):
                    st.write(content)
            else:
                with st.chat_message('user'):
                    st.write(content)

        # Conversation-driven Q->A and free chat input using st.chat_input
        conv = st.session_state.get('conversation')
        # If conversation is active, ensure the current question prompt is shown as an assistant message
        if conv and conv.get('active'):
            idx = conv['index']
            q = conv['questions'][idx]
            # If the last assistant message isn't the current prompt, display it now
            last_assistant = None
            for m in reversed(st.session_state.assistant_messages):
                if m.get('role') == 'assistant':
                    last_assistant = m.get('content')
                    break
            if last_assistant != q['prompt']:
                append_assistant_message('assistant', q['prompt'])
                with st.chat_message('assistant'):
                    st.write(q['prompt'])

        user_input = st.chat_input('Message the Clinical Pathway Agent')
        if user_input:
            append_assistant_message('user', user_input)
            # If a guided conversation is active, treat this as an answer to the current question
            if conv and conv.get('active'):
                handle_conversation_response(user_input)
                st.rerun()
            else:
                # Free-form chat handling
                if 'summarize' in user_input.lower() or 'summary' in user_input.lower():
                    try:
                        summary = summarize_pathway()
                    except Exception as e:
                        summary = f'Error generating summary: {e}'
                    append_assistant_message('assistant', summary)
                else:
                    reply = ask_assistant(user_input)
                    append_assistant_message('assistant', reply)

        # --- UI Tabs ---
        # If LLM is active, hide the structured tabs by default to focus on conversation
        show_tabs = True
        if client:
            show_tabs = False
            with st.expander("View Structured Data & Controls", expanded=False):
                st.info("Structured fields are hidden in LLM mode to focus on the conversation. Expand to view or edit manually.")
                tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Scope & Charter","2. Evidence Appraisal","3. Logic & Visuals","4. User Testing","5. Final Report"])
                
                with tab1:
                    st.header("Phase 1 — Scope & Charter")
                    with st.form('scope_form'):
                        cond = st.text_input('Clinical Condition', value=st.session_state.pathway_data['scope'].get('condition',''))
                        pop = st.text_input('Target Population', value=st.session_state.pathway_data['scope'].get('population',''))
                        setting = st.text_input('Care Setting', value=st.session_state.pathway_data['scope'].get('setting',''))
                        problem = st.text_area('Problem Statement', value=st.session_state.pathway_data['scope'].get('problem',''))
                        objectives = st.text_area('SMART Objectives', value='\n'.join(st.session_state.pathway_data['scope'].get('objectives',[])))
                        if st.form_submit_button('Save Charter', key='save_charter'):
                            st.session_state.pathway_data['scope'] = {'condition':cond,'population':pop,'setting':setting,'problem':problem,'objectives':[o for o in objectives.split('\n') if o.strip()]}
                            st.success('Scope saved')
                        # Phase controls
                        if st.form_submit_button('Auto-run Phase 1 (Guidance)', key='auto_run_phase1'):
                            run_phase(1)
                        if st.form_submit_button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase1'):
                            start_conversation(1)
                        if st.form_submit_button('Next: Go to Phase 2', key='next_phase1'):
                            st.session_state.current_phase = 2
                            run_phase(2)

                with tab2:
                    st.header('Phase 2 — Rapid Evidence Appraisal')
                    node = st.text_input('Decision Node / Clinical Question')
                    if st.button('Search PubMed & Verify', key='search_pubmed_verify') and node:
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
                    if st.button('Auto-run Phase 2 (Automated Evidence Search)', key='auto_run_phase2'):
                        run_phase(2)
                    if st.button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase2'):
                        start_conversation(2)
                    if st.button('Next: Go to Phase 3', key='next_phase2'):
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
                    if st.button('Generate Flowchart', key='generate_flowchart'):
                        nodes = [e['point'] for e in st.session_state.pathway_data['evidence']]
                        if not nodes:
                            st.error('Add evidence nodes first (Tab 2)')
                        else:
                            code = generate_mermaid(entry_pt, nodes, exit_pt)
                            st.session_state.pathway_data['mermaid'] = code
                            st.session_state.pathway_data['logic'] = {'entry':entry_pt,'endpoints':exit_pt,'nodes':nodes}
                            st.success('Mermaid generated')

                    # Phase controls
                    if st.button('Auto-run Phase 3 (Generate from Evidence)', key='auto_run_phase3'):
                        run_phase(3)
                    if st.button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase3'):
                        start_conversation(3)
                    if st.button('Next: Go to Phase 4', key='next_phase3'):
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
                    if st.button('Save Testing', key='save_testing'):
                        st.session_state.pathway_data['testing'] = {'issues':heur,'mitigation':mitig,'status':'Saved'}
                        st.success('Testing feedback saved')

                    # Phase controls
                    if st.button('Auto-run Phase 4 (Testing Guidance)', key='auto_run_phase4'):
                        run_phase(4)
                    if st.button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase4'):
                        start_conversation(4)
                    if st.button('Next: Go to Phase 5', key='next_phase4'):
                        st.session_state.current_phase = 5
                        run_phase(5)

                with tab5:
                    st.header('Phase 5 — Final Report')
                    if st.button('Compile Final Report', key='compile_final_report'):
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
                    if st.button('Auto-run Phase 5 (Compile & Summary)', key='auto_run_phase5'):
                        run_phase(5)
                    if st.button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase5'):
                        start_conversation(5)
        else:
            # Standard view for Demo Mode
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Scope & Charter","2. Evidence Appraisal","3. Logic & Visuals","4. User Testing","5. Final Report"])

            with tab1:
                st.header("Phase 1 — Scope & Charter")
                with st.form('scope_form'):
                    cond = st.text_input('Clinical Condition', value=st.session_state.pathway_data['scope'].get('condition',''))
                    pop = st.text_input('Target Population', value=st.session_state.pathway_data['scope'].get('population',''))
                    setting = st.text_input('Care Setting', value=st.session_state.pathway_data['scope'].get('setting',''))
                    problem = st.text_area('Problem Statement', value=st.session_state.pathway_data['scope'].get('problem',''))
                    objectives = st.text_area('SMART Objectives', value='\n'.join(st.session_state.pathway_data['scope'].get('objectives',[])))
                    if st.form_submit_button('Save Charter', key='save_charter'):
                        st.session_state.pathway_data['scope'] = {'condition':cond,'population':pop,'setting':setting,'problem':problem,'objectives':[o for o in objectives.split('\n') if o.strip()]}
                        st.success('Scope saved')
                    # Phase controls
                    if st.form_submit_button('Auto-run Phase 1 (Guidance)', key='auto_run_phase1'):
                        run_phase(1)
                    if st.form_submit_button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase1'):
                        start_conversation(1)
                    if st.form_submit_button('Next: Go to Phase 2', key='next_phase1'):
                        st.session_state.current_phase = 2
                        run_phase(2)

            with tab2:
                st.header('Phase 2 — Rapid Evidence Appraisal')
                node = st.text_input('Decision Node / Clinical Question')
                if st.button('Search PubMed & Verify', key='search_pubmed_verify') and node:
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
                if st.button('Auto-run Phase 2 (Automated Evidence Search)', key='auto_run_phase2'):
                    run_phase(2)
                if st.button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase2'):
                    start_conversation(2)
                if st.button('Next: Go to Phase 3', key='next_phase2'):
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
                if st.button('Generate Flowchart', key='generate_flowchart'):
                    nodes = [e['point'] for e in st.session_state.pathway_data['evidence']]
                    if not nodes:
                        st.error('Add evidence nodes first (Tab 2)')
                    else:
                        code = generate_mermaid(entry_pt, nodes, exit_pt)
                        st.session_state.pathway_data['mermaid'] = code
                        st.session_state.pathway_data['logic'] = {'entry':entry_pt,'endpoints':exit_pt,'nodes':nodes}
                        st.success('Mermaid generated')

                # Phase controls
                if st.button('Auto-run Phase 3 (Generate from Evidence)', key='auto_run_phase3'):
                    run_phase(3)
                if st.button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase3'):
                    start_conversation(3)
                if st.button('Next: Go to Phase 4', key='next_phase3'):
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
                if st.button('Save Testing', key='save_testing'):
                    st.session_state.pathway_data['testing'] = {'issues':heur,'mitigation':mitig,'status':'Saved'}
                    st.success('Testing feedback saved')

                # Phase controls
                if st.button('Auto-run Phase 4 (Testing Guidance)', key='auto_run_phase4'):
                    run_phase(4)
                if st.button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase4'):
                    start_conversation(4)
                if st.button('Next: Go to Phase 5', key='next_phase4'):
                    st.session_state.current_phase = 5
                    run_phase(5)

            with tab5:
                st.header('Phase 5 — Final Report')
                if st.button('Compile Final Report', key='compile_final_report'):
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
                if st.button('Auto-run Phase 5 (Compile & Summary)', key='auto_run_phase5'):
                    run_phase(5)
                if st.button('Get guidance (Clinical Pathway Agent)', key='get_guidance_phase5'):
                    start_conversation(5)

st.sidebar.markdown('---')
st.sidebar.write('CarePathIQ — minimal Streamlit implementation')

# Debug: allow loading demo Phase 1 data into session state
def load_demo_data():
    import json
    from pathlib import Path
    demo_path = Path('demo_phase1_saved.json')
    if demo_path.exists():
        try:
            data = json.loads(demo_path.read_text())
        except Exception:
            data = None
    else:
        data = None
    if not data:
        data = {
            'scope': {
                'condition': 'Acute Chest Pain',
                'population': 'Adults >=18 years presenting to ED with chest pain',
                'setting': 'Emergency Department',
                'problem': 'Need a clear, evidence-based pathway to risk-stratify chest pain and reduce unnecessary admissions.',
                'objectives': [
                    'Reduce time to risk stratification to <30 minutes',
                    'Ensure ≥90% of high-risk patients receive cardiology consult',
                    'Decrease unnecessary admissions for low-risk patients by 20%'
                ]
            },
            'evidence': [],
            'logic': {},
            'testing': {},
            'operations': {},
            'mermaid': ''
        }
    st.session_state.pathway_data = data
    append_assistant_message('assistant', 'Demo Phase 1 data loaded into session state.')
    st.sidebar.success('Demo data loaded')

if st.sidebar.button('Load demo Phase 1 data', key='load_demo_data'):
    load_demo_data()

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

# Debug helper: programmatic demo loader and snapshot writer
def _load_demo_and_snapshot():
    import json
    from pathlib import Path
    demo_path = Path('demo_phase1_saved.json')
    if demo_path.exists():
        try:
            data = json.loads(demo_path.read_text())
        except Exception:
            data = None
    else:
        data = None
    if not data:
        data = {
            'scope': {
                'condition': 'Acute Chest Pain',
                'population': 'Adults >=18 years presenting to ED with chest pain',
                'setting': 'Emergency Department',
                'problem': 'Need a clear, evidence-based pathway to risk-stratify chest pain and reduce unnecessary admissions.',
                'objectives': [
                    'Reduce time to risk stratification to <30 minutes',
                    'Ensure ≥90% of high-risk patients receive cardiology consult',
                    'Decrease unnecessary admissions for low-risk patients by 20%'
                ]
            },
            'evidence': [],
            'logic': {},
            'testing': {},
            'operations': {},
            'mermaid': ''
        }
    st.session_state.pathway_data = data
    st.session_state.started = True
    append_assistant_message('assistant', 'Demo Phase 1 data auto-loaded into session state (debug).')
    # write snapshot to workspace so the agent can read it
    try:
        Path('session_snapshot.json').write_text(json.dumps(st.session_state.pathway_data, indent=2))
    except Exception:
        pass

# If a trigger file exists, auto-load demo on next session run
from pathlib import Path
if Path('.auto_load_demo').exists():
    try:
        _load_demo_and_snapshot()
    except Exception:
        pass
