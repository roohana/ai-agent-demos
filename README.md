# AI Agent Demos: Microsoft AI & Power Platform

Demo recreations of agent and automation patterns I build with **Microsoft Copilot Studio, Azure OpenAI (Microsoft Foundry), Power Platform, Dynamics 365, Azure Logic Apps, LangChain and MCP**.

> **Please read:** these are independent demos that use **fictional data** and a **mock D365 API**. They are *not* client code and contain no client data. Each project folder says exactly what is runnable here and what is a reference design.

Each project has:
- `diagram.png` / `diagram.svg`: the technical flow
- `agent.md`: the main instruction (system prompt) for that project's agent
- `README.md`: what it does, what to demo, how to run or build it

## Projects

| # | Project | What it shows | Status |
|---|---------|---------------|--------|
| 01 | [Order-to-Cash Assistant Agent](01-order-to-cash-agent) | Copilot Studio agent using built-in CRM + ERP connectors and a custom connector, with confirmed writes | Connector + mock API + prompt (agent built in Copilot Studio) |
| 02 | [Procure-to-Pay Approval Automation](02-procure-to-pay-logic-apps) | Agent-triggered Azure Logic App: validate, route approval, write back, notify | Workflow JSON + runnable simulation |
| 03 | [D365 MCP Server](03-d365-mcp-server) | Python MCP server with read / write / ops tools, scopes, confirmation and audit log | **Runnable, tested** |
| 04 | [Healthcare AI Assistant](04-healthcare-ai-assistant) | Copilot Studio agent for patient and practitioner records with privacy guardrails | Reference design + prompt |
| 05 | [Finance & Operations Insights Copilot](05-d365-fo-copilot) | Natural-language finance and procurement insights with controlled actions | Reference design + prompt |
| 06 | [Telemetry Batch Agent](06-telemetry-batch-agent) | SRE / monitoring AI over Application Insights telemetry | Reference design + KQL templates + prompt |
| 07 | [PromptEdge: SOW & Estimation](07-promptedge-sow-estimation) | Two-agent pipeline for D365 F&O SOWs and estimates | Reference design + schema + prompt |
| 08 | [AI Voice FNOL](08-voice-fnol) | Speech-to-text, LLM and text-to-speech claims intake | Reference design + prompt |
| 09 | [Secure GPT](09-secure-gpt) | Private ChatGPT/Claude-style assistant with a data-leak guard | **Runnable, tested** |
| 10 | [AI Cost Optimization](10-ai-cost-optimization) | Token tracking, waste detection and forecast | **Runnable** (synthetic data) |

## Quick start

Run these from the repository root.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r shared/mock-d365-api/requirements.txt -r 03-d365-mcp-server/requirements.txt -r 09-secure-gpt/requirements.txt

# run the tests (the MCP server tests start their own mock API)
(cd 03-d365-mcp-server && pytest -q)
(cd 09-secure-gpt && pytest -q)

# start the shared mock D365 CRM + ERP API (docs at http://localhost:8000/docs)
cd shared/mock-d365-api && uvicorn app:app --port 8000
```

Default API key for the mock: `demo-key` (header `x-api-key`).

## Repo layout

```
shared/mock-d365-api/      FastAPI mock of D365 CRM + F&O (fictional data)
01-... to 10-...           one folder per project (diagram, agent.md, README, code where applicable)
docs/make_diagrams.py      regenerates every diagram.svg / diagram.png (needs Graphviz)
.github/workflows/ci.yml   runs the tests
```

## Notes on using real systems

The mock API mirrors the *shape* of typical CRM/ERP operations. To use a real D365 sandbox, keep the tool and connector contracts and replace the HTTP calls with the Dataverse Web API (CRM) and Finance & Operations OData endpoints, authenticated with Microsoft Entra ID. Never point demos at production data.

## License

MIT, see [LICENSE](LICENSE).
