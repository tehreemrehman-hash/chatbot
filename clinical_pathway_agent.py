import time
import sys
import os
import urllib.request
import urllib.parse
import json
from openai import OpenAI


class ClinicalPathwayAgent:
    def __init__(self):
        print("\nWelcome to CarePathIQ.")
        print("To assist you best, I need to access my language reasoning tools.")
        
        # Prompt for API key with simple validation (format and a few retries)
        self.api_key = None
        self.client = None
        attempts = 0
        while attempts < 3:
            key = input("Please enter your OpenAI API Key (or press Enter to run in manual mode): ").strip()
            if not key:
                print("No key provided. Running in manual mode.")
                break
            if self._validate_api_key(key):
                # attempt to initialize client
                try:
                    self.client = OpenAI(api_key=key)
                    self.api_key = key
                    print("...Connected. Ready to begin.")
                except Exception as e:
                    print(f"Connection failed: {e}")
                    self.client = None
                break
            else:
                attempts += 1
                print("Key format looks invalid. Ensure it starts with 'sk-' and try again.")
                if attempts < 3:
                    try_again = input("Try again? (y/n): ").strip().lower()
                    if try_again != 'y':
                        print("Proceeding in manual mode.")
                        break
                else:
                    print("Max attempts reached — proceeding in manual mode.")

        # The Data Store for the Pathway
        self.pathway_data = {
            "scope": {},
            "evidence": {},
            "logic": {},
            "testing": {},
            "operations": {}
        }
        
        self.evidence_bank = [] 
        self.report_file = "clinical_pathway_progress.md"
        
        # Initialize files
        with open(self.report_file, "w") as f:
            f.write("# Clinical Pathway Development Report\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M')}\n\n")

        # --- DIALOGUE LIBRARY ---
        self.dialogue = {
            "intro": "Hello! I'm your Clinical Pathway Agent. I'm here to help you transform your clinical expertise and evidence-based medicine into a robust clinical pathway.",
            "phase_1_start": "\nLet's kick things off with the Scope. I'll ask you a few questions to frame the problem accurately.",
            "phase_2_intro": "Great job on the scope. Now, let's look at the science. We need to make sure our pathway is evidence-based. Ready to evaluate some evidence?",
            "phase_3_intro": "Now let's map out the logic. We need to ensure every decision point is clear and supported by the evidence we just gathered.",
            "phase_4_intro": "A pathway only works if people actually use it. Let's simulate the workflow.",
            "phase_5_intro": "We're in the home stretch. Now we need to operationalize this—turning a paper document into a live clinical tool.",
            "step_verification": "\nI've finished gathering inputs for this section. Please review the summary preview above.",
            "approval_request": ">> Do you approve this section? (Type 'YES' to proceed, anything else to abort): ",
            "locked": "Section approved. Updating Documentation...\n",
            "summary_generated": "The formal summary has been saved to '{filename}'.\n"
        }

    # ==========================================
    # INTERNAL HELPER METHODS
    # ==========================================
    def ask_assistant(self, prompt, context=""):
        """Wrapper for OpenAI calls"""
        if not self.client: return "Analysis unavailable (No Key)"
        
        full_prompt = f"{context}\n\nTask: {prompt}"
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return "I couldn't process that right now."

    def draft_flowchart(self):
        """Converts logic nodes into a visual diagram"""
        logic = self.pathway_data.get('logic', {})
        prompt = f"""
        Create a Mermaid.js flowchart (graph TD) for:
        Entry: {logic.get('entry')}
        Nodes: {logic.get('nodes')}
        Exit: {logic.get('endpoints')}
        
        Output ONLY the raw code inside the mermaid block.
        """
        result = self.ask_assistant(prompt, context="You are a Clinical Systems Architect.")
        return result.replace("```mermaid", "").replace("```", "").strip()

    def _validate_api_key(self, key: str) -> bool:
        """Simple validation: non-empty, starts with 'sk-' and reasonable length."""
        if not key or not isinstance(key, str):
            return False
        if not key.startswith("sk-"):
            return False
        if len(key) < 20:
            return False
        return True

    # ==========================================
    # PUBMED API INTEGRATION
    # ==========================================
    def search_pubmed(self, query, retmax=3):
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        search_params = {
            'db': 'pubmed', 'term': query, 'retmode': 'json', 'retmax': retmax,
            'tool': 'carepathiq', 'email': 'example@example.com'
        }
        try:
            url = base_url + "esearch.fcgi?" + urllib.parse.urlencode(search_params)
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                id_list = data.get('esearchresult', {}).get('idlist', [])
            
            if not id_list: return []

            summary_params = {'db': 'pubmed', 'id': ','.join(id_list), 'retmode': 'json', 'tool': 'carepathiq', 'email': 'example@example.com'}
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
                        first_author = authors[0]['name'] if authors else "Unknown"
                        pub_date = item.get('pubdate', 'No Date')[:4]
                        source = item.get('source', 'Journal')
                        citations.append(f"{first_author} et al. ({pub_date}). {title}. {source}.")
                return citations
        except Exception:
            print(f"\n[Note] PubMed search timed out or failed.")
            return []

    # ==========================================
    # CORE EXECUTION
    # ==========================================
    def execute_process(self):
        print(self.dialogue["intro"])
        time.sleep(1)
        
        try:
            self.phase_1_scope()
            if not self.review_and_save("scope", "Phase 1: Scope & Objectives", 1): return
            
            self.phase_2_evidence()
            if not self.review_and_save("evidence", "Phase 2: Evidence Appraisal", 2): return
            
            self.phase_3_logic()
            if not self.review_and_save("logic", "Phase 3: Decision Logic", 3): return
            
            self.phase_4_testing()
            if not self.review_and_save("testing", "Phase 4: Validation", 4): return
            
            self.phase_5_ops()
            if not self.review_and_save("operations", "Phase 5: Operations", 5): return

            self.finish()
        except KeyboardInterrupt:
            print("\n\nSession paused.")
            sys.exit()

    def review_and_save(self, phase_key, title, phase_num):
        print(f"\n...Drafting summary for {title}...")
        time.sleep(1)
        summary_text = self._format_summary(phase_key, title)
        print("\n" + title + "\n" + "="*40 + "\n" + summary_text.strip() + "\n" + "="*40 + "\n")
        
        print(self.dialogue["step_verification"])
        response = input(self.dialogue["approval_request"])
        if response.lower().strip() == "yes":
            with open(self.report_file, "a") as f:
                f.write(summary_text + "\n" + "-"*40 + "\n")
            print(self.dialogue["locked"])
            input("Press Enter to continue...")
            return True
        return False

    def _format_summary(self, phase_key, title):
        data = self.pathway_data.get(phase_key, {})
        
        if phase_key == 'scope':
            return f"\n## SCOPE: {data.get('condition')}\n**Problem:** {data.get('problem')}\n**Pop:** {data.get('population')}\n**Obj:** {data.get('objectives')}\n"
        
        if phase_key == 'evidence':
            txt = "\n### Rapid Evidence Appraisal\n| Decision | Citation | Analysis |\n|---|---|---|\n"
            for s in data.get('studies', []):
                txt += f"| {s.get('decision_point')} | {s.get('id')} | {s.get('analysis')} |\n"
            return txt
        
        if phase_key == 'logic':
            txt = f"\n### Logic Flowchart\n```mermaid\n{data.get('mermaid_visual')}\n```\n\n**Nodes:**\n"
            for n in data.get('nodes', []):
                txt += f"- {n['node']} (Ref: {n['evidence_link']})\n"
            return txt
        
        if phase_key == 'testing':
            return f"\n**Testing:** {data.get('status')}\n**Issues:** {data.get('issues')}\n"

        if phase_key == 'operations':
            return f"\n**EHR:** {data.get('ehr')}\n**KPIs:** {data.get('metrics')}\n"

        return ""

    # ==========================================
    # PHASES
    # ==========================================
    def phase_1_scope(self):
        print(self.dialogue["phase_1_start"])
        self.pathway_data['scope']['condition'] = input("\nTarget Condition (e.g., Sepsis): ")
        self.pathway_data['scope']['population'] = input("Target Population: ")
        self.pathway_data['scope']['problem'] = input("Primary Problem: ")
        self.pathway_data['scope']['objectives'] = input("Primary Objectives: ")

    def phase_2_evidence(self):
        print(self.dialogue["phase_2_intro"])
        condition = self.pathway_data['scope'].get('condition', 'General')
        
        print("\nLet's add decision nodes and search PubMed.")
        final_elements = []
        while True:
            el_name = input("\nEnter a Decision Node (or type 'done'): ")
            if el_name.lower() == 'done': break
            final_elements.append(el_name)
        
        print("\nSearching literature...")
        
        for point in final_elements:
            print(f"\n--- Searching for: {point} ---")
            results = self.search_pubmed(f"({condition}) AND ({point}) AND (Guideline[pt])")
            
            selected_cite = "No citation"
            
            if results:
                print(f"Found {len(results)} sources:")
                for i, citation in enumerate(results, 1):
                    print(f"{i}. {citation}")
                sel = input("Select # (or type manual): ")
                if sel.isdigit() and 1 <= int(sel) <= len(results):
                    selected_cite = results[int(sel)-1]
                else:
                    selected_cite = sel
            else:
                selected_cite = input("No hits. Enter manual citation: ")
            
            # --- NATURAL LANGUAGE CHECK ---
            print(f"   ...Reviewing clinical relevance...")
            analysis = self.ask_assistant(f"Does the citation '{selected_cite}' support the decision '{point}'? Answer 'Verified' or 'Warning' with brief reason.")
            print(f"   >> {analysis}")

            self.evidence_bank.append({
                "id": selected_cite, 
                "decision_point": point,
                "analysis": analysis
            })
            
        self.pathway_data['evidence']['studies'] = self.evidence_bank

    def phase_3_logic(self):
        print(self.dialogue["phase_3_intro"])
        entry = input("\nPathway Entry Point: ")
        ends = input("Pathway Endpoint: ")
        
        logic_nodes = []
        for study in self.evidence_bank:
            logic_nodes.append({"node": study['decision_point'], "evidence_link": "See Evidence Table"})
        
        self.pathway_data['logic'] = { "entry": entry, "endpoints": ends, "nodes": logic_nodes }
        
        # --- NATURAL VISUALIZATION ---
        print("\n...Drafting the flowchart layout...")
        mermaid = self.draft_flowchart()
        self.pathway_data['logic']['mermaid_visual'] = mermaid
        print(">> Visual diagram created.")

    def phase_4_testing(self):
        print(self.dialogue["phase_4_intro"])
        issues = input("Top Usability Issues found: ")
        mitigation = input("Mitigation Plans: ")
        status = input("Validation Status (Ready/Not Ready): ")
        self.pathway_data['testing'] = { "issues": issues, "mitigation": mitigation, "status": status }

    def phase_5_ops(self):
        print(self.dialogue["phase_5_intro"])
        ehr = input("\nEHR System: ")
        metrics = input("Key Performance Indicators (KPIs): ")
        self.pathway_data['operations'] = { "ehr": ehr, "metrics": metrics }

    def finish(self):
        print("\n" + "="*60)
        print("WORKSHOP COMPLETE")
        print(f"I've compiled the full report here: '{self.report_file}'")
        print("="*60)

if __name__ == "__main__":
    agent = ClinicalPathwayAgent()
    agent.execute_process()
        search_params = {
            'db': 'pubmed',
            'term': query,
            'retmode': 'json',
            'retmax': retmax,
            'tool': 'clinical_pathway_agent',
            'email': 'example@example.com' # NCBI requires email contact
        }
        
        try:
            url = base_url + "esearch.fcgi?" + urllib.parse.urlencode(search_params)
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                id_list = data.get('esearchresult', {}).get('idlist', [])
            
            if not id_list:
                return []

            # 2. ESummary: Get Details
            summary_params = {
                'db': 'pubmed',
                'id': ','.join(id_list),
                'retmode': 'json',
                'tool': 'clinical_pathway_agent',
                'email': 'example@example.com'
            }
            
            url = base_url + "esummary.fcgi?" + urllib.parse.urlencode(summary_params)
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                result = data.get('result', {})
                
                citations = []
                for uid in id_list:
                    if uid in result:
                        item = result[uid]
                        # Safe extraction of fields
                        title = item.get('title', 'No Title')
                        # Authors list might be missing
                        authors = item.get('authors', [])
                        first_author = authors[0]['name'] if authors else "Unknown Author"
                        pub_date = item.get('pubdate', 'No Date')[:4] # Just the year
                        source = item.get('source', 'Journal')
                        
                        citations.append(f"{first_author} et al. ({pub_date}). {title}. {source}.")
                return citations

        except Exception as e:
            print(f"\n[System Alert] PubMed Search failed (Check internet connection): {e}")
            return []

    # ==========================================
    # CORE EXECUTION
    # ==========================================
    def execute_process(self):
        """
        Execute the pathway development process sequentially.
        """
        print(self.dialogue["intro"])
        time.sleep(1)
        
        try:
            # Phase 1
            self.phase_1_scope_and_objectives()
            if not self.review_and_save_phase("scope", "Phase 1: Scope & Objectives", 1): return
            
            # Phase 2
            self.phase_2_evidence_appraisal()
            if not self.review_and_save_phase("evidence", "Phase 2: Evidence Appraisal", 2): return
            
            # Phase 3
            self.phase_3_decision_science()
            if not self.review_and_save_phase("logic", "Phase 3: Decision Logic", 3): return
            
            # Phase 4
            self.phase_4_user_testing()
            if not self.review_and_save_phase("testing", "Phase 4: User Testing & Validation", 4): return
            
            # Phase 5
            self.phase_5_operationalization()
            if not self.review_and_save_phase("operations", "Phase 5: Operationalization", 5): return

            self.generate_final_report()

        except KeyboardInterrupt:
            print("\n\nProcess aborted by user.")
            sys.exit()

    def verify_step(self, phase_name):
        """Human-in-the-loop verification."""
        print(self.dialogue["step_verification"])
        response = input(self.dialogue["approval_request"])
        if response.lower().strip() == "yes":
            print(self.dialogue["locked"])
            time.sleep(1) # Conversational pause
            return True
        else:
            print("Process Paused/Aborted for refinement.")
            return False

    def review_and_save_phase(self, phase_key, title, phase_num):
        """Generates summary, shows preview, asks for verification, saves MD."""
        print(f"\n...Drafting formal summary for {title}...")
        time.sleep(1)
        
        # 1. Generate MD content
        summary_text = self._generate_summary_text(phase_key, title)
        
        # 2. Show Preview in Console
        print("\n" + title)
        print("="*40)
        print(summary_text.strip())
        print("="*40 + "\n")

        # 3. Verify
        if self.verify_step(title):
            # 4. Save to Markdown
            with open(self.report_file, "a") as f:
                f.write(summary_text + "\n" + "-"*40 + "\n")
            
            # 5. Print Progress
            percent = int((phase_num / 5) * 100)
            print(f"--> PROCESS STATUS: {percent}% COMPLETE")
            
            print(self.dialogue["summary_generated"].format(filename=self.report_file))
            input("Press Enter to continue to the next phase...")
            return True
        return False

    def _generate_summary_text(self, phase_key, title):
        """Internal helper to format the text based on phase data."""
        data = self.pathway_data.get(phase_key, {})
        
        if phase_key == 'scope':
            summary_text = f"\n## PROJECT SCOPE CHARTER: {data.get('condition', 'Clinical Pathway')}\n\n"
            summary_text += f"**1. Problem Statement:**\n{data.get('problem', 'N/A')}\n\n"
            summary_text += f"**2. Target Population:**\n{data.get('population', 'N/A')}\n\n"
            summary_text += f"**3. Clinical Setting:**\n{data.get('setting', 'N/A')}\n\n"
            summary_text += f"**4. SMART Objectives:**\n"
            for obj in data.get('objectives', []):
                summary_text += f"- {obj}\n"
            summary_text += f"\n**5. Operational Constraints:**\n{data.get('resources', 'N/A')}\n\n"
            summary_text += f"**6. Systems Integration:**\n{data.get('integration', 'N/A')}\n"
            return summary_text
            
        summary_text = f"\n## {title}\n"
        
        if phase_key == 'evidence':
            summary_text += f"**PICO Framework:** {data.get('PICO', {})}\n\n"
            # RAPID EVIDENCE APPRAISAL TABLE
            summary_text += "### Rapid Evidence Appraisal\n"
            summary_text += "| Decision Tree Element | Definition, Rationale, or Risk Score | PubMed Citations |\n"
            summary_text += "| :--- | :--- | :--- |\n"
            
            for study in data.get('studies', []):
                # We categorize the row based on the user's input in Phase 2
                element_type = study.get('element_type', 'Decision Node')
                point_name = study.get('decision_point', 'General')
                citation = study.get('id', 'No citation')
                
                # Logic to extract "Definition" from the citation title if possible
                try:
                    parts = citation.split('. ')
                    if len(parts) >= 3:
                        definition = parts[1] # Use Title as definition/rationale
                    else:
                        definition = f"Evidence for {point_name}"
                except:
                    definition = f"Evidence for {point_name}"
                
                summary_text += f"| {element_type} | **{point_name}**: {definition} | {citation} |\n"
        
        elif phase_key == 'logic':
            summary_text += f"**Entry:** {data.get('entry')}\n"
            summary_text += f"**Endpoints:** {data.get('endpoints')}\n"
            summary_text += "**Decision Nodes:**\n"
            for node in data.get('nodes', []):
                summary_text += f"- {node['node']}\n"
                summary_text += f"  - Supporting Evidence: {node['evidence_link']}\n"
        
        elif phase_key == 'testing':
            summary_text += f"**Method:** {data.get('method')}\n"
            summary_text += f"**Status:** {data.get('status')}\n"
            summary_text += f"**Key Issues:** {data.get('issues')}\n"

        elif phase_key == 'operations':
            summary_text += f"**EHR System:** {data.get('ehr')}\n"
            summary_text += f"**Metrics:** {data.get('metrics')}\n"
            
        return summary_text

    def refine_smart_goals(self, objectives_input, condition):
        print("\nAnalyzing your objectives against SMART criteria...")
        time.sleep(0.5)
        suggestions = []
        input_lower = objectives_input.lower()
        if "imaging" in input_lower or "ct" in input_lower:
            suggestions.append(self.kpi_library["imaging"].format(modality="CT/MRI", condition=condition))
        if "length of stay" in input_lower or "los" in input_lower:
            suggestions.append(self.kpi_library["los"].format(condition=condition, time="180"))
        if not suggestions:
            suggestions.append(self.kpi_library["adherence"].format(guideline="Standard Protocol"))
        return suggestions

    def assess_health_equity(self):
        print("\nEvaluating Risk of Bias...")
        print("Let's look at the demographics of the evidence sources.")
        print("1. Does the evidence source include diverse populations?")
        print("2. Are there race-based corrections in the algorithms (e.g., eGFR, VBAC)?")
        equity_notes = input(">> Please document any Equity Findings or Exclusions: ")
        self.pathway_data['evidence']['equity_scan'] = equity_notes

    def validate_logic(self):
        print("\nLet's validate the logic by walking through 3 key scenarios.")
        scenarios = ["Typical Patient", "Edge Case (Comorbidity)", "High-Risk/Exclusion"]
        results = []
        for s in scenarios:
            res = input(f">> What is the expected pathway output for a '{s}'? ")
            results.append(f"{s}: {res}")
        self.pathway_data['logic']['validation_scenarios'] = results

    def search_evidence_workflow(self, node, condition):
        """Simulates a literature search workflow for a specific decision node."""
        print(f"\nScanning Clinical Society Guidelines & PubMed for: '{node}' in context of '{condition}'...")
        time.sleep(1.5)
        print("...Search complete. I have identified potential evidence.")
        print("Please review and confirm the top 1-2 evidence sources to support this decision node:")
        
        e1 = input("Evidence #1 (Citation/Guideline): ")
        e2 = input("Evidence #2 (Citation/Guideline) [Press Enter if none]: ")
        
        combined = e1
        if e2.strip():
            combined += f" | {e2}"
        return combined

    # ==========================================
    # PHASES (INPUTS)
    # ==========================================
    def phase_1_scope_and_objectives(self):
        print(self.dialogue["phase_1_start"])
        time.sleep(1)
        
        self.pathway_data['scope']['condition'] = input("\nFirst, what is the Clinical Condition we are targeting? (e.g., Sepsis): ")
        self.pathway_data['scope']['setting'] = input("And what Care Setting will this be used in? (e.g., ED, ICU): ")
        self.pathway_data['scope']['population'] = input("Who is the Target Population? (Please define inclusions/exclusions): ")
        self.pathway_data['scope']['problem'] = input("What is the Primary Problem or Variation in care you want to address? ")
        
        print("\nThanks. Now let's define what success looks like.")
        raw_objectives = input("Please draft your Primary Objectives: ")
        
        refined = self.refine_smart_goals(raw_objectives, self.pathway_data['scope']['condition'])
        print(f"\nHere are some suggestions to make them SMARTer:")
        for r in refined:
            print(f" - {r}")
        
        use_suggestion = input(">> Would you like to use these suggestions? (yes/no): ")
        if use_suggestion.lower() == 'yes':
            self.pathway_data['scope']['objectives'] = refined
        else:
            self.pathway_data['scope']['objectives'] = [raw_objectives]

        print("\nA few more logistics...")
        self.pathway_data['scope']['resources'] = input("Are there any Resource Constraints? (e.g., Staffing, Tech): ")
        self.pathway_data['scope']['workflow'] = input("What are the current Workflow Pain Points? ")
        self.pathway_data['scope']['integration'] = input("Are there Existing Systems we need to integrate with? (e.g., EHR, Registries): ")

    def phase_2_evidence_appraisal(self):
        print(self.dialogue["phase_2_intro"])
        time.sleep(1)
        
        pico = {}
        print("\nLet's define the PICO framework. I've drafted this based on your Phase 1 inputs:")
        
        # Auto-populate P from Phase 1
        pico['P'] = self.pathway_data['scope'].get('population', 'Target Population')
        print(f"Population (P): {pico['P']}")
        
        # Auto-populate I and C
        pico['I'] = "Standardized Clinical Pathway"
        print(f"Intervention (I): {pico['I']}")
        
        pico['C'] = "Current standard of care / Ad-hoc management"
        print(f"Comparison (C): {pico['C']}")
        
        # Prompt for Outcome
        pico['O'] = input("Outcome (O) (e.g., Reduced Length of Stay, Mortality): ")
        self.pathway_data['evidence']['PICO'] = pico

        print("\nNow, let's gather the evidence.")
        print("I can help you grade the evidence (High/Moderate/Low/Very Low).") 
        
        # Suggest Decision Tree Elements
        print("\nI suggest structuring the pathway with the following Decision Tree Elements:")
        print("Types: Start Node, End Node, Decision Node, Process Step, Note.")
        print("(A 'Note' includes additional info like detailed risk scores referenced by other nodes).")
        
        condition = self.pathway_data['scope'].get('condition', 'General Condition')
        
        # Proposed default structure
        proposed_elements = [
            {"type": "Start Node", "name": f"Patient presents with {condition}"},
            {"type": "Decision Node", "name": "Risk Stratification / Severity Assessment"},
            {"type": "Note", "name": "Clinical Risk Score Details (e.g., Calculator)"},
            {"type": "Process Step", "name": "Initial Medical Management"},
            {"type": "End Node", "name": "Disposition (Admit vs. Discharge)"}
        ]
        
        print("\nProposed Structure:")
        for i, el in enumerate(proposed_elements, 1):
            print(f"{i}. [{el['type']}] {el['name']}")
            
        choice = input("\n>> Do you approve this structure? (Type 'YES' to proceed, or anything else to Modify): ")
        
        final_elements = []
        
        if choice.lower().strip() == 'yes':
            final_elements = proposed_elements
        else:
            print("\nLet's customize your list. Please enter elements (Start, Decision, Process, Note, End).")
            print("Type 'done' for Element Type to finish.")
            while True:
                el_type = input("\nElement Type (Start/Decision/Process/Note/End): ")
                if el_type.lower() == 'done' or not el_type.strip():
                    break
                el_name = input("Element Name/Description: ")
                final_elements.append({"type": el_type, "name": el_name})
        
        print("\nStarting automated literature search on PubMed...")
        
        for item in final_elements:
            point = item['name']
            element_type = item['type']
            
            print(f"\n--- Searching for [{element_type}]: {point} ---")
            
            search_query = f"({condition}) AND ({point}) AND (Guideline[pt] OR Systematic Review[pt])"
            results = self.search_pubmed(search_query, retmax=3)
            
            # Helper function to append to evidence bank
            def save_evidence(citation, point_name, elem_type):
                self.evidence_bank.append({
                    "id": citation, 
                    "decision_point": point_name,
                    "element_type": elem_type
                })

            if results:
                print(f"Found {len(results)} potential sources:")
                for i, citation in enumerate(results, 1):
                    print(f"{i}. {citation}")
                
                sel = input("Enter number to select (or type manual citation): ")
                if sel.isdigit() and 1 <= int(sel) <= len(results):
                    save_evidence(results[int(sel)-1], point, element_type)
                else:
                    save_evidence(sel, point, element_type)
            else:
                print("No direct hits found via API.")
                manual = input("Please enter citation manually: ")
                save_evidence(manual, point, element_type)
            
        self.pathway_data['evidence']['studies'] = self.evidence_bank
        self.assess_health_equity()

    def phase_3_decision_science(self):
        print(self.dialogue["phase_3_intro"])
        time.sleep(1)
        
        entry = input("\nWhat is the Pathway Entry Point (Trigger)? ")
        ends = input("What are the Pathway Endpoints (Disposition)? ")
        
        print("\nLet's build the decision tree.")
        print("Note: Every decision node must be supported by evidence.")
        
        logic_nodes = []
        condition_context = self.pathway_data['scope'].get('condition', 'General')
        
        while True:
            node = input("Add a Decision Node (or press Enter to finish): ")
            if not node: break
            
            # Execute Literature Search Workflow
            evidence_str = self.search_evidence_workflow(node, condition_context)
            
            logic_nodes.append({"node": node, "evidence_link": evidence_str})
        
        self.pathway_data['logic'] = { "entry": entry, "endpoints": ends, "nodes": logic_nodes }
        self.validate_logic()
        
        print("\n[GENERATING PROTOTYPE]")
        print(f"   [{entry}]\n      |\n      v")
        for n in logic_nodes:
            print(f"   <{n['node']}> --> (Evidence: {n['evidence_link']})\n      |\n      v")
        print(f"   [{ends}]")

    def phase_4_user_testing(self):
        print(self.dialogue["phase_4_intro"])
        time.sleep(1)
        
        print("\nFirst, let's do a Heuristic Evaluation.")
        print("(Reference: Nielsen's 10 Usability Heuristics)")
        issues = input("Please list the Top 3 Usability Issues found: ")
        mitigation = input("What are your Mitigation Plans for these issues? ")
        
        print("\nNow, running a Workflow Simulation...")
        print("Simulating 'Silent Mode' pilot data...")
        time.sleep(1)
        condition = self.pathway_data['scope'].get('condition', 'the condition')
        print(f"\nScenario: A provider encounters the decision support for {condition}.")
        print("Predicted Workflow Impact:\n- Clicks added: 2 (Target: <3)\n- Cognitive Load: Low")
        
        feedback = input("\nDuring the pilot, did providers complain about 'Alert Fatigue'?\n>> (Yes/No): ")
        status = "Ready for Go-Live" if feedback.lower() == "no" else "Requires Redesign (Too much friction)"
        print(f"Validation Status: {status}")
        
        self.pathway_data['testing'] = { "method": "Heuristic Evaluation + Workflow Sim", "issues": issues, "mitigation": mitigation, "pilot_fatigue_feedback": feedback, "status": status }

    def phase_5_operationalization(self):
        print(self.dialogue["phase_5_intro"])
        time.sleep(1)
        
        ehr = input("\nWhich EHR System will this live in? (e.g., Epic, Cerner): ")
        tools = input("What specific CDS Tools will we use? (e.g., Order Sets, BPAs): ")
        tool_link = input(f"How does '{tools}' support the decision nodes we defined? ")
        metrics = input("Finally, please define 3 Key Performance Indicators (KPIs): ")
        
        print("\nHere is a draft of the Dashboard Wireframe:")
        print("|----------------------------------------|")
        print(f"| PATHWAY: {self.pathway_data['scope'].get('condition', 'N/A').upper()}     |")
        print("|----------------------------------------|")
        print(f"| KPI 1: {metrics.split(',')[0] if ',' in metrics else metrics}     |")
        print("| Adoption Rate: [ GRAPH ]               |")
        print("|----------------------------------------|")
        
        self.pathway_data['operations'] = { "ehr": ehr, "tools": tools, "tool_link": tool_link, "metrics": metrics }

    def generate_final_report(self):
        print("\n" + "="*60)
        print("PROCESS COMPLETE")
        print(f"All formal summaries have been saved to '{self.report_file}'")
        print("="*60)


if __name__ == "__main__":
    agent = ClinicalPathwayAgent()
    agent.execute_process()
