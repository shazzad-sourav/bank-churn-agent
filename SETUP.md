# Setup on Windows (about 15 minutes)

You'll need: Anaconda (already installed), a Google account, and this folder.

## 1. Get a free Gemini API key
1. Go to **https://aistudio.google.com/apikey** and sign in with your Google account.
2. Click **Create API key** and copy it. No card is needed.

## 2. Create a Python environment
Open **Anaconda Prompt** from the Start menu and run these one at a time:

```bat
cd C:\Users\shazz\DataAnalyst\bank-churn-agent
conda create -n churn-agent python=3.12 -y
conda activate churn-agent
pip install -r requirements.txt
```

The install takes a few minutes. Next time you only need the `cd` and `conda activate churn-agent` lines.

## 3. Add your key
```bat
copy .env.example .env
notepad .env
```
Replace `paste-your-key-here` with your key, then save and close Notepad.

`.env` holds your secret key. It's listed in `.gitignore`, so never upload it to GitHub.

## 4. Check which Gemini models your key can use
```bat
python -m churn_agent.list_models
```
If `gemini-3-flash-preview` isn't in the list, open `.env` and set `MODEL=google_genai:<a flash model from the list>`.

## 5. Build the database and run the tests
```bat
python -m churn_agent.database
pytest -q
```
You should see `44 passed`. The tests don't use your API key.

## 6. Chat with the agent
```bat
streamlit run app.py
```
Your browser opens at http://localhost:8501. Click an example question on the left.
- Expand **tool calls** under an answer to see the SQL it wrote.
- The first docs question takes ~30 seconds while the embedding model (~80 MB) downloads once.
- Try the export example. The agent stops and asks you to **Approve** or **Reject**.

Stop the app with **Ctrl+C** in Anaconda Prompt.

## 7. Run the evaluation
```bat
python -m eval.run_eval --pause 12
```
This asks all 27 questions with a pause between them to stay inside the free tier's per-minute limit, so it takes ~10 minutes. The report is saved to `eval\results\latest.md`.

Each Gemini model has its own free daily quota. When one runs out, the agent switches to the next model in `FALLBACK_MODELS` automatically, and each result line shows which model answered. If every model is used up, the eval stops by itself and keeps its progress. Quotas reset at midnight Pacific (3 a.m. Toronto); then continue with:
```bat
python -m eval.run_eval --resume --pause 12
```
`--resume` keeps the questions that already passed and re-runs only the failed or missing ones.

## 8. Put the score in the README
Open `eval\results\latest.md`, copy the line that says **X/27 passed**, and paste it into README.md where it says *run `python -m eval.run_eval` to fill this in*.

## Switching to OpenAI or Claude later
```bat
pip install langchain-openai
```
Then in `.env` add `OPENAI_API_KEY=...` and set `MODEL=openai:gpt-4o-mini`. Re-run the eval with `--model openai:gpt-4o-mini` to compare providers.
