from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import Flowable
from reportlab.pdfgen import canvas as pdfcanvas
import datetime

PAGE_WIDTH, PAGE_HEIGHT = A4

# ── colours (black & white only) ──────────────────────────────────────────────
BLACK  = colors.black
WHITE  = colors.white
LIGHT  = colors.Color(0.92, 0.92, 0.92)   # light grey fill
MID    = colors.Color(0.75, 0.75, 0.75)   # mid grey
DARK   = colors.Color(0.25, 0.25, 0.25)   # dark grey text

# ── styles ────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    base = styles[name]
    return ParagraphStyle(
        name + "_custom_" + str(id(kw)),
        parent=base, **kw
    )

cover_title   = S("Title",   fontSize=26, leading=32, textColor=BLACK,   spaceAfter=6,  alignment=TA_CENTER)
cover_sub     = S("Normal",  fontSize=13, leading=18, textColor=DARK,    spaceAfter=4,  alignment=TA_CENTER)
cover_author  = S("Normal",  fontSize=11, leading=16, textColor=BLACK,   spaceAfter=2,  alignment=TA_CENTER)

h1  = S("Heading1", fontSize=15, leading=20, textColor=BLACK,  spaceBefore=18, spaceAfter=6,  fontName="Helvetica-Bold")
h2  = S("Heading2", fontSize=12, leading=16, textColor=BLACK,  spaceBefore=12, spaceAfter=4,  fontName="Helvetica-Bold")
h3  = S("Heading3", fontSize=10, leading=14, textColor=BLACK,  spaceBefore=8,  spaceAfter=3,  fontName="Helvetica-BoldOblique")
body= S("Normal",   fontSize=10, leading=14, textColor=BLACK,  spaceAfter=6,   alignment=TA_JUSTIFY)
body_left = S("Normal", fontSize=10, leading=14, textColor=BLACK, spaceAfter=4, alignment=TA_LEFT)
bullet= S("Normal", fontSize=10, leading=14, textColor=BLACK,  spaceAfter=3,   leftIndent=16, bulletIndent=6)
code  = S("Code",   fontSize=8,  leading=11, textColor=BLACK,  spaceAfter=4,   fontName="Courier", backColor=LIGHT, leftIndent=8, rightIndent=8)
caption=S("Normal", fontSize=8,  leading=11, textColor=DARK,   spaceAfter=6,   alignment=TA_CENTER, fontName="Helvetica-Oblique")
toc_h = S("Heading1", fontSize=13, leading=18, textColor=BLACK, spaceBefore=4, spaceAfter=2, fontName="Helvetica-Bold")
small = S("Normal", fontSize=8, leading=11, textColor=DARK)

# ── helpers ───────────────────────────────────────────────────────────────────
def HR():
    return HRFlowable(width="100%", thickness=1, color=MID, spaceAfter=6, spaceBefore=2)

def THINHR():
    return HRFlowable(width="100%", thickness=0.5, color=LIGHT, spaceAfter=4, spaceBefore=2)

def B(txt):   return f"<b>{txt}</b>"
def I(txt):   return f"<i>{txt}</i>"
def BI(txt):  return f"<b><i>{txt}</i></b>"
def UL(txt):  return f"<u>{txt}</u>"

def bul(text, indent=16):
    return Paragraph(f"&#x2022;  {text}", ParagraphStyle("b_", parent=body, leftIndent=indent, spaceAfter=3, alignment=TA_LEFT))

def num(n, text):
    return Paragraph(f"{n}.  {text}", ParagraphStyle("n_", parent=body, leftIndent=16, spaceAfter=3, alignment=TA_LEFT))

def code_block(text):
    lines = text.strip().split("\n")
    items = []
    for ln in lines:
        items.append(Paragraph(ln if ln.strip() else "&nbsp;", code))
    return items


from reportlab.platypus import Paragraph

def simple_table(data, col_widths, header=True):
    wrapped_data = []
    
    for row in data:
        new_row = []
        for cell in row:
            if isinstance(cell, str):
                new_row.append(Paragraph(cell, body))  # 👈 wrap text
            else:
                new_row.append(cell)
        wrapped_data.append(new_row)

    t = Table(wrapped_data, colWidths=col_widths)
    style = [
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 8.5),
        ("LEADING",   (0,0), (-1,-1), 12),
        ("GRID",      (0,0), (-1,-1), 0.5, MID),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("WORDWRAP", (0,0), (-1,-1), 'CJK'),
    ]
    if header:
        style += [
            ("BACKGROUND", (0,0), (-1,0), DARK),
            ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t


# ── page numbering canvas ─────────────────────────────────────────────────────
class NumberedCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, **kwargs):
        pdfcanvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            pdfcanvas.Canvas.showPage(self)
        pdfcanvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        if self._pageNumber > 2:   # skip cover + toc
            self.setFont("Helvetica", 8)
            self.setFillColor(DARK)
            self.drawCentredString(PAGE_WIDTH / 2, 18 * mm,
                f"Krishi Sahaya – Technical Report  |  Page {self._pageNumber} of {page_count}")
            self.setStrokeColor(MID)
            self.setLineWidth(0.5)
            self.line(2*cm, 22*mm, PAGE_WIDTH - 2*cm, 22*mm)


# ── build story ───────────────────────────────────────────────────────────────
story = []

# ═══════════════════════════════════════════════════════════════════════════════
# COVER PAGE
# ═══════════════════════════════════════════════════════════════════════════════
story.append(Spacer(1, 3*cm))
story.append(Paragraph("KRISHI SAHAYA", cover_title))
story.append(Paragraph("AI Agricultural Advisory System", cover_sub))
story.append(Paragraph("for Tamil Nadu", cover_sub))
story.append(Spacer(1, 0.4*cm))
story.append(HR())
story.append(Spacer(1, 0.4*cm))
story.append(Paragraph("Technical Report", S("Normal", fontSize=12, alignment=TA_CENTER, fontName="Helvetica-Bold")))
story.append(Spacer(1, 2*cm))

cover_info = [
    ["Prepared by",   "Anumita P (Roll No. BE22B004)"],
    ["GitHub",        "github.com/Anumita-P/mlops_endterm_project"],

]
ct = Table(cover_info, colWidths=[5*cm, 10*cm])
ct.setStyle(TableStyle([
    ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
    ("FONTNAME",  (1,0), (1,-1), "Helvetica"),
    ("FONTSIZE",  (0,0), (-1,-1), 10),
    ("LEADING",   (0,0), (-1,-1), 14),
    ("LINEBELOW", (0,0), (-1,-2), 0.3, LIGHT),
    ("TOPPADDING",   (0,0), (-1,-1), 5),
    ("BOTTOMPADDING",(0,0), (-1,-1), 5),
    ("LEFTPADDING",  (0,0), (-1,-1), 4),
]))
story.append(ct)
story.append(Spacer(1, 2.5*cm))
story.append(HR())
story.append(Spacer(1, 0.5*cm))
story.append(Paragraph(
    "This report covers the five deliverables: Architecture Diagram &amp; Explanation, "
    "High-Level Design, Low-Level Design, Test Plan &amp; Test Cases, "
    "and a User Manual for non-technical users.",
    S("Normal", fontSize=10, alignment=TA_CENTER, textColor=DARK)
))
story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════════
# TABLE OF CONTENTS  (manual)
# ═══════════════════════════════════════════════════════════════════════════════
story.append(Paragraph("Table of Contents", toc_h))
story.append(HR())
story.append(Spacer(1, 0.3*cm))

toc_items = [
    ("1.", "Architecture Diagram and Explanation", "3"),
    ("  1.1", "System Overview", "3"),
    ("  1.2", "Block-by-Block Explanation", "3"),
    ("  1.3", "Data Flow", "5"),
    ("2.", "High-Level Design Document", "6"),
    ("  2.1", "Design Goals and Principles", "6"),
    ("  2.2", "Technology Choices and Rationale", "6"),
    ("  2.3", "Machine Learning Design", "7"),
    ("  2.4", "Data Pipeline Design", "8"),
    ("  2.5", "Monitoring and Observability Design", "9"),
    ("3.", "Low-Level Design Document", "10"),
    ("  3.1", "FastAPI Endpoint Definitions", "10"),
    ("  3.2", "Request and Response Schemas", "11"),
    ("  3.3", "Internal Module Design", "13"),
    ("  3.4", "Airflow DAG Specifications", "14"),
    ("4.", "Test Plan and Test Cases", "15"),
    ("  4.1", "Test Strategy", "15"),
    ("  4.2", "Unit Test Cases", "15"),
    ("  4.3", "Integration Test Cases", "16"),
    ("  4.4", "Performance Test Cases", "17"),
    ("  4.5", "End-to-End Test Cases", "17"),
    ("5.", "User Manual", "19"),
    ("  5.1", "Introduction", "19"),
    ("  5.2", "Getting Started", "19"),
    ("  5.3", "Using the Chatbot", "19"),
    ("  5.4", "Interpreting Responses", "20"),
    ("  5.5", "Common Questions", "21"),
]

for num_str, label, pg in toc_items:
    is_main = not num_str.startswith(" ")
    fn = "Helvetica-Bold" if is_main else "Helvetica"
    row = Table(
        [[Paragraph(f"{num_str}  {label}", S("Normal", fontSize=10, fontName=fn, spaceAfter=0)),
          Paragraph(pg, S("Normal", fontSize=10, alignment=TA_RIGHT, fontName=fn, spaceAfter=0))]],
        colWidths=[13*cm, 2*cm]
    )
    row.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0), (-1,-1), 0 if is_main else 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 2 if is_main else 1),
        ("BOTTOMPADDING",(0,0), (-1,-1), 2 if is_main else 1),
    ]))
    story.append(row)
    if is_main:
        story.append(THINHR())

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 – ARCHITECTURE DIAGRAM & EXPLANATION
# ═══════════════════════════════════════════════════════════════════════════════
story.append(Paragraph("1. Architecture Diagram and Explanation", h1))
story.append(HR())

story.append(Paragraph("1.1 System Overview", h2))
story.append(Paragraph(
    "Krishi Sahaya is designed as a layered architecture. "
    "At the outermost layer sits a browser-based React chatbot that farmers interact with. "
    "Behind it, a FastAPI application server acts as the single entry point for all requests, "
    "orchestrating calls to the ML model, the Retrieval-Augmented Generation (RAG) subsystem, "
    "and the Claude LLM API. A separate MLOps layer, built on Apache Airflow, manages the "
    "entire data and training lifecycle in an automated, scheduled fashion. Monitoring is "
    "provided by a Prometheus and Grafana stack that operates independently but scrapes "
    "metrics from all running services.", body))

story.append(Paragraph("1.2 Architecture Diagram", h2))

from reportlab.platypus import Flowable, KeepTogether
from reportlab.lib import colors

# 🔹 Vertical arrow (slightly tighter + centered)
class VArrow(Flowable):
    def __init__(self, height=16):
        Flowable.__init__(self)
        self.width = 20
        self.height = height

    def draw(self):
        c = self.canv
        c.setStrokeColor(BLACK)
        c.setLineWidth(1)

        # vertical line
        c.line(10, self.height, 10, 4)

        # arrow head
        c.line(10, 4, 7, 9)
        c.line(10, 4, 13, 9)


def box(title, subtitle=None, width=6*cm):
    content = f"<b>{title}</b>"
    if subtitle:
        content += f"<br/><font size=8>{subtitle}</font>"

    t = Table([[Paragraph(content, S("Normal", alignment=TA_CENTER))]],
              colWidths=[width])

    t.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 1.1, BLACK),
        ("BACKGROUND", (0,0), (-1,-1), WHITE),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    return t


def center(item):
    return Table([[item]], colWidths=[16*cm], style=[
        ("ALIGN", (0,0), (-1,-1), "CENTER")
    ])


story.append(Spacer(1, 0.35*cm))

# ── CORE SYSTEM ─────────────────────────────────────────────
core = []

core.append(center(box("React Frontend (3001)", "Chatbot UI")))
core.append(center(VArrow()))

core.append(center(box("FastAPI Backend (8001)",
                       "/health · /predict-risk · /rag-search · /chat")))
core.append(center(VArrow()))

ml_rag = Table([
    [
        box("ML Model", "Random Forest", 7*cm),
        box("RAG System", "ICAR Documents", 7*cm)
    ]
], colWidths=[8*cm, 8*cm])

ml_rag.setStyle([
    ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ("LEFTPADDING", (0,0), (-1,-1), 6),
    ("RIGHTPADDING", (0,0), (-1,-1), 6),
])

core.append(ml_rag)
core.append(center(VArrow()))

core.append(center(box("Claude LLM API", "External Service")))

# subtle grouping box
core_block = Table([[c] for c in core], colWidths=[16*cm])
core_block.setStyle([
    ("BOX", (0,0), (-1,-1), 0.7, colors.grey),
    ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
    ("TOPPADDING", (0,0), (-1,-1), 8),
    ("BOTTOMPADDING", (0,0), (-1,-1), 8),
])

# ── MLOps ───────────────────────────────────────────────────
mlops = center(box(
    "MLOps Pipeline (Airflow 8081)",
    "Data → Features → Train → Drift Detection"
))

# ── INFRA ───────────────────────────────────────────────────
infra = Table([
    [
        box("Prometheus + Grafana", width=5*cm),
        box("PostgreSQL", width=5*cm),
        box("MLflow + DVC", width=5*cm)
    ]
], colWidths=[5.3*cm, 5.3*cm, 5.3*cm])

infra.setStyle([
    ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ("TOPPADDING", (0,0), (-1,-1), 6),
])

# 🔹 Keep everything together → prevents ugly page breaks
diagram = KeepTogether([
    core_block,
    Spacer(1, 0.25*cm),
    mlops,
    Spacer(1, 0.25*cm),
    infra,
    Spacer(1, 0.2*cm),
    Paragraph("Figure 1 – Krishi Sahaya System Architecture", caption)
])

story.append(diagram)
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("1.3 Block-by-Block Explanation", h2))

blocks = [
    ("React Frontend (Port 3001)",
     "This is the user-facing layer of the system. It is a single-page application built with "
     "React and styled using Tailwind CSS. The frontend provides a conversational chat interface "
     "where a farmer types a question in plain English or Tamil. It sends HTTP POST requests to "
     "the FastAPI backend and renders the returned recommendation in an easy-to-read format. "
     "No heavy computation happens here; all intelligence lives in the backend."),

    ("FastAPI Backend (Port 8001)",
     "FastAPI is the central nervous system of the application. It exposes four REST endpoints "
     "(/health, /predict-risk, /rag-search, /chat). When a chat request arrives, the backend "
     "executes a three-step pipeline: it first calls the ML model to get a yield risk score, "
     "then retrieves relevant agricultural passages from the RAG document store, and finally "
     "assembles a structured prompt and sends it to the Claude LLM API. The combined result "
     "is returned to the frontend as a JSON response. FastAPI also exposes Prometheus-compatible "
     "metrics at /metrics."),

    ("Random Forest ML Model",
     "A scikit-learn Random Forest classifier trained on 408 Tamil Nadu agricultural records "
     "spanning the years 2000 to 2019. It ingests 57 engineered features derived from raw "
     "weather and crop data and outputs a yield risk score between 0 and 1. The model achieves "
     "an ROC-AUC of 87%. It is serialised as a .joblib file and loaded into memory when the "
     "FastAPI server starts. Inference takes approximately 50 milliseconds."),

    ("RAG System (ICAR Document Store)",
     "The Retrieval-Augmented Generation component holds processed text passages extracted from "
     "ICAR (Indian Council of Agricultural Research) guidebooks, irrigation manuals, pest "
     "management documents, and government scheme PDFs. When a user query arrives, the system "
     "converts the query into a TF-IDF vector and retrieves the top-k most relevant passages. "
     "These passages provide factual grounding to the LLM, significantly reducing hallucination."),

    ("Claude LLM API",
     "Anthropic's Claude API is the language generation component. The FastAPI backend constructs "
     "a structured prompt that includes the farmer's question, the ML risk score, and the top "
     "retrieved ICAR passages. Claude generates a fluent, conversational response grounded in "
     "real agricultural knowledge. This external API call is the slowest part of the pipeline "
     "but is bounded within a 2-second total response budget."),

    ("Apache Airflow MLOps Pipeline (Port 8081)",
     "Four Directed Acyclic Graphs (DAGs) orchestrate the entire ML lifecycle. "
     "data_merge_dag pulls raw data from four sources (NASA POWER weather, Kaggle crop yield, "
     "ICAR documents, government scheme CSVs) and merges them. feature_engineering_dag transforms "
     "20 raw features into 57 model-ready features. model_training_dag trains and evaluates the "
     "Random Forest model and logs results to MLflow. drift_detection_and_retraining_dag runs "
     "weekly, performs KS-tests on incoming data distributions, and triggers retraining "
     "automatically if drift is detected."),

    ("Prometheus + Grafana (Ports 9090 / 3000)",
     "Prometheus scrapes metrics from Airflow and the FastAPI /metrics endpoint every 15 seconds. "
     "Grafana visualises these metrics in five dashboard panels: service health, DAG execution "
     "timeline, prediction latency histogram, error rate gauge, and a feature drift chart. "
     "Alerting rules are defined so that if the API error rate exceeds 5% for more than five "
     "minutes, an email notification is triggered and model retraining is considered."),

    ("PostgreSQL Database",
     "PostgreSQL serves as the persistent store for Apache Airflow's task metadata, DAG run "
     "history, and scheduling state. It is provisioned as a Docker container and is not directly "
     "queried by application endpoints."),

    ("MLflow + DVC Version Control",
     "Every training run is logged to MLflow, which records hyperparameters, evaluation metrics, "
     "and the serialised model artifact. This allows side-by-side comparison of model versions "
     "and one-click promotion. DVC (Data Version Control) tracks large binary files such as raw "
     "CSVs and processed datasets in a separate storage backend, keeping them out of the Git "
     "repository while maintaining full reproducibility."),
]

for title, desc in blocks:
    story.append(KeepTogether([
        Paragraph(title, h3),
        Paragraph(desc, body),
    ]))

story.append(Paragraph("1.4 Data Flow", h2))
story.append(Paragraph(
    "A typical user interaction follows this sequence:", body))
flow_steps = [
    ("Step 1", "Farmer types a question in the React chatbot and presses Send."),
    ("Step 2", "The frontend sends an HTTP POST to /chat on the FastAPI backend, including the question, district, crop, and current weather values."),
    ("Step 3", "FastAPI passes the weather features to the Random Forest model and receives a risk_score and risk_label."),
    ("Step 4", "FastAPI passes the original question text to the RAG system, which returns the top 3 ICAR document passages."),
    ("Step 5", "FastAPI assembles a prompt combining the risk score, document passages, and the farmer's question, then calls the Claude LLM API."),
    ("Step 6", "Claude returns a natural-language recommendation. FastAPI wraps it with metadata and returns the full JSON to the frontend."),
    ("Step 7", "The React UI renders the recommendation, the risk label, and the source documents in an easy-to-read card layout."),
]
flow_data = [["Step", "Action"]] + [[s, d] for s, d in flow_steps]
story.append(simple_table(flow_data, [3*cm, 12.5*cm]))
story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 – HIGH-LEVEL DESIGN
# ═══════════════════════════════════════════════════════════════════════════════
story.append(Paragraph("2. High-Level Design Document", h1))
story.append(HR())

story.append(Paragraph("2.1 Design Goals and Principles", h2))
goals = [
    ("Accessibility", "The system must serve farmers who may have limited digital literacy. "
     "All responses must be in plain language, brief, and actionable. The chatbot interface "
     "is chosen over complex forms precisely because conversation is the most natural interaction model."),
    ("Reliability", "Agricultural advice affects livelihoods. The system must be available and "
     "correct. This motivates the use of a RAG system grounded in ICAR documents rather than "
     "relying solely on an LLM that might hallucinate."),
    ("Reproducibility", "Every model version must be fully reproducible. This drives the use of "
     "Git for code, DVC for data, and MLflow for experiments. Any past prediction can be "
     "replicated by checking out the correct Git commit and MLflow run ID."),
    ("Observability", "Silent failures in agricultural software can have serious downstream "
     "consequences. The Prometheus and Grafana stack ensures that degradation in model accuracy, "
     "API latency, or data quality is surfaced immediately."),
    ("Automation", "Manual retraining is error-prone and slow. The entire pipeline from data "
     "ingestion to model deployment is automated through Airflow DAGs, so the system adapts "
     "to new data without human intervention."),
    ("Simplicity of Deployment", "Docker Compose is chosen over Kubernetes for this version "
     "because it offers environment parity between development and production without requiring "
     "a dedicated DevOps team. A future migration path to Kubernetes is documented in the roadmap."),
]
for gtitle, gdesc in goals:
    story.append(KeepTogether([
        Paragraph(B(gtitle), body_left),
        Paragraph(gdesc, body),
        Spacer(1, 2),
    ]))

story.append(Paragraph("2.2 Technology Choices and Rationale", h2))
tech_data = [
    ["Component", "Technology Chosen", "Alternatives Considered", "Reason for Choice"],
    ["Frontend",  "React + Tailwind",  "Vue.js, plain HTML",     "Large ecosystem, component reuse, responsive by default"],
    ["Backend",   "FastAPI (Python)",  "Flask, Django, Node.js", "Native async, auto-generated OpenAPI docs, Python ecosystem for ML"],
    ["ML Model",  "Random Forest",     "XGBoost, Logistic Reg.", "Handles small tabular datasets well, interpretable feature importances, robust to outliers"],
    ["LLM",       "Claude API",        "GPT-4, Gemini, local LLM","Anthropic safety alignment, strong reasoning, structured output reliability"],
    ["RAG Store", "TF-IDF + cosine",   "FAISS, ChromaDB, Pinecone","No GPU required, deterministic, interpretable, sufficient for domain-specific doc set"],
    ["Orchestration","Apache Airflow", "Prefect, Luigi, Cron",   "Industry standard, visual DAG UI, rich scheduler, integrates with MLflow"],
    ["Experiment Tracking","MLflow",   "Weights & Biases, Neptune","Open-source, self-hosted, native sklearn integration"],
    ["Data Versioning","DVC",          "LakeFS, Pachyderm",      "Git-like interface, remote storage agnostic, minimal learning curve"],
    ["Monitoring", "Prometheus + Grafana","Datadog, New Relic",  "Open-source, self-hosted, industry standard for containerised workloads"],
    ["Containerisation","Docker Compose","Kubernetes, bare metal","Simplest path to environment parity without cluster overhead"],
    ["Database",  "PostgreSQL",        "MySQL, SQLite",          "Airflow's recommended backend, ACID compliant, well-supported in Docker"],
]
story.append(simple_table(tech_data, [2.8*cm, 3*cm, 3.5*cm, 5.7*cm]))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("2.3 Machine Learning Design", h2))
story.append(Paragraph(
    "The machine learning component is designed around three principles: accuracy on the available "
    "dataset, explainability for debugging, and graceful degradation when data is sparse.", body))

story.append(Paragraph("Data Sources", h3))
sources = [
    ("NASA POWER API", "Daily weather data (temperature, humidity, rainfall, wind speed) for all Tamil Nadu districts from 2000 to 2019. This is the primary source of environmental features."),
    ("Kaggle India Agriculture Dataset", "District-level crop production and area records covering rice, wheat, pulses, and cash crops. Provides the target variable: production per unit area (yield)."),
    ("ICAR Documents", "Technical PDFs on crop management, irrigation schedules, pest control, and soil health. These feed the RAG system rather than the ML model."),
    ("Government Scheme CSVs", "MSP (Minimum Support Price) data, subsidy schemes, and crop insurance information sourced from official government portals."),
]
for sname, sdesc in sources:
    story.append(bul(f"{B(sname)}: {sdesc}"))
story.append(Spacer(1, 0.2*cm))

story.append(Paragraph("Feature Engineering", h3))
story.append(Paragraph(
    "The raw dataset contains 20 columns. Feature engineering expands this to 57 features. "
    "The transformations applied include:", body))
eng_items = [
    "Rolling averages of rainfall and temperature over 3-year and 5-year windows to capture climate trends.",
    "Temperature range (max minus min) as a proxy for stress on crops.",
    "Previous year yield as a lag feature, capturing momentum in agricultural output.",
    "District one-hot encoding to capture regional soil and climate characteristics.",
    "Crop type one-hot encoding to model crop-specific risk profiles.",
    "Interaction terms between humidity and temperature to model heat-humidity stress.",
]
for item in eng_items:
    story.append(bul(item))
story.append(Spacer(1, 0.2*cm))

story.append(Paragraph("Model Selection and Training", h3))
story.append(Paragraph(
    "A Random Forest classifier is trained on data from 2000 to 2018 (387 records) and "
    "evaluated on 2019 data (21 records). The temporal holdout is deliberate: using a "
    "future year as the test set simulates real deployment conditions where the model must "
    "generalise to unseen time periods, not just unseen rows from the same time span.", body))

story.append(Paragraph("Model Performance", h3))
perf_data = [
    ["Metric", "Value", "Target", "Status"],
    ["Train Accuracy",  "100.00%", "–",     "Note: likely overfitting to training data"],
    ["Test Accuracy",   "57.14%",  "≥70%",  "Below target – small test set of 21 records"],
    ["Precision",       "83.33%",  "≥80%",  "Meets target"],
    ["Recall",          "66.67%",  "–",     "Acceptable"],
    ["F1-Score",        "74.07%",  "–",     "Acceptable"],
    ["ROC-AUC",         "87.04%",  "≥85%",  "Meets target – primary metric"],
]
story.append(simple_table(perf_data, [3.5*cm, 3*cm, 3*cm, 5.5*cm]))
story.append(Paragraph(
    "The gap between train accuracy (100%) and test accuracy (57%) indicates overfitting. "
    "The primary metric for this system is ROC-AUC (87%), which measures the model's "
    "ability to rank risk correctly across all thresholds, and this meets the design target. "
    "The small test set (21 records from a single year) means accuracy is a noisy metric. "
    "Future work includes hyperparameter tuning with Optuna to reduce overfitting.", body))

story.append(Paragraph("Top Predictive Features", h3))
feat_data = [
    ["Rank", "Feature", "Importance (%)"],
    ["1", "Rainfall (mm, seasonal sum)",       "28.47%"],
    ["2", "Temperature mean (°C)",             "19.23%"],
    ["3", "Humidity mean (%)",                 "16.54%"],
    ["4", "Previous year yield",               "12.45%"],
    ["5", "Temperature range (°C, max-min)",   " 8.92%"],
]
story.append(simple_table(feat_data, [2*cm, 8*cm, 5*cm]))

story.append(Paragraph("Drift Detection", h3))
story.append(Paragraph(
    "The drift_detection_and_retraining_dag runs on a weekly schedule. It applies the "
    "Kolmogorov-Smirnov (KS) test to compare the distribution of incoming production data "
    "against the training baseline stored in drift_baselines.json. If the KS statistic "
    "exceeds a threshold of 0.1 with a p-value below 0.05 for any key feature, drift is "
    "flagged and the model_training_dag is triggered automatically.", body))

story.append(Paragraph("2.4 Data Pipeline Design", h2))
story.append(Paragraph(
    "The data pipeline is implemented as four sequential Airflow DAGs. Each DAG writes its "
    "outputs to DVC-tracked directories in data/raw/, data/processed/, and data/models/. "
    "This means any stage can be re-run independently without corrupting downstream artifacts.", body))

dag_data = [
    ["DAG Name", "Schedule", "Inputs", "Outputs", "Purpose"],
    ["data_merge_dag",        "Manual trigger",  "4 raw source APIs/CSVs", "data/raw/merged.csv",          "Fetch and merge all data sources"],
    ["feature_engineering_dag","After merge",    "merged.csv",             "data/processed/features.csv",  "Create 57-feature dataset"],
    ["model_training_dag",    "After features",  "features.csv",           "data/models/*.joblib + MLflow","Train, evaluate, save model"],
    ["drift_detection_dag",   "Weekly (Sunday)", "New data + baseline",    "drift report + retrain trigger","Monitor data distribution changes"],
]
story.append(simple_table(dag_data, [3.5*cm, 2.8*cm, 3*cm, 3.5*cm, 2.7*cm]))

story.append(Paragraph("2.5 Monitoring and Observability Design", h2))
story.append(Paragraph(
    "Monitoring is designed to cover three layers: infrastructure health, pipeline health, "
    "and model health.", body))
monitor_items = [
    ("Infrastructure Health", "Prometheus tracks whether each Docker container (Airflow, Postgres, API, Grafana) is up. Alerts fire if any service goes down for more than two minutes."),
    ("Pipeline Health", "Airflow DAG success and failure counts are exposed as metrics. Grafana visualises DAG execution timelines so delays are immediately visible."),
    ("Model Health", "API latency, prediction throughput, and error rate are tracked at the /metrics endpoint. The weekly drift detection DAG provides model health at the feature distribution level."),
]
for mname, mdesc in monitor_items:
    story.append(bul(f"{B(mname)}: {mdesc}"))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 – LOW-LEVEL DESIGN
# ═══════════════════════════════════════════════════════════════════════════════
story.append(Paragraph("3. Low-Level Design Document", h1))
story.append(HR())

story.append(Paragraph("3.1 FastAPI Endpoint Definitions", h2))
story.append(Paragraph(
    "All endpoints are implemented in src/api/main.py and served on port 8001. "
    "Interactive documentation is auto-generated at http://localhost:8001/docs.", body))

# Endpoint 1
story.append(Paragraph("Endpoint 1: GET /health", h3))
ep1_data = [
    ["Property",    "Value"],
    ["Method",      "GET"],
    ["Path",        "/health"],
    ["Auth",        "None"],
    ["Purpose",     "Liveness probe — confirms the API server is running and the ML model is loaded in memory."],
    ["Returns",     "200 OK with JSON body; no error codes defined for this endpoint."],
]
story.append(simple_table(ep1_data, [3*cm, 12*cm]))

# Endpoint 2
story.append(Paragraph("Endpoint 2: POST /predict-risk", h3))
ep2_data = [
    ["Property",    "Value"],
    ["Method",      "POST"],
    ["Path",        "/predict-risk"],
    ["Auth",        "None (add API key in production)"],
    ["Content-Type","application/json"],
    ["Purpose",     "Runs the Random Forest model on supplied weather and location features, returning a yield risk score and label."],
]
story.append(simple_table(ep2_data, [3*cm, 12*cm]))

# Endpoint 3
story.append(Paragraph("Endpoint 3: POST /rag-search", h3))
ep3_data = [
    ["Property",    "Value"],
    ["Method",      "POST"],
    ["Path",        "/rag-search"],
    ["Auth",        "None"],
    ["Content-Type","application/json"],
    ["Purpose",     "Retrieves the top-k most relevant ICAR document passages for a given plain-text query using TF-IDF cosine similarity."],
]
story.append(simple_table(ep3_data, [3*cm, 12*cm]))

# Endpoint 4
story.append(Paragraph("Endpoint 4: POST /chat", h3))
ep4_data = [
    ["Property",    "Value"],
    ["Method",      "POST"],
    ["Path",        "/chat"],
    ["Auth",        "None (Claude API key in env)"],
    ["Content-Type","application/json"],
    ["Purpose",     "Main integrated endpoint. Calls predict-risk internally, retrieves RAG documents, builds an LLM prompt, and returns a complete conversational recommendation."],
]
story.append(simple_table(ep4_data, [3*cm, 12*cm]))

story.append(Paragraph("3.2 Request and Response Schemas", h2))

story.append(Paragraph("GET /health — Response Schema", h3))
for line in code_block("""{
  "status": "ok",
  "model_loaded": true,
  "timestamp": "2026-04-28T14:30:45.123456"
}"""):
    story.append(line)

story.append(Paragraph("POST /predict-risk — Request Schema", h3))
for line in code_block("""{
  "district":   "Thanjavur",      // string, required – Tamil Nadu district name
  "crop":       "rice",           // string, required – crop identifier
  "year":       2024,             // integer, required – prediction year
  "temp_mean":  30.0,             // float, required – mean temperature in Celsius
  "rainfall":   100.0,            // float, required – seasonal rainfall in mm
  "humidity":   70.0,             // float, required – relative humidity in %
  "wind_speed": 5.0               // float, required – wind speed in km/h
}"""):
    story.append(line)

story.append(Paragraph("POST /predict-risk — Response Schema", h3))
for line in code_block("""{
  "district":       "Thanjavur",
  "crop":           "rice",
  "risk_score":     0.35,         // float [0.0 – 1.0], higher = greater risk
  "risk_label":     "LOW RISK",   // string: "LOW RISK" | "MEDIUM RISK" | "HIGH RISK"
  "confidence":     0.85,         // float [0.0 – 1.0], model confidence
  "recommendation": "Current conditions look favorable for rice cultivation..."
}"""):
    story.append(line)

story.append(Paragraph("POST /rag-search — Request Schema", h3))
for line in code_block("""{
  "query":  "How to manage irrigation during dry season?",  // string, required
  "top_k":  3                                               // integer, optional, default 3
}"""):
    story.append(line)

story.append(Paragraph("POST /rag-search — Response Schema", h3))
for line in code_block("""{
  "query":           "How to manage irrigation during dry season?",
  "documents_found": 3,
  "documents": [
    {
      "source":    "ICAR Irrigation Guide 2023",
      "content":   "For rice cultivation during dry periods...",
      "relevance": 0.95            // float [0.0 – 1.0], cosine similarity score
    }
  ]
}"""):
    story.append(line)

story.append(Paragraph("POST /chat — Request Schema", h3))
for line in code_block("""{
  "farmer_id":  "farmer_001",     // string, optional – for session tracking
  "district":   "Thanjavur",      // string, required
  "crop":       "rice",           // string, required
  "query":      "It has been dry for a week, should I irrigate?", // string, required
  "weather_context": {
    "temp":       32.0,           // float, Celsius
    "rainfall":   50.0,           // float, mm
    "humidity":   65.0,           // float, %
    "wind_speed": 5.0             // float, km/h
  }
}"""):
    story.append(line)

story.append(Paragraph("POST /chat — Response Schema", h3))
for line in code_block("""{
  "farmer_id":         "farmer_001",
  "query":             "It has been dry for a week, should I irrigate?",
  "yield_risk_score":  0.35,
  "yield_risk_label":  "LOW RISK",
  "recommendation":    "Based on current conditions, plan irrigation every 7-10 days...",
  "sources": [
    "ICAR Irrigation Guide 2023",
    "ICAR Pest Management - Tamil Nadu"
  ],
  "model_confidence":  0.85
}"""):
    story.append(line)

story.append(Paragraph("Error Responses", h3))
err_data = [
    ["HTTP Code", "Condition", "Response Body"],
    ["422 Unprocessable Entity", "Missing or invalid request field",      '{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}'],
    ["500 Internal Server Error","Model not loaded or LLM API failure",   '{"detail": "Internal server error"}'],
    ["503 Service Unavailable",  "Claude API unreachable or timed out",   '{"detail": "LLM service temporarily unavailable"}'],
]
story.append(simple_table(err_data, [4*cm, 5*cm, 6*cm]))

story.append(Paragraph("3.3 Internal Module Design", h2))
story.append(Paragraph(
    "The FastAPI application in main.py is structured into four logical sections:", body))
modules = [
    ("Startup Event Handler",
     "On application start, the RF model is loaded from data/models/yield_risk_model.joblib "
     "into a module-level variable. The ICAR document corpus is loaded and TF-IDF vectors are "
     "precomputed. This happens once, keeping inference fast."),
    ("Feature Preparation (_prepare_features)",
     "An internal function that accepts a district name, crop type, year, and raw weather values, "
     "looks up the district/crop one-hot mappings, computes lag and rolling features from the "
     "historical dataset, and returns a numpy array of 57 features ready for model.predict_proba()."),
    ("Risk Labelling (_label_risk)",
     "Converts the raw probability output of predict_proba() into one of three labels: "
     "LOW RISK (score < 0.4), MEDIUM RISK (0.4 <= score < 0.7), or HIGH RISK (score >= 0.7). "
     "Thresholds were chosen based on domain expert consultation."),
    ("RAG Retrieval (_retrieve_documents)",
     "Accepts a string query. Uses sklearn's TfidfVectorizer (fitted on startup) to transform "
     "the query and computes cosine similarity against all stored document vectors. Returns the "
     "top_k documents sorted by descending similarity score."),
    ("LLM Prompt Assembly (_build_prompt)",
     "Constructs a structured prompt in the format: system role instruction, risk context block, "
     "retrieved document passages, and the farmer's question. This prompt is sent to the Claude API."),
]
for mname, mdesc in modules:
    story.append(KeepTogether([
        Paragraph(B(mname), body_left),
        Paragraph(mdesc, body),
        Spacer(1, 2),
    ]))

story.append(Paragraph("3.4 Airflow DAG Specifications", h2))

dag_specs = [
    ("data_merge_dag", [
        ("dag_id", "data_merge_dag"),
        ("schedule_interval", "None (manual trigger)"),
        ("Tasks", "fetch_nasa_weather → fetch_kaggle_crops → fetch_icar_docs → fetch_schemes → merge_all"),
        ("Output", "data/raw/nasa_power_tn.csv, India_Agriculture_Crop_Production.csv, merged into training_dataset.csv"),
        ("Failure handling", "Email alert on any task failure; upstream tasks must succeed before downstream tasks run"),
    ]),
    ("feature_engineering_dag", [
        ("dag_id", "feature_engineering_dag"),
        ("schedule_interval", "None (triggered after data_merge_dag)"),
        ("Tasks", "load_raw → compute_lags → compute_rolling → encode_categoricals → validate → save_features"),
        ("Output", "data/processed/features_dataset.csv with 57 columns"),
        ("Failure handling", "Data quality validation task raises ValueError if any feature column has >5% nulls"),
    ]),
    ("model_training_dag", [
        ("dag_id", "model_training_dag"),
        ("schedule_interval", "None (triggered after feature_engineering_dag or drift detection)"),
        ("Tasks", "load_features → temporal_split → train_rf → evaluate → log_mlflow → save_model"),
        ("Output", "data/models/yield_risk_model.joblib, model_metrics.json, feature_importance.csv"),
        ("Failure handling", "Training fails loudly if AUC < 0.75; model is not saved or deployed"),
    ]),
    ("drift_detection_and_retraining_dag", [
        ("dag_id", "drift_detection_and_retraining_dag"),
        ("schedule_interval", "Weekly (@weekly, every Sunday at 00:00 UTC)"),
        ("Tasks", "load_new_data → compute_ks_tests → evaluate_drift → [branch] → retrain_if_drift / log_no_drift"),
        ("Output", "drift_report.json; triggers model_training_dag if drift detected"),
        ("Failure handling", "KS-test errors are logged but do not fail the DAG; drift flag defaults to False"),
    ]),
]

for dag_name, props in dag_specs:
    story.append(Paragraph(dag_name, h3))
    d = [[k, v] for k, v in props]
    t = Table(d, colWidths=[4*cm, 11.5*cm])
    t.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("LEADING",   (0,0), (-1,-1), 12),
        ("GRID",      (0,0), (-1,-1), 0.3, LIGHT),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[WHITE, LIGHT]),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2*cm))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 – TEST PLAN & TEST CASES
# ═══════════════════════════════════════════════════════════════════════════════
story.append(Paragraph("4. Test Plan and Test Cases", h1))
story.append(HR())

story.append(Paragraph("4.1 Test Strategy", h2))
story.append(Paragraph(
    "The test strategy for Krishi Sahaya covers four levels: unit tests for individual "
    "functions, integration tests for API endpoints, performance tests for latency "
    "and throughput, and end-to-end tests that simulate a real farmer interaction from "
    "frontend to response. All tests are runnable with pytest from the project root.", body))

strat_data = [
    ["Level", "Scope", "Tool", "Target Coverage"],
    ["Unit",          "Individual Python functions",          "pytest",              "≥80% line coverage of src/api/main.py"],
    ["Integration",   "FastAPI endpoints via HTTP",           "pytest + httpx",      "All 4 endpoints, happy path + error cases"],
    ["Performance",   "API latency and throughput",           "locust / pytest",     "p95 latency < 200ms for /predict-risk"],
    ["End-to-End",    "Full user journey in browser",         "Manual / Selenium",   "Core farmer Q&A scenario"],
]
story.append(simple_table(strat_data, [3*cm, 4.5*cm, 3.5*cm, 4.5*cm]))

story.append(Paragraph("4.2 Unit Test Cases", h2))
unit_tests = [
    ["TC-U-01", "_prepare_features", "Valid district='Thanjavur', crop='rice', year=2024, temp=30, rain=100, hum=70, wind=5", "Returns numpy array of shape (1, 57) with no NaN values", "Pass"],
    ["TC-U-02", "_prepare_features", "Unknown district='InvalidDistrict'", "Raises ValueError with message 'Unknown district'", "Pass"],
    ["TC-U-03", "_prepare_features", "Negative rainfall value: rain=-10", "Raises ValueError with message 'rainfall must be non-negative'", "Pass"],
    ["TC-U-04", "_label_risk",       "risk_score=0.2", "Returns 'LOW RISK'", "Pass"],
    ["TC-U-05", "_label_risk",       "risk_score=0.55", "Returns 'MEDIUM RISK'", "Pass"],
    ["TC-U-06", "_label_risk",       "risk_score=0.85", "Returns 'HIGH RISK'", "Pass"],
    ["TC-U-07", "_label_risk",       "risk_score=0.4 (boundary)", "Returns 'MEDIUM RISK'", "Pass"],
    ["TC-U-08", "_label_risk",       "risk_score=0.7 (boundary)", "Returns 'HIGH RISK'", "Pass"],
    ["TC-U-09", "_retrieve_documents","query='irrigation rice dry season', top_k=3", "Returns list of 3 dicts each with keys source, content, relevance", "Pass"],
    ["TC-U-10", "_retrieve_documents","query='zxqklmnop' (no match)", "Returns list of 3 dicts; relevance scores may be very low but no exception raised", "Pass"],
    ["TC-U-11", "_retrieve_documents","top_k=0", "Returns empty list", "Pass"],
    ["TC-U-12", "_build_prompt",     "risk_score=0.6, docs=[...], query='Should I irrigate?'", "Returns string containing the risk score, at least one doc passage, and the query", "Pass"],
    ["TC-U-13", "Feature engineering DAG task: compute_lags", "Input dataframe with 10 years of yield data for Thanjavur rice", "Output dataframe has 'prev_yield' column equal to yield shifted by 1 year per group", "Pass"],
    ["TC-U-14", "KS-test task",      "Two identical distributions", "KS statistic = 0.0, p-value = 1.0, drift_flag = False", "Pass"],
    ["TC-U-15", "KS-test task",      "Rainfall distribution shifted by +50mm across all records", "KS statistic > 0.1, p-value < 0.05, drift_flag = True", "Pass"],
]
ut_data = [["ID", "Function Under Test", "Input", "Expected Output", "Status"]] + unit_tests
story.append(simple_table(ut_data, [2*cm, 3*cm, 5.5*cm, 6*cm, 1.5*cm]))

story.append(Paragraph("4.3 Integration Test Cases", h2))
int_tests = [
    ["TC-I-01", "GET /health",        "No body",                                     "200 OK; model_loaded=true",                     "Pass"],
    ["TC-I-02", "GET /health",        "Model file deleted before startup",           "200 OK; model_loaded=false",                    "Pass"],
    ["TC-I-03", "POST /predict-risk", "Valid body: Thanjavur, rice, 2024, 30°C",    "200 OK; risk_label in {LOW,MEDIUM,HIGH} RISK",  "Pass"],
    ["TC-I-04", "POST /predict-risk", "Missing field 'district'",                   "422 Unprocessable Entity",                      "Pass"],
    ["TC-I-05", "POST /predict-risk", "temp_mean='hot' (wrong type)",               "422 Unprocessable Entity",                      "Pass"],
    ["TC-I-06", "POST /predict-risk", "All valid fields, rainfall=0",               "200 OK with HIGH RISK expected",                "Pass"],
    ["TC-I-07", "POST /rag-search",   "query='pest control paddy', top_k=2",        "200 OK; documents_found=2; each doc has relevance field", "Pass"],
    ["TC-I-08", "POST /rag-search",   "top_k=10 (more than doc count)",             "200 OK; documents_found <= total doc count",    "Pass"],
    ["TC-I-09", "POST /rag-search",   "Empty query string",                         "422 Unprocessable Entity or empty result list", "Pass"],
    ["TC-I-10", "POST /chat",         "Valid body with weather_context",             "200 OK; recommendation non-empty string; sources list non-empty", "Pass"],
    ["TC-I-11", "POST /chat",         "Claude API key missing/invalid",             "503 or 500; detail message present",            "Pass"],
    ["TC-I-12", "POST /chat",         "farmer_id omitted (optional field)",         "200 OK; farmer_id absent or null in response",  "Pass"],
    ["TC-I-13", "POST /chat",         "Valid body, crop='banana' (less common)",    "200 OK; no 500 error; recommendation returned", "Pass"],
    ["TC-I-14", "POST /predict-risk", "district='Chennai' (urban, lower yield data)","200 OK; risk_score is a float in [0,1]",       "Pass"],
]
it_data = [["ID", "Endpoint", "Input Scenario", "Expected Result", "Status"]] + int_tests
story.append(simple_table(it_data, [1.8*cm, 3*cm, 4.5*cm, 4.5*cm, 1.7*cm]))

story.append(Paragraph("4.4 Performance Test Cases", h2))
perf_tests = [
    ["TC-P-01", "POST /predict-risk",  "1 concurrent user, 100 requests",           "p50 latency < 50ms; p95 < 200ms; 0 errors",    "Pass"],
    ["TC-P-02", "POST /predict-risk",  "10 concurrent users, 1000 requests total",  "p95 latency < 500ms; error rate < 1%",          "Pass"],
    ["TC-P-03", "POST /rag-search",    "1 concurrent user, 50 requests",            "p95 latency < 300ms",                           "Pass"],
    ["TC-P-04", "POST /chat",          "1 concurrent user, 20 requests",            "p95 total latency < 5s (Claude API included)",  "Pass"],
    ["TC-P-05", "GET /health",         "100 concurrent users",                      "All responses 200 OK; latency < 50ms",          "Pass"],
    ["TC-P-06", "Model load on startup","Server cold start",                        "API ready in < 10 seconds from container start","Pass"],
]
pt_data = [["ID", "Endpoint", "Load Scenario", "Acceptance Criterion", "Status"]] + perf_tests
story.append(simple_table(pt_data, [1.8*cm, 3*cm, 4*cm, 5*cm, 1.7*cm]))

story.append(Paragraph("4.5 End-to-End Test Cases", h2))
story.append(Paragraph(
    "End-to-end tests verify the complete user journey. These are run manually or with "
    "a browser automation tool such as Selenium or Playwright.", body))
e2e_tests = [
    ["TC-E-01",
     "Farmer asks basic irrigation question",
     "1. Open http://localhost:3001. 2. Type: 'I farm rice in Thanjavur. It has been dry for 10 days. Should I irrigate?' 3. Press Send.",
     "Response appears within 5 seconds. Response contains a risk label, an irrigation recommendation, and at least one ICAR source citation. No error message shown.",
     "Pass"],
    ["TC-E-02",
     "Farmer asks about government schemes",
     "1. Open chatbot. 2. Type: 'What MSP support is available for paddy farmers in 2024?'",
     "Response includes mention of MSP or government scheme information. ICAR or scheme document cited as source.",
     "Pass"],
    ["TC-E-03",
     "Farmer asks about pest management",
     "1. Open chatbot. 2. Type: 'My rice crop has yellow leaves. What pest should I suspect?'",
     "Response mentions at least one probable cause (e.g. nitrogen deficiency, stem borer). Source document cited.",
     "Pass"],
    ["TC-E-04",
     "Frontend resilience to slow network",
     "1. Open chatbot with browser DevTools throttled to 'Slow 3G'. 2. Send a question.",
     "Loading indicator visible. Response eventually rendered correctly. No crash or blank screen.",
     "Pass"],
    ["TC-E-05",
     "Airflow DAG end-to-end pipeline",
     "1. Open Airflow UI at http://localhost:8081. 2. Enable and trigger data_merge_dag. 3. After success, trigger feature_engineering_dag. 4. After success, trigger model_training_dag. 5. Check MLflow at the run URL.",
     "All three DAGs complete with status 'success'. MLflow shows a new run with ROC-AUC logged. A new .joblib file is written to data/models/.",
     "Pass"],
    ["TC-E-06",
     "Grafana dashboard visible",
     "1. Open http://localhost:3000 (admin/admin). 2. Navigate to the Krishi Sahaya dashboard.",
     "Five panels visible: Services Health, DAG Metrics, Prediction Latency, Error Rate, Feature Drift. No 'No data' panels after at least one API call.",
     "Pass"],
]
e2e_data = [["ID", "Scenario", "Steps", "Expected Result", "Status"]] + e2e_tests
story.append(simple_table(e2e_data, [1.8*cm, 3*cm, 5*cm, 4.2*cm, 1.5*cm]))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 – USER MANUAL
# ═══════════════════════════════════════════════════════════════════════════════
story.append(Paragraph("5. User Manual", h1))
story.append(HR())
story.append(Paragraph(
    I("This section is written for farmers, agricultural officers, and any non-technical user "
      "who wants to use the Krishi Sahaya chatbot to get advice about their crops. "
      "No programming knowledge is required."), body))

story.append(Paragraph("5.1 Introduction – What is Krishi Sahaya?", h2))
story.append(Paragraph(
    "Krishi Sahaya (meaning 'Agricultural Helper' in Sanskrit) is a free, easy-to-use chatbot "
    "that helps farmers in Tamil Nadu make better decisions about their crops. You can ask it "
    "questions in plain English about:", body))
for item in [
    "Whether your crop is at risk of low yield this season",
    "When and how much to irrigate",
    "How to identify and control pests",
    "What government schemes and MSP rates apply to your crop",
    "General crop management advice from ICAR guidelines",
]:
    story.append(bul(item))
story.append(Paragraph(
    "The system uses weather data for your district, a machine learning model trained on years "
    "of Tamil Nadu crop records, and a library of official ICAR agricultural documents to give "
    "you grounded, relevant advice.", body))

story.append(Paragraph("5.2 Getting Started", h2))
story.append(Paragraph(
    "To use Krishi Sahaya, all you need is a computer or smartphone with a web browser "
    "(such as Google Chrome, Mozilla Firefox, or Microsoft Edge) connected to the internet "
    "or to your local network. No app download is required.", body))

story.append(Paragraph("Step 1 – Open the Chatbot", h3))
story.append(Paragraph(
    "Open your web browser and type the following address in the address bar at the top:", body))
for line in code_block("http://localhost:3001"):
    story.append(line)
story.append(Paragraph(
    "Press Enter. The Krishi Sahaya chatbot page will load. You will see a chat window with "
    "a text box at the bottom.", body))

story.append(Paragraph("Step 2 – Type Your Question", h3))
story.append(Paragraph(
    "Click inside the text box at the bottom of the screen. Type your question in English. "
    "Be as specific as possible. Here are some examples of good questions:", body))
examples = [
    '"I farm rice in Thanjavur. It has not rained for two weeks. Should I irrigate?"',
    '"My paddy crop has brown spots on the leaves near Madurai. What could it be?"',
    '"What is the MSP for cotton this season?"',
    '"When is the best time to apply fertiliser for sugarcane in Tiruchirapalli?"',
    '"My tomatoes in Coimbatore are not flowering well. What should I do?"',
]
for ex in examples:
    story.append(bul(ex))

story.append(Paragraph("Step 3 – Press Send", h3))
story.append(Paragraph(
    "After typing your question, press the Enter key on your keyboard or click the Send button "
    "(usually shown as an arrow icon). The chatbot will take a few seconds to think "
    "and then show its answer on the screen above your question.", body))

story.append(Paragraph("5.3 Understanding the Information the Chatbot Needs", h2))
story.append(Paragraph(
    "Krishi Sahaya gives better answers when you include the following details in your question:", body))
info_data = [
    ["Information", "Why it matters", "Example"],
    ["Your district",     "The system uses district-specific weather and crop data",    "'I am in Thanjavur district'"],
    ["Your crop",         "Different crops have different risk profiles and needs",      "'I grow rice' or 'I farm cotton'"],
    ["Recent weather",    "Helps the ML model estimate yield risk more accurately",     "'It has been dry for 10 days'"],
    ["Specific symptom",  "Helps the system find the most relevant ICAR document",      "'The leaves are turning yellow at the tips'"],
    ["Time of season",    "Advice differs between sowing, growing, and harvest stages", "'We are in the third month after sowing'"],
]
story.append(simple_table(info_data, [3.5*cm, 5*cm, 6.5*cm]))

story.append(Paragraph("5.4 Reading and Interpreting the Response", h2))
story.append(Paragraph(
    "Every response from Krishi Sahaya contains up to three parts:", body))

story.append(Paragraph("Part 1 – Yield Risk Assessment", h3))
story.append(Paragraph(
    "This section tells you how risky current conditions are for your crop's yield. "
    "The risk is shown as one of three labels:", body))
risk_data = [
    ["Label", "Meaning", "What you should do"],
    ["LOW RISK",    "Current weather and historical patterns suggest your crop should do well this season.", "Continue normal farming practices. Stay alert for pest activity."],
    ["MEDIUM RISK", "Some conditions are unfavourable. Your yield may be affected.",                        "Follow the chatbot's specific advice on irrigation, fertiliser, or pest control. Monitor your crop closely."],
    ["HIGH RISK",   "Conditions are significantly unfavourable. There is a real chance of reduced yield.",  "Take immediate action based on the chatbot's recommendation. Consider contacting your nearest Krishi Vigyan Kendra or agricultural officer."],
]
story.append(simple_table(risk_data, [2.8*cm, 5.5*cm, 6.7*cm]))

story.append(Paragraph("Part 2 – Recommendation", h3))
story.append(Paragraph(
    "This is the main advice section. It is written in plain English and is based on your "
    "question, your weather conditions, and official ICAR guidelines. Read this carefully "
    "and follow the steps described. The advice may include:", body))
for item in [
    "How often to irrigate and how much water to apply.",
    "Which fertiliser to use and when to apply it.",
    "Which pest or disease is likely causing a symptom and how to treat it.",
    "Information about a government scheme or MSP rate.",
]:
    story.append(bul(item))

story.append(Paragraph("Part 3 – Sources", h3))
story.append(Paragraph(
    "At the bottom of the response, you will see a list of source documents. These are the "
    "official ICAR guidebooks or government publications that the system used to form its advice. "
    "This tells you that the advice is not invented — it comes from tested, official knowledge. "
    "You can ask an agricultural officer to look up these documents if you want more detail.", body))

story.append(Paragraph("5.5 A Sample Conversation", h2))
story.append(Paragraph("The following example shows how a conversation might look:", body))

from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

# Define a proper wrapping style
table_text_style = ParagraphStyle(
    "table_text",
    fontSize=9,
    leading=12,
    alignment=TA_LEFT,
    wordWrap='CJK'   # 🔹 ensures proper wrapping
)

data = [
    ["", "Text"],
    [
        "You type:",
        Paragraph(
            "I farm rice in Thanjavur. It has been dry for 8 days and temperature is around 32 degrees. Should I irrigate now?",
            table_text_style
        )
    ],
    [
        "Krishi Sahaya responds:",
        Paragraph(
            "Yield Risk: MEDIUM RISK (confidence: 78%)<br/><br/>"
            "Recommendation:Based on current conditions in Thanjavur, rice under moderate moisture stress at 32°C "
            "requires attention. Irrigate now to bring soil moisture back to field capacity. Apply 5 cm of water "
            "if using flood irrigation. For drip-irrigated fields, run for 4 to 6 hours depending on soil type. "
            "Avoid irrigating during the hottest part of the day; early morning is preferred. Monitor for stem borer "
            "activity, which increases under water-stressed conditions.\n\n" 
            "Sources: ICAR Irrigation Guide 2023, ICAR Pest Management – Tamil Nadu",
            table_text_style
        )
    ]
]

table = Table(
    data,
    colWidths=[4*cm, 12*cm]   # 🔹 force proper wrapping width
)

table.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), colors.grey),
    ("TEXTCOLOR", (0,0), (-1,0), colors.white),

    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ALIGN", (0,0), (0,-1), "LEFT"),

    ("BOX", (0,0), (-1,-1), 0.8, colors.black),
    ("INNERGRID", (0,0), (-1,-1), 0.3, colors.grey),

    ("LEFTPADDING", (0,0), (-1,-1), 6),
    ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ("TOPPADDING", (0,0), (-1,-1), 4),
    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(table)
story.append(Paragraph("5.6 Tips for Getting the Best Answers", h2))
tips = [
    "Always mention your district by name. For example, write 'in Thanjavur' rather than just 'in my area'.",
    "Mention your crop clearly. Write 'my rice crop' or 'my cotton fields' rather than just 'my crop'.",
    "Describe symptoms precisely. Instead of 'my plants look sick', write 'the leaves are turning yellow at the tips with brown edges'.",
    "One question at a time gives clearer answers. If you have multiple issues, ask about each one separately.",
    "If the answer mentions a term you do not know, type 'What does [term] mean?' and the chatbot will explain it.",
    "The chatbot's advice is based on patterns in historical data. For urgent or unusual situations, always confirm with a Krishi Vigyan Kendra or qualified agronomist.",
]
for i, tip in enumerate(tips, 1):
    story.append(num(i, tip))

story.append(Paragraph("5.7 Common Questions", h2))
faqs = [
    ("Is Krishi Sahaya free to use?",
     "Yes. The chatbot is completely free for all farmers."),
    ("Can I use it in Tamil?",
     "The current version is designed for English questions. Tamil language support is planned for a future version."),
    ("How accurate is the yield risk prediction?",
     "The model has an ROC-AUC score of 87%, which means it correctly ranks risk levels in roughly 87 out of 100 cases. "
     "It is a useful guide but should not replace direct observation of your fields or advice from an agricultural officer."),
    ("What if I do not know the exact temperature or humidity?",
     "Give your best estimate. Even approximate values improve the prediction compared to leaving them out. "
     "You can find weather information for your district on weather apps or by calling your local Meteorological Department."),
    ("Will the system remember my previous questions?",
     "Each session starts fresh. If you want to continue from a previous question, briefly summarise the context again in your new message."),
    ("What if the chatbot gives wrong advice?",
     "No automated system is perfect. Always use the chatbot's advice as a starting point and verify with your "
     "local agricultural department or Krishi Vigyan Kendra before making large decisions like changing your irrigation "
     "schedule or applying a new pesticide."),
    ("Can I access it on my phone?",
     "Yes. The chatbot works in any modern smartphone browser. Open your browser, type the address, "
     "and the page will adjust to fit your screen automatically."),
    ("What are the ICAR sources mentioned in the response?",
     "ICAR stands for the Indian Council of Agricultural Research. These are official Indian government research "
     "organisations that publish guidelines on farming practices. When Krishi Sahaya cites an ICAR source, "
     "the advice comes directly from tested, peer-reviewed agricultural knowledge."),
]
for q, a in faqs:
    story.append(KeepTogether([
        Paragraph(B(q), body_left),
        Paragraph(a, body),
        Spacer(1, 3),
    ]))

story.append(Paragraph("5.8 Contacting Support", h2))
story.append(Paragraph(
    "If you encounter a technical problem with the system (for example, the page does not load "
    "or you receive an error message), please contact the project maintainer:", body))
for line in code_block("GitHub Issues : https://github.com/Anumita-P/mlops_endterm_project/issues\nEmail         : anumitap@example.com"):
    story.append(line)
story.append(Paragraph(
    "For agricultural advice beyond what the chatbot provides, contact your nearest "
    "Krishi Vigyan Kendra (KVK) or the Tamil Nadu Agricultural University (TNAU) extension services.", body))

story.append(Spacer(1, 1*cm))
story.append(HR())
story.append(Paragraph(
    "End of Report — Krishi Sahaya Technical Documentation, Version 1.0.0, April 2026",
    S("Normal", fontSize=9, alignment=TA_CENTER, textColor=DARK, fontName="Helvetica-Oblique")))

# ── Build ─────────────────────────────────────────────────────────────────────
import os

os.makedirs("outputs", exist_ok=True)

output_path = "outputs/Krishi_Sahaya_Final_Report.pdf"

doc = SimpleDocTemplate(
    output_path,
    pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=2.2*cm, bottomMargin=2.8*cm,
    title="Krishi Sahaya – Technical Report",
    author="Anumita",
)
doc.build(story, canvasmaker=NumberedCanvas)
print(f"PDF written to {output_path}")