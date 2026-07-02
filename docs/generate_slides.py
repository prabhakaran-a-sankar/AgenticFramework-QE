"""Generate Accenture-styled one-pager slides for QEAF agents."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.enum.dml import MSO_THEME_COLOR
import io

# ── Accenture brand colours ──────────────────────────────────────────────────
PURPLE       = RGBColor(0xA1, 0x00, 0xFF)   # Accenture signature purple
DARK         = RGBColor(0x1A, 0x1A, 0x1A)   # Near-black
WHITE        = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_PURPLE = RGBColor(0xF2, 0xE8, 0xFF)   # Tinted bg
MID_GRAY     = RGBColor(0x66, 0x66, 0x66)
LIGHT_GRAY   = RGBColor(0xF5, 0xF5, 0xF5)
DARK_PURPLE  = RGBColor(0x44, 0x00, 0x88)   # Section borders

# ── Architecture slide extra colours (light theme) ───────────────────────────
ARCH_BG      = RGBColor(0xF7, 0xF5, 0xFA)   # Very light lavender (slide bg)
STAGE_BG     = RGBColor(0xEE, 0xE5, 0xFF)   # Light purple tint (pipeline stages)
STAGE_LLM    = RGBColor(0xDD, 0xC4, 0xFF)   # Highlighted LLM stage (brighter tint)
INPUT_BG     = RGBColor(0xE5, 0xEF, 0xFF)   # Light blue (inputs)
OUTPUT_BG    = RGBColor(0xE5, 0xF7, 0xEE)   # Light green (outputs)
BLUE_ACCENT  = RGBColor(0x22, 0x66, 0xDD)   # Input border accent
GREEN_ACCENT = RGBColor(0x00, 0xAA, 0x66)   # Output border accent
ARCH_GRAY    = RGBColor(0x33, 0x33, 0x44)   # Body text on light bg

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)


def add_rect(slide, l, t, w, h, fill_rgb=None, line_rgb=None, line_w=Pt(0)):
    from pptx.util import Pt
    shape = slide.shapes.add_shape(1, l, t, w, h)  # MSO_SHAPE_TYPE.RECTANGLE = 1
    shape.line.width = line_w
    if fill_rgb:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_rgb
    else:
        shape.fill.background()
    if line_rgb:
        shape.line.color.rgb = line_rgb
    else:
        shape.line.fill.background()
    return shape


def add_text_box(slide, text, l, t, w, h,
                 font_name="Segoe UI", font_size=Pt(11),
                 bold=False, italic=False, color=DARK,
                 align=PP_ALIGN.LEFT, word_wrap=True):
    txBox = slide.shapes.add_textbox(l, t, w, h)
    tf = txBox.text_frame
    tf.word_wrap = word_wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = font_size
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txBox


def add_multiline_text_box(slide, lines, l, t, w, h,
                           font_name="Segoe UI", font_size=Pt(10),
                           bold=False, color=DARK,
                           align=PP_ALIGN.LEFT, line_spacing_pt=None,
                           bullet=False):
    txBox = slide.shapes.add_textbox(l, t, w, h)
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    for line in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        if bullet:
            p.space_before = Pt(2)
        p.alignment = align
        run = p.add_run()
        run.text = ("• " if bullet else "") + line
        run.font.name = font_name
        run.font.size = font_size
        run.font.bold = bold
        run.font.color.rgb = color
        if line_spacing_pt:
            p.space_after = Pt(line_spacing_pt)
    return txBox


def add_rounded_rect(slide, l, t, w, h, fill_rgb=None, border_rgb=None, border_w=Pt(1.5)):
    """Rounded rectangle shape (autoshape type 5)."""
    sh = slide.shapes.add_shape(5, l, t, w, h)
    if fill_rgb:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill_rgb
    else:
        sh.fill.background()
    if border_rgb:
        sh.line.color.rgb = border_rgb
        sh.line.width = border_w
    else:
        sh.line.fill.background()
    return sh


# ── Shared layout elements ───────────────────────────────────────────────────

def draw_chrome(slide, title_text, subtitle_text):
    """Top bar, header band, title, and footer."""
    # Purple top bar
    add_rect(slide, 0, 0, SLIDE_W, Inches(0.07), fill_rgb=PURPLE)

    # Dark header band
    add_rect(slide, 0, Inches(0.07), SLIDE_W, Inches(1.0), fill_rgb=DARK)

    # "Accenture." wordmark
    tb = slide.shapes.add_textbox(Inches(0.4), Inches(0.1), Inches(3), Inches(0.5))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    r1 = p.add_run(); r1.text = "Accenture"
    r1.font.name = "Segoe UI"; r1.font.size = Pt(18); r1.font.bold = True
    r1.font.color.rgb = WHITE
    r2 = p.add_run(); r2.text = "."
    r2.font.name = "Segoe UI"; r2.font.size = Pt(18); r2.font.bold = True
    r2.font.color.rgb = PURPLE

    # Badge
    add_rect(slide, Inches(11.2), Inches(0.18), Inches(1.8), Inches(0.38), fill_rgb=PURPLE)
    add_text_box(slide, "AI-POWERED AGENT", Inches(11.22), Inches(0.2), Inches(1.78), Inches(0.34),
                 font_size=Pt(7), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

    # Hero gradient band
    add_rect(slide, 0, Inches(1.07), SLIDE_W, Inches(1.55), fill_rgb=DARK_PURPLE)

    # Hero title
    tb = slide.shapes.add_textbox(Inches(0.4), Inches(1.12), Inches(9), Inches(0.7))
    tf = tb.text_frame; tf.word_wrap = False
    p = tf.paragraphs[0]
    # split on first word for light/bold split
    words = title_text.split(" ", 1)
    r1 = p.add_run(); r1.text = words[0] + " "
    r1.font.name = "Segoe UI"; r1.font.size = Pt(28); r1.font.bold = False
    r1.font.color.rgb = WHITE
    if len(words) > 1:
        r2 = p.add_run(); r2.text = words[1]
        r2.font.name = "Segoe UI"; r2.font.size = Pt(28); r2.font.bold = True
        r2.font.color.rgb = PURPLE

    # Hero subtitle
    add_text_box(slide, subtitle_text,
                 Inches(0.4), Inches(1.78), Inches(10.5), Inches(0.75),
                 font_size=Pt(10.5), color=RGBColor(0xCC, 0xCC, 0xCC))

    # Footer band
    add_rect(slide, 0, Inches(7.1), SLIDE_W, Inches(0.4), fill_rgb=DARK)
    add_text_box(slide, "Quality Engineering Agentic Framework  |  Accenture",
                 Inches(0.4), Inches(7.12), Inches(9), Inches(0.28),
                 font_size=Pt(8), color=RGBColor(0x88, 0x88, 0x88))
    add_text_box(slide, "© 2025 Accenture. All rights reserved.",
                 Inches(9.5), Inches(7.12), Inches(3.5), Inches(0.28),
                 font_size=Pt(8), color=RGBColor(0x66, 0x66, 0x66), align=PP_ALIGN.RIGHT)

    # Purple accent line below hero
    add_rect(slide, 0, Inches(2.62), SLIDE_W, Inches(0.04), fill_rgb=PURPLE)


def draw_section_card(slide, section_title, l, t, w, h):
    """Draws a card with left purple border and section header."""
    add_rect(slide, l, t, w, h, fill_rgb=LIGHT_GRAY)
    add_rect(slide, l, t, Inches(0.05), h, fill_rgb=PURPLE)
    add_text_box(slide, section_title.upper(),
                 l + Inches(0.12), t + Inches(0.07), w - Inches(0.2), Inches(0.22),
                 font_size=Pt(7.5), bold=True, color=PURPLE)


def draw_stat_block(slide, number, label, l, t):
    add_text_box(slide, number, l, t, Inches(1.4), Inches(0.42),
                 font_size=Pt(24), bold=True, color=PURPLE)
    add_text_box(slide, label.upper(), l, t + Inches(0.4), Inches(1.4), Inches(0.22),
                 font_size=Pt(7), color=RGBColor(0xAA, 0xAA, 0xAA))


# ── SLIDE 1: Standalone Automation Agent ────────────────────────────────────

def build_slide_1(slide):
    draw_chrome(
        slide,
        "Standalone Automation Agent",
        "An intelligent AI agent that generates production-ready test automation scripts that integrate seamlessly\n"
        "into your existing framework — learning your team's patterns, conventions, and architecture first."
    )

    # Stat strip
    stats = [
        ("4+",     "Languages"),
        ("6+",     "Frameworks"),
        ("3-step", "Fallback"),
        ("Auto",   "Self-Healing"),
    ]
    for i, (num, lbl) in enumerate(stats):
        draw_stat_block(slide, num, lbl, Inches(0.4 + i * 1.8), Inches(2.7))

    # ── LEFT COLUMN ─────────────────────────────────────────────────────────
    # WHAT IS IT
    draw_section_card(slide, "What Is It", Inches(0.3), Inches(3.2), Inches(4.1), Inches(1.4))
    add_multiline_text_box(
        slide,
        ["An AI agent within Accenture's QEAF that reads your existing automation project — its structure, "
         "page objects, helpers, and conventions — then generates scripts that fit natively into your framework. "
         "Supports local (on-server) and remote (cloud-hosted) delivery."],
        Inches(0.48), Inches(3.45), Inches(3.9), Inches(1.1),
        font_size=Pt(9.5), color=MID_GRAY
    )

    # KEY CAPABILITIES
    draw_section_card(slide, "Key Capabilities", Inches(0.3), Inches(4.72), Inches(4.1), Inches(2.15))
    caps = [
        "Framework Profiling — auto-detects language & framework from project markers",
        "Pattern Learning — extracts real class names, method signatures, page objects",
        "Style Replication — mirrors fixture patterns, locators, assertion style",
        "Self-Healing — validates syntax; auto-requests LLM fixes (up to 2 passes)",
        "Multi-Host Fallback — adapts prompt size for small-context environments",
        "Dual Delivery — local disk write or remote base64 file map for cloud MCP",
    ]
    add_multiline_text_box(slide, caps,
                           Inches(0.5), Inches(4.97), Inches(3.85), Inches(1.85),
                           font_size=Pt(9), color=DARK, bullet=True)

    # ── RIGHT COLUMN ────────────────────────────────────────────────────────
    # HOW IT WORKS
    draw_section_card(slide, "How It Works", Inches(4.6), Inches(3.2), Inches(4.3), Inches(1.55))
    steps = [
        "① Profile Framework  →  scan markers, detect language & framework",
        "② Extract Patterns  →  collect class/method names, page objects",
        "③ Build Adaptive Prompt  →  learn style or apply best practices",
        "④ Generate Code  →  full files with imports, classes, assertions",
        "⑤ Validate & Heal  →  syntax check + auto LLM fix loop",
        "⑥ Review & Apply  →  diff + Allow/Skip before writing files",
    ]
    add_multiline_text_box(slide, steps,
                           Inches(4.78), Inches(3.45), Inches(4.05), Inches(1.25),
                           font_size=Pt(8.8), color=DARK)

    # INPUTS / OUTPUTS side by side
    draw_section_card(slide, "Inputs", Inches(4.6), Inches(4.88), Inches(2.0), Inches(1.98))
    inputs = [
        "Test cases (JSON or text)",
        "Automation type: UI / API",
        "Project path or file map",
        "Optional: DOM, API details",
    ]
    add_multiline_text_box(slide, inputs,
                           Inches(4.78), Inches(5.12), Inches(1.8), Inches(1.65),
                           font_size=Pt(9), color=DARK, bullet=True)

    draw_section_card(slide, "Outputs", Inches(6.72), Inches(4.88), Inches(2.18), Inches(1.98))
    outputs = [
        "Runnable test scripts",
        "Validation report (per-file)",
        "Healing log (auto-fix record)",
        "Review mode (diff + Allow/Skip)",
    ]
    add_multiline_text_box(slide, outputs,
                           Inches(6.9), Inches(5.12), Inches(1.95), Inches(1.65),
                           font_size=Pt(9), color=DARK, bullet=True)

    # ── FAR RIGHT COLUMN ───────────────────────────────────────────────────
    # BUSINESS BENEFITS
    draw_section_card(slide, "Business Benefits", Inches(9.1), Inches(3.2), Inches(3.9), Inches(3.66))
    benefits = [
        ("⚡ Faster Delivery",     "Hours → minutes for new test scripts"),
        ("🔁 Zero Divergence",     "Code fits existing project; no refactor"),
        ("🛡️ Consistent Quality",  "Enforces team conventions automatically"),
        ("☁️ Cloud-Ready",         "Hosted MCP; no local setup required"),
        ("🔍 Full Traceability",   "Validation report + healing log per run"),
        ("🤖 Greenfield Support",  "Best-practice standards when no base exists"),
    ]
    y = Inches(3.48)
    for icon_label, desc in benefits:
        add_text_box(slide, icon_label, Inches(9.28), y, Inches(3.6), Inches(0.22),
                     font_size=Pt(9.5), bold=True, color=DARK)
        add_text_box(slide, desc, Inches(9.28), y + Inches(0.2), Inches(3.6), Inches(0.2),
                     font_size=Pt(8.5), color=MID_GRAY)
        y += Inches(0.52)

    # TECH TAGS
    draw_section_card(slide, "Languages & Frameworks", Inches(0.3), Inches(6.92 - 0.1), Inches(8.6), Inches(0.0))
    tags = ["Python", "Java", "JavaScript/TS", "C#", "Selenium", "Playwright", "Cypress",
            "RestAssured", "requests", "supertest", "MCP Server"]
    x = Inches(0.35)
    for tag in tags:
        w = Inches(len(tag) * 0.085 + 0.35)
        add_rect(slide, x, Inches(6.72), w, Inches(0.28), fill_rgb=DARK)
        add_text_box(slide, tag, x + Inches(0.04), Inches(6.73), w - Inches(0.06), Inches(0.25),
                     font_size=Pt(8), bold=True, color=WHITE)
        x += w + Inches(0.07)


# ── SLIDE 2: Test Analyser Agent ─────────────────────────────────────────────

def build_slide_2(slide):
    draw_chrome(
        slide,
        "Test Analyser Agent",
        "An intelligent AI agent that reads your existing test project, understands every test's intent, and exports\n"
        "a professionally styled Excel workbook — turning automation code into stakeholder-ready documentation."
    )

    # Stat strip
    stats = [
        ("3",       "Output Formats"),
        ("500+",    "Tests / Run"),
        ("4+",      "Languages"),
        ("Read-Only","Zero Risk"),
    ]
    for i, (num, lbl) in enumerate(stats):
        draw_stat_block(slide, num, lbl, Inches(0.4 + i * 1.8), Inches(2.7))

    # ── LEFT COLUMN ─────────────────────────────────────────────────────────
    # WHAT IS IT
    draw_section_card(slide, "What Is It", Inches(0.3), Inches(3.2), Inches(4.1), Inches(1.4))
    add_multiline_text_box(
        slide,
        ["A read-only AI agent within Accenture's QEAF. It scans your test automation project, extracts every test method, "
         "and uses LLM batch conversion to produce a professionally styled Excel workbook — ready to share with "
         "PMs, BA teams, or auditors without any manual editing."],
        Inches(0.48), Inches(3.45), Inches(3.9), Inches(1.1),
        font_size=Pt(9.5), color=MID_GRAY
    )

    # KEY CAPABILITIES
    draw_section_card(slide, "Key Capabilities", Inches(0.3), Inches(4.72), Inches(4.1), Inches(2.15))
    caps = [
        "Language Auto-Detection — identifies Python, Java, JS/TS, C# from markers",
        "Test Discovery — finds all test methods with class, file, and line number",
        "LLM Batch Conversion — groups tests in 15s; AI generates readable descriptions",
        "Large Project Handling — folder-level counts + user selection for >20 files",
        "Graceful Fallback — readable stubs if LLM fails on any batch",
        "Dual Delivery — writes .xlsx to disk or returns base64 bytes for cloud use",
    ]
    add_multiline_text_box(slide, caps,
                           Inches(0.5), Inches(4.97), Inches(3.85), Inches(1.85),
                           font_size=Pt(9), color=DARK, bullet=True)

    # ── MIDDLE COLUMN ───────────────────────────────────────────────────────
    # OUTPUT FORMATS
    draw_section_card(slide, "Output Formats", Inches(4.6), Inches(3.2), Inches(4.3), Inches(1.55))
    formats = [
        ("BDD",          "Feature · Scenario · Given · When · Then · Tags"),
        ("Plain",        "Test ID · Title · Preconditions · Steps · Expected · Priority"),
        ("Step-by-Step", "Test ID · Title · Step # · Action · Expected Result"),
    ]
    y = Inches(3.45)
    for fmt, cols in formats:
        add_text_box(slide, fmt, Inches(4.78), y, Inches(4.05), Inches(0.22),
                     font_size=Pt(9.5), bold=True, color=PURPLE)
        add_text_box(slide, cols, Inches(4.78), y + Inches(0.2), Inches(4.05), Inches(0.18),
                     font_size=Pt(8), color=MID_GRAY)
        y += Inches(0.44)

    # HOW IT WORKS
    draw_section_card(slide, "How It Works", Inches(4.6), Inches(4.88), Inches(4.3), Inches(1.4))
    steps = [
        "① Detect Language  →  check project markers & file extensions",
        "② Discover Test Files  →  walk project, extract test methods",
        "③ Elicit Selection  →  folder counts shown if >20 files",
        "④ LLM Batch Convert  →  batches of 15 → structured descriptions",
        "⑤ Build Rows  →  merge LLM output with source metadata",
        "⑥ Style & Export  →  styled xlsx with headers, colors, filters",
    ]
    add_multiline_text_box(slide, steps,
                           Inches(4.78), Inches(5.12), Inches(4.05), Inches(1.1),
                           font_size=Pt(8.8), color=DARK)

    # INPUTS / OUTPUTS
    draw_section_card(slide, "Inputs", Inches(4.6), Inches(6.38), Inches(2.0), Inches(0.52))
    inputs = ["Project path or file map", "Format: bdd / plain / step_by_step", "Optional: language, output path"]
    add_multiline_text_box(slide, inputs,
                           Inches(4.78), Inches(6.6), Inches(1.85), Inches(0.42),
                           font_size=Pt(8.5), color=DARK, bullet=True)

    draw_section_card(slide, "Outputs", Inches(6.72), Inches(6.38), Inches(2.18), Inches(0.52))
    outputs = ["Styled Excel (.xlsx) workbook", "Test count + feature list", "Summary (e.g. '47 tests, 5 classes')"]
    add_multiline_text_box(slide, outputs,
                           Inches(6.9), Inches(6.6), Inches(1.95), Inches(0.42),
                           font_size=Pt(8.5), color=DARK, bullet=True)

    # ── FAR RIGHT COLUMN ───────────────────────────────────────────────────
    # BUSINESS BENEFITS
    draw_section_card(slide, "Business Benefits", Inches(9.1), Inches(3.2), Inches(3.9), Inches(3.66))
    benefits = [
        ("📋 Instant Documentation", "Code → readable specs in minutes"),
        ("🤝 Stakeholder Visibility", "Excel every stakeholder can open"),
        ("✅ Audit-Ready Output",    "Structured, formatted, shareable"),
        ("🔒 Zero Risk",             "Read-only — never modifies project"),
        ("📊 BDD & PM-Friendly",     "Three formats match any team process"),
        ("🔁 Large Scale",           "Handles 500+ tests with folder controls"),
    ]
    y = Inches(3.48)
    for icon_label, desc in benefits:
        add_text_box(slide, icon_label, Inches(9.28), y, Inches(3.6), Inches(0.22),
                     font_size=Pt(9.5), bold=True, color=DARK)
        add_text_box(slide, desc, Inches(9.28), y + Inches(0.2), Inches(3.6), Inches(0.2),
                     font_size=Pt(8.5), color=MID_GRAY)
        y += Inches(0.52)

    # TECH TAGS
    tags = ["Python", "Java", "JavaScript/TS", "C#", "pytest", "JUnit/TestNG",
            "Jest/Mocha", "NUnit", "openpyxl", "MCP Server"]
    x = Inches(0.35)
    for tag in tags:
        w = Inches(len(tag) * 0.085 + 0.35)
        add_rect(slide, x, Inches(6.72), w, Inches(0.28), fill_rgb=DARK)
        add_text_box(slide, tag, x + Inches(0.04), Inches(6.73), w - Inches(0.06), Inches(0.25),
                     font_size=Pt(8), bold=True, color=WHITE)
        x += w + Inches(0.07)


# ── Architecture slide helpers ────────────────────────────────────────────────

def draw_arch_chrome(slide, agent_name, slide_label="High-Level Architecture"):
    """Slim dark header for architecture slides + full dark background."""
    # Full slide background
    add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=ARCH_BG)

    # Purple top bar
    add_rect(slide, 0, 0, SLIDE_W, Inches(0.06), fill_rgb=PURPLE)

    # Dark header band
    add_rect(slide, 0, Inches(0.06), SLIDE_W, Inches(0.68), fill_rgb=DARK)

    # "Accenture." wordmark
    tb = slide.shapes.add_textbox(Inches(0.4), Inches(0.08), Inches(3), Inches(0.45))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    r1 = p.add_run(); r1.text = "Accenture"
    r1.font.name = "Segoe UI"; r1.font.size = Pt(15); r1.font.bold = True
    r1.font.color.rgb = WHITE
    r2 = p.add_run(); r2.text = "."
    r2.font.name = "Segoe UI"; r2.font.size = Pt(15); r2.font.bold = True
    r2.font.color.rgb = PURPLE

    # Slide context tag (right of header)
    add_text_box(slide, "QUALITY ENGINEERING AGENTIC FRAMEWORK",
                 Inches(3.5), Inches(0.16), Inches(7.5), Inches(0.28),
                 font_size=Pt(7), color=RGBColor(0x77, 0x77, 0x77),
                 align=PP_ALIGN.CENTER)

    # "Architecture" badge
    add_rect(slide, Inches(11.35), Inches(0.14), Inches(1.7), Inches(0.32), fill_rgb=DARK_PURPLE)
    add_text_box(slide, "ARCHITECTURE", Inches(11.37), Inches(0.16), Inches(1.66), Inches(0.28),
                 font_size=Pt(7), bold=True, color=PURPLE, align=PP_ALIGN.CENTER)

    # Subtitle band (light purple)
    add_rect(slide, 0, Inches(0.74), SLIDE_W, Inches(0.62), fill_rgb=RGBColor(0xF0, 0xE8, 0xFF))

    # Agent name
    tb = slide.shapes.add_textbox(Inches(0.4), Inches(0.78), Inches(9), Inches(0.5))
    tf = tb.text_frame; tf.word_wrap = False
    p = tf.paragraphs[0]
    words = agent_name.split(" ", 1)
    r1 = p.add_run(); r1.text = words[0] + " "
    r1.font.name = "Segoe UI"; r1.font.size = Pt(20); r1.font.bold = False
    r1.font.color.rgb = DARK
    if len(words) > 1:
        r2 = p.add_run(); r2.text = words[1]
        r2.font.name = "Segoe UI"; r2.font.size = Pt(20); r2.font.bold = True
        r2.font.color.rgb = PURPLE

    # Slide label (right side of subtitle band)
    add_text_box(slide, slide_label.upper(),
                 Inches(9.5), Inches(0.85), Inches(3.5), Inches(0.28),
                 font_size=Pt(8), bold=True, color=DARK_PURPLE,
                 align=PP_ALIGN.RIGHT)

    # Purple divider
    add_rect(slide, 0, Inches(1.36), SLIDE_W, Inches(0.04), fill_rgb=PURPLE)

    # Footer
    add_rect(slide, 0, Inches(7.1), SLIDE_W, Inches(0.4), fill_rgb=DARK)
    add_text_box(slide, "Quality Engineering Agentic Framework  |  Accenture",
                 Inches(0.4), Inches(7.13), Inches(9), Inches(0.26),
                 font_size=Pt(7.5), color=RGBColor(0x77, 0x77, 0x77))
    add_text_box(slide, "© 2025 Accenture. All rights reserved.",
                 Inches(9.5), Inches(7.13), Inches(3.5), Inches(0.26),
                 font_size=Pt(7.5), color=RGBColor(0x55, 0x55, 0x55), align=PP_ALIGN.RIGHT)


def draw_pipeline_box(slide, x, y, w, h, num, title, bullets,
                      box_bg=None, border_color=None, highlight_llm=False):
    """Draw a single pipeline stage box."""
    bg = box_bg or (STAGE_LLM if highlight_llm else STAGE_BG)
    border = border_color or PURPLE

    # Main box
    add_rect(slide, x, y, w, h, fill_rgb=bg)

    # Left accent border
    add_rect(slide, x, y, Inches(0.055), h, fill_rgb=border)

    # Top accent stripe
    add_rect(slide, x, y, w, Inches(0.04), fill_rgb=border)

    # Stage number (top-left)
    add_text_box(slide, num,
                 x + Inches(0.1), y + Inches(0.06), Inches(0.35), Inches(0.32),
                 font_size=Pt(9), bold=True, color=border)

    # Stage title (allow 2 lines)
    add_text_box(slide, title,
                 x + Inches(0.1), y + Inches(0.34), w - Inches(0.15), Inches(0.5),
                 font_size=Pt(9.5), bold=True, color=DARK)

    # Thin divider below title
    add_rect(slide, x + Inches(0.1), y + Inches(0.88), w - Inches(0.2), Inches(0.02),
             fill_rgb=RGBColor(0xCC, 0xBB, 0xEE))

    # Bullet content
    add_multiline_text_box(slide, bullets,
                           x + Inches(0.1), y + Inches(0.95), w - Inches(0.15),
                           h - Inches(1.05),
                           font_size=Pt(8.2), color=ARCH_GRAY, bullet=True)


def draw_arrow(slide, x, y_mid, w=Inches(0.22), h=Inches(0.28), color=None):
    """Draw a right-pointing arrow as a filled shape between pipeline boxes."""
    c = color or PURPLE
    # Shaft
    shaft_h = Inches(0.08)
    add_rect(slide, x, y_mid - shaft_h / 2, w * 0.6, shaft_h, fill_rgb=c)
    # Arrowhead as a right-pointing triangle: draw as 3 thin rects approximated
    head_x = x + w * 0.55
    head_w = w * 0.45
    rows = 4
    for i in range(rows):
        row_h = h / rows
        row_inset = (rows - 1 - i) * (head_w / rows)
        add_rect(slide, head_x + row_inset,
                 y_mid - h / 2 + i * row_h,
                 head_w - row_inset, row_h,
                 fill_rgb=c)


def draw_arch_integration_bar(slide, tags):
    """Bottom integration tag row (light band with labelled chips)."""
    bar_y = Inches(6.22)
    bar_h = Inches(0.56)
    add_rect(slide, 0, bar_y, SLIDE_W, bar_h, fill_rgb=RGBColor(0xED, 0xE8, 0xF5))
    add_rect(slide, 0, bar_y, SLIDE_W, Inches(0.03), fill_rgb=PURPLE)

    add_text_box(slide, "INTEGRATIONS",
                 Inches(0.35), bar_y + Inches(0.15), Inches(1.2), Inches(0.28),
                 font_size=Pt(7.5), bold=True, color=PURPLE)

    x = Inches(1.55)
    for tag, color in tags:
        tag_w = Inches(len(tag) * 0.083 + 0.42)
        add_rect(slide, x, bar_y + Inches(0.1), tag_w, Inches(0.34), fill_rgb=color)
        add_text_box(slide, tag, x + Inches(0.07), bar_y + Inches(0.12),
                     tag_w - Inches(0.1), Inches(0.28),
                     font_size=Pt(8), bold=True, color=WHITE)
        x += tag_w + Inches(0.1)


def draw_io_box(slide, x, y, w, h, label, items, bg, accent):
    """Draw the Inputs or Outputs endpoint box."""
    add_rect(slide, x, y, w, h, fill_rgb=bg)
    add_rect(slide, x, y, Inches(0.055), h, fill_rgb=accent)
    add_rect(slide, x, y, w, Inches(0.04), fill_rgb=accent)
    add_text_box(slide, label,
                 x + Inches(0.1), y + Inches(0.08), w - Inches(0.14), Inches(0.28),
                 font_size=Pt(8.5), bold=True, color=accent)
    add_rect(slide, x + Inches(0.1), y + Inches(0.4), w - Inches(0.2), Inches(0.02),
             fill_rgb=RGBColor(0xBB, 0xCC, 0xEE))
    add_multiline_text_box(slide, items,
                           x + Inches(0.1), y + Inches(0.48), w - Inches(0.15),
                           h - Inches(0.58),
                           font_size=Pt(8.2), color=ARCH_GRAY, bullet=True)


# ── SLIDE 3: Standalone Automation Agent — Architecture ──────────────────────

def build_slide_arch_standalone(slide):
    draw_arch_chrome(slide, "Standalone Automation Agent")

    # ── Layout constants ──────────────────────────────────────────────────
    BOX_TOP = Inches(1.46)
    BOX_H   = Inches(4.66)   # fills to ~6.12"

    # x positions (calculated to fit 13.33" width)
    X_INPUT   = Inches(0.30)
    W_INPUT   = Inches(1.65)
    W_ARROW   = Inches(0.22)
    W_STAGE   = Inches(1.55)
    GAP       = Inches(0.18)
    W_OUTPUT  = Inches(2.0)

    x_arr1    = X_INPUT + W_INPUT
    x_s1      = x_arr1 + W_ARROW
    x_arr2    = x_s1 + W_STAGE
    x_s2      = x_arr2 + GAP
    x_arr3    = x_s2 + W_STAGE
    x_s3      = x_arr3 + GAP
    x_arr4    = x_s3 + W_STAGE
    x_s4      = x_arr4 + GAP
    x_arr5    = x_s4 + W_STAGE
    x_s5      = x_arr5 + GAP
    x_arr_out = x_s5 + W_STAGE
    x_output  = x_arr_out + W_ARROW

    y_mid = BOX_TOP + BOX_H / 2

    # ── Inputs ────────────────────────────────────────────────────────────
    draw_io_box(slide, X_INPUT, BOX_TOP, W_INPUT, BOX_H,
                "INPUTS",
                ["Test cases (JSON or text)",
                 "Automation type: UI / API",
                 "Project path or file map",
                 "Optional: DOM snapshot",
                 "Optional: API base URL / auth",
                 "Language override (optional)"],
                INPUT_BG, BLUE_ACCENT)

    draw_arrow(slide, x_arr1, y_mid)

    # ── Pipeline stages ───────────────────────────────────────────────────
    draw_pipeline_box(slide, x_s1, BOX_TOP, W_STAGE, BOX_H,
                      "01", "Framework\nProfiler",
                      ["Scan project markers\n(pom.xml, package.json)",
                       "Auto-detect language\n& test framework",
                       "Map directory layout\nand file structure",
                       "Identify module system\n(ESM vs CommonJS)"])

    draw_arrow(slide, x_arr2, y_mid)

    draw_pipeline_box(slide, x_s2, BOX_TOP, W_STAGE, BOX_H,
                      "02", "Pattern\nExtractor",
                      ["Extract class & method\nsignatures from project",
                       "Index page objects,\nAPI clients, helpers",
                       "Select sample test\nfor style analysis",
                       "Discover config files\n(base URL, auth scheme)"])

    draw_arrow(slide, x_arr3, y_mid)

    draw_pipeline_box(slide, x_s3, BOX_TOP, W_STAGE, BOX_H,
                      "03", "Adaptive\nPrompt Builder",
                      ["Learn team coding style\n& fixture conventions",
                       "Build adaptive prompt\nwith style contract",
                       "Apply 3-step fallback\nladder (full→lean→min)",
                       "Cap context to prevent\nhost rejection errors"])

    draw_arrow(slide, x_arr4, y_mid)

    draw_pipeline_box(slide, x_s4, BOX_TOP, W_STAGE, BOX_H,
                      "04", "LLM Code\nGenerator",
                      ["Generate complete test\nscripts per language",
                       "Reuses only real\nmethods from codebase",
                       "Full imports, classes,\nassertions included",
                       "Powered by Claude /\nCopilot via MCP host"],
                      highlight_llm=True)

    draw_arrow(slide, x_arr5, y_mid)

    draw_pipeline_box(slide, x_s5, BOX_TOP, W_STAGE, BOX_H,
                      "05", "Validate\n& Heal",
                      ["Static syntax / parse\ncheck on every file",
                       "Auto-request LLM fix\nfor broken files",
                       "Up to 2 healing passes\nper file",
                       "Produce validation\nreport + healing log"])

    draw_arrow(slide, x_arr_out, y_mid)

    # ── Outputs ───────────────────────────────────────────────────────────
    draw_io_box(slide, x_output, BOX_TOP, W_OUTPUT, BOX_H,
                "OUTPUTS",
                ["Runnable test scripts\n(Python / Java / JS / C#)",
                 "Validation report\n(per-file syntax status)",
                 "Healing log\n(auto-fix record)",
                 "Review mode: diff +\nAllow/Skip per file",
                 "Or: direct apply\nto disk (local mode)"],
                OUTPUT_BG, GREEN_ACCENT)

    # ── Integration bar ───────────────────────────────────────────────────
    draw_arch_integration_bar(slide, [
        ("MCP Server (hosted)",      DARK_PURPLE),
        ("Claude / GitHub Copilot",  RGBColor(0x50, 0x00, 0x90)),
        ("Sampling + Token Fallback",RGBColor(0x33, 0x33, 0x55)),
        ("Selenium / Playwright",    RGBColor(0x33, 0x33, 0x55)),
        ("Cypress / RestAssured",    RGBColor(0x33, 0x33, 0x55)),
        ("VS Code Extension",        RGBColor(0x33, 0x33, 0x55)),
    ])


# ── SLIDE 4: Test Analyser Agent — Architecture ───────────────────────────────

def build_slide_arch_test_analyser(slide):
    draw_arch_chrome(slide, "Test Analyser Agent")

    BOX_TOP = Inches(1.46)
    BOX_H   = Inches(4.66)

    X_INPUT   = Inches(0.30)
    W_INPUT   = Inches(1.65)
    W_ARROW   = Inches(0.22)
    W_STAGE   = Inches(1.55)
    GAP       = Inches(0.18)
    W_OUTPUT  = Inches(2.0)

    x_arr1    = X_INPUT + W_INPUT
    x_s1      = x_arr1 + W_ARROW
    x_arr2    = x_s1 + W_STAGE
    x_s2      = x_arr2 + GAP
    x_arr3    = x_s2 + W_STAGE
    x_s3      = x_arr3 + GAP
    x_arr4    = x_s3 + W_STAGE
    x_s4      = x_arr4 + GAP
    x_arr5    = x_s4 + W_STAGE
    x_s5      = x_arr5 + GAP
    x_arr_out = x_s5 + W_STAGE
    x_output  = x_arr_out + W_ARROW

    y_mid = BOX_TOP + BOX_H / 2

    # ── Inputs ────────────────────────────────────────────────────────────
    draw_io_box(slide, X_INPUT, BOX_TOP, W_INPUT, BOX_H,
                "INPUTS",
                ["Project path (local)\nor file map (remote)",
                 "Output format:\nbdd / plain / step_by_step",
                 "Language override\n(optional)",
                 "Output path\n(optional)",
                 "max_tests cap\n(default: 500)"],
                INPUT_BG, BLUE_ACCENT)

    draw_arrow(slide, x_arr1, y_mid)

    # ── Pipeline stages ───────────────────────────────────────────────────
    draw_pipeline_box(slide, x_s1, BOX_TOP, W_STAGE, BOX_H,
                      "01", "Language\nDetector",
                      ["Check project markers\n(pom.xml → java, etc.)",
                       "Scan file extensions\nif no markers found",
                       "Identify test framework\n(pytest, JUnit, Jest…)",
                       "Fall back to Python\nif language unknown"])

    draw_arrow(slide, x_arr2, y_mid)

    draw_pipeline_box(slide, x_s2, BOX_TOP, W_STAGE, BOX_H,
                      "02", "Test\nDiscovery",
                      ["Walk project files\n(disk or file map)",
                       "Filter to test files\nusing per-lang regex",
                       "Extract test method\nnames + line numbers",
                       "Record class name\nand file path per test"])

    draw_arrow(slide, x_arr3, y_mid)

    draw_pipeline_box(slide, x_s3, BOX_TOP, W_STAGE, BOX_H,
                      "03", "Scope\nSelector",
                      ["Count tests per folder\nfor large projects",
                       "Elicit folder selection\nwhen >20 test files",
                       "Apply max_tests cap\n(default 500)",
                       "Confirm scope before\nLLM processing begins"])

    draw_arrow(slide, x_arr4, y_mid)

    draw_pipeline_box(slide, x_s4, BOX_TOP, W_STAGE, BOX_H,
                      "04", "LLM Batch\nConverter",
                      ["Group tests in\nbatches of 15",
                       "Convert each batch to\nBDD / plain / step format",
                       "Parse JSON response\nfrom model output",
                       "Fallback to readable\nstubs on failure"],
                      highlight_llm=True)

    draw_arrow(slide, x_arr5, y_mid)

    draw_pipeline_box(slide, x_s5, BOX_TOP, W_STAGE, BOX_H,
                      "05", "Excel\nBuilder",
                      ["Merge LLM output with\nsource file metadata",
                       "Expand step arrays\nfor step-by-step format",
                       "Apply professional\nstyles via openpyxl",
                       "Headers, alt-row colors,\nfrozen row, auto-filter"])

    draw_arrow(slide, x_arr_out, y_mid)

    # ── Outputs ───────────────────────────────────────────────────────────
    draw_io_box(slide, x_output, BOX_TOP, W_OUTPUT, BOX_H,
                "OUTPUTS",
                ["Styled Excel .xlsx\n(BDD / plain / step-by-step)",
                 "Total test count\n& feature list",
                 "Summary string\n(e.g. '47 tests, 5 classes')",
                 "Base64 bytes (remote)\nor disk file (local)",
                 "Read-only: source\nproject unchanged"],
                OUTPUT_BG, GREEN_ACCENT)

    # ── Integration bar ───────────────────────────────────────────────────
    draw_arch_integration_bar(slide, [
        ("MCP Server (hosted)",      DARK_PURPLE),
        ("Claude / GitHub Copilot",  RGBColor(0x50, 0x00, 0x90)),
        ("openpyxl (Excel engine)",  RGBColor(0x33, 0x33, 0x55)),
        ("pytest / JUnit / Jest",    RGBColor(0x33, 0x33, 0x55)),
        ("NUnit / MSTest",           RGBColor(0x33, 0x33, 0x55)),
        ("VS Code Extension",        RGBColor(0x33, 0x33, 0x55)),
    ])


# ── SLIDE 5: Combined End-to-End Architecture ────────────────────────────────

def draw_compact_stage(slide, x, y, w, h, num, title, bullets, bg, llm=False):
    """Compact pipeline box for the combined architecture slide."""
    border = PURPLE
    box_bg = RGBColor(0xDD, 0xC4, 0xFF) if llm else bg
    add_rect(slide, x, y, w, h, fill_rgb=box_bg)
    add_rect(slide, x, y, Inches(0.05), h, fill_rgb=border)
    add_rect(slide, x, y, w, Inches(0.035), fill_rgb=border)
    add_text_box(slide, num,
                 x + Inches(0.09), y + Inches(0.04), Inches(0.28), Inches(0.2),
                 font_size=Pt(7.5), bold=True, color=border)
    add_text_box(slide, title,
                 x + Inches(0.09), y + Inches(0.22), w - Inches(0.13), Inches(0.38),
                 font_size=Pt(8.8), bold=True, color=DARK)
    add_rect(slide, x + Inches(0.09), y + Inches(0.63), w - Inches(0.18), Inches(0.02),
             fill_rgb=RGBColor(0xCC, 0xBB, 0xEE))
    add_multiline_text_box(slide, bullets,
                           x + Inches(0.09), y + Inches(0.68), w - Inches(0.13),
                           h - Inches(0.75),
                           font_size=Pt(7.5), color=ARCH_GRAY, bullet=True)


def draw_compact_io(slide, x, y, w, h, label, items, bg, accent):
    """Compact input/output endpoint box."""
    add_rect(slide, x, y, w, h, fill_rgb=bg)
    add_rect(slide, x, y, Inches(0.05), h, fill_rgb=accent)
    add_rect(slide, x, y, w, Inches(0.035), fill_rgb=accent)
    add_text_box(slide, label,
                 x + Inches(0.09), y + Inches(0.05), w - Inches(0.13), Inches(0.24),
                 font_size=Pt(8), bold=True, color=accent)
    add_rect(slide, x + Inches(0.09), y + Inches(0.32), w - Inches(0.18), Inches(0.02),
             fill_rgb=RGBColor(0xBB, 0xCC, 0xEE))
    add_multiline_text_box(slide, items,
                           x + Inches(0.09), y + Inches(0.38), w - Inches(0.13),
                           h - Inches(0.44),
                           font_size=Pt(7.5), color=ARCH_GRAY, bullet=True)


def draw_down_arrow(slide, x_center, y_top, height):
    """Draw a vertical down-arrow at x_center."""
    shaft_w = Inches(0.09)
    head_h  = Inches(0.14)
    shaft_h = height - head_h
    add_rect(slide, x_center - shaft_w / 2, y_top, shaft_w, shaft_h, fill_rgb=PURPLE)
    rows = 5
    head_w = Inches(0.26)
    for i in range(rows):
        row_h = head_h / rows
        row_w = head_w * (i + 1) / rows
        add_rect(slide, x_center - row_w / 2,
                 y_top + shaft_h + i * row_h,
                 row_w, row_h, fill_rgb=PURPLE)


def build_slide_combined_arch(slide):
    """Single combined slide: both agents + data-flow handshake between them."""
    draw_arch_chrome(slide, "QEAF End-to-End Agent Pipeline",
                     "Combined Agent Architecture")

    # ── Layout constants ──────────────────────────────────────────────────
    PIPE_H = Inches(1.68)
    LBL_H  = Inches(0.28)
    ARROW_ZONE = Inches(0.12)   # gap used for down-arrows between sections

    # Pipeline x-positions — same across both agent rows
    X_LEFT = Inches(0.30)
    W_IN   = Inches(1.28)
    W_ARR  = Inches(0.17)
    W_STG  = Inches(1.66)
    GAP    = Inches(0.16)
    W_OUT  = Inches(1.45)

    x_arr1    = X_LEFT + W_IN
    x_s1      = x_arr1 + W_ARR
    x_arr2    = x_s1 + W_STG
    x_s2      = x_arr2 + GAP
    x_arr3    = x_s2 + W_STG
    x_s3      = x_arr3 + GAP
    x_arr4    = x_s3 + W_STG
    x_s4      = x_arr4 + GAP
    x_arr5    = x_s4 + W_STG
    x_s5      = x_arr5 + GAP
    x_arr_out = x_s5 + W_STG
    x_output  = x_arr_out + W_ARR

    X_CENTER = SLIDE_W / 2   # used for down-arrows

    # ── AGENT 1 LABEL ─────────────────────────────────────────────────────
    A1_LBL_Y = Inches(1.38)
    add_rect(slide, 0, A1_LBL_Y, SLIDE_W, LBL_H,
             fill_rgb=RGBColor(0xE8, 0xD8, 0xFF))
    add_rect(slide, 0, A1_LBL_Y, Inches(0.06), LBL_H, fill_rgb=PURPLE)
    add_text_box(slide, "① TEST ANALYSER AGENT",
                 Inches(0.2), A1_LBL_Y + Inches(0.05), Inches(4.5), Inches(0.2),
                 font_size=Pt(9), bold=True, color=PURPLE)
    add_text_box(slide,
                 "Reads your existing test project and exports structured test case specifications",
                 Inches(4.8), A1_LBL_Y + Inches(0.06), Inches(8.3), Inches(0.18),
                 font_size=Pt(8), color=MID_GRAY)

    # ── AGENT 1 PIPELINE ──────────────────────────────────────────────────
    A1_Y   = A1_LBL_Y + LBL_H
    y_mid1 = A1_Y + PIPE_H / 2

    draw_compact_io(slide, X_LEFT, A1_Y, W_IN, PIPE_H, "INPUT",
                    ["Test project\n(path / file map)", "Format choice",
                     "Language override"],
                    INPUT_BG, BLUE_ACCENT)
    draw_arrow(slide, x_arr1, y_mid1)

    draw_compact_stage(slide, x_s1, A1_Y, W_STG, PIPE_H, "01",
                       "Language\nDetector",
                       ["Detect from project markers", "Identify test framework"],
                       STAGE_BG)
    draw_arrow(slide, x_arr2, y_mid1)

    draw_compact_stage(slide, x_s2, A1_Y, W_STG, PIPE_H, "02",
                       "Test\nDiscovery",
                       ["Walk files, extract methods", "Capture class + line numbers"],
                       STAGE_BG)
    draw_arrow(slide, x_arr3, y_mid1)

    draw_compact_stage(slide, x_s3, A1_Y, W_STG, PIPE_H, "03",
                       "Scope\nSelector",
                       ["Folder counts for >20 files", "User selects scope (≤500)"],
                       STAGE_BG)
    draw_arrow(slide, x_arr4, y_mid1)

    draw_compact_stage(slide, x_s4, A1_Y, W_STG, PIPE_H, "04",
                       "LLM Batch\nConverter",
                       ["Batch-convert tests (15/batch)", "BDD / plain / step format"],
                       STAGE_BG, llm=True)
    draw_arrow(slide, x_arr5, y_mid1)

    draw_compact_stage(slide, x_s5, A1_Y, W_STG, PIPE_H, "05",
                       "Excel\nBuilder",
                       ["Build styled rows per format", "Export .xlsx with filters"],
                       STAGE_BG)
    draw_arrow(slide, x_arr_out, y_mid1)

    draw_compact_io(slide, x_output, A1_Y, W_OUT, PIPE_H, "OUTPUT",
                    ["Structured test cases",
                     "BDD / plain / step-by-step",
                     "Test titles, steps,\nexpected results"],
                    OUTPUT_BG, GREEN_ACCENT)

    # ── DOWN ARROW → HANDSHAKE ────────────────────────────────────────────
    ARW1_Y = A1_Y + PIPE_H + Inches(0.02)
    draw_down_arrow(slide, X_CENTER, ARW1_Y, Inches(0.2))

    # ── HANDSHAKE BAND ────────────────────────────────────────────────────
    HS_Y = ARW1_Y + Inches(0.22)
    HS_H = Inches(0.84)
    HS_BG = RGBColor(0xFF, 0xF3, 0xFF)

    add_rect(slide, 0, HS_Y, SLIDE_W, HS_H, fill_rgb=HS_BG)
    add_rect(slide, 0, HS_Y, SLIDE_W, Inches(0.04), fill_rgb=PURPLE)
    add_rect(slide, 0, HS_Y + HS_H - Inches(0.04), SLIDE_W,
             Inches(0.04), fill_rgb=PURPLE)

    # Left block: Analyser output description
    add_rect(slide, Inches(0.3), HS_Y + Inches(0.08),
             Inches(3.8), HS_H - Inches(0.18),
             fill_rgb=RGBColor(0xEE, 0xE0, 0xFF))
    add_rect(slide, Inches(0.3), HS_Y + Inches(0.08),
             Inches(0.05), HS_H - Inches(0.18), fill_rgb=GREEN_ACCENT)
    add_text_box(slide, "ANALYSER OUTPUT",
                 Inches(0.42), HS_Y + Inches(0.1), Inches(3.5), Inches(0.2),
                 font_size=Pt(7.5), bold=True, color=GREEN_ACCENT)
    add_text_box(slide,
                 "Structured test cases in BDD, plain, or step-by-step format — "
                 "each test converted to human-readable title, steps & expected result",
                 Inches(0.42), HS_Y + Inches(0.32), Inches(3.6), Inches(0.46),
                 font_size=Pt(8), color=DARK)

    # Centre: large arrow + handshake label
    add_text_box(slide, "⟶",
                 Inches(4.4), HS_Y + Inches(0.14), Inches(1.5), Inches(0.45),
                 font_size=Pt(32), bold=True, color=PURPLE, align=PP_ALIGN.CENTER)
    add_text_box(slide, "DATA HANDSHAKE",
                 Inches(4.2), HS_Y + Inches(0.58), Inches(1.9), Inches(0.2),
                 font_size=Pt(7), bold=True, color=PURPLE, align=PP_ALIGN.CENTER)

    # Centre description
    add_text_box(slide,
                 "Passed as  test_cases  input\nJSON / text descriptions",
                 Inches(6.1), HS_Y + Inches(0.2), Inches(2.5), Inches(0.45),
                 font_size=Pt(8.5), bold=False, color=DARK, align=PP_ALIGN.CENTER)
    add_text_box(slide, "No manual transfer required",
                 Inches(6.1), HS_Y + Inches(0.58), Inches(2.5), Inches(0.2),
                 font_size=Pt(7.5), italic=True, color=MID_GRAY,
                 align=PP_ALIGN.CENTER)

    # Right block: Automation input description
    add_rect(slide, Inches(8.9), HS_Y + Inches(0.08),
             Inches(4.1), HS_H - Inches(0.18),
             fill_rgb=RGBColor(0xE5, 0xEF, 0xFF))
    add_rect(slide, Inches(8.9), HS_Y + Inches(0.08),
             Inches(0.05), HS_H - Inches(0.18), fill_rgb=BLUE_ACCENT)
    add_text_box(slide, "STANDALONE AGENT INPUT",
                 Inches(9.02), HS_Y + Inches(0.1), Inches(3.8), Inches(0.2),
                 font_size=Pt(7.5), bold=True, color=BLUE_ACCENT)
    add_text_box(slide,
                 "Drives prompt construction — test case titles & steps define what code "
                 "to generate; existing framework files define how to write it",
                 Inches(9.02), HS_Y + Inches(0.32), Inches(3.9), Inches(0.46),
                 font_size=Pt(8), color=DARK)

    # ── DOWN ARROW → AGENT 2 ──────────────────────────────────────────────
    ARW2_Y = HS_Y + HS_H + Inches(0.02)
    draw_down_arrow(slide, X_CENTER, ARW2_Y, Inches(0.2))

    # ── AGENT 2 LABEL ─────────────────────────────────────────────────────
    A2_LBL_Y = ARW2_Y + Inches(0.22)
    add_rect(slide, 0, A2_LBL_Y, SLIDE_W, LBL_H,
             fill_rgb=RGBColor(0xD8, 0xE8, 0xFF))
    add_rect(slide, 0, A2_LBL_Y, Inches(0.06), LBL_H, fill_rgb=BLUE_ACCENT)
    add_text_box(slide, "② STANDALONE AUTOMATION AGENT",
                 Inches(0.2), A2_LBL_Y + Inches(0.05), Inches(5), Inches(0.2),
                 font_size=Pt(9), bold=True, color=BLUE_ACCENT)
    add_text_box(slide,
                 "Profiles your automation framework and generates executable test scripts from the received test cases",
                 Inches(5.4), A2_LBL_Y + Inches(0.06), Inches(7.7), Inches(0.18),
                 font_size=Pt(8), color=MID_GRAY)

    # ── AGENT 2 PIPELINE ──────────────────────────────────────────────────
    A2_Y   = A2_LBL_Y + LBL_H
    y_mid2 = A2_Y + PIPE_H / 2

    draw_compact_io(slide, X_LEFT, A2_Y, W_IN, PIPE_H, "INPUT",
                    ["test_cases (from\nAnalyser output)",
                     "Project path\n/ file map",
                     "Automation type"],
                    INPUT_BG, BLUE_ACCENT)
    draw_arrow(slide, x_arr1, y_mid2)

    draw_compact_stage(slide, x_s1, A2_Y, W_STG, PIPE_H, "01",
                       "Framework\nProfiler",
                       ["Auto-detect language & framework", "Map project structure"],
                       STAGE_BG)
    draw_arrow(slide, x_arr2, y_mid2)

    draw_compact_stage(slide, x_s2, A2_Y, W_STG, PIPE_H, "02",
                       "Pattern\nExtractor",
                       ["Extract real methods & objects", "Discover config & base URLs"],
                       STAGE_BG)
    draw_arrow(slide, x_arr3, y_mid2)

    draw_compact_stage(slide, x_s3, A2_Y, W_STG, PIPE_H, "03",
                       "Adaptive\nPrompt Builder",
                       ["Learn team coding style", "3-step fallback ladder"],
                       STAGE_BG)
    draw_arrow(slide, x_arr4, y_mid2)

    draw_compact_stage(slide, x_s4, A2_Y, W_STG, PIPE_H, "04",
                       "LLM Code\nGenerator",
                       ["Generate complete test scripts", "Reuses only real methods"],
                       STAGE_BG, llm=True)
    draw_arrow(slide, x_arr5, y_mid2)

    draw_compact_stage(slide, x_s5, A2_Y, W_STG, PIPE_H, "05",
                       "Validate\n& Heal",
                       ["Syntax check all files", "Auto-fix up to 2 passes"],
                       STAGE_BG)
    draw_arrow(slide, x_arr_out, y_mid2)

    draw_compact_io(slide, x_output, A2_Y, W_OUT, PIPE_H, "OUTPUT",
                    ["Runnable test scripts\n(Python/Java/JS/C#)",
                     "Validation report",
                     "Healing log"],
                    OUTPUT_BG, GREEN_ACCENT)

    # ── INTEGRATION BAR ───────────────────────────────────────────────────
    draw_arch_integration_bar(slide, [
        ("MCP Server (hosted)",     DARK_PURPLE),
        ("Claude / Copilot (LLM)",  RGBColor(0x50, 0x00, 0x90)),
        ("openpyxl",                RGBColor(0x33, 0x33, 0x55)),
        ("Selenium / Playwright",   RGBColor(0x33, 0x33, 0x55)),
        ("Cypress / RestAssured",   RGBColor(0x33, 0x33, 0x55)),
        ("VS Code Extension",       RGBColor(0x33, 0x33, 0x55)),
    ])


# ── SLIDE 6: MCP-Based Architecture (Accenture light theme) ──────────────────

def build_slide_mcp_arch(slide):
    """Accenture-styled MCP architecture — detailed Test Analyser + Standalone Agent."""

    # === PALETTE ============================================================
    PRP  = PURPLE                           # A100FF – Accenture purple
    DPRP = DARK_PURPLE                      # 440088
    BLU  = RGBColor(0x22, 0x66, 0xDD)      # Blue – Standalone agent
    GRN  = GREEN_ACCENT                     # 00AA66 – Test Analyser
    LLM  = RGBColor(0x66, 0x00, 0xAA)      # LLM purple
    BG   = RGBColor(0xF7, 0xF5, 0xFA)      # Light lavender
    LGRD = RGBColor(0xBB, 0xBB, 0xCC)      # Light gray border

    F_MCP  = RGBColor(0xF0, 0xE8, 0xFF)
    F_TOOL = RGBColor(0xF8, 0xF5, 0xFF)
    F_TA   = RGBColor(0xEE, 0xF9, 0xF4)
    F_SA   = RGBColor(0xEE, 0xF2, 0xFF)
    F_HS   = RGBColor(0xFF, 0xF4, 0xFF)
    F_SCR  = RGBColor(0xEA, 0xF8, 0xF0)
    F_ART  = RGBColor(0xF2, 0xF0, 0xF8)
    F_USR  = RGBColor(0xFF, 0xFF, 0xFF)

    def rr(l, t, w, h, fill=None, brd=None, bw=Pt(1.5)):
        return add_rounded_rect(slide, l, t, w, h, fill, brd, bw)

    def tx(text, l, t, w, h, fs=Pt(8.5), bold=False, color=DARK,
           align=PP_ALIGN.LEFT, italic=False):
        return add_text_box(slide, text, l, t, w, h, font_size=fs, bold=bold,
                            color=color, align=align, italic=italic)

    def rc(l, t, w, h, fill=None):
        return add_rect(slide, l, t, w, h, fill_rgb=fill)

    # === BACKGROUND =========================================================
    rc(0, 0, SLIDE_W, SLIDE_H, fill=BG)

    # === ACCENTURE HEADER ===================================================
    rc(0, 0, SLIDE_W, Inches(0.06), fill=PRP)
    rc(0, Inches(0.06), SLIDE_W, Inches(0.66), fill=DARK)

    tb = slide.shapes.add_textbox(Inches(0.4), Inches(0.08), Inches(3), Inches(0.44))
    tf = tb.text_frame
    p  = tf.paragraphs[0]
    r1 = p.add_run(); r1.text = "Accenture"
    r1.font.name = "Segoe UI"; r1.font.size = Pt(15); r1.font.bold = True
    r1.font.color.rgb = WHITE
    r2 = p.add_run(); r2.text = "."
    r2.font.name = "Segoe UI"; r2.font.size = Pt(15); r2.font.bold = True
    r2.font.color.rgb = PRP

    tx("MCP Agent Architecture: Test Analyser  &  Standalone Automation Agent",
       Inches(3.0), Inches(0.14), Inches(7.8), Inches(0.32),
       fs=Pt(12.5), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

    rc(Inches(11.3), Inches(0.16), Inches(1.75), Inches(0.30), fill=DPRP)
    tx("ARCHITECTURE", Inches(11.32), Inches(0.17), Inches(1.71), Inches(0.27),
       fs=Pt(7), bold=True, color=PRP, align=PP_ALIGN.CENTER)

    rc(0, Inches(0.72), SLIDE_W, Inches(0.04), fill=PRP)

    CY = Inches(0.82)   # content top
    CH = Inches(6.18)   # column height

    # === COLUMN GEOMETRY ====================================================
    # Left:  MCP SERVER   (wider — no consumers)
    # Right: Both agents  (wider pipeline stages)
    LX = Inches(0.15);  LW = Inches(3.50)
    RX = Inches(3.90);  RW = SLIDE_W - Inches(3.90) - Inches(0.12)
    c2r_w = RX - (LX + LW)            # gap between MCP right edge and agents left edge
    da_xc = RX + RW / 2               # agents column centre x

    # Pipeline stage dimensions (5 stages inside RW)
    psw = (RW - Inches(0.30) - Inches(0.16) * 4) / 5   # ≈ 1.66"
    pgap = Inches(0.16)
    psh  = Inches(1.80)

    # === LEFT: MCP SERVER ===================================================
    rr(LX, CY, LW, CH, fill=F_MCP, brd=PRP, bw=Pt(2))

    # Top accent stripe
    rc(LX, CY, LW, Inches(0.04), fill=PRP)

    tx("MCP SERVER", LX + Inches(0.18), CY + Inches(0.10), LW - Inches(0.30), Inches(0.30),
       fs=Pt(13), bold=True, color=DARK)
    tx("FastMCP  /  SSE  /  stdio",
       LX + Inches(0.18), CY + Inches(0.44), LW - Inches(0.30), Inches(0.22),
       fs=Pt(9), italic=True, color=MID_GRAY)
    tx("Routes MCP tool calls to the\nappropriate agent at runtime",
       LX + Inches(0.18), CY + Inches(0.68), LW - Inches(0.30), Inches(0.36),
       fs=Pt(8.5), color=MID_GRAY)

    # Divider
    rc(LX + Inches(0.18), CY + Inches(1.10), LW - Inches(0.36), Inches(0.02),
       fill=RGBColor(0xCC, 0xBB, 0xEE))

    # Tools inner box
    ty = CY + Inches(1.18)
    rr(LX + Inches(0.18), ty, LW - Inches(0.36), Inches(3.00),
       fill=F_TOOL, brd=RGBColor(0xBB, 0xAA, 0xDD), bw=Pt(1))
    tx("Available Tools", LX + Inches(0.28), ty + Inches(0.12), LW - Inches(0.56), Inches(0.22),
       fs=Pt(8.5), bold=True, color=DPRP)
    rc(LX + Inches(0.28), ty + Inches(0.37), LW - Inches(0.56), Inches(0.02),
       fill=RGBColor(0xCC, 0xBB, 0xEE))
    for off, lbl, sub, clr in [
        (Inches(0.48), "test_analyser",          "Discover & convert existing tests",    GRN),
        (Inches(0.94), "standalone_automation",   "Generate executable test scripts",     BLU),
        (Inches(1.40), "generate_test_cases",     "Create tests from requirements",       PRP),
        (Inches(1.86), "analyse_requirements",    "Parse requirement documents",          RGBColor(0xCC, 0x55, 0x00)),
        (Inches(2.32), "export_to_testrail",      "Push results to TestRail",             RGBColor(0x88, 0x55, 0x00)),
    ]:
        tx("⚙  " + lbl,
           LX + Inches(0.28), ty + off, LW - Inches(0.46), Inches(0.24),
           fs=Pt(8.8), bold=True, color=clr)
        tx(sub,
           LX + Inches(0.30), ty + off + Inches(0.24), LW - Inches(0.46), Inches(0.18),
           fs=Pt(7.5), italic=True, color=MID_GRAY)

    # Protocol badges at bottom of MCP box
    badge_y = CY + CH - Inches(0.62)
    rc(LX + Inches(0.18), badge_y, LW - Inches(0.36), Inches(0.02),
       fill=RGBColor(0xCC, 0xBB, 0xEE))
    for bx, blbl, bclr in [
        (LX + Inches(0.22), "SSE",   RGBColor(0xA1, 0x00, 0xFF)),
        (LX + Inches(1.06), "stdio", RGBColor(0x22, 0x66, 0xDD)),
        (LX + Inches(1.90), "HTTP",  RGBColor(0x00, 0x88, 0x44)),
    ]:
        rr(bx, badge_y + Inches(0.10), Inches(0.72), Inches(0.32),
           fill=F_USR, brd=bclr, bw=Pt(1.2))
        tx(blbl, bx, badge_y + Inches(0.16), Inches(0.72), Inches(0.22),
           fs=Pt(8), bold=True, color=bclr, align=PP_ALIGN.CENTER)

    # === MCP → AGENT HORIZONTAL ARROWS =====================================
    # Test Analyser arrow (green) — drawn at TA centre y after TA coords are known
    # Standalone arrow (blue) — drawn at SA centre y after SA coords are known

    # === RIGHT: BOTH AGENTS =================================================

    # ── TEST ANALYSER AGENT ─────────────────────────────────────────────────
    ta_y = CY + Inches(0.06);  ta_h = Inches(2.20)
    rr(RX + Inches(0.06), ta_y, RW - Inches(0.06), ta_h, fill=F_TA, brd=GRN, bw=Pt(2))

    rc(RX + Inches(0.06), ta_y,                  RW - Inches(0.06), Inches(0.02), fill=GRN)
    rc(RX + Inches(0.06), ta_y + Inches(0.34),   RW - Inches(0.06), Inches(0.02),
       fill=RGBColor(0xBB, 0xEE, 0xDD))

    tx("  Test Analyser Agent",
       RX + Inches(0.14), ta_y + Inches(0.06), Inches(4.2), Inches(0.24),
       fs=Pt(10.5), bold=True, color=RGBColor(0x00, 0x66, 0x44))
    tx("Reads existing test project  ›  Discovers tests  ›  Exports structured specifications",
       RX + Inches(4.4), ta_y + Inches(0.08), RW - Inches(4.58), Inches(0.20),
       fs=Pt(7.5), italic=True, color=MID_GRAY)

    px = RX + Inches(0.15);  py = ta_y + Inches(0.40)
    for i, (num, title, b1, b2, clr) in enumerate([
        ("01", "Language\nDetector",   "Check project markers",  "Identify test framework", GRN),
        ("02", "Test\nDiscovery",      "Walk files, find tests",  "Capture class + line no", GRN),
        ("03", "Scope\nSelector",      "Folder counts > 20",      "User selects (≤ 500)",   GRN),
        ("04", "LLM Batch\nConverter", "Groups of 15 tests",      "BDD / plain / step",      LLM),
        ("05", "Excel\nBuilder",       "Build styled rows",       "Export .xlsx + filters",  RGBColor(0x00, 0x88, 0x44)),
    ]):
        rr(px, py, psw, psh, fill=F_USR, brd=clr, bw=Pt(1.5))
        tx(num,   px + Inches(0.07), py + Inches(0.05), Inches(0.28), Inches(0.20),
           fs=Pt(7.5), bold=True, color=clr)
        tx(title, px + Inches(0.07), py + Inches(0.22), psw - Inches(0.10), Inches(0.36),
           fs=Pt(9), bold=True)
        rc(px + Inches(0.07), py + Inches(0.62), psw - Inches(0.14), Inches(0.02),
           fill=RGBColor(0xCC, 0xEE, 0xDD))
        add_multiline_text_box(slide, [b1, b2],
                               px + Inches(0.07), py + Inches(0.68), psw - Inches(0.10),
                               psh - Inches(0.76), font_size=Pt(7.5),
                               color=MID_GRAY, bullet=True)
        if i < 4:
            rc(px + psw + Inches(0.02), py + psh / 2 - Inches(0.035),
               pgap - Inches(0.04), Inches(0.07), fill=GRN)
        px += psw + pgap

    tx("OUTPUT  ›  Structured test cases  (BDD / plain / step)  →  passed as test_cases to Standalone Agent",
       RX + Inches(0.15), ta_y + ta_h - Inches(0.24), RW - Inches(0.22), Inches(0.20),
       fs=Pt(7.5), italic=True, color=RGBColor(0x00, 0x77, 0x44))

    # MCP → TA arrow
    rc(LX + LW, ta_y + ta_h / 2 - Inches(0.04), c2r_w, Inches(0.08), fill=GRN)

    # ── DATA HANDSHAKE BAND ─────────────────────────────────────────────────
    hs_y = ta_y + ta_h + Inches(0.05);  hs_h = Inches(0.50)
    rr(RX + Inches(0.06), hs_y, RW - Inches(0.06), hs_h, fill=F_HS, brd=PRP, bw=Pt(1.5))

    left_bw = RW * 0.42
    rr(RX + Inches(0.16), hs_y + Inches(0.07), left_bw, hs_h - Inches(0.14),
       fill=RGBColor(0xE8, 0xFF, 0xF2), brd=GRN, bw=Pt(1))
    tx("ANALYSER OUTPUT  ›  Structured test cases  (BDD / plain / step-by-step)",
       RX + Inches(0.26), hs_y + Inches(0.14), left_bw - Inches(0.20), Inches(0.24),
       fs=Pt(8), color=RGBColor(0x00, 0x66, 0x44))

    tx("⟶", da_xc - Inches(0.8), hs_y + Inches(0.01), Inches(1.6), Inches(0.46),
       fs=Pt(28), bold=True, color=PRP, align=PP_ALIGN.CENTER)
    tx("DATA HANDSHAKE", da_xc - Inches(0.8), hs_y + Inches(0.32), Inches(1.6), Inches(0.16),
       fs=Pt(7), bold=True, color=PRP, align=PP_ALIGN.CENTER)

    right_bx = RX + RW - left_bw - Inches(0.10)
    rr(right_bx, hs_y + Inches(0.07), left_bw, hs_h - Inches(0.14),
       fill=RGBColor(0xE8, 0xF2, 0xFF), brd=BLU, bw=Pt(1))
    tx("STANDALONE INPUT  ›  test_cases param drives code generation",
       right_bx + Inches(0.10), hs_y + Inches(0.14), left_bw - Inches(0.15), Inches(0.24),
       fs=Pt(8), color=RGBColor(0x22, 0x44, 0x99))

    # ── STANDALONE AUTOMATION AGENT ─────────────────────────────────────────
    sa_y = hs_y + hs_h + Inches(0.05);  sa_h = Inches(2.20)
    rr(RX + Inches(0.06), sa_y, RW - Inches(0.06), sa_h, fill=F_SA, brd=BLU, bw=Pt(2))

    rc(RX + Inches(0.06), sa_y,                RW - Inches(0.06), Inches(0.02), fill=BLU)
    rc(RX + Inches(0.06), sa_y + Inches(0.34), RW - Inches(0.06), Inches(0.02),
       fill=RGBColor(0xBB, 0xCC, 0xEE))

    tx("  Standalone Automation Agent",
       RX + Inches(0.14), sa_y + Inches(0.06), Inches(4.2), Inches(0.24),
       fs=Pt(10.5), bold=True, color=RGBColor(0x22, 0x44, 0xAA))
    tx("Profiles existing framework  ›  Generates & validates production-ready test scripts",
       RX + Inches(4.4), sa_y + Inches(0.08), RW - Inches(4.58), Inches(0.20),
       fs=Pt(7.5), italic=True, color=MID_GRAY)

    px = RX + Inches(0.15);  py = sa_y + Inches(0.40)
    for i, (num, title, b1, b2, clr) in enumerate([
        ("01", "Framework\nProfiler",      "Detect language & fw",   "Map project structure",   BLU),
        ("02", "Pattern\nExtractor",        "Extract real methods",    "Discover config / URLs",  BLU),
        ("03", "Adaptive\nPrompt Builder",  "Learn coding style",      "3-step fallback ladder",  BLU),
        ("04", "LLM Code\nGenerator",       "Generate full scripts",   "Reuse real methods",      LLM),
        ("05", "Validate\n& Heal",          "Syntax check all files",  "Auto-fix (2 passes)",     RGBColor(0x22, 0x66, 0xAA)),
    ]):
        rr(px, py, psw, psh, fill=F_USR, brd=clr, bw=Pt(1.5))
        tx(num,   px + Inches(0.07), py + Inches(0.05), Inches(0.28), Inches(0.20),
           fs=Pt(7.5), bold=True, color=clr)
        tx(title, px + Inches(0.07), py + Inches(0.22), psw - Inches(0.10), Inches(0.36),
           fs=Pt(9), bold=True)
        rc(px + Inches(0.07), py + Inches(0.62), psw - Inches(0.14), Inches(0.02),
           fill=RGBColor(0xCC, 0xDD, 0xEE))
        add_multiline_text_box(slide, [b1, b2],
                               px + Inches(0.07), py + Inches(0.68), psw - Inches(0.10),
                               psh - Inches(0.76), font_size=Pt(7.5),
                               color=MID_GRAY, bullet=True)
        if i < 4:
            rc(px + psw + Inches(0.02), py + psh / 2 - Inches(0.035),
               pgap - Inches(0.04), Inches(0.07), fill=BLU)
        px += psw + pgap

    tx("OUTPUT  ›  Executable test scripts  (Python / Java / JavaScript / C#)  ·  Validation report  ·  Healing log",
       RX + Inches(0.15), sa_y + sa_h - Inches(0.24), RW - Inches(0.22), Inches(0.20),
       fs=Pt(7.5), italic=True, color=RGBColor(0x22, 0x44, 0xAA))

    # MCP → SA arrow
    rc(LX + LW, sa_y + sa_h / 2 - Inches(0.04), c2r_w, Inches(0.08), fill=BLU)

    # ── SCRIPTS BAR ─────────────────────────────────────────────────────────
    sc_y = sa_y + sa_h + Inches(0.08)
    rc(da_xc - Inches(0.04), sc_y, Inches(0.08), Inches(0.18), fill=GRN)
    sc_y += Inches(0.20)
    rr(RX + Inches(0.06), sc_y, RW - Inches(0.06), Inches(0.36),
       fill=F_SCR, brd=GRN, bw=Pt(1.8))
    tx("⚡  EXECUTABLE AUTOMATION SCRIPTS   (Playwright  /  Selenium  /  Pytest  /  TestNG)",
       RX + Inches(0.20), sc_y + Inches(0.08), RW - Inches(0.40), Inches(0.22),
       fs=Pt(9), bold=True, color=RGBColor(0x00, 0x77, 0x44), align=PP_ALIGN.CENTER)

    # ── ARTIFACT REPO ───────────────────────────────────────────────────────
    ar_y = sc_y + Inches(0.36) + Inches(0.04)
    rc(da_xc - Inches(0.04), ar_y, Inches(0.08), Inches(0.16), fill=GRN)
    ar_y += Inches(0.18)
    rr(RX + Inches(0.06), ar_y, RW - Inches(0.06), Inches(0.30),
       fill=F_ART, brd=LGRD, bw=Pt(1))
    tx("\U0001f4e6  ARTIFACT REPOSITORY / DOWNLOADS",
       RX + Inches(0.20), ar_y + Inches(0.07), RW - Inches(0.40), Inches(0.20),
       fs=Pt(9), bold=True, align=PP_ALIGN.CENTER)

    # === FOOTER =============================================================
    rc(0, Inches(7.1), SLIDE_W, Inches(0.4), fill=DARK)
    add_text_box(slide, "Quality Engineering Agentic Framework  |  Accenture",
                 Inches(0.4), Inches(7.13), Inches(9), Inches(0.26),
                 font_size=Pt(7.5), color=RGBColor(0x77, 0x77, 0x77))
    add_text_box(slide, "© 2025 Accenture. All rights reserved.",
                 Inches(9.5), Inches(7.13), Inches(3.5), Inches(0.26),
                 font_size=Pt(7.5), color=RGBColor(0x55, 0x55, 0x55),
                 align=PP_ALIGN.RIGHT)


# ── SLIDE 7: Full System Architecture (white background) ─────────────────────

def build_slide_system_arch(slide):
    """White-bg full system architecture: Copilot → MCP → Agents → LLM → Outputs."""

    WHT  = RGBColor(0xFF, 0xFF, 0xFF)
    PRP  = PURPLE
    DPRP = DARK_PURPLE
    BLU  = RGBColor(0x22, 0x66, 0xDD)
    GRN  = GREEN_ACCENT
    LLM_C = RGBColor(0x66, 0x00, 0xAA)
    ORG  = RGBColor(0xCC, 0x55, 0x00)
    LGRD = RGBColor(0xCC, 0xCC, 0xCC)

    # Layer fills
    L1_BG  = RGBColor(0xF7, 0xF5, 0xFA)
    L2_BG  = RGBColor(0xF0, 0xE8, 0xFF)
    TA_BG  = RGBColor(0xED, 0xF8, 0xF3)
    SA_BG  = RGBColor(0xED, 0xF2, 0xFF)
    HS_BG  = RGBColor(0xFF, 0xF3, 0xFF)
    L4_BG  = RGBColor(0xFF, 0xF5, 0xE8)
    STG    = RGBColor(0xFF, 0xFF, 0xFF)
    GRN_DK = RGBColor(0x00, 0x77, 0x44)
    BLU_DK = RGBColor(0x22, 0x44, 0xAA)

    def rr(l, t, w, h, fill=None, brd=None, bw=Pt(1.5)):
        return add_rounded_rect(slide, l, t, w, h, fill, brd, bw)

    def tx(text, l, t, w, h, fs=Pt(8.5), bold=False, color=DARK,
           align=PP_ALIGN.LEFT, italic=False):
        return add_text_box(slide, text, l, t, w, h, font_size=fs, bold=bold,
                            color=color, align=align, italic=italic)

    def rc(l, t, w, h, fill=None):
        return add_rect(slide, l, t, w, h, fill_rgb=fill)

    def down_arrow(xc, y_top, height, clr):
        rc(xc - Inches(0.035), y_top + Inches(0.03),
           Inches(0.07), height - Inches(0.06), fill=clr)

    # === WHITE BACKGROUND ===================================================
    rc(0, 0, SLIDE_W, SLIDE_H, fill=WHT)

    # === ACCENTURE HEADER ===================================================
    rc(0, 0, SLIDE_W, Inches(0.06), fill=PRP)
    rc(0, Inches(0.06), SLIDE_W, Inches(0.66), fill=DARK)

    tb = slide.shapes.add_textbox(Inches(0.4), Inches(0.08), Inches(3), Inches(0.44))
    tf = tb.text_frame; p = tf.paragraphs[0]
    r1 = p.add_run(); r1.text = "Accenture"
    r1.font.name = "Segoe UI"; r1.font.size = Pt(15); r1.font.bold = True
    r1.font.color.rgb = WHT
    r2 = p.add_run(); r2.text = "."
    r2.font.name = "Segoe UI"; r2.font.size = Pt(15); r2.font.bold = True
    r2.font.color.rgb = PRP

    tx("System Architecture: QEAF Agents with MCP & AI Integration",
       Inches(3.0), Inches(0.14), Inches(7.8), Inches(0.32),
       fs=Pt(12.5), bold=True, color=WHT, align=PP_ALIGN.CENTER)

    rc(Inches(11.3), Inches(0.16), Inches(1.75), Inches(0.30), fill=DPRP)
    tx("ARCHITECTURE", Inches(11.32), Inches(0.17), Inches(1.71), Inches(0.27),
       fs=Pt(7), bold=True, color=PRP, align=PP_ALIGN.CENTER)

    rc(0, Inches(0.72), SLIDE_W, Inches(0.04), fill=PRP)

    CY = Inches(0.82);  MX = Inches(0.12);  CW = SLIDE_W - Inches(0.24)

    # ── LAYER 1: ENTRY POINTS ───────────────────────────────────────────────
    L1_y = CY + Inches(0.06);  L1_h = Inches(1.02)

    # Left sidebar label
    rc(MX, L1_y, Inches(0.04), L1_h, fill=DPRP)
    tx("ENTRY\nPOINTS", MX + Inches(0.08), L1_y + Inches(0.28),
       Inches(0.84), Inches(0.44), fs=Pt(6.5), bold=True, color=DPRP)

    cbw = (CW - Inches(1.02) - Inches(0.10) * 4) / 5
    cx  = MX + Inches(1.02)
    for icon, title, sub, b_clr in [
        ("⚡", "GitHub Copilot\n& VS Code",    "MCP Extension\nnative tool calls",   RGBColor(0x1A,0x1A,0x2E)),
        ("◆",  "Claude Desktop\n& Claude.ai",  "MCP Client\nstdio / SSE protocol",   PRP),
        ("✦",  "Cursor AI  /\nWindsurf IDE",   "MCP-enabled IDE\ntool invocation",    BLU),
        ("⬡",  "Web Dashboard\n(Streamlit)",   "REST API\nFastAPI backend",           RGBColor(0x00,0x77,0xAA)),
        ("▶",  "CLI  /  Terminal",             "Direct execution\nsubprocess / API",  RGBColor(0x44,0x44,0x44)),
    ]:
        rr(cx, L1_y, cbw, L1_h, fill=L1_BG, brd=b_clr, bw=Pt(1.5))
        tx(icon,  cx + Inches(0.12),  L1_y + Inches(0.10), Inches(0.32), Inches(0.34),
           fs=Pt(14), bold=True, color=b_clr)
        tx(title, cx + Inches(0.48),  L1_y + Inches(0.06), cbw - Inches(0.56), Inches(0.34),
           fs=Pt(8.5), bold=True, color=DARK)
        tx(sub,   cx + Inches(0.48),  L1_y + Inches(0.52), cbw - Inches(0.56), Inches(0.38),
           fs=Pt(7.5), italic=True, color=MID_GRAY)
        cx += cbw + Inches(0.10)

    # Arrows L1 → L2 (at each client centre)
    L1_bot = L1_y + L1_h
    L2_y   = L1_bot + Inches(0.20)
    arw_h  = L2_y - L1_bot
    cx_tmp = MX + Inches(1.02) + cbw / 2
    for _ in range(5):
        down_arrow(cx_tmp, L1_bot, arw_h, LGRD)
        cx_tmp += cbw + Inches(0.10)

    # ── LAYER 2: MCP PROTOCOL LAYER ─────────────────────────────────────────
    L2_h = Inches(0.74)
    rr(MX, L2_y, CW, L2_h, fill=L2_BG, brd=PRP, bw=Pt(2))
    rc(MX, L2_y, CW, Inches(0.04), fill=PRP)

    tx("MCP SERVER", MX + Inches(0.18), L2_y + Inches(0.10), Inches(1.60), Inches(0.26),
       fs=Pt(12), bold=True)
    tx("FastMCP  /  SSE  /  stdio  /  HTTP",
       MX + Inches(0.18), L2_y + Inches(0.40), Inches(2.50), Inches(0.22),
       fs=Pt(8.5), italic=True, color=MID_GRAY)

    tx("Registered tools:", MX + Inches(2.84), L2_y + Inches(0.10),
       Inches(1.20), Inches(0.20), fs=Pt(7.5), color=MID_GRAY)
    tool_x = MX + Inches(2.84)
    for tlbl, tclr, tw in [
        ("test_analyser",          GRN,  Inches(1.26)),
        ("standalone_automation",  BLU,  Inches(1.80)),
        ("generate_test_cases",    PRP,  Inches(1.60)),
        ("analyse_requirements",   ORG,  Inches(1.66)),
        ("export_to_testrail",     RGBColor(0x88,0x55,0x00), Inches(1.50)),
    ]:
        rr(tool_x, L2_y + Inches(0.34), tw, Inches(0.30),
           fill=WHT, brd=tclr, bw=Pt(1))
        tx("⚙ " + tlbl, tool_x + Inches(0.06), L2_y + Inches(0.38),
           tw - Inches(0.10), Inches(0.22), fs=Pt(7.5), bold=True, color=tclr)
        tool_x += tw + Inches(0.08)

    # Arrows L2 → L3
    L2_bot = L2_y + L2_h
    L3_y   = L2_bot + Inches(0.20)
    arw_h2 = L3_y - L2_bot
    HS_w  = Inches(1.10)
    ag_w  = (CW - HS_w - Inches(0.16)) / 2
    TA_x  = MX
    SA_x  = TA_x + ag_w + Inches(0.08) + HS_w + Inches(0.08)
    for xc, clr in [(TA_x + ag_w / 2, GRN), (SA_x + ag_w / 2, BLU)]:
        down_arrow(xc, L2_bot, arw_h2, clr)

    # ── LAYER 3: AGENTS ─────────────────────────────────────────────────────
    L3_h = Inches(2.00)
    HS_x  = TA_x + ag_w + Inches(0.08)
    pgap  = Inches(0.09)
    psw   = (ag_w - Inches(0.22) - pgap * 4) / 5
    psh   = L3_h - Inches(0.36) - Inches(0.24)   # 1.40"

    # ── TEST ANALYSER AGENT ──
    rr(TA_x, L3_y, ag_w, L3_h, fill=TA_BG, brd=GRN, bw=Pt(2))
    rc(TA_x, L3_y, ag_w, Inches(0.02), fill=GRN)
    rc(TA_x, L3_y + Inches(0.34), ag_w, Inches(0.02), fill=RGBColor(0xBB,0xEE,0xDD))
    tx("  Test Analyser Agent",
       TA_x + Inches(0.12), L3_y + Inches(0.06), Inches(3.4), Inches(0.24),
       fs=Pt(10.5), bold=True, color=GRN_DK)
    tx("Reads test project  ›  Discovers tests  ›  Converts to structured specification",
       TA_x + Inches(3.62), L3_y + Inches(0.08), ag_w - Inches(3.76), Inches(0.20),
       fs=Pt(7.5), italic=True, color=MID_GRAY)

    px = TA_x + Inches(0.11);  py = L3_y + Inches(0.38)
    for i, (num, ttl, b1, b2, sc) in enumerate([
        ("01", "Language\nDetector",   "Check project markers",  "Identify test framework", GRN),
        ("02", "Test\nDiscovery",      "Walk file tree",          "Find test classes",        GRN),
        ("03", "Scope\nSelector",      "Count per folder",        "Select up to 500",         GRN),
        ("04", "LLM Batch\nConverter", "Groups of 15",            "BDD / plain / step",       LLM_C),
        ("05", "Excel\nBuilder",       "Build styled rows",       "Export .xlsx",             RGBColor(0x00,0x88,0x44)),
    ]):
        rr(px, py, psw, psh, fill=STG, brd=sc, bw=Pt(1.5))
        tx(num,  px+Inches(0.06), py+Inches(0.04), psw-Inches(0.08), Inches(0.18),
           fs=Pt(7), bold=True, color=sc)
        tx(ttl,  px+Inches(0.06), py+Inches(0.22), psw-Inches(0.08), Inches(0.32),
           fs=Pt(8.8), bold=True)
        rc(px+Inches(0.06), py+Inches(0.57), psw-Inches(0.12), Inches(0.02),
           fill=RGBColor(0xCC,0xEE,0xDD))
        add_multiline_text_box(slide, [b1, b2],
                               px+Inches(0.06), py+Inches(0.62), psw-Inches(0.08),
                               psh - Inches(0.68), font_size=Pt(7.5),
                               color=MID_GRAY, bullet=True)
        if i < 4:
            rc(px + psw + Inches(0.01), py + psh / 2 - Inches(0.03),
               pgap - Inches(0.02), Inches(0.06), fill=GRN)
        px += psw + pgap

    tx("OUTPUT  ›  Structured test cases (.xlsx)  +  test_cases JSON  →  input to Standalone Agent",
       TA_x + Inches(0.12), L3_y + L3_h - Inches(0.22), ag_w - Inches(0.20), Inches(0.18),
       fs=Pt(7.5), italic=True, color=GRN_DK)

    # ── HANDSHAKE CONNECTOR ──
    rr(HS_x, L3_y, HS_w, L3_h, fill=HS_BG, brd=PRP, bw=Pt(1.5))
    tx("DATA\nHANDSHAKE",
       HS_x, L3_y + Inches(0.24), HS_w, Inches(0.44),
       fs=Pt(8.5), bold=True, color=PRP, align=PP_ALIGN.CENTER)
    tx("test_cases",
       HS_x, L3_y + Inches(0.78), HS_w, Inches(0.26),
       fs=Pt(9), bold=True, color=DARK, align=PP_ALIGN.CENTER)
    tx("JSON payload",
       HS_x, L3_y + Inches(1.02), HS_w, Inches(0.18),
       fs=Pt(7.5), italic=True, color=MID_GRAY, align=PP_ALIGN.CENTER)
    rc(HS_x + HS_w / 2 - Inches(0.035), L3_y + Inches(1.26),
       Inches(0.07), Inches(0.40), fill=PRP)
    tx("↓",
       HS_x, L3_y + Inches(1.56), HS_w, Inches(0.26),
       fs=Pt(14), bold=True, color=PRP, align=PP_ALIGN.CENTER)

    # ── STANDALONE AUTOMATION AGENT ──
    rr(SA_x, L3_y, ag_w, L3_h, fill=SA_BG, brd=BLU, bw=Pt(2))
    rc(SA_x, L3_y, ag_w, Inches(0.02), fill=BLU)
    rc(SA_x, L3_y + Inches(0.34), ag_w, Inches(0.02), fill=RGBColor(0xBB,0xCC,0xEE))
    tx("  Standalone Automation Agent",
       SA_x + Inches(0.12), L3_y + Inches(0.06), Inches(3.6), Inches(0.24),
       fs=Pt(10.5), bold=True, color=BLU_DK)
    tx("Profiles framework  ›  Generates & validates production-ready test scripts",
       SA_x + Inches(3.80), L3_y + Inches(0.08), ag_w - Inches(3.94), Inches(0.20),
       fs=Pt(7.5), italic=True, color=MID_GRAY)

    px = SA_x + Inches(0.11);  py = L3_y + Inches(0.38)
    for i, (num, ttl, b1, b2, sc) in enumerate([
        ("01", "Framework\nProfiler",      "Detect language & fw",  "Map project structure",   BLU),
        ("02", "Pattern\nExtractor",        "Real helper methods",    "Config & base URLs",      BLU),
        ("03", "Adaptive\nPrompt Builder",  "Learn coding style",     "3-step fallback",         BLU),
        ("04", "LLM Code\nGenerator",       "Generate full scripts",  "Reuse real methods",      LLM_C),
        ("05", "Validate\n& Heal",          "Syntax check all",       "Auto-fix 2 passes",       RGBColor(0x22,0x66,0xAA)),
    ]):
        rr(px, py, psw, psh, fill=STG, brd=sc, bw=Pt(1.5))
        tx(num,  px+Inches(0.06), py+Inches(0.04), psw-Inches(0.08), Inches(0.18),
           fs=Pt(7), bold=True, color=sc)
        tx(ttl,  px+Inches(0.06), py+Inches(0.22), psw-Inches(0.08), Inches(0.32),
           fs=Pt(8.8), bold=True)
        rc(px+Inches(0.06), py+Inches(0.57), psw-Inches(0.12), Inches(0.02),
           fill=RGBColor(0xCC,0xDD,0xEE))
        add_multiline_text_box(slide, [b1, b2],
                               px+Inches(0.06), py+Inches(0.62), psw-Inches(0.08),
                               psh - Inches(0.68), font_size=Pt(7.5),
                               color=MID_GRAY, bullet=True)
        if i < 4:
            rc(px + psw + Inches(0.01), py + psh / 2 - Inches(0.03),
               pgap - Inches(0.02), Inches(0.06), fill=BLU)
        px += psw + pgap

    tx("OUTPUT  ›  Executable scripts  (Python / Java / JS / C#)  ·  Validation report  ·  Healing log",
       SA_x + Inches(0.12), L3_y + L3_h - Inches(0.22), ag_w - Inches(0.20), Inches(0.18),
       fs=Pt(7.5), italic=True, color=BLU_DK)

    # Arrows L3 → L4 (agents call LLMs)
    L3_bot = L3_y + L3_h
    L4_y   = L3_bot + Inches(0.20)
    arw_h3 = L4_y - L3_bot
    for xc, clr in [(TA_x + ag_w * 0.5, LLM_C), (SA_x + ag_w * 0.5, LLM_C)]:
        down_arrow(xc, L3_bot, arw_h3, clr)

    # ── LAYER 4: AI / LLM SERVICES ──────────────────────────────────────────
    L4_h = Inches(0.68)
    rr(MX, L4_y, CW, L4_h, fill=L4_BG, brd=RGBColor(0xBB,0x88,0x00), bw=Pt(1.5))
    rc(MX, L4_y, CW, Inches(0.04), fill=RGBColor(0xBB,0x77,0x00))

    rc(MX, L4_y, Inches(0.04), L4_h, fill=LLM_C)
    tx("AI / LLM\nSERVICES", MX + Inches(0.10), L4_y + Inches(0.10),
       Inches(0.88), Inches(0.44), fs=Pt(7), bold=True, color=RGBColor(0x77,0x44,0x00))

    lbw = (CW - Inches(1.06) - Inches(0.09) * 4) / 5
    lx  = MX + Inches(1.06)
    for llbl, lbrd, lfill in [
        ("Claude  (Anthropic)",   PRP,                          RGBColor(0xF7,0xF0,0xFF)),
        ("OpenAI  GPT-4",         BLU,                          RGBColor(0xF0,0xF4,0xFF)),
        ("GitHub Copilot API",    RGBColor(0x1A,0x1A,0x2E),    RGBColor(0xF2,0xF2,0xF5)),
        ("Azure  OpenAI",         RGBColor(0x00,0x78,0xD4),    RGBColor(0xE8,0xF4,0xFF)),
        ("Local LLM  (Ollama)",   GRN,                          RGBColor(0xEE,0xF8,0xF3)),
    ]:
        rr(lx, L4_y + Inches(0.10), lbw, L4_h - Inches(0.20),
           fill=lfill, brd=lbrd, bw=Pt(1.2))
        tx(llbl, lx + Inches(0.10), L4_y + Inches(0.22), lbw - Inches(0.16), Inches(0.22),
           fs=Pt(8.8), bold=True, color=lbrd, align=PP_ALIGN.CENTER)
        lx += lbw + Inches(0.09)

    # ── LLM call note ──
    tx("⇅  Agents call at runtime — pluggable, model-agnostic",
       MX + Inches(0.10), L4_y + L4_h - Inches(0.20), CW - Inches(0.20), Inches(0.18),
       fs=Pt(7.5), italic=True, color=RGBColor(0x88,0x66,0x00))

    # Arrows L4 → L5
    L4_bot = L4_y + L4_h
    L5_y   = L4_bot + Inches(0.20)
    arw_h4 = L5_y - L4_bot
    for xc in [TA_x + ag_w * 0.35, SA_x + ag_w * 0.65]:
        down_arrow(xc, L4_bot, arw_h4, LGRD)

    # ── LAYER 5: INPUTS & OUTPUTS ────────────────────────────────────────────
    L5_h  = Inches(0.54)
    inp_w = CW * 0.40
    out_w = CW - inp_w - Inches(0.12)

    rr(MX, L5_y, inp_w, L5_h, fill=RGBColor(0xF0,0xF4,0xFF),
       brd=RGBColor(0x88,0x99,0xCC), bw=Pt(1.2))
    tx("INPUT  ›  Existing test project  (Python / Java / JS / C#)  ·  Manual test specs  ·  Requirements docs",
       MX + Inches(0.14), L5_y + Inches(0.16), inp_w - Inches(0.22), Inches(0.22),
       fs=Pt(8), color=RGBColor(0x22,0x44,0x88))

    rr(MX + inp_w + Inches(0.12), L5_y, out_w, L5_h, fill=RGBColor(0xEE,0xF8,0xF3),
       brd=GRN, bw=Pt(1.2))
    tx("OUTPUT  ›  Excel test cases (.xlsx)  ·  test_cases JSON  ·  Executable scripts  ·  Artifact repository",
       MX + inp_w + Inches(0.26), L5_y + Inches(0.16), out_w - Inches(0.30), Inches(0.22),
       fs=Pt(8), color=GRN_DK)

    # === FOOTER =============================================================
    rc(0, Inches(7.1), SLIDE_W, Inches(0.4), fill=DARK)
    add_text_box(slide, "Quality Engineering Agentic Framework  |  Accenture",
                 Inches(0.4), Inches(7.13), Inches(9), Inches(0.26),
                 font_size=Pt(7.5), color=RGBColor(0x77, 0x77, 0x77))
    add_text_box(slide, "© 2025 Accenture. All rights reserved.",
                 Inches(9.5), Inches(7.13), Inches(3.5), Inches(0.26),
                 font_size=Pt(7.5), color=RGBColor(0x55, 0x55, 0x55),
                 align=PP_ALIGN.RIGHT)


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H

    blank_layout = prs.slide_layouts[6]  # completely blank

    slide1 = prs.slides.add_slide(blank_layout)
    build_slide_1(slide1)

    slide2 = prs.slides.add_slide(blank_layout)
    build_slide_2(slide2)

    slide3 = prs.slides.add_slide(blank_layout)
    build_slide_arch_standalone(slide3)

    slide4 = prs.slides.add_slide(blank_layout)
    build_slide_arch_test_analyser(slide4)

    slide5 = prs.slides.add_slide(blank_layout)
    build_slide_combined_arch(slide5)

    slide6 = prs.slides.add_slide(blank_layout)
    build_slide_mcp_arch(slide6)

    slide7 = prs.slides.add_slide(blank_layout)
    build_slide_system_arch(slide7)

    out = "/Users/prabhakaran.a.sankar/AgenticFramework-QE/docs/QEAF_Agent_One_Pagers.pptx"
    prs.save(out)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
