---
name: "consulting-analysis"
description: "Write consulting-grade research reports (market, industry, competitor, brand, consumer, financial analysis): build the analysis framework, collect data, and write a fully sourced report."
---

# Professional Research Report Skill

> **Adapted for Claude (from bytedance/deer-flow, MIT).** In this environment there are no separate "data collection skills":
> - Unless the user asks for the framework only, run Phase 1 → do the data collection yourself with web search / fetch (and any files or connectors the user provides) → Phase 2, in one task.
> - Charts: if a charting tool or the dataviz skill is available, build charts from the collected numbers; otherwise use comparison tables as the visual anchor. Never invent data for a chart.
> - Default `output_locale` is **zh_TW (Traditional Chinese)** unless the user asks otherwise. Deliver a long report as a document artifact when one is available.

## Overview

This skill produces professional, consulting-grade research reports in Markdown format, covering domains such as **market analysis, consumer insights, brand strategy, financial analysis, industry research, competitive intelligence, investment research, and macroeconomic analysis**. It operates across two distinct phases:

1. **Phase 1 — Analysis Framework Generation**: Given a research subject, produce a rigorous analysis framework including chapter skeleton, per-chapter data requirements, analysis logic, and visualization plan.
2. **Phase 2 — Report Generation**: After data has been collected, synthesize all inputs into a final polished report.

The output adheres to McKinsey/BCG consulting voice standards. The report language follows the `output_locale` setting (default: `zh_TW` for Traditional Chinese).

## Data Authenticity Protocol

**Strict Adherence Rule**: All data presented in the report and visualized in charts MUST be derived directly from the provided **Data Summary** or **External Search Findings**.
- **NO Hallucinations**: Do not invent, estimate, or simulate data. If data is missing, state "Data not available" rather than fabricating numbers.
- **Traceable Sources**: Every major claim and chart must be traceable back to the input data package.

## Core Capabilities

- **Design analysis frameworks** from scratch given only a research subject and scope
- Transform raw data into structured, high-depth research reports
- Follow the **"Visual Anchor → Data Contrast → Integrated Analysis"** flow per sub-chapter
- Produce insights following the **"Data → User Psychology → Strategy Implication"** chain
- Embed charts and construct comparison tables
- Generate inline citations formatted per **GB/T 7714-2015** standards
- Output reports in the language specified by `output_locale` with professional consulting tone
- Adapt analytical depth and structure to domain (marketing, finance, industry, etc.)

## When to Use This Skill

- User asks for a market analysis, consumer insight report, financial analysis, industry research, or any consulting-grade analytical report
- User provides a research subject and needs a structured analysis framework before data collection
- User provides data summaries, analysis frameworks, or chart files to be synthesized into a report
- The task involves transforming research findings into structured strategic narratives

# Phase 1: Analysis Framework Generation

## Purpose

Given a **research subject** (e.g., "Gen-Z Skincare Market Analysis", "NEV Industry Competitive Landscape", "Brand X Consumer Profiling"), produce a complete **analysis framework** that serves as the blueprint for data collection and final report generation.

## Phase 1 Inputs

| Input | Description | Required |
|-------|-------------|----------|
| **Research Subject** | The topic or question to be analyzed | Yes |
| **Scope / Constraints** | Geographic scope, time range, industry segment, target audience, etc. | Optional |
| **Specific Angles** | Any particular angles or hypotheses the user wants explored | Optional |
| **Domain** | The analytical domain: market, finance, industry, brand, consumer, investment, etc. | Inferred |

## Phase 1 Workflow

### Step 1.1: Understand the Research Subject

- Parse the research subject to identify the **core entity** (market, brand, product, industry, consumer segment, financial instrument, etc.)
- Identify the **analytical domain**
- Determine the **natural analytical dimensions** based on domain:

| Domain | Typical Dimensions |
|--------|--------------------|
| Market Analysis | Market size, growth trends, market segmentation, growth drivers, competitive landscape, consumer profiling |
| Brand Analysis | Brand positioning, market share, consumer perception, marketing strategy, competitor comparison |
| Consumer Insights | Demographic profiling, purchase behavior, decision journey, pain points, scenario analysis |
| Financial Analysis | Macro environment, industry trends, company fundamentals, financial metrics, valuation, risk assessment |
| Industry Research | Value chain analysis, market size, competitive landscape, policy environment, technology trends, entry barriers |
| Investment Due Diligence | Business model, financial health, management assessment, market opportunity, risk factors, exit pathways |
| Competitive Intelligence | Competitor identification, strategic comparison, SWOT analysis, differentiated positioning, market dynamics |

### Step 1.2: Select Analysis Frameworks & Models

#### Strategic & Environmental Analysis

| Framework | Description | Best For |
|-----------|-------------|----------|
| **SWOT Analysis** | Strengths, Weaknesses, Opportunities, Threats | Brand assessment, competitive positioning, strategic planning |
| **PEST / PESTEL Analysis** | Political, Economic, Social, Technological (+ Environmental, Legal) | Macro-environment scanning, market entry assessment, policy impact |
| **Porter's Five Forces** | Supplier power, buyer power, new entrants, substitutes, rivalry | Industry competitive landscape, entry barriers, profit margins |
| **Porter's Diamond Model** | Factor conditions, demand conditions, related industries, firm strategy & structure | National/regional competitive advantage |
| **VRIO Analysis** | Value, Rarity, Imitability, Organization | Core competency assessment |

#### Market & Growth Analysis

| Framework | Description | Best For |
|-----------|-------------|----------|
| **STP Analysis** | Segmentation, Targeting, Positioning | Market segmentation, brand positioning |
| **BCG Matrix** | Stars, Cash Cows, Question Marks, Dogs | Product portfolio management |
| **Ansoff Matrix** | Market penetration, market development, product development, diversification | Growth strategy selection |
| **Product Life Cycle (PLC)** | Introduction, growth, maturity, decline | Product strategy, market timing |
| **TAM-SAM-SOM** | Total / Serviceable / Obtainable Market | Market sizing |
| **Technology Adoption Lifecycle** | Innovators → Early Adopters → Early Majority → Late Majority → Laggards | Emerging category penetration |

#### Consumer & Behavioral Analysis

| Framework | Description | Best For |
|-----------|-------------|----------|
| **Consumer Decision Journey** | Awareness → Consideration → Evaluation → Purchase → Loyalty | Touchpoint optimization |
| **AARRR Funnel** | Acquisition, Activation, Retention, Revenue, Referral | User growth, conversion |
| **RFM Model** | Recency, Frequency, Monetary | Customer value segmentation |
| **Maslow's Hierarchy of Needs** | Physiological → Safety → Social → Esteem → Self-actualization | Consumer psychology, value proposition |
| **Jobs-to-be-Done (JTBD)** | The "job" a user needs to accomplish in a context | Demand insight, product innovation |

#### Financial & Valuation Analysis

| Framework | Description | Best For |
|-----------|-------------|----------|
| **DuPont Analysis** | ROE = Net Profit Margin × Asset Turnover × Equity Multiplier | Profitability decomposition |
| **DCF** | Free cash flow discounting | Enterprise/project valuation |
| **Comparable Company Analysis** | PE, PB, PS, EV/EBITDA multiples | Relative valuation |
| **EVA** | After-tax operating profit - Cost of capital | Value creation assessment |

#### Competitive & Strategic Positioning

| Framework | Description | Best For |
|-----------|-------------|----------|
| **Benchmarking** | KPI item-by-item comparison | Competitor gap analysis |
| **Strategic Group Mapping** | Cluster competitors along two key dimensions | White-space identification |
| **Value Chain Analysis** | Primary + support activities | Cost advantage, differentiation |
| **Blue Ocean Strategy** | Value curve, Eliminate-Reduce-Raise-Create | Differentiated innovation |
| **Perceptual Mapping** | Brand positions on two perceived dimensions | Brand positioning, market gaps |

#### Industry & Supply Chain Analysis

| Framework | Description | Best For |
|-----------|-------------|----------|
| **Industry Value Chain** | Upstream → Midstream → Downstream | Profit distribution analysis |
| **Gartner Hype Cycle** | Trigger → Peak → Trough → Slope → Plateau | Technology maturity |
| **GE-McKinsey Matrix** | Industry Attractiveness × Competitive Strength | Portfolio prioritization |

#### Selection Principles

1. **Domain-First**: select **2-4** most relevant frameworks for the domain
2. **Complementary**: e.g., macro-level PESTEL + micro-level Five Forces
3. **Depth over Breadth**: deeply apply 2 frameworks rather than stack 6
4. **Data-Feasible**: if the data a framework needs cannot reasonably be obtained, downgrade or substitute
5. **Explicit Mapping**: annotate which framework each chapter uses and how

#### Framework Selection Output Format

```markdown
## Framework Selection

| Chapter | Selected Framework(s) | Application |
|---------|----------------------|-------------|
| Market Size & Growth Trends | TAM-SAM-SOM + Product Life Cycle | Quantify market space; determine market stage |
| Competitive Landscape | Porter's Five Forces + Strategic Group Mapping | Competition intensity; positioning map |
```

### Step 1.3: Design Chapter Skeleton

Each chapter must include: **Chapter Title**, **Analysis Objective**, **Analysis Logic** (referencing the chosen frameworks), **Core Hypothesis**, plus Data Requirements (1.4) and Visualization Plan (1.5).

### Step 1.4: Define Data Query Requirements Per Chapter

| Field | Description |
|-------|-------------|
| **Data Metric** | The specific metric needed (e.g., "Taiwan health insurance premium income 2020-2025") |
| **Data Type** | Quantitative, Qualitative, or Mixed |
| **Suggested Sources** | Industry reports, financial statements, government statistics, social media, e-commerce, surveys, news |
| **Search Keywords** | Concrete search queries |
| **Priority** | P0 (Required) / P1 (Important) / P2 (Supplementary) |
| **Time Range** | Period the data should cover |

### Step 1.5: Define Visualization & Content Structure Per Chapter

For each chapter specify: **Visualization Type**, **Title**, **Data Mapping** (axes/segments), **Comparison Table Design**, and **Argument Structure**:
1. **Observation (What)**: surface phenomenon revealed by data
2. **Attribution (Why)**: driving factors
3. **Implication (So What)**: strategic implications

### Step 1.6: Output Complete Analysis Framework

```markdown
# [Research Subject] Analysis Framework

## Research Overview
- **Research Subject** / **Scope** / **Analysis Domain**
- **Core Research Questions**: [1-3 key questions]

## Framework Selection
[table]

## Chapter Skeleton
### 1. [Chapter Title]
- Analysis Objective / Analysis Logic / Core Hypothesis
#### Data Requirements
| # | Data Metric | Data Type | Suggested Sources | Search Keywords | Priority | Time Range |
#### Visualization & Content Plan
[Chart plan + comparison table design + argument structure]

## Data Collection Task List
[All P0/P1 requirements, deduplicated]
```

## Phase 1 Quality Checklist

- [ ] Framework covers all natural dimensions for the domain
- [ ] 2-4 complementary, data-feasible frameworks explicitly mapped to chapters
- [ ] Each chapter has Objective, Logic, Hypothesis
- [ ] Data requirements are specific, measurable, with search keywords
- [ ] Every chapter has at least one visualization plan
- [ ] Priorities assigned realistically; task list deduplicated

# Phase 1→2: Data Collection & Charts

Execute the search keywords yourself, collect quantitative data, qualitative insights, and source URLs, and assemble a **Data Package**: Data Summary per chapter, charts (if a charting tool is available), and External Search Findings for citations.

# Phase 2: Report Generation

### Step 2.1: Validate Inputs
Confirm framework, data summary per chapter (cross-check against P0), and chart availability. If any P0 data is missing, note it in the report and flag it for the user.

### Step 2.2: Map Report Structure
Abstract → 1. Introduction → 2..N Body Chapters → N+1 Conclusion → N+2 References (GB/T 7714-2015).

### Step 2.3: Generate Charts First
Build all planned charts before writing. **CRITICAL**: Use ONLY numbers from the Data Summary; do not invent or "smooth" data. If a chart cannot be built, fall back to a comparison table.

### Step 2.4: Write the Report
For each sub-chapter follow **Visual Anchor → Data Contrast → Integrated Analysis**:
1. Chart (or table) as visual evidence
2. Markdown comparison table of key metrics — every number from the Data Summary
3. Narrative "What → Why → So What" explaining only the provided data

Each sub-chapter ends with a robust analytical paragraph (min. 200 words) that synthesizes conflicting/reinforcing data, reveals the underlying tension or opportunity, and optionally ends with a punchy one-liner in a blockquote (`>`).

### Step 2.5: Final Self-Check
All sections present in order; must NOT stop after the Conclusion — References is the final section.

## Formatting & Tone Standards

- **Tone**: McKinsey/BCG — authoritative, objective, professional
- **Language**: headings and content in `output_locale`
- **Numbers**: English commas for thousands (`1,000`); **bold** key viewpoints and numbers
- **Titling**: `1.`, `1.1` numbering; no "Chapter/Part/Section" prefixes; avoid gimmicky words ("Decoding", "DNA", "Secrets", "Unlocking")
- **Insight depth** — every insight connects **Data → User Psychology → Strategy Implication**:

```
❌ Bad: "Females are 60%. Strategy: Target females."
✅ Good: "Females constitute 60% with a high TGI of 180. This suggests the purchase decision is driven by aesthetic and social validation rather than pure utility. Consequently, media spend should pivot towards visual-heavy platforms to maximize CTR, treating male audiences as a secondary gift-giving segment."
```

- **References**: inline markdown links `[Source Title](URL)`; References section per GB/T 7714-2015
- **Markdown**: begin directly with `# Report Title`; no horizontal rules (`---`)
- **Conclusion**: flowing prose, no bullets, no detailed recommendations (those belong in body chapters)

## Report Structure Template

```markdown
# [Report Title]

## Abstract
[Executive summary, 3-5 key takeaways]

## 1. Introduction
[Background, objectives, methodology, data sources]

## 2. [Body Chapter Title]
### 2.1 [Sub-chapter Title]
[chart]

| Metric | A | B |
|--------|---|---|

[Integrated analysis, min. 200 words]

> [Optional one-liner truth]

## N+1. Conclusion
[Para 1: fundamental nature of the market/group]
[Para 2: core tension or behavior pattern]
[Final: one or two sentences stating the objective truth]

## N+2. References
[1] Author. Title[EB/OL]. URL, Date.
```

## Phase 2 Quality Checklist

- [ ] **NO HALLUCINATION**: every number and chart verified against the Data Summary
- [ ] Sections in order: Abstract → Introduction → Body → Conclusion → References
- [ ] Every sub-chapter follows Visual Anchor → Data Contrast → Integrated Analysis and ends with a 200+ word analytical paragraph
- [ ] Insights follow Data → Psychology → Strategy
- [ ] Proper numbering, English thousands separators, no `---`, starts with `#` title
- [ ] Conclusion in prose without bullets
- [ ] Missing P0 data explicitly flagged

## Settings

```
output_locale = zh_TW  # configurable per user request
```

## Notes

- Rewrite framework topics into professional, concise subject-based headers.
- **ZERO HALLUCINATION POLICY**: each statement, chart and number must be supported by collected data; if data is missing, admit it.
- **Traceability**: be able to point to the source supporting any claim.
- When the subject is ambiguous, default to the broadest reasonable scope and state assumptions.