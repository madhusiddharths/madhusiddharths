#!/usr/bin/env python3
"""Render the profile README's panels in the portfolio's agent-console theme.

The portfolio (Next.js, ~/Documents/webstorm/version_2) is the source of truth
for look and content. This script reads its fonts, thumbnails, tech icons and
certificate badges, and writes self-contained SVGs to assets/agent/:

  * fonts are the site's own IBM Plex Sans + JetBrains Mono, instanced per
    weight and subset to the exact characters each SVG uses (GitHub renders
    README SVGs as <img>, so nothing can load from the network)
  * text is laid out with the real glyph advances, so wrapping matches

Usage:  python3 scripts/build_assets.py [--portfolio PATH]
The portfolio must have been built once (`npm run build`) so its fonts exist
in .next/static/media.
"""
from __future__ import annotations

import argparse
import base64
import io
import re
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "agent"

# --------------------------------------------------------------------------
# tokens — copied from app/console.css (.ag-skin) and components/agent/engine.ts
# --------------------------------------------------------------------------
BG0, BG1, PANEL, PANEL2 = "#0a0a0a", "#0e0e0e", "#111111", "#171717"
LINE, LINE2, RULE = "#1a1a1a", "#262626", "#222222"
INK, HI, MUTED, FAINT = "#ececec", "#ffffff", "#a0a0a0", "#6f6f6f"
RED, RED_INK, OK, STR = "#ff4133", "#ff6a5e", "#5fd38d", "#d9c08a"
AGENT = {
    "planner": "#c8ff4d", "planner2": "#8fe36a", "coder": "#4de1ff", "coder2": "#6f9bff",
    "coder3": "#3fd0c0", "stylist": "#ff6bd6", "stylist2": "#ff8f9f", "sizer": "#a78bff",
    "aligner": "#5dffc4", "critic": "#ffb547", "critic2": "#ffd56b",
}
W = 900  # every panel shares one width so the README reads as one page
PAD = 28
SITE = "https://www.madhusiddharths.com"

FALLBACK = {
    "s": "'IBM Plex Sans',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif",
    "m": "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace",
}

# --------------------------------------------------------------------------
# content — mirrors lib/projects.ts and app/page.tsx of the portfolio
# --------------------------------------------------------------------------
PROFILE = dict(
    name="Madhu Siddharth Suthagar",
    role="AI Engineer",
    bio="I'm an AI engineer who cares less about demos and more about the moment a system has to work on its own. Right now that means teaching a video-QA model to run on an 18 GB laptop, lifting it from 54.7% to 73.5%. Before that, I distilled a 550B model's tool-calling into a 3B student to find exactly where small agents break, used LLMs to map 18,000 untapped sales sites from government compliance data, and published a federated intrusion-detection paper at IEEE. I enjoy taking a manual, multi-step process, turning it into an AI-driven workflow, and measuring honestly where it holds up and where it needs a human in the loop.",
    email="madhusiddharths1@outlook.com",
)
TOOLS = ["LangGraph", "MCP", "Claude", "vLLM", "PyTorch", "Hugging Face", "FastAPI", "Docker"]
FOCUS = ["agent_orchestration", "tool_integration", "fine_tuning", "evaluation", "deployment"]
METRICS = [
    ("550B → 3B", "teacher distilled into tool-calling agents"),
    ("73.5%", "video QA accuracy, up from 54.7%"),
    ("26K+", "sites enriched with LLMs"),
    ("1.8B+", "Gaia DR3 sources processed"),
]
RUNS = [
    dict(org="Parsec", role="AI Engineering Intern", when="Oct 2026 — present", where="Remote", status="running",
         task="Own the video track of OpenJev — an open-source model that scores answer options in one forward pass, running locally on an 18 GB laptop.",
         out=[("video QA · dev split", "54.7% → 73.5%"), ("LoRA training set", "7,392 Qs · 1,955 videos"), ("memory budget", "64 frames in 18 GB")],
         tools=["MLX", "LoRA", "Gemma 4 E4B", "PyTorch", "FastAPI"]),
    dict(org="Labelmaster", role="Data Science Co-op", when="Jan — May 2026", where="Chicago, IL", status="completed",
         task="White-space analysis: pulled sites from 9 government compliance databases and enriched them with LLMs to surface prospects that had never bought.",
         out=[("sites mapped", "26,290 · 178 families"), ("white space", "17,999 zero-sales sites"), ("LLM enrichment", "12 attrs · mean conf 0.81")],
         tools=["Gemini API", "Perplexity", "SciPy", "Placekey", "Python"]),
]
CKPTS = [
    dict(tag="fine-tune", degree="M.S. Data Science", school="Illinois Institute of Technology", where="Chicago, IL", when="May 2026", gpa="3.77"),
    dict(tag="pretrain", degree="B.Tech Information Technology", school="Coimbatore Institute of Technology", where="Coimbatore, India", when="Apr 2024", gpa="3.66 · 8.91/10"),
]
PROJECTS = [
    dict(slug="tool-router-ladder", i="01", name="Tool Router Ladder", domain="LLM post-training · Agent evaluation", thumb="tool_router.png",
         summary="How small can a tool router go? A research build that distils a 550B teacher's tool-calling into Qwen2.5 0.5B–3B LoRA students on τ²-bench retail, then measures where multi-step agent reliability breaks — across 16/40/80-tool catalogs, SFT vs DPO vs GRPO, and a log-prob confidence router that escalates hard steps back to the teacher.",
         tech=["PyTorch", "Hugging Face", "vLLM", "LangGraph", "LangChain", "OpenAI API", "OpenRouter", "Weights & Biases", "Docker", "Python", "LLM Fine-tuning", "Agentic AI"],
         results=[("73% → 7.7%", "step agreement vs task success, 1.5B student"), ("48%", "task success of the 550B teacher"), ("0.797", "AUROC of the confidence router"), ("GRPO > DPO", "step-level GRPO improved every catalog")]),
    dict(slug="pulsetrade", i="02", name="PulseTrade", domain="Real-time streaming · Agentic AI", thumb="pulsetrade.png",
         summary="Real-time financial intelligence platform that streams market data through Kafka and Delta Lake, then uses an agentic AI investigator to explain anomalies in plain language.",
         tech=["Apache Kafka", "Apache Airflow", "Databricks", "Kubernetes", "FastAPI", "PostgreSQL", "Python", "LangGraph", "MCP", "Gemini API", "Hugging Face", "Agentic AI"]),
    dict(slug="ai-counselling", i="03", name="AI-counselling", domain="Multimodal AI · Wellbeing", thumb="ai_chatbot.png",
         summary="A counselling assistant that grounds its replies in the DSM-5 through retrieval, reads tone of voice and facial emotion alongside the words, and keeps long-term memory, with a safety-routing layer in front of the model.",
         tech=["FastAPI", "GCP", "MongoDB", "TypeScript", "Docker", "Node.js", "Python", "Gemini API", "Hugging Face"]),
    dict(slug="alzheimers", i="04", name="Alzheimer's Progression", domain="Medical imaging · GANs", thumb="alzheimers.jpg",
         summary="Stages an Alzheimer's MRI slice with a fine-tuned EfficientNetB4 (~98% accuracy), then chains three stage-transition DCGANs to synthesize how that brain is likely to look as the disease advances.",
         tech=["PyTorch", "Pandas", "Matplotlib", "OpenCV", "Docker", "MLflow", "Flask", "Python"]),
    dict(slug="galaxy", i="05", name="Galaxy Explorer", domain="3D visualization · 557M+ stars", thumb="stars.jpg",
         summary="A cloud-native 3D visualization platform that dynamically queries and renders 557M+ Gaia DR3 stars with real-time kinematic projection using serverless BigQuery and GPU acceleration.",
         tech=["Polars", "Apache Spark", "FastAPI", "Three.js", "GCP", "Docker", "Python", "JavaScript"]),
    dict(slug="growth-retention", i="06", name="Growth & Retention", domain="Experimentation · 20M+ events", thumb="growth_retention.png",
         summary="An end-to-end data pipeline and machine learning system that processes 20M+ e-commerce events to validate A/B tests and predict cart abandonment in real-time.",
         tech=["Python", "dbt", "FastAPI", "Streamlit", "Docker", "SQL"]),
    dict(slug="crypto-tweet-impact", i="07", name="Crypto Tweet Impact", domain="Event study · NLP", thumb="crypto.png",
         summary="A statistically rigorous data-science pipeline and event study that evaluates the market impact of ~20,000 LLM-classified tweets on Bitcoin and Dogecoin prices using multiple-testing corrections and an interactive Shiny dashboard.",
         tech=["R", "OpenAI API"]),
]
# the rest of the index, as ledger rows (index, name, domain, link label, url)
MORE = [
    ("08", "Federated IoT Security", "IEEE ICAIC 2026 · first author", "paper", "https://ieeexplore.ieee.org/document/11395795", "federated-iot"),
    ("09", "Online Retail", "Analytics engineering · Cloud DW", "report", None, "online-retail"),
    ("10", "Image Retrieval", "Vector search · Computer vision", "report", None, "image-retrieval"),
    ("11", "Traffic Prediction", "Fleet routing · 50-stop VRP", "report", None, "traffic-prediction"),
    ("12", "SATURDAE", "Spatial design · Patented", "report", None, "saturdae"),
    ("13", "Hotspot", "Geospatial health · Exposure modeling", "report", None, "hotspot"),
]
# tool registry — `calls` = projects in the portfolio using each tool (computed from lib/projects.ts)
REGISTRY = {
    "languages_query": ("Languages & Query", [("Python", 12), ("R", 1), ("SQL", 2), ("PostgreSQL", 1), ("JavaScript", 1)]),
    "ai_engineering_agents": ("AI Engineering & Agents", [("Agentic AI", 2), ("LangGraph", 2), ("LangChain", 1), ("MCP", 1), ("LLM APIs", 4), ("OpenRouter", 1), ("Ollama", 0), ("Hugging Face", 3), ("vLLM", 1), ("Weights & Biases", 1), ("MLflow", 1), ("LLM Fine-tuning", 1)]),
    "ml_data_science": ("ML / Data Science", [("Pandas", 5), ("NumPy", 2), ("PyTorch", 4), ("TensorFlow", 0), ("scikit-learn", 1), ("Matplotlib", 2), ("Plotly", 1), ("OpenCV", 1), ("NLP", 0), ("Time Series Analysis", 0)]),
    "data_cloud_infra": ("Data & Cloud Infra", [("Apache Airflow", 1), ("Apache Kafka", 1), ("Apache Spark", 1), ("Docker", 6), ("GCP", 3), ("AWS", 0), ("Snowflake", 1), ("Databricks", 1)]),
    "serving_bi": ("Serving & BI", [("FastAPI", 4), ("Streamlit", 3), ("Tableau", 0), ("Power BI", 0)]),
    "top_calls": ("Most called", [("Python", 12), ("Docker", 6), ("Pandas", 5), ("LLM APIs", 4), ("PyTorch", 4), ("FastAPI", 4)]),
}
REG_COLUMNS = [["languages_query", "data_cloud_infra"], ["ai_engineering_agents", "top_calls"], ["ml_data_science", "serving_bi"]]
CERTS = [
    ("IBM Machine Learning Specialist — Advanced", "IBM", "Aug 2025", "ibm-machine-learning-specialist-advanced.png"),
    ("IBM Data Science Professional Certificate", "IBM", "Apr 2023", "ibm-data-science-professional-certificate.png"),
    ("AWS Certified Cloud Practitioner", "Amazon Web Services", "Jun 2025", "aws-certified-cloud-practitioner.png"),
    ("Google Data Analytics Professional Certificate", "Google", "May 2022", "google_data_analytics.png"),
]
ICONS = {
    "Python": "Python", "R": "R", "SQL": "MySQL", "PostgreSQL": "PostgresSQL", "JavaScript": "JavaScript",
    "TypeScript": "TypeScript", "Pandas": "Pandas", "NumPy": "NumPy", "Matplotlib": "Matplotlib", "Plotly": "Ploty",
    "PyTorch": "PyTorch", "TensorFlow": "TensorFlow", "scikit-learn": "scikit-learn", "OpenCV": "OpenCV",
    "LangChain": "langchain", "LangGraph": "LangGraph", "MCP": "MCP-mono", "Hugging Face": "HuggingFace",
    "vLLM": "vLLM", "OpenAI API": "OpenAI-mono", "Claude": "Claude", "Gemini API": "Gemini", "Ollama": "Ollama-mono",
    "Weights & Biases": "WandB", "Docker": "Docker", "Kubernetes": "Kubernetes", "Apache Airflow": "Apache Airflow",
    "Apache Kafka": "Apache Kafka", "Apache Spark": "Apache Spark", "GCP": "Google Cloud", "AWS": "AWS",
    "Snowflake": "snowflake-color", "Databricks": "azure-databricks", "Polars": "Polars", "dbt": "Dbt",
    "MongoDB": "MongoDB", "Node.js": "Node.js", "FastAPI": "FastAPI", "Flask": "Flask", "Streamlit": "Streamlit",
    "Three.js": "Three.js", "Tableau": "tableau", "Power BI": "power-bi-embedded",
}
ICON_PATHS = {  # components/icons.tsx
    "github": ("0 0 64 64", "M32,6c-14.359,0 -26,11.641 -26,26c0,12.277 8.512,22.56 19.955,25.286c-0.592,-0.141 -1.179,-0.299 -1.755,-0.479v-5.957c0,0 -0.975,0.325 -2.275,0.325c-3.637,0 -5.148,-3.245 -5.525,-4.875c-0.229,-0.993 -0.827,-1.934 -1.469,-2.509c-0.767,-0.684 -1.126,-0.686 -1.131,-0.92c-0.01,-0.491 0.658,-0.471 0.975,-0.471c1.625,0 2.857,1.729 3.429,2.623c1.417,2.207 2.938,2.577 3.721,2.577c0.975,0 1.817,-0.146 2.397,-0.426c0.268,-1.888 1.108,-3.57 2.478,-4.774c-6.097,-1.219 -10.4,-4.716 -10.4,-10.4c0,-2.928 1.175,-5.619 3.133,-7.792c-0.2,-0.567 -0.533,-1.714 -0.533,-3.583c0,-1.235 0.086,-2.751 0.65,-4.225c0,0 3.708,0.026 7.205,3.338c1.614,-0.47 3.341,-0.738 5.145,-0.738c1.804,0 3.531,0.268 5.145,0.738c3.497,-3.312 7.205,-3.338 7.205,-3.338c0.567,1.474 0.65,2.99 0.65,4.225c0,2.015 -0.268,3.19 -0.432,3.697c1.898,2.153 3.032,4.802 3.032,7.678c0,5.684 -4.303,9.181 -10.4,10.4c1.628,1.43 2.6,3.513 2.6,5.85v8.557c-0.576,0.181 -1.162,0.338 -1.755,0.479c11.443,-2.726 19.955,-13.009 19.955,-25.286c0,-14.359 -11.641,-26 -26,-26z"),
    "linkedin": ("0 0 50 50", "M9,4c-2.74952,0 -5,2.25048 -5,5v32c0,2.74952 2.25048,5 5,5h32c2.74952,0 5,-2.25048 5,-5v-32c0,-2.74952 -2.25048,-5 -5,-5zM9,6h32c1.66848,0 3,1.33152 3,3v32c0,1.66848 -1.33152,3 -3,3h-32c-1.66848,0 -3,-1.33152 -3,-3v-32c0,-1.66848 1.33152,-3 3,-3zM14,11.01172c-1.09522,0 -2.08078,0.32736 -2.81055,0.94141c-0.72977,0.61405 -1.17773,1.53139 -1.17773,2.51367c0,1.86718 1.61957,3.32281 3.67969,3.4668c0.0013,0.00065 0.0026,0.0013 0.00391,0.00195c0.09817,0.03346 0.20099,0.05126 0.30469,0.05273c2.27301,0 3.98828,-1.5922 3.98828,-3.52148c-0.00018,-0.01759 -0.00083,-0.03518 -0.00195,-0.05274c-0.10175,-1.90023 -1.79589,-3.40234 -3.98633,-3.40234zM11,19c-0.55226,0.00006 -0.99994,0.44774 -1,1v19c0.00006,0.55226 0.44774,0.99994 1,1h6c0.55226,-0.00006 0.99994,-0.44774 1,-1v-19c-0.00006,-0.55226 -0.44774,-0.99994 -1,-1zM20,19c-0.55226,0.00006 -0.99994,0.44774 -1,1v19c0.00006,0.55226 0.44774,0.99994 1,1h6c0.55226,-0.00006 0.99994,-0.44774 1,-1v-10c0,-0.82967 0.22639,-1.65497 0.625,-2.19531c0.39861,-0.54035 0.90147,-0.86463 1.85742,-0.84766c0.98574,0.01695 1.50758,0.35464 1.90234,0.88477c0.39477,0.53013 0.61523,1.32487 0.61523,2.1582v10c0.00006,0.55226 0.44774,0.99994 1,1h6c0.55226,-0.00006 0.99994,-0.44774 1,-1v-10.73828c0,-2.96154 -0.87721,-5.30739 -2.38086,-6.89453c-1.50365,-1.58714 -3.59497,-2.36719 -5.80664,-2.36719c-2.10202,0 -3.70165,0.70489 -4.8125,1.42383v-0.42383c-0.00006,-0.55226 -0.44774,-0.99994 -1,-1z"),
    "discord": ("0 -28.5 256 256", "M216.856339,16.5966031 C200.285002,8.84328665 182.566144,3.2084988 164.041564,0 C161.766523,4.11318106 159.108624,9.64549908 157.276099,14.0464379 C137.583995,11.0849896 118.072967,11.0849896 98.7430163,14.0464379 C96.9108417,9.64549908 94.1925838,4.11318106 91.8971895,0 C73.3526068,3.2084988 55.6133949,8.86399117 39.0420583,16.6376612 C5.61752293,67.146514 -3.4433191,116.400813 1.08711069,164.955721 C23.2560196,181.510915 44.7403634,191.567697 65.8621325,198.148576 C71.0772151,190.971126 75.7283628,183.341335 79.7352139,175.300261 C72.104019,172.400575 64.7949724,168.822202 57.8887866,164.667963 C59.7209612,163.310589 61.5131304,161.891452 63.2445898,160.431257 C105.36741,180.133187 151.134928,180.133187 192.754523,160.431257 C194.506336,161.891452 196.298154,163.310589 198.110326,164.667963 C191.183787,168.842556 183.854737,172.420929 176.223542,175.320965 C180.230393,183.341335 184.861538,190.991831 190.096624,198.16893 C211.238746,191.588051 232.743023,181.531619 254.911949,164.955721 C260.227747,108.668201 245.831087,59.8662432 216.856339,16.5966031 Z M85.4738752,135.09489 C72.8290281,135.09489 62.4592217,123.290155 62.4592217,108.914901 C62.4592217,94.5396472 72.607595,82.7145587 85.4738752,82.7145587 C98.3405064,82.7145587 108.709962,94.5189427 108.488529,108.914901 C108.508531,123.290155 98.3405064,135.09489 85.4738752,135.09489 Z M170.525237,135.09489 C157.88039,135.09489 147.510584,123.290155 147.510584,108.914901 C147.510584,94.5396472 157.658606,82.7145587 170.525237,82.7145587 C183.391518,82.7145587 193.761324,94.5189427 193.539891,108.914901 C193.539891,123.290155 183.391518,135.09489 170.525237,135.09489 Z"),
    "mail": ("0 0 24 24", "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2zm0 2v.4l8 5 8-5V6H4zm16 2.7-7.47 4.67a1 1 0 0 1-1.06 0L4 8.7V18h16V8.7z"),
}


# --------------------------------------------------------------------------
# fonts
# --------------------------------------------------------------------------
class Face:
    """One weight of a variable font: measures text and emits a subset @font-face."""

    def __init__(self, family_key: str, path: Path, weight: int):
        self.key = f"{family_key}{weight}"
        self.family = family_key
        font = TTFont(path)
        if "fvar" in font:
            axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
            axes["wght"] = weight
            font = instancer.instantiateVariableFont(font, axes)
        self.font = font
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.hmtx = font["hmtx"].metrics
        self._fallback = self.hmtx[self.cmap[ord("n")]][0]

    def width(self, text: str, size: float) -> float:
        adv = 0
        for ch in text:
            g = self.cmap.get(ord(ch))
            adv += self.hmtx[g][0] if g else self._fallback
        return adv * size / self.upm

    def has(self, ch: str) -> bool:
        return ord(ch) in self.cmap

    def css(self, chars: set[str]) -> str:
        buf = io.BytesIO()
        self.font.save(buf)
        font = TTFont(io.BytesIO(buf.getvalue()))
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga", "calt"]
        opts.name_IDs = []
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(c for c in chars if self.has(c))) or " ")
        sub.subset(font)
        out = io.BytesIO()
        font.flavor = "woff2"
        font.save(out)
        data = base64.b64encode(out.getvalue()).decode()
        return f"@font-face{{font-family:'{self.key}';src:url(data:font/woff2;base64,{data}) format('woff2');}}"


FACES: dict[str, Face] = {}


def load_fonts(portfolio: Path) -> None:
    media = portfolio / ".next" / "static" / "media"
    best: dict[str, tuple[int, Path]] = {}
    for f in media.glob("*.woff2"):
        name = TTFont(f)["name"].getDebugName(1) or ""
        glyphs = len(TTFont(f).getGlyphOrder())
        for fam, key in (("IBM Plex Sans", "s"), ("JetBrains Mono", "m")):
            # the latin subset is the preloaded (.p.) file
            if name.startswith(fam) and ".p." in f.name and glyphs > best.get(key, (0, f))[0]:
                best[key] = (glyphs, f)
    if set(best) != {"s", "m"}:
        raise SystemExit(f"fonts not found in {media} — run `npm run build` in the portfolio first")
    for key, weights in (("s", (400, 500, 600)), ("m", (400, 500, 600))):
        for w in weights:
            FACES[f"{key}{w}"] = Face(key, best[key][1], w)


# --------------------------------------------------------------------------
# SVG canvas
# --------------------------------------------------------------------------
PING = '<animate attributeName="r" values="3;9" dur="1.8s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.9;0" dur="1.8s" repeatCount="indefinite"/>'


def esc(s: str) -> str:
    return escape(s, {'"': "&quot;"})


class SVG:
    def __init__(self, w: float, h: float, title: str):
        self.w, self.h, self.title = w, h, title
        self.parts: list[str] = []
        self.defs: list[str] = []
        self.css: list[str] = []
        self.used: dict[str, set[str]] = defaultdict(set)

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, face="s400", size=14, fill=INK, anchor="start", ls=0.0, extra="") -> float:
        """Draw one run; returns its advance width."""
        f = FACES[face]
        lead = len(s) - len(s.lstrip(" "))
        if lead and anchor == "start":
            x += f.width(" " * lead, size) + ls * lead
            total = self.text(x, y, s[lead:], face, size, fill, anchor, ls, extra)
            return total + f.width(" " * lead, size) + ls * lead
        self.used[face].update(s)
        attrs = f'x="{x:.1f}" y="{y:.1f}" font-family="{f.key},{FALLBACK[f.family]}" font-size="{size}" fill="{fill}"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if ls:
            attrs += f' letter-spacing="{ls}"'
        self.add(f"<text {attrs} {extra}>{esc(s)}</text>")
        return f.width(s, size) + ls * len(s)

    def runs(self, x, y, spans, size=14) -> float:
        """Inline runs: [(text, face, fill)], laid out left to right."""
        cx = x
        for t, face, fill in spans:
            cx += self.text(cx, y, t, face, size, fill)
        return cx - x

    def para(self, x, y, s, maxw, face="s400", size=14, fill=MUTED, lh=None, max_lines=None) -> float:
        """Wrapped paragraph; returns the y just below the last baseline."""
        lh = lh or size * 1.6
        lines = wrap(s, face, size, maxw)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while FACES[face].width(last + "…", size) > maxw and " " in last:
                last = last.rsplit(" ", 1)[0]
            lines[-1] = last.rstrip(",;:—– ") + "…"
        for i, line in enumerate(lines):
            self.text(x, y + i * lh, line, face, size, fill)
        return y + (len(lines) - 1) * lh

    def rect(self, x, y, w, h, fill="none", stroke=None, rx=3, extra="") -> None:
        s = f' stroke="{stroke}" stroke-width="1"' if stroke else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{s} {extra}/>')

    def line(self, x1, y1, x2, y2, stroke=RULE, extra="") -> None:
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="1" {extra}/>')

    def icon(self, name, x, y, size, fill=INK) -> None:
        vb, d = ICON_PATHS[name]
        self.add(f'<svg x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" viewBox="{vb}"><path d="{d}" fill="{fill}"/></svg>')

    def image(self, x, y, w, h, data_uri, extra="", fit="slice") -> None:
        self.add(f'<image x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" href="{data_uri}" preserveAspectRatio="xMidYMid {fit}" {extra}/>')

    def frame(self, grid=True) -> None:
        """Outer window: graphite page, faint layout grid, hairline border."""
        if grid:
            self.defs.append(
                f'<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
                f'<path d="M40 0H0V40" fill="none" stroke="#ffffff" stroke-opacity="0.035" stroke-width="1"/></pattern>'
            )
        self.parts.insert(0, f'<rect width="{self.w}" height="{self.h}" rx="6" fill="{BG0}"/>')
        if grid:
            self.parts.insert(1, f'<rect width="{self.w}" height="{self.h}" rx="6" fill="url(#grid)"/>')
        self.add(f'<rect x="0.5" y="0.5" width="{self.w - 1}" height="{self.h - 1}" rx="6" fill="none" stroke="{LINE2}"/>')

    def save(self, name: str) -> None:
        fonts = "".join(FACES[k].css(ch) for k, ch in sorted(self.used.items()))
        style = f"<style>{fonts}{''.join(self.css)}</style>"
        body = "".join(self.parts)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w:.0f}" height="{self.h:.0f}" '
            f'viewBox="0 0 {self.w:.0f} {self.h:.0f}" xml:space="preserve" role="img" aria-label="{esc(self.title)}">'
            f"<title>{esc(self.title)}</title>{style}<defs>{''.join(self.defs)}</defs>{body}</svg>"
        )
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"  {name:28s} {len(svg) / 1024:7.1f} KB")


def wrap(s: str, face: str, size: float, maxw: float) -> list[str]:
    words, lines, cur = s.split(" "), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if FACES[face].width(trial, size) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------
PORTFOLIO: Path = Path()


def data_uri(img: Image.Image, fmt="JPEG", quality=80) -> str:
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        mime = "image/jpeg"
    else:
        img.save(buf, "PNG", optimize=True)
        mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


def thumb(name: str, w: int, h: int) -> str:
    """Card thumbnail in colour; grayscale/brightness come from the animated SVG filter (hover_glow)."""
    img = Image.open(PORTFOLIO / "public/img/project_img" / name).convert("RGB")
    img = ImageOps.fit(img, (w * 2, h * 2), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    return data_uri(img, quality=72)


_icon_cache: dict[str, str | None] = {}


def tech_icon(name: str) -> str | None:
    if name not in _icon_cache:
        file = ICONS.get(name)
        path = PORTFOLIO / "public/img/color_images" / f"{file}.png" if file else None
        if path and path.exists():
            img = Image.open(path).convert("RGBA")
            img.thumbnail((36, 36), Image.LANCZOS)
            # near-black logos (MCP, Kafka, AWS…) vanish on graphite: invert them, like the site's mono icons
            px = [(r, g, b) for r, g, b, a in img.getdata() if a > 128]
            luma = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / max(len(px), 1)
            if file.endswith("-mono") or luma < 70:
                r, g, b, a = img.split()
                img = Image.merge("RGBA", (*(ImageOps.invert(c) for c in (r, g, b)), a))
            _icon_cache[name] = data_uri(img, "PNG")
        else:
            _icon_cache[name] = None
    return _icon_cache[name]


def badge(file: str) -> str:
    img = Image.open(PORTFOLIO / "public/img/certification" / file).convert("RGBA")
    img.thumbnail((112, 112), Image.LANCZOS)
    return data_uri(img, "PNG")


# --------------------------------------------------------------------------
# shared pieces
# --------------------------------------------------------------------------
def chip(svg: SVG, x, y, label, icon: str | None = None, size=11, h=22, fill=PANEL2, color=MUTED, face="m400") -> float:
    """A mono tag; returns its width."""
    pad = 8
    iw = 14 if icon else 0
    w = FACES[face].width(label, size) + pad * 2 + (iw + 5 if icon else 0)
    svg.rect(x, y, w, h, fill=fill, stroke=LINE2)
    tx = x + pad
    if icon:
        uri = tech_icon(icon)
        if uri:
            svg.image(tx, y + (h - iw) / 2, iw, iw, uri, fit="meet")
        tx += iw + 5
    svg.text(tx, y + h / 2 + size * 0.36, label, face, size, color)
    return w


def sec_head(svg: SVG, y, n, sec, eyebrow, title, lead=None) -> float:
    """Ruled console header: hairline + red tick, shell line, eyebrow, title, lead."""
    x = PAD
    svg.line(x, y, W - PAD, y, LINE2)
    svg.add(f'<rect x="{x}" y="{y - 0.5}" width="40" height="1.5" fill="{RED}"/>')
    svg.runs(x, y + 30, [("madhu@agent", "m400", FAINT), (":", "m400", FAINT), ("~$ ", "m400", FAINT),
                         (f"cat {sec}.md", "m400", MUTED), (f"  # {n}/05", "m400", FAINT)], size=11.5)
    svg.text(x, y + 66, eyebrow.lower(), "m500", 11.5, RED_INK, ls=0.2)
    svg.text(x, y + 106, title, "s600", 36, HI, ls=-0.9)
    bottom = y + 106
    if lead:
        bottom = svg.para(x, y + 142, lead, 640, "s400", 15, MUTED, lh=24)
    return bottom


def agent_cursor(svg: SVG, name, color, path, dur=9, begin=0) -> None:
    """A labelled agent cursor gliding along `path` (the site's swarm cursors)."""
    lw = FACES["m500"].width(name, 10) + 12
    svg.used["m500"].update(name)
    f = FACES["m500"]
    svg.add(
        f'<g opacity="0"><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.1;0.85;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
        f'<animateMotion path="{path}" dur="{dur}s" begin="{begin}s" repeatCount="indefinite" calcMode="spline" keyTimes="0;1" keySplines="0.16 1 0.3 1"/>'
        f'<path d="M1.5 1.5 L16 9.2 L9.4 10.9 L6.2 17.6 Z" fill="{color}" stroke="#050507" stroke-width="1.4" stroke-linejoin="round"/>'
        f'<rect x="14" y="16" width="{lw:.1f}" height="17" rx="3" fill="{color}"/>'
        f'<text x="20" y="28" font-family="{f.key},{FALLBACK["m"]}" font-size="10" fill="#0a0a0a">{esc(name)}</text></g>'
    )


# --------------------------------------------------------------------------
# panels
# --------------------------------------------------------------------------
WIRE, WIRE_LINE = "#4de1ff", "rgba(77,225,255,0.55)"


class Swarm:
    """Replays the portfolio's build on load: Planners frame every block as a
    cyan wireframe, Coders write each block in (a left-to-right reveal) while
    their cursors hop between blocks, then the page settles to its static
    render. SMIL only, so it runs inside GitHub's <img>; it plays once per
    page load and freezes on the finished page."""

    PLAN0, PLAN_STEP = 0.25, 0.09     # planners frame blocks
    FILL0, FILL_STEP = 1.9, 0.38      # coders write blocks
    WRITE = 0.55                      # seconds a reveal takes
    SLACK = 140                       # the reveal runs past the wire box so long lines never clip
    CODERS = [("Coder·1", AGENT["coder"]), ("Coder·2", AGENT["coder2"]), ("Coder·3", AGENT["coder3"])]
    PLANNER = ("Planner·1", AGENT["planner"])

    def __init__(self, svg: SVG):
        self.svg = svg
        self.blocks = []  # (box, label, t_plan, t_fill, coder)
        svg.defs.append(
            '<pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<rect width="7" height="7" fill="rgba(77,225,255,0.035)"/><line x1="0" y1="0" x2="0" y2="7" stroke="rgba(77,225,255,0.09)" stroke-width="2"/></pattern>'
        )

    def start(self) -> int:
        return len(self.svg.parts)

    def end(self, idx: int, box, label: str) -> None:
        i = len(self.blocks)
        t_plan = self.PLAN0 + i * self.PLAN_STEP
        t_fill = self.FILL0 + i * self.FILL_STEP
        x, y, w, h = box
        cid = f"bk{i}"
        self.svg.defs.append(
            f'<clipPath id="{cid}"><rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="0" height="{h + 8:.1f}">'
            f'<animate attributeName="width" from="0" to="{w + 8 + self.SLACK:.1f}" begin="{t_fill:.2f}s" dur="{self.WRITE}s" fill="freeze" '
            f'calcMode="spline" keyTimes="0;1" keySplines=".4 0 .2 1"/></rect></clipPath>'
        )
        inner = "".join(self.svg.parts[idx:])
        self.svg.parts[idx:] = [f'<g clip-path="url(#{cid})">{inner}</g>']
        self.blocks.append((box, label, t_plan, t_fill, self.CODERS[i % 3]))

    @property
    def done(self) -> float:
        return self.FILL0 + len(self.blocks) * self.FILL_STEP + 0.6

    def _text(self, *a, **k) -> str:
        self.svg.text(*a, **k)
        return self.svg.parts.pop()

    def _cursor(self, name, color, stops, show, hide) -> None:
        """stops: [(t, x, y)] — the cursor eases between them; visible show..hide."""
        T = hide + 0.4
        f = FACES["m500"]
        self.svg.used["m500"].update(name)
        stops = [(0, *stops[0][1:])] + stops + [(T, *stops[-1][1:])]
        kt = ";".join(f"{t / T:.4f}" for t, _, _ in stops)
        vals = ";".join(f"{x:.1f} {y:.1f}" for _, x, y in stops)
        splines = ";".join([".16 1 .3 1"] * (len(stops) - 1))
        lw = f.width(name, 10) + 12
        self.svg.add(
            f'<g opacity="0"><animate attributeName="opacity" values="0;0;1;1;0" '
            f'keyTimes="0;{show / T:.4f};{(show + .2) / T:.4f};{hide / T:.4f};1" dur="{T:.2f}s" fill="freeze"/>'
            f'<g><animateTransform attributeName="transform" type="translate" values="{vals}" keyTimes="{kt}" '
            f'dur="{T:.2f}s" fill="freeze" calcMode="spline" keySplines="{splines}"/>'
            f'<path d="M1.5 1.5 L16 9.2 L9.4 10.9 L6.2 17.6 Z" fill="{color}" stroke="#050507" stroke-width="1.4" stroke-linejoin="round"/>'
            f'<rect x="14" y="16" width="{lw:.1f}" height="17" rx="3" fill="{color}"/>'
            f'<text x="20" y="28" font-family="{f.key},{FALLBACK["m"]}" font-size="10" fill="#0a0a0a">{esc(name)}</text></g></g>'
        )

    def finish(self) -> None:
        svg = self.svg
        # wireframes: appear when planned, vanish once written
        for (x, y, w, h), label, tp, tf, _ in self.blocks:
            T = tf + self.WRITE + 0.3
            kt = f"0;{tp / T:.4f};{(tp + .25) / T:.4f};{(tf + .1) / T:.4f};1"
            lab = self._text(x, y - 4, label, "m400", 9.5, WIRE)
            svg.add(
                f'<g opacity="0"><animate attributeName="opacity" values="0;0;1;1;0" keyTimes="{kt}" dur="{T:.2f}s" fill="freeze"/>'
                f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="{w + 8:.1f}" height="{h + 8:.1f}" fill="url(#hatch)" '
                f'stroke="{WIRE_LINE}" stroke-width="1" stroke-dasharray="3 3" rx="2"/>{lab}</g>'
            )
        # planner sweeps the layout, coders hop to the blocks they write
        name, color = self.PLANNER
        stops = [(tp, x + w * 0.5, y + h * 0.4) for (x, y, w, h), _, tp, _, _ in self.blocks]
        self._cursor(name, color, stops, show=0.15, hide=self.FILL0 - 0.1)
        for ci, (cname, ccolor) in enumerate(self.CODERS):
            mine = [b for i, b in enumerate(self.blocks) if i % 3 == ci]
            stops = []
            for (x, y, w, h), _, _, tf, _ in mine:
                stops += [(tf - 0.3, x - 6, y + h * 0.5), (tf + self.WRITE, x + w, y + h * 0.5)]
            self._cursor(f"{cname} write", ccolor, stops, show=self.FILL0 - 0.6, hide=self.done - 0.2)



def build_hero() -> None:
    svg = SVG(W, 700, "Madhu Siddharth — AI Engineer. Agentic workflows, end-to-end automation. I ship agents that do the work, then measure exactly where they break.")
    svg.css.append(
        "@keyframes blink{0%,50%{opacity:1}50.01%,100%{opacity:0}}.caret{animation:blink 1.1s steps(1) infinite}"
        "@keyframes spin{to{transform:rotate(360deg)}}.spin{transform-box:fill-box;transform-origin:center;animation:spin 1s linear infinite}"
    )
    sw = Swarm(svg)

    def block(box, label, draw):
        i = sw.start()
        draw()
        sw.end(i, box, label)

    # chrome bar
    svg.add(f'<path d="M6 0.5H{W - 6}A5.5 5.5 0 0 1 {W - 0.5} 6V44H0.5V6A5.5 5.5 0 0 1 6 0.5Z" fill="{BG1}"/>')
    svg.line(0, 44, W, 44, LINE2)
    svg.add(f'<path d="M24 17l-5 5 5 5M42 17l5 5-5 5" fill="none" stroke="{FAINT}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>')
    svg.add(f'<path d="M73 22a6 6 0 1 1-1.8-4.3M71.5 15.5v3.2h-3.2" fill="none" stroke="{FAINT}" stroke-width="1.5" stroke-linecap="round"/>')
    svg.rect(92, 10, 330, 24, fill=BG0, stroke=LINE2)
    svg.runs(104, 26.5, [("agent://", "m400", RED_INK), ("madhusiddharth.dev/", "m400", INK)], size=12)
    # build progress under the address bar
    svg.add(f'<rect x="92" y="33" height="1.5" width="0" fill="{WIRE}"><animate attributeName="width" from="0" to="330" '
            f'begin="0s" dur="{sw.FILL0 + 16 * sw.FILL_STEP + .6:.2f}s" fill="freeze"/>'
            f'<animate attributeName="opacity" from="1" to="0" begin="{sw.FILL0 + 16 * sw.FILL_STEP + .8:.2f}s" dur=".4s" fill="freeze"/></rect>')
    rw = FACES["m400"].width("Replay build", 11.5) + 22
    svg.rect(W - PAD - rw + 12, 10, rw, 24, fill=PANEL, stroke=LINE2)
    svg.text(W - PAD - rw + 23, 26, "Replay build", "m400", 11.5, INK)
    status_idx = len(svg.parts)  # status swaps are wrapped once the build length is known
    sx = W - PAD - rw - FACES["m400"].width("static render", 11.5) - 6
    svg.add(f'<circle cx="{sx - 10}" cy="22" r="3" fill="{RED}"/>')
    svg.text(sx, 26, "static render", "m400", 11.5, MUTED)
    static_parts = svg.parts[status_idx:]
    del svg.parts[status_idx:]
    ox = W - PAD - rw - FACES["m400"].width("orchestrating 11 agents", 11.5) - 6
    svg.add(f'<path class="spin" d="M{ox - 10} 17a5 5 0 1 1-5 5" fill="none" stroke="{WIRE}" stroke-width="1.5" stroke-linecap="round"/>')
    svg.text(ox, 26, "orchestrating 11 agents", "m400", 11.5, MUTED)
    busy_parts = svg.parts[status_idx:]
    del svg.parts[status_idx:]

    # status line
    y = 80
    def status():
        svg.add(f'<circle cx="{PAD + 4}" cy="{y - 4}" r="3.5" fill="none" stroke="{OK}">{PING}</circle>')
        svg.add(f'<circle cx="{PAD + 4}" cy="{y - 4}" r="3.5" fill="{OK}"/>')
        svg.runs(PAD + 16, y, [("available for work ", "m400", MUTED), ("/ ", "m400", FAINT), ("chicago ", "m400", MUTED),
                               (" gmt-6 ", "m400", INK), ("/ ", "m400", FAINT), ("building ", "m400", MUTED),
                               ("tool router ladder", "m500", INK)], size=12)
    block((PAD - 2, y - 13, 470, 18), "p.env", status)

    # playground window
    px, py, pw = PAD, 100, W - 2 * PAD
    win_idx = len(svg.parts)
    svg.add(f'<path d="M{px + 3} {py + 0.5}H{px + pw - 3}V{py + 36}H{px + 0.5}V{py + 3}Z" fill="{PANEL}"/>')
    svg.line(px, py + 36, px + pw, py + 36, LINE2)
    svg.add(f'<rect x="{px + 14}" y="{py + 15}" width="7" height="7" fill="{RED}"/>')
    x = px + 28
    x += svg.text(x, py + 23, "playground", "m500", 12, INK) + 14
    svg.text(x, py + 23, "run_01JD4M · madhu-v2", "m400", 11.5, FAINT)
    bw = FACES["m400"].width("streaming", 11) + 34
    bx = px + pw - 14 - bw
    svg.rect(bx, py + 8, bw, 20, fill=BG0, stroke=LINE2)
    svg.add(f'<path class="spin" d="M{bx + 15} {py + 13}a5 5 0 1 1-5 5" fill="none" stroke="{AGENT["coder"]}" stroke-width="1.6" stroke-linecap="round"/>')
    svg.text(bx + 25, py + 22, "streaming", "m400", 11, INK)

    # thread
    cfg_w = 236
    tx0, tx1 = px, px + pw - cfg_w
    lx, cx = tx0 + 16, tx0 + 104
    cw = tx1 - cx - 20
    y = py + 66
    svg.text(lx, y, "system", "m400", 11, FAINT)
    sys_y = y
    block((cx, y - 12, cw, 34), "msg.system",
          lambda: svg.para(cx, sys_y, "Answer as Madhu. Ground every claim in the résumé, the project logs and the repos.", cw, "m400", 12, MUTED, lh=20))
    y += 20 + 14
    ctx_y = y
    def ctx():
        cxx = cx
        for i, label in enumerate(["resume_kb.yaml", "13 projects", "2 roles", "4 certs"]):
            if i == 0:
                w = FACES["m500"].width("ctx ", 11) + FACES["m400"].width(label, 11) + 16
                svg.rect(cxx, ctx_y, w, 22, fill=PANEL2, stroke=LINE2)
                svg.runs(cxx + 8, ctx_y + 15, [("ctx ", "m500", INK), (label, "m400", MUTED)], size=11)
            else:
                w = chip(svg, cxx, ctx_y, label)
            cxx += w + 6
    block((cx, ctx_y, 340, 22), "ctx.retrieved", ctx)
    y += 22 + 16
    svg.line(tx0 + 1, y, tx1, y, LINE)
    y += 30
    svg.text(lx, y, "user", "m400", 11, FAINT)
    uy = y
    block((cx, y - 14, 300, 19), "msg.user", lambda: svg.text(cx, uy, "Who are you, and what do you ship?", "s500", 16, INK))
    y += 18
    svg.line(tx0 + 1, y, tx1, y, LINE)
    y += 28
    svg.text(lx, y, "assistant", "m500", 11, INK)
    svg.add(f'<rect class="caret" x="{lx + FACES["m500"].width("assistant", 11) + 5}" y="{y - 9}" width="5" height="11" fill="{FAINT}"/>')
    hy = y
    block((cx, y - 11, 80, 14), "span.hello", lambda: svg.text(cx, hy, "Hello, I'm", "m400", 12, FAINT))
    y += 56
    ny = y
    nw = FACES["s600"].width("Madhu Siddharth.", 56) - 2.5 * 16
    def name():
        svg.text(cx - 2, ny, "Madhu Siddharth.", "s600", 56, HI, ls=-2.5)
        svg.add(f'<rect class="caret" x="{cx + nw + 4}" y="{ny - 42}" width="5" height="44" fill="{RED}"/>')
    block((cx - 2, y - 44, nw + 12, 52), "h1.name", name)
    y += 30
    ry = y
    def role():
        svg.add(f'<rect x="{cx}" y="{ry - 8}" width="6" height="6" fill="{RED}"/>')
        svg.text(cx + 14, ry, "ai engineer · agentic workflows · end-to-end automation", "m400", 11.5, MUTED)
    block((cx, y - 11, 400, 14), "p.role", role)
    y += 34
    ty = y
    def tagline():
        w1 = svg.text(cx, ty, "I ship ", "s400", 19, MUTED)
        w2 = svg.text(cx + w1, ty, "agents that do the work", "s400", 19, INK)
        t = sw.FILL0 + len(sw.blocks) * sw.FILL_STEP + sw.WRITE
        svg.add(f'<rect x="{cx + w1}" y="{ty + 5}" height="1.5" fill="{RED}" width="0"><animate attributeName="width" from="0" to="{w2:.1f}" '
                f'begin="{t:.2f}s" dur="1.2s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".16 1 .3 1"/></rect>')
        svg.text(cx + w1 + w2, ty, ", then measure exactly where", "s400", 19, MUTED)
        svg.text(cx, ty + 28, "they break.", "s400", 19, MUTED)
    block((cx, y - 17, cw + 8, 50), "p.tagline", tagline)
    # tool_calls
    y += 58
    cy0 = y
    def calls():
        svg.text(cx, cy0, "tool_calls · 3", "m400", 11, FAINT)
        bx = cx
        for fn, arg, go in [("get_resume", "()", True), ("connect", "(linkedin)", False), ("view_source", "(github)", False)]:
            w = FACES["m400"].width(fn + arg, 12.5) + 36
            svg.rect(bx, cy0 + 10, w, 32, fill=RED if go else "none", stroke=None if go else LINE2)
            svg.runs(bx + 11, cy0 + 30.5, [(fn, "m400", HI if go else INK), (arg, "m400", "#ffd9d5" if go else MUTED)], size=12.5)
            ax = bx + w - 17
            svg.add(f'<path d="M{ax} {cy0 + 30}l6-6M{ax + 1} {cy0 + 24}h5v5" fill="none" stroke="{HI if go else MUTED}" stroke-width="1.4" stroke-linecap="round"/>')
            bx += w + 6
    block((cx, y - 11, 440, 53), "tool_calls", calls)
    thread_end = y + 42

    # config aside
    ax, aw = tx1 + 18, cfg_w - 36
    y = py + 66
    my0 = y
    def model():
        yy = my0
        for k, v in (("model", "madhu-v2"), ("role", "AI Engineer")):
            svg.text(ax, yy, k, "m400", 11, FAINT)
            svg.text(ax + aw, yy, v, "m400", 12, INK, anchor="end")
            yy += 26
        svg.text(ax, yy, "temperature", "m400", 11, FAINT)
        svg.text(ax + aw, yy, "0.2", "m400", 12, INK, anchor="end")
        svg.rect(ax + aw - 92, yy - 5, 60, 2, fill=LINE2, rx=1)
        svg.rect(ax + aw - 92, yy - 5, 12, 2, fill=RED, rx=1)
    block((ax, y - 12, aw, 68), "cfg.model", model)
    y += 52 + 22
    svg.line(tx1, y, px + pw, y, LINE)
    y += 28
    ty0 = y
    def tools():
        svg.runs(ax, ty0, [("tools ", "m400", FAINT), (str(len(TOOLS)), "m500", INK)], size=11)
        for i, t in enumerate(TOOLS):
            yy = ty0 + 10 + i * 22
            uri = tech_icon(t)
            if uri:
                svg.image(ax, yy + 5, 14, 14, uri, fit="meet")
            svg.text(ax + 22, yy + 16, t, "s400", 13, INK)
    block((ax, y - 11, aw, 10 + len(TOOLS) * 22 + 12), "cfg.tools", tools)
    y += 10 + len(TOOLS) * 22 + 14
    svg.line(tx1, y, px + pw, y, LINE)
    y += 24
    ry0 = y
    def run():
        svg.text(ax, ry0, "this run", "m400", 11, FAINT)
        yy = ry0 + 10
        cwid = aw / 3
        svg.rect(ax, yy, aw, 44, fill=BG0, stroke=LINE2)
        for i, (k, v) in enumerate([("nodes", "63/63"), ("wall", "11.6s"), ("agents", "11")]):
            xx = ax + i * cwid
            if i:
                svg.line(xx, yy, xx, yy + 44, LINE2)
            svg.text(xx + 9, yy + 17, k, "m400", 10, FAINT)
            svg.text(xx + 9, yy + 35, v, "m500", 13, INK)
    block((ax, y - 11, aw, 65), "cfg.usage", run)
    y += 10
    ph = max(thread_end, y + 44) + 22 - py
    svg.parts.insert(win_idx, f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="3" fill="{BG1}" stroke="{LINE2}"/>')
    svg.line(tx1, py + 36, tx1, py + ph, LINE2)

    # eval metrics, joined like the site's eval table
    my, mh = py + ph + 18, 112
    svg.h = my + mh + PAD
    mw = (W - 2 * PAD) / 4
    svg.rect(PAD, my, W - 2 * PAD, mh, fill=BG1, stroke=LINE2)
    for i, (v, label) in enumerate(METRICS):
        x = PAD + i * mw
        if i:
            svg.line(x, my, x, my + mh, LINE2)
        def metric(x=x, v=v, label=label):
            svg.text(x + 18, my + 22, "eval.metric", "m400", 10, FAINT)
            svg.text(x + 18, my + 56, v, "m400", 27, HI, ls=-0.8)
            svg.para(x + 18, my + 80, label, mw - 36, "s400", 12.5, MUTED, lh=18)
        block((x + 14, my + 10, mw - 28, mh - 20), "eval.metric", metric)

    # chrome status: "orchestrating" while building, then "static render"
    done = sw.done
    svg.add(f'<g><set attributeName="opacity" to="0" begin="{done:.2f}s" fill="freeze"/>{"".join(busy_parts)}</g>')
    svg.add(f'<g opacity="0"><set attributeName="opacity" to="1" begin="{done:.2f}s" fill="freeze"/>{"".join(static_parts)}</g>')
    sw.finish()
    svg.frame(grid=False)
    svg.save("hero.svg")


def build_button(name, fn, arg, href_hint, go=False, icon=None, w=None) -> None:
    """A linked tool_call button (the README wraps it in <a>)."""
    size = 12.5
    tw = FACES["m400"].width(fn + arg, size)
    iw = 18 if icon else 0
    width = w or tw + 44 + iw
    h = 40
    svg = SVG(width, h, f"{fn}{arg} → {href_hint}")
    svg.rect(0.5, 0.5, width - 1, h - 1, fill=RED if go else BG0, stroke=None if go else LINE2, rx=3)
    x = 14
    if icon:
        svg.icon(icon, x, 13, 14, HI if go else INK)
        x += iw
    svg.runs(x, 24.5, [(fn, "m400", HI if go else INK), (arg, "m400", "#ffd9d5" if go else MUTED)], size=size)
    ax = width - 22
    svg.add(f'<path d="M{ax} {h / 2 + 4}l7-7M{ax + 1} {h / 2 - 3}h6v6" fill="none" stroke="{HI if go else MUTED}" stroke-width="1.5" stroke-linecap="round"/>')
    svg.save(name)


def build_icon_button(name, icon) -> None:
    svg = SVG(40, 40, name)
    svg.rect(0.5, 0.5, 39, 39, fill=BG0, stroke=LINE2)
    svg.icon(icon, 11.5, 11.5, 17, INK)
    svg.save(f"icon-{name}.svg")


def build_about() -> None:
    sentences = re.split(r"(?<=\.)\s+", PROFILE["bio"])
    lead, body, quote = sentences[0], " ".join(sentences[1:-1]), sentences[-1]
    H = 1078
    svg = SVG(W, H, "About — " + PROFILE["bio"])
    y0 = 40
    sec_head(svg, y0, "01", "about", "Agent profile", "Background, runs & checkpoints")

    # copy + principle
    y = y0 + 176
    lw = 480
    y = svg.para(PAD, y, lead, lw, "s400", 22, INK, lh=32)
    y = svg.para(PAD, y + 40, body, lw, "s400", 14.5, MUTED, lh=24)
    y += 36
    svg.text(PAD, y, "→", "m400", 11.5, RED_INK)
    y = svg.para(PAD + 18, y, "For analyst-focused roles, a tailored Data Analyst résumé is available.", lw - 18, "m400", 11.5, MUTED, lh=19)
    copy_bottom = y

    cx, cy, cw = PAD + lw + 40, y0 + 160, W - 2 * PAD - lw - 40
    qlines = wrap("// " + quote, "m400", 12.5, cw - 36)
    rows, xx = 1, 0
    for f in FOCUS:
        w = FACES["m400"].width(f, 11) + 30
        if xx + w > cw - 30:
            rows, xx = rows + 1, 0
        xx += w + 6
    ch = 66 + len(qlines) * 21 + 40 + rows * 30 + 10
    svg.rect(cx, cy, cw, ch, fill=PANEL, stroke=LINE2)
    svg.runs(cx + 16, cy + 24, [("memory/", "m400", FAINT), ("principle.md", "m500", INK)], size=11.5)
    svg.line(cx, cy + 38, cx + cw, cy + 38, LINE2)
    yy = cy + 66
    for i, ln in enumerate(qlines):
        if i == 0:
            svg.runs(cx + 18, yy, [("// ", "m400", FAINT), (ln[3:], "m400", INK)], size=12.5)
        else:
            svg.text(cx + 18, yy, ln, "m400", 12.5, INK)
        yy += 21
    yy += 14
    svg.line(cx, yy - 10, cx + cw, yy - 10, LINE)
    svg.text(cx + 18, yy + 12, "capabilities", "m400", 11, FAINT)
    yy += 26
    xx = cx + 18
    for f in FOCUS:
        w = FACES["m400"].width(f, 11) + 30
        if xx + w > cx + cw - 12:
            xx, yy = cx + 18, yy + 30
        svg.rect(xx, yy, w, 23, fill=BG1, stroke=LINE2)
        svg.add(f'<rect x="{xx + 9}" y="{yy + 9}" width="5" height="5" fill="{AGENT["coder"]}"/>')
        svg.text(xx + 20, yy + 15.5, f, "m400", 11, INK)
        xx += w + 6

    # runs
    y = max(copy_bottom, cy + ch) + 56
    svg.runs(PAD, y, [("runs/ ", "m500", INK), ("experience · 2", "m400", FAINT)], size=12)
    y += 16
    rw = (W - 2 * PAD) / 2
    rh = 300
    svg.rect(PAD, y, W - 2 * PAD, rh, fill=BG1, stroke=LINE2)
    svg.line(PAD + rw, y, PAD + rw, y + rh, LINE2)
    for i, r in enumerate(RUNS):
        x = PAD + i * rw + 20
        iw = rw - 40
        yy = y + 30
        color = AGENT["coder"] if r["status"] == "running" else OK
        svg.add(f'<circle cx="{x + 3}" cy="{yy - 4}" r="3" fill="{color}"/>')
        if r["status"] == "running":
            svg.add(f'<circle cx="{x + 3}" cy="{yy - 4}" r="3" fill="none" stroke="{color}">{PING}</circle>')
        svg.text(x + 12, yy, r["status"], "m400", 11, color)
        svg.text(x + iw, yy, r["when"], "m400", 11, FAINT, anchor="end")
        yy += 34
        svg.runs(x, yy, [(r["org"], "s600", HI), (" / " + r["role"], "s400", MUTED)], size=20)
        yy += 20
        svg.text(x, yy, r["where"], "m400", 11, FAINT)
        yy += 30
        svg.text(x, yy, "task", "m400", 11, FAINT)
        yy = svg.para(x + 38, yy, r["task"], iw - 38, "s400", 13.5, INK, lh=21)
        yy += 22
        for k, v in r["out"]:
            svg.line(x, yy - 15, x + iw, yy - 15, LINE)
            svg.text(x, yy, k, "m400", 11, MUTED)
            svg.text(x + iw, yy, v, "m400", 11.5, INK, anchor="end")
            yy += 28
        svg.line(x, yy - 15, x + iw, yy - 15, LINE)
        yy = y + rh - 38
        xx = x
        for t in r["tools"]:
            xx += chip(svg, xx, yy, t, icon=t if tech_icon(t) else None, size=10.5, h=22, fill=BG0) + 5

    # checkpoints
    y += rh + 52
    svg.runs(PAD, y, [("checkpoints/ ", "m500", INK), ("education · 2", "m400", FAINT)], size=12)
    y += 16
    kh = 166
    svg.rect(PAD, y, W - 2 * PAD, kh, fill=BG1, stroke=LINE2)
    svg.line(PAD + rw, y, PAD + rw, y + kh, LINE2)
    for i, c in enumerate(CKPTS):
        x = PAD + i * rw + 20
        iw = rw - 40
        svg.text(x, y + 30, f"ckpt · {c['tag']}", "m400", 11, FAINT)
        svg.text(x, y + 60, c["degree"], "s600", 17, HI)
        svg.text(x, y + 82, c["school"], "s400", 14, MUTED)
        my = y + 100
        svg.rect(x, my, iw, 46, fill=BG0, stroke=LINE2)
        colw = [0.34, 0.27, 0.39]
        xx = x
        for j, (k, v) in enumerate((("gpa", c["gpa"]), ("saved", c["when"]), ("where", c["where"]))):
            if j:
                svg.line(xx, my, xx, my + 46, LINE2)
            svg.text(xx + 10, my + 17, k, "m400", 10, FAINT)
            svg.text(xx + 10, my + 35, v, "m400", 12, INK)
            xx += iw * colw[j]

    svg.h = y + kh + 40
    svg.frame()
    svg.save("about.svg")


def build_head(name, n, sec, eyebrow, title, lead, h) -> None:
    svg = SVG(W, h, f"{title} — {lead}" if lead else title)
    sec_head(svg, 40, n, sec, eyebrow, title, lead)
    svg.frame()
    svg.save(name)


def card_body(svg: SVG, p, x, y, w, max_lines=4, title_size=19) -> float:
    svg.add(f'<rect x="{x}" y="{y - 7}" width="6" height="6" fill="{RED}"/>')
    svg.text(x + 13, y, "case study", "m400", 11, MUTED)
    svg.text(x + w, y, f"P.{p['i']}", "m400", 11, FAINT, anchor="end")
    y += 34
    svg.text(x, y, p["name"], "s600", title_size, HI, ls=-0.3)
    y += 22
    svg.text(x, y, p["domain"], "m400", 11.5, MUTED)
    y += 28
    y = svg.para(x, y, p["summary"], w, "s400", 13.5, MUTED, lh=21, max_lines=max_lines)
    y += 20
    xx = x
    shown = 0
    for t in p["tech"]:
        tw = FACES["m400"].width(t, 10.5) + 16
        if shown == 5 or xx + tw > x + w - 40:
            break
        xx += chip(svg, xx, y, t, size=10.5, h=21, fill=BG0) + 5
        shown += 1
    if len(p["tech"]) > shown:
        chip(svg, xx, y, f"+{len(p['tech']) - shown}", size=10.5, h=21, fill=BG0, color=FAINT)
    return y + 21


HALF = W / 2   # a pair of cards fills one README row exactly; each half carries its own gutter
GUT = 5
FOOT_H = 44
REPO_W = 58     # width of the GitHub half of a card's action bar (incl. gutter)
FADE = ('<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0.55" stop-color="#0e0e0e" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#0e0e0e" stop-opacity="0.6"/></linearGradient>')
GLOW_CYCLE = 21  # seconds; the cards "hover" one after another, 3 s each


def hover_glow(svg: SVG, slot: int) -> str:
    """The site's card hover, played on a timer: the thumbnail goes from
    grayscale(1) brightness(.62) to grayscale(.15) brightness(.9) and the
    border lights up. GitHub shows SVGs as <img>, which never sees the
    pointer, so this is the closest a README can get. Returns the filter id."""
    t0 = (slot * 3) / GLOW_CYCLE
    on, off = t0 + 0.6 / GLOW_CYCLE, t0 + 2.6 / GLOW_CYCLE
    end = t0 + 3.2 / GLOW_CYCLE
    kt = f"0;{t0:.4f};{on:.4f};{off:.4f};{end:.4f};1"
    anim = lambda attr, a, b: (f'<animate attributeName="{attr}" values="{a};{a};{b};{b};{a};{a}" keyTimes="{kt}" '
                               f'dur="{GLOW_CYCLE}s" repeatCount="indefinite" calcMode="spline" '
                               f'keySplines="0 0 1 1;.16 1 .3 1;0 0 1 1;.16 1 .3 1;0 0 1 1"/>')
    svg.defs.append(
        '<filter id="glow" color-interpolation-filters="sRGB">'
        f'<feColorMatrix type="saturate" values="0">{anim("values", 0, 0.85)}</feColorMatrix>'
        '<feComponentTransfer>'
        + "".join(f'<feFunc{c} type="linear" slope="0.64">{anim("slope", 0.64, 0.92)}</feFunc{c}>' for c in "RGB")
        + '</feComponentTransfer></filter>'
    )
    return "glow"


def glow_border(svg: SVG, x, y, w, h, slot: int) -> None:
    t0 = (slot * 3) / GLOW_CYCLE
    kt = f"0;{t0:.4f};{t0 + 0.6 / GLOW_CYCLE:.4f};{t0 + 2.6 / GLOW_CYCLE:.4f};{t0 + 3.2 / GLOW_CYCLE:.4f};1"
    svg.add(f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="6" fill="none" stroke="{LINE2}">'
            f'<animate attributeName="stroke" values="{LINE2};{LINE2};#4a4a4a;#4a4a4a;{LINE2};{LINE2}" keyTimes="{kt}" '
            f'dur="{GLOW_CYCLE}s" repeatCount="indefinite"/></rect>')


def build_lead_card(p, slot=0) -> None:
    h = 430
    svg = SVG(W, h, f"{p['name']} — {p['summary']}")
    lw = 440
    iw, ih = lw - 40, round((lw - 40) / 1.833)
    ix, iy = 20, 20
    fid = hover_glow(svg, slot)
    svg.add(f'<clipPath id="c"><rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="3"/></clipPath>')
    svg.image(ix, iy, iw, ih, thumb(p["thumb"], iw, ih), f'clip-path="url(#c)" filter="url(#{fid})"')
    svg.rect(ix, iy, iw, ih, stroke=LINE2)
    y = iy + ih + 34
    svg.text(ix, y, "results", "m400", 11, FAINT)
    y += 10
    for v, label in p["results"]:
        svg.line(ix, y, ix + iw, y, LINE)
        svg.text(ix, y + 24, v, "m500", 13.5, HI)
        svg.para(ix + 112, y + 24, label, iw - 112, "s400", 12, MUTED, lh=16, max_lines=1)
        y += 36
    svg.line(lw, 0, lw, h, RULE)
    x, w = lw + 26, W - lw - 52
    card_body(svg, p, x, 38, w, max_lines=7, title_size=24)
    svg.parts.insert(0, f'<rect width="{W}" height="{h}" rx="6" fill="{BG1}"/>')
    glow_border(svg, 0, 0, W, h, slot)
    svg.save(f"card-{p['slug']}.svg")


def build_card(p, side: str, slot: int) -> None:
    """One half of a card pair. `side` puts the gutter between the two cards."""
    w, h, th = HALF - GUT, 446, 210
    ox = 0 if side == "L" else GUT
    svg = SVG(HALF, h, f"{p['name']} — {p['summary']}")
    fid = hover_glow(svg, slot)
    svg.add(f'<clipPath id="c"><path d="M{ox + 6} 0H{ox + w - 6}A6 6 0 0 1 {ox + w} 6V{th}H{ox}V6A6 6 0 0 1 {ox + 6} 0Z"/></clipPath>')
    svg.image(ox, 0, w, th, thumb(p["thumb"], int(w), th), f'clip-path="url(#c)" filter="url(#{fid})"')
    svg.defs.append(FADE)
    svg.rect(ox, 0, w, th, fill="url(#fade)", rx=0, extra='clip-path="url(#c)"')
    svg.line(ox, th, ox + w, th, RULE)
    card_body(svg, p, ox + 20, th + 32, w - 40, max_lines=4)
    svg.parts.insert(0, f'<rect x="{ox}" width="{w}" height="{h}" rx="6" fill="{BG1}"/>')
    glow_border(svg, ox, 0, w, h, slot)
    svg.save(f"card-{p['slug']}.svg")


def build_card_actions(p, side: str) -> None:
    """The card footer as two links: field report (site) and source (GitHub).
    side: "L"/"R" for a half-width card, "F" for the full-width lead card."""
    total = W if side == "F" else HALF
    gl = GUT if side == "R" else 0          # gutter on the left of the report half
    gr = GUT if side == "L" else 0          # gutter on the right of the repo half
    repo_w = REPO_W if side == "L" else REPO_W - GUT
    report_w = total - repo_w
    # report half
    svg = SVG(report_w, FOOT_H, f"Open the {p['name']} field report")
    bw = report_w - gl - 6
    svg.rect(gl + 0.5, 0.5, bw - 1, FOOT_H - 1, fill=BG1, stroke=LINE2, rx=4)
    x = gl + 18
    x += svg.text(x, 27, "field report", "m400", 12, INK) + 9
    svg.add(f'<path d="M{x} 22.5h11M{x + 7} 18l4.5 4.5-4.5 4.5" fill="none" stroke="{INK}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>')
    svg.text(gl + bw - 18, 27, "madhusiddharths.com", "m400", 11, FAINT, anchor="end")
    svg.save(f"act-{p['slug']}-report.svg")
    # repo half
    svg = SVG(repo_w, FOOT_H, f"{p['name']} source on GitHub")
    bw = repo_w - gr
    svg.rect(0.5, 0.5, bw - 1, FOOT_H - 1, fill=BG1, stroke=LINE2, rx=4)
    svg.icon("github", (bw - 17) / 2, (FOOT_H - 17) / 2, 17, INK)
    svg.save(f"act-{p['slug']}-repo.svg")


def build_ledger_row(idx, name, domain, kind, slug) -> None:
    w, h = 445, 58
    svg = SVG(w, h, f"P.{idx} {name} — {domain}")
    svg.rect(0.5, 0.5, w - 1, h - 1, fill=BG1, stroke=LINE2, rx=4)
    svg.text(18, 34, f"P.{idx}", "m400", 11, FAINT)
    svg.text(64, 27, name, "s600", 14.5, HI)
    svg.text(64, 45, domain, "m400", 10.5, MUTED)
    label = f"{kind} "
    lw = FACES["m400"].width(label, 11)
    svg.text(w - 34 - lw, 34, label, "m400", 11, INK)
    ax = w - 30
    svg.add(f'<path d="M{ax} {35}l7-7M{ax + 1} {28}h6v6" fill="none" stroke="{MUTED}" stroke-width="1.4" stroke-linecap="round"/>')
    svg.save(f"row-{slug}.svg")


def build_index_button() -> None:
    label = "All 13 projects — full index"
    w = FACES["s500"].width(label, 13.5) + 64
    svg = SVG(w, 44, label)
    svg.rect(0.5, 0.5, w - 1, 43, fill=BG0, stroke=LINE2)
    svg.text(18, 27, label, "s500", 13.5, INK)
    ax = w - 34
    svg.add(f'<path d="M{ax} 22h13M{ax + 8} 17l5 5-5 5" fill="none" stroke="{INK}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>')
    svg.save("btn-index.svg")


def build_registry() -> None:
    max_calls = 12
    colw = (W - 2 * PAD - 24) / 3
    row_h = 25

    def panel_h(ns):
        return 98 + len(REGISTRY[ns][1]) * row_h + 40

    col_heights = [sum(panel_h(ns) for ns in col) + 12 * (len(col) - 1) for col in REG_COLUMNS]
    top = 40 + 196
    H = top + max(col_heights) + 36
    svg = SVG(W, H, "Tool registry — " + "; ".join(f"{t}: {', '.join(i for i, _ in items)}" for t, items in REGISTRY.values()))
    sec_head(svg, 40, "03", "stack", "Tool registry", "Tools the agents can call",
             "Everything I reach for, registered by namespace. calls counts the projects in my portfolio that use each tool.")
    for ci, col in enumerate(REG_COLUMNS):
        x = PAD + ci * (colw + 12)
        y = top
        for ns in col:
            title, items = REGISTRY[ns]
            ph = panel_h(ns)
            svg.rect(x, y, colw, ph, fill=BG1, stroke=LINE2)
            svg.add(f'<path d="M{x + 3} {y + 0.5}H{x + colw - 3}V{y + 34}H{x + 0.5}V{y + 3}Z" fill="{PANEL}"/>')
            svg.line(x, y + 34, x + colw, y + 34, LINE2)
            svg.runs(x + 14, y + 22, [("ns ", "m400", FAINT), (ns, "m500", INK)], size=11)
            svg.text(x + colw - 14, y + 22, f"{len(items)} tools", "m400", 10.5, FAINT, anchor="end")
            svg.text(x + 14, y + 60, title, "s600", 14.5, HI)
            hy = y + 86
            svg.text(x + 38, hy, "tool", "m400", 10, FAINT)
            svg.text(x + colw - 14, hy, "calls", "m400", 10, FAINT, anchor="end")
            svg.line(x + 14, hy + 7, x + colw - 14, hy + 7, LINE)
            ry = hy + 7
            for i, (t, n) in enumerate(items):
                cy = ry + i * row_h + row_h / 2
                uri = tech_icon(t)
                if uri:
                    dim = ' opacity="0.4"' if n == 0 else ""
                    svg.image(x + 14, cy - 7, 14, 14, uri, dim, fit="meet")
                else:
                    svg.add(f'<circle cx="{x + 21}" cy="{cy}" r="2.5" fill="{FAINT}"/>')
                svg.text(x + 38, cy + 4.5, t, "s400", 13, INK if n else FAINT)
                svg.text(x + colw - 14, cy + 4, str(n), "m400", 11.5, INK if n else FAINT, anchor="end")
                bw = 42
                bx = x + colw - 34 - bw
                svg.rect(bx, cy - 0.75, bw, 1.5, fill=LINE2, rx=0.75)
                if n:
                    svg.rect(bx + bw * (1 - n / max_calls), cy - 0.75, bw * n / max_calls, 1.5,
                             fill=RED if ns == "top_calls" else MUTED, rx=0.75)
            fy = y + ph - 14
            svg.line(x, fy - 18, x + colw, fy - 18, LINE)
            used = sum(1 for _, n in items if n)
            svg.text(x + 14, fy, f"{used}/{len(items)} in use", "m400", 10.5, FAINT)
            svg.text(x + colw - 14, fy, f"Σ {sum(n for _, n in items)} calls", "m400", 10.5, FAINT, anchor="end")
            y += ph + 12
    svg.frame()
    svg.save("registry.svg")


def build_cred(i, name, issuer, date, img) -> None:
    w, h = 214, 286
    svg = SVG(w, h, f"{name} — {issuer}, {date}. Verified on Credly.")
    svg.rect(0.5, 0.5, w - 1, h - 1, fill=BG1, stroke=LINE2, rx=4)
    svg.text(16, 26, f"cred_0{i}", "m400", 10.5, FAINT)
    svg.text(w - 16, 26, "✓ verified", "m400", 10.5, OK, anchor="end")
    svg.image(16, 44, 56, 56, badge(img), fit="meet")
    y = svg.para(16, 132, name, w - 32, "s500", 14.5, HI, lh=20)
    svg.para(16, y + 26, f"{issuer} · {date}", w - 32, "m400", 10.5, FAINT, lh=16)
    svg.line(16, h - 50, w - 16, h - 50, RULE)
    svg.runs(16, h - 23, [("verify", "m500", INK), ('("credly")', "m400", MUTED)], size=11)
    ax = w - 30
    svg.add(f'<path d="M{ax} {h - 23}l7-7M{ax + 1} {h - 30}h6v6" fill="none" stroke="{MUTED}" stroke-width="1.4" stroke-linecap="round"/>')
    svg.save(f"cred-{i}.svg")


def build_contact() -> None:
    H = 470
    svg = SVG(W, H, "Your turn to prompt. Hiring for agentic AI, LLM post-training or applied ML? Email madhusiddharths1@outlook.com, LinkedIn or GitHub.")
    sec_head(svg, 40, "05", "contact", "Next steps?", "Your turn to prompt.")
    y = 236
    svg.para(PAD, y, "Hiring for agentic AI, LLM post-training or applied ML? Send the request. Email, LinkedIn or GitHub all reach me, and every one gets a reply.",
             360, "s400", 16, MUTED, lh=26)
    rx, rw = PAD + 410, W - 2 * PAD - 410
    ry, rh = 206, 224
    svg.rect(rx, ry, rw, rh, fill=BG1, stroke=LINE2)
    svg.add(f'<path d="M{rx + 3} {ry + 0.5}H{rx + rw - 3}V{ry + 36}H{rx + 0.5}V{ry + 3}Z" fill="{PANEL}"/>')
    svg.line(rx, ry + 36, rx + rw, ry + 36, LINE2)
    x = rx + 14
    x += svg.text(x, ry + 23, "POST", "m600", 11, RED_INK) + 12
    svg.text(x, ry + 23, "/v1/contact", "m400", 12, INK)
    svg.text(rx + rw - 14, ry + 23, "200 OK", "m400", 11, OK, anchor="end")
    lines = [
        [("{", MUTED)],
        [('  "to"', INK), (": ", MUTED), (f'"{PROFILE["email"]}"', STR), (",", MUTED)],
        [('  "role"', INK), (": ", MUTED), ('"AI Engineer"', STR), (",", MUTED)],
        [('  "status"', INK), (": ", MUTED), ('"open_to_opportunities"', STR), (",", MUTED)],
        [('  "timezone"', INK), (": ", MUTED), ('"America/Chicago"', STR), (",", MUTED)],
        [('  "channels"', INK), (": [", MUTED), ('"github"', STR), (", ", MUTED), ('"linkedin"', STR), (", ", MUTED), ('"discord"', STR), ("]", MUTED)],
        [("}", MUTED)],
    ]
    yy = ry + 64
    for ln in lines:
        svg.runs(rx + 16, yy, [(t, "m400", c) for t, c in ln], size=12)
        yy += 22
    svg.frame()
    svg.save("contact.svg")


def build_footer() -> None:
    svg = SVG(W, 56, "© 2026 Madhu Siddharth Suthagar — assembled by an 11-agent swarm")
    svg.text(PAD, 33, f"© 2026 {PROFILE['name']}", "m400", 11, FAINT)
    svg.runs(W - PAD - FACES["m400"].width("assembled by an 11-agent swarm · hit replay to watch ↗", 11), 33,
             [("assembled by an 11-agent swarm · ", "m400", FAINT), ("hit replay to watch ↗", "m400", MUTED)], size=11)
    svg.frame(grid=False)
    svg.save("footer.svg")


def main() -> None:
    global PORTFOLIO
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--portfolio", type=Path, default=Path("~/Documents/webstorm/version_2").expanduser())
    PORTFOLIO = ap.parse_args().portfolio.expanduser()
    load_fonts(PORTFOLIO)
    print(f"writing {OUT.relative_to(ROOT)}/")
    build_hero()
    build_button("btn-resume.svg", "get_resume", "()", "résumé", go=True)
    build_button("btn-portfolio.svg", "launch", "(portfolio)", "madhusiddharths.com")
    build_button("btn-linkedin.svg", "connect", "(linkedin)", "LinkedIn")
    build_button("btn-email.svg", "send", "(email)", PROFILE["email"], icon="mail")
    build_about()
    build_head("head-work.svg", "02", "work", "Architectural showcase", "Flagship Deployments",
               "End-to-end systems spanning data engineering, applied machine learning, and agentic AI. Open one for the full field report.", 236)
    build_lead_card(PROJECTS[0], slot=0)
    build_card_actions(PROJECTS[0], "F")
    for i, p in enumerate(PROJECTS[1:]):
        side = "LR"[i % 2]
        build_card(p, side, slot=i + 1)
        build_card_actions(p, side)
    for idx, name, domain, kind, _url, slug in MORE:
        build_ledger_row(idx, name, domain, kind, slug)
    build_index_button()
    build_registry()
    build_head("head-certs.svg", "04", "certs", "Credential verifier", "Verified credentials",
               "Industry certifications across machine learning, data science, cloud and analytics — each one checks out against its public Credly record.", 236)
    for i, c in enumerate(CERTS, 1):
        build_cred(i, *c)
    build_contact()
    build_button("btn-touch.svg", "Get in touch", "", PROFILE["email"], go=True, icon="mail")
    for n in ("github", "linkedin", "discord"):
        build_icon_button(n, n)
    build_footer()


if __name__ == "__main__":
    main()
