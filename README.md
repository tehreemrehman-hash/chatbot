# 💬 Chatbot template

A simple Streamlit app that shows how to build a chatbot using OpenAI's GPT-3.5.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://chatbot-template.streamlit.app/)

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```


### Command-line Clinical Pathway Agent

A simple interactive CLI tool to guide clinical teams through pathway development
(`clinical_pathway_agent.py`). This script uses only the Python standard library
and performs live PubMed lookups via NCBI E-utilities.

Run it with:

```bash
python3 clinical_pathway_agent.py
```

The script will prompt for scope, evidence searches, decision logic, testing
inputs, and will save progress to `clinical_pathway_progress.md` in the project
folder.

Note: PubMed requests require internet access and include an email field in the
query (adjust `search_pubmed` if you'd like to change the contact address).

