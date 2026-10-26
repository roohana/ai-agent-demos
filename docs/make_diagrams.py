"""Generates diagram.svg / diagram.png / diagram.dot in every project folder (needs Graphviz `dot`).

    python docs/make_diagrams.py
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = {  # fill, border
    "user": ("#F2F4F7", "#667085"),
    "agent": ("#DCEBFA", "#215E99"),
    "integ": ("#DDF3EE", "#1B7F6B"),
    "system": ("#FDEBD9", "#C2611B"),
    "data": ("#EBE4F7", "#6B4BB0"),
    "human": ("#E3F4DF", "#3C8A2E"),
    "guard": ("#FDE7E7", "#B42318"),
}
LEGEND = [("user", "User / channel"), ("agent", "AI agent / model"), ("integ", "Integration layer"),
          ("system", "System of record"), ("data", "Data / telemetry"), ("guard", "Control / guardrail"), ("human", "Human step")]


def node(i, label, kind, shape="box"):
    fill, border = KINDS[kind]
    label = label.replace('"', '\\"')
    return f'  {i} [label="{label}", shape={shape}, style="rounded,filled", fillcolor="{fill}", color="{border}", fontcolor="#1B1F24"];'


def cluster(name, label, members, color="#98A2B3"):
    inner = "\n".join(f"    {m};" for m in members)
    return f'  subgraph cluster_{name} {{\n    label="{label}"; labeljust="l"; style="rounded,dashed"; color="{color}"; fontcolor="#475467"; fontsize=11;\n{inner}\n  }}'


def edge(a, b, label="", style="solid", color="#475467"):
    lab = f', label="{label}"' if label else ""
    return f'  {a} -> {b} [style={style}, color="{color}"{lab}];'


def legend(used):
    items = [(k, t) for k, t in LEGEND if k in used]
    rows = "".join(f'<TR><TD BGCOLOR="{KINDS[k][0]}" BORDER="1" COLOR="{KINDS[k][1]}" WIDTH="14" HEIGHT="14"></TD><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{t}</FONT></TD></TR>' for k, t in items)
    return f'  legend [shape=plaintext, label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="3">{rows}</TABLE>>];'


def build(title, nodes, edges, clusters=(), rankdir="TB"):
    used = {k for _, _, k, *_ in nodes}
    body = [node(*n) for n in nodes] + list(clusters) + list(edges) + [legend(used)]
    return (f'digraph G {{\n  rankdir={rankdir}; labelloc=t; label="{title}"; fontsize=18; fontname="DejaVu Sans"; pad=0.4; nodesep=0.5; ranksep=0.6; splines=true; bgcolor="white";\n'
            f'  node [fontname="DejaVu Sans", fontsize=11, margin="0.18,0.10"];\n  edge [fontname="DejaVu Sans", fontsize=9, arrowsize=0.8];\n'
            + "\n".join(body) + "\n}\n")


D = {}

D["01-order-to-cash-agent"] = build("Order-to-Cash Assistant: CRM + ERP agent flow", [
    ("user", "Sales / finance user\\nTeams or web chat", "user"),
    ("auth", "Entra ID sign-in\\nacts with user permissions (RBAC)", "guard"),
    ("agent", "Copilot Studio agent\\n(agent.md instructions,\\ngenerative orchestration)", "agent"),
    ("gate", "Confirmation gate\\nsummary -> user says yes", "guard"),
    ("crmc", "Built-in CRM connector\\n(Dataverse / D365 Sales)", "integ"),
    ("erpc", "Built-in ERP connector\\n(Finance & Operations)", "integ"),
    ("cust", "Custom connector\\n(OpenAPI: stock + credit-checked\\nsales orders)", "integ"),
    ("crm", "D365 CRM\\naccounts, opportunities", "system"),
    ("erp", "D365 F&O\\ninvoices, items, sales orders", "system"),
    ("api", "Custom ERP service endpoint", "system"),
    ("llm", "Azure OpenAI", "agent"),
], [
    edge("user", "auth"), edge("auth", "agent", "request"),
    edge("agent", "llm", "plan + answer", "dashed"),
    edge("agent", "crmc", "read: accounts,\\nopportunities"), edge("agent", "erpc", "read: invoices"),
    edge("agent", "cust", "read: stock"),
    edge("agent", "gate", "write intent"), edge("gate", "crmc", "create / update\\nopportunity"), edge("gate", "cust", "create sales order"),
    edge("crmc", "crm"), edge("erpc", "erp"), edge("cust", "api"), edge("api", "erp", "stock + credit rules"),
])

D["02-procure-to-pay-logic-apps"] = build("Procure-to-Pay approval: Copilot agent + Azure Logic Apps", [
    ("emp", "Employee\\n\"I need to buy 10 monitors\"", "user"),
    ("agent", "Copilot Studio agent\\n(agent.md)", "agent"),
    ("trig", "HTTP trigger\\n{requisitionId}", "integ"),
    ("get", "Get requisition + vendor\\n(HTTP, retry x3)", "integ"),
    ("dec", "Needs approval?", "guard", "diamond"),
    ("auto", "Auto-approved\\n(<= 1,000)", "human"),
    ("appr", "Approval email\\n(Outlook, wait for response)", "integ"),
    ("mgr", "Line manager (<= 10,000)\\nor Finance (> 10,000)", "human"),
    ("write", "Write decision to ERP\\n(HTTP POST, retry x3)", "integ"),
    ("note", "Notify requester\\n(Outlook mail)", "integ"),
    ("erp", "D365 F&O\\npurchase requisitions", "system"),
    ("err", "Failure scope\\nResponse 500 + runId", "guard"),
    ("ai", "Application Insights /\\nLog Analytics\\nrun diagnostics", "data"),
], [
    edge("emp", "agent"), edge("agent", "erp", "create requisition\\n(custom connector)"), edge("agent", "trig", "start workflow"),
    edge("trig", "get"), edge("get", "erp", "read", "dashed"), edge("get", "dec"),
    edge("dec", "auto", "no"), edge("dec", "appr", "yes"), edge("appr", "mgr"), edge("mgr", "write", "Approve / Reject"),
    edge("write", "erp", "update status", "dashed"), edge("auto", "note"), edge("write", "note"),
    edge("get", "err", "on failure", "dotted", "#B42318"), edge("err", "ai", "", "dotted", "#B42318"), edge("note", "ai", "run history", "dotted"),
])

D["03-d365-mcp-server"] = build("D365 MCP server: governed read / write / ops tools", [
    ("a1", "Copilot Studio agent", "agent"), ("a2", "LangChain / LangGraph agent", "agent"), ("a3", "Claude Desktop / other MCP client", "agent"),
    ("scope", "Scope filter\\nMCP_SCOPES = read,write,ops\\n(tool not granted = not listed)", "guard"),
    ("val", "Input validation\\n(id formats, ranges, enums)", "guard"),
    ("read", "Read tools (8)\\nsearch_customers, get_customer_overview,\\nlist_invoices, list_items, search_vendors,\\nlist_purchase_orders, get_requisition_status,\\nlist_batch_jobs", "integ"),
    ("write", "Write tools (4)\\ncreate_sales_order, create_purchase_requisition,\\ncreate_opportunity, update_opportunity", "integ"),
    ("ops", "Ops tools (2)\\nrerun_batch_job,\\ntrigger_approval_workflow", "integ"),
    ("conf", "Two-step confirmation\\npreview + token -> human yes\\n-> confirm=true", "guard"),
    ("audit", "Audit log\\nevery call (JSON lines,\\nsecrets masked)", "data"),
    ("cli", "D365 client (httpx)\\nerrors -> readable messages", "integ"),
    ("api", "D365 CRM + ERP API\\n(mock here; real D365 via\\nDataverse Web API / OData)", "system"),
    ("la", "Logic App\\napproval workflow", "system"),
], [
    edge("a1", "scope", "MCP (stdio /\\nstreamable HTTP)"), edge("a2", "scope"), edge("a3", "scope"),
    edge("scope", "val"), edge("val", "read"), edge("val", "write"), edge("val", "ops"),
    edge("write", "conf"), edge("ops", "conf"), edge("conf", "cli", "only after confirm"), edge("read", "cli"),
    edge("cli", "api"), edge("conf", "la", "HTTP trigger", "dashed"),
    edge("read", "audit", "", "dotted"), edge("conf", "audit", "", "dotted"),
])

D["04-healthcare-ai-assistant"] = build("Healthcare AI Assistant: patient and practitioner records agent", [
    ("user", "Clinician / admin\\nplatform UI or Teams", "user"),
    ("agent", "Copilot Studio agent\\n(agent.md)", "agent"),
    ("priv", "Privacy guardrails\\nidentity check (2 identifiers),\\nminimum necessary,\\nno clinical advice", "guard"),
    ("rbac", "User's own permissions\\n(role-based access)", "guard"),
    ("dv", "Dataverse tables\\npractitioners, patients,\\nappointments, referrals", "system"),
    ("plat", "Dynamics 365-based healthcare\\ncloud platform\\n(patients, providers, payers)", "system"),
    ("flow", "Power Automate flows\\nnotifications, record updates\\n(after confirmation)", "integ"),
    ("gen", "Generated output\\nsummaries, navigation help,\\ndraft letters (\"for staff review\")", "agent"),
    ("llm", "Azure OpenAI", "agent"),
    ("esc", "Emergency / out-of-scope\\n-> human clinician", "human"),
], [
    edge("user", "agent"), edge("agent", "priv"), edge("priv", "rbac"), edge("rbac", "dv", "query"),
    edge("dv", "plat", "", "dashed"), edge("agent", "llm", "", "dashed"), edge("dv", "gen", "record data"), edge("llm", "gen", "", "dashed"),
    edge("gen", "user", "answer"), edge("agent", "flow", "confirmed action"), edge("flow", "plat", "update / notify"),
    edge("priv", "esc", "urgent or clinical", "dotted", "#B42318"),
])

D["05-d365-fo-copilot"] = build("Finance & Operations Insights Copilot", [
    ("user", "Finance / AP / procurement user", "user"),
    ("agent", "Copilot agent\\n(agent.md)", "agent"),
    ("llm", "Azure OpenAI\\nquery planning + explanation", "agent"),
    ("tools", "Tool layer\\ncustom connector / API\\n(OData, tool-calling)", "integ"),
    ("sec", "Security roles (RBAC)\\nlegal entity + period scoping", "guard"),
    ("fo", "D365 Finance & Operations\\nGL, AP, AR, procurement", "system"),
    ("read", "Read: balances, open items,\\nvendor spend, transaction\\nexplanations", "integ"),
    ("gate", "Write requests\\nsummary -> user yes", "guard"),
    ("act", "Actions: vendor invoice processing,\\npurchase requisition,\\nreport generation,\\nperiod-end checklist", "integ"),
], [
    edge("user", "agent", "natural language"), edge("agent", "llm", "", "dashed"), edge("agent", "sec"), edge("sec", "tools"),
    edge("tools", "read"), edge("read", "fo", "query"), edge("agent", "gate", "write intent"), edge("gate", "act", "confirmed"),
    edge("act", "fo", "create / trigger"), edge("fo", "agent", "results", "dashed"), edge("agent", "user", "answer + basis\\n(entity, period)"),
])

D["06-telemetry-batch-agent"] = build("Telemetry Batch Agent: SRE and monitoring AI for D365 FSCM", [
    ("fscm", "D365 Finance & Supply Chain\\nbatch jobs, performance", "system"),
    ("ai", "Azure Application Insights /\\nLog Analytics\\nfailures, durations, exceptions", "data"),
    ("kql", "KQL tool\\n(approved query templates,\\nread-only)", "integ"),
    ("llm", "Azure OpenAI analysis layer\\nsummarise, find patterns,\\nrecommend actions", "agent"),
    ("agent", "Copilot interface\\n\"Why did batch jobs fail last night?\"", "agent"),
    ("ops", "Operations / SRE team", "user"),
    ("mon", "Azure Monitor alerts\\nfailure rate, p95 duration,\\nrepeated failures", "guard"),
    ("teams", "Teams channel\\nincident notes", "human"),
    ("gate", "Confirmation gate\\nre-run only if transient,\\nmax 2 per 24h", "guard"),
    ("rerun", "Batch job re-run", "integ"),
    ("cost", "Cost view\\nlong-running / resource-heavy jobs", "data"),
], [
    edge("fscm", "ai", "telemetry"), edge("ai", "mon", "rules", "dashed"), edge("mon", "teams", "alert"),
    edge("ops", "agent", "question"), edge("agent", "kql", "tool call"), edge("kql", "ai", "query"), edge("ai", "llm", "results", "dashed"),
    edge("llm", "agent", "summary, impact,\\nlikely cause, action"), edge("agent", "ops", "answer"),
    edge("agent", "gate", "re-run proposal"), edge("gate", "rerun", "after yes"), edge("rerun", "fscm", "", "dashed"),
    edge("llm", "cost", "", "dotted"),
])

D["07-promptedge-sow-estimation"] = build("PromptEdge: AI SOW and estimation tool for D365 F&O implementations", [
    ("ui", "Multi-step wizard UI\\nmodules, processes, data migration,\\nintegrations, AI workload,\\ntemplate + example upload", "user"),
    ("hist", "Historical project data\\n(actuals by workstream)", "data"),
    ("est", "Estimation agent\\nrange per workstream +\\ntimeline + risks", "agent"),
    ("json", "Estimate JSON\\n(validated against schema)", "integ"),
    ("rev1", "Consultant review\\nopen questions resolved", "human"),
    ("kb", "Templates, example content,\\ncompany knowledge base", "data"),
    ("sow", "SOW / proposal writer agent\\n(grounded; new text marked [REVIEW])", "agent"),
    ("llm", "Azure OpenAI", "agent"),
    ("doc", "Document generation\\nSOW (Word)", "integ"),
    ("ppt", "PowerPoint automation\\nproposal deck", "integ"),
    ("rev2", "Legal / commercial review", "human"),
    ("out", "Export", "user"),
], [
    edge("ui", "est", "scope inputs"), edge("hist", "est", "similar projects"), edge("est", "json"), edge("json", "rev1"),
    edge("rev1", "sow", "approved estimate"), edge("kb", "sow", "grounding"), edge("sow", "llm", "", "dashed"),
    edge("sow", "doc"), edge("sow", "ppt"), edge("doc", "rev2"), edge("ppt", "rev2"), edge("rev2", "out"),
    edge("ui", "kb", "uploads", "dotted"),
])

D["08-voice-fnol"] = build("AI Voice FNOL: first notice of loss voice assistant", [
    ("caller", "Caller", "user"),
    ("tel", "Telephony / voice client", "integ"),
    ("stt", "Azure Speech\\nspeech-to-text", "integ"),
    ("agent", "LLM agent (Azure OpenAI)\\nagent.md: spoken style,\\nverify -> collect -> confirm -> create", "agent"),
    ("kb", "Custom knowledge base\\nservice times, process, FAQs", "data"),
    ("tts", "Azure Speech\\ntext-to-speech", "integ"),
    ("fn", "Azure Functions\\nget_policy, create_claim,\\nget_claim_status", "integ"),
    ("claims", "Claims / policy system", "system"),
    ("id", "Identity verification\\npolicy no. + 2 checks", "guard"),
    ("human", "Human agent handoff\\ninjury, failed ID, caller request", "human"),
], [
    edge("caller", "tel", "voice"), edge("tel", "stt"), edge("stt", "agent", "transcript"), edge("agent", "kb", "retrieve", "dashed"),
    edge("agent", "id"), edge("id", "fn", "verified"), edge("agent", "fn", "tool calls"), edge("fn", "claims"),
    edge("agent", "tts", "reply text"), edge("tts", "tel"), edge("tel", "caller", "voice"),
    edge("agent", "human", "escalate", "dotted", "#B42318"),
])

D["09-secure-gpt"] = build("Secure GPT: private enterprise AI assistant", [
    ("emp", "Employee\\n(instead of public ChatGPT / Claude)", "user"),
    ("auth", "Entra ID sign-in (Easy Auth)\\nallow-list of approved staff", "guard"),
    ("web", "Secure GPT web app\\nFastAPI + chat UI\\n(in the company's Azure tenant)", "integ"),
    ("dlp", "Data-leak guard\\nredact / block emails, cards,\\nID numbers, keys, passwords", "guard"),
    ("aoai", "Company's Azure OpenAI deployment\\nmanaged identity, private to tenant,\\nnot used to train models", "agent"),
    ("sys", "System prompt\\n(agent.md)", "agent"),
    ("log", "Metadata-only logging\\nuser, turns, tokens, DLP flag\\n(no conversation content)", "data"),
    ("ext", "Public AI tools\\n(sensitive data exposure risk)", "system"),
], [
    edge("emp", "auth"), edge("auth", "web"), edge("web", "dlp", "prompt"), edge("dlp", "aoai", "clean prompt"), edge("sys", "aoai", "", "dashed"),
    edge("aoai", "web", "answer"), edge("web", "emp", "answer + notice"), edge("web", "log", "", "dotted"),
    edge("emp", "ext", "replaced", "dotted", "#B42318"),
])

D["10-ai-cost-optimization"] = build("AI Cost Optimization & Token Management framework", [
    ("apps", "AI apps / agents\\non Azure OpenAI deployments", "agent"),
    ("usage", "Usage capture\\nprompt + completion tokens,\\nrequests, latency, model", "integ"),
    ("store", "Usage store\\n(logs / table)", "data"),
    ("price", "Price table\\nper model", "data"),
    ("track", "Token tracking +\\ncost calculation", "integ"),
    ("cmp", "Model comparison\\nquality / latency / cost\\non evaluation set", "integ"),
    ("fc", "Cost prediction\\nforecast + confidence", "integ"),
    ("dash", "Cost dashboards\\nby app, model, prompt", "user"),
    ("agent", "Cost analyst agent\\n(agent.md)", "agent"),
    ("rec", "Ranked recommendations\\nprompt trimming, history limits,\\ncaching, model selection", "human"),
    ("budget", "Budget alerts", "guard"),
], [
    edge("apps", "usage", "every call"), edge("usage", "store"), edge("store", "track"), edge("price", "track"),
    edge("track", "dash"), edge("track", "fc"), edge("fc", "budget"), edge("track", "cmp", "candidates", "dashed"),
    edge("dash", "agent", "questions"), edge("track", "agent", "data tool"), edge("cmp", "agent"), edge("fc", "agent"),
    edge("agent", "rec"), edge("rec", "apps", "owners apply changes", "dotted"),
])

for folder, dot in D.items():
    d = ROOT / folder
    (d / "diagram.dot").write_text(dot, encoding="utf-8")
    subprocess.run(["dot", "-Tsvg", str(d / "diagram.dot"), "-o", str(d / "diagram.svg")], check=True)
    subprocess.run(["dot", "-Tpng", "-Gdpi=150", str(d / "diagram.dot"), "-o", str(d / "diagram.png")], check=True)
    print("rendered", folder)
