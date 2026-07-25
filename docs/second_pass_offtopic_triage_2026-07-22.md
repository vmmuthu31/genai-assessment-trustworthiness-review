# Second-Pass Off-Topic Triage — v2, Protocol-Literal Re-Adjudication (2026-07-22)

**Status: still a proposed-exclusion list. Corpus remains frozen at 146.**
**No CSV has been touched. No PA-004 issued.** This supersedes the first
triage pass by re-testing every one of the 54 against the literal protocol
text (`config/inclusion_exclusion.yaml`), specifically
`core_inclusion_requires_all: directly_relevant_to_automated_educational_assessment`
— i.e. does the study assess a **learner's** work or performance using
generative AI — rather than a domain-keyword judgment (medicine, e-commerce,
etc. were signals I used to *find* candidates, not the reason to exclude them).

## Result of the re-check

50 of the 54 still fail cleanly on this literal test: none of them assess a
learner's work, performance, or educational output at all — they assess
medical scans, civic complaints, news claims, software artifacts, retail
chat, government RAG systems, or the AI model's own general knowledge.
Domain was a useful signal for finding these, but the actual disqualifying
fact in each row below is the *absence of a learner as the assessment
target*, quoted directly from the paper.

**4 are genuinely borderline** and are called out separately below,
per your specific examples — these need your judgment call, not mine.

I want to be direct about one thing: I did not manufacture inclusions to
land closer to your expected 20-35/10-20 split. Re-reading these against
the literal protocol text mostly confirmed the original exclusions — the
relevance pre-filter really does appear to be keying on LLM+evaluation
vocabulary independent of the learner-assessment requirement, across a much
wider range of unrelated applications than the original 12 caught. If you
read through the 4 borderline cases and land on 'include' for some of
them, the corpus lands a few records higher than 92 — but I don't think the
evidence supports pulling the other 50 back in.

## Review table — 50 unchanged (still recommended exclude, E09 unless noted)

| Record ID | Why it fails `directly_relevant_to_automated_educational_assessment` | Confidence | Evidence quote |
|---|---|---|---|
| REC-000011 | Assesses ultrasound scan quality (clinical imaging), not a learner's work or performance. | High | "automated quality assessment of mid-trimester fetal ultrasound examinations" |
| REC-000020 | Assesses medical endoscopy images for anomaly grading, not a learner. | High | "grading of rhinitis severity in nasal endoscopy" |
| REC-000172 | Assesses civic complaints/grievances, not learners. | High | "civic grievance redressal... urgency estimation... abuse detection" |
| REC-000265 | Assesses news/social content for misinformation, not learners. | High | "detecting out-of-context (OOC) misinformation" |
| REC-000308 | Assesses recommender-system robustness against attacks, not learners. | High | "robust LLM-based recommender system for defending against shilling and prompt injection attacks" |
| REC-000316 | Assesses RAG output faithfulness in e-government, not learners. | High | "Evaluating Faithfulness in Agentic RAG Systems for e-Governance Applications" |
| REC-000657 | Assesses patients for depression via speech, not learners. | High | "Reliable Depression Detection in LLMs... using Speech Timing Information" |
| REC-000954 | Assesses factuality of news claims, not learners. | High | "assessing the factuality of news from conventional sources" |
| REC-000981 | Benchmarks LLM/AI capability itself (a difficulty-calibrated exam FOR models), not an assessment of human learners. | High | "Benchmarks are important tools for tracking the rapid advancements in large language model (LLM) capabilities" |
| REC-001197 | Assesses 3D point-cloud OOD detection (robotics/perception), not learners. | High | "Out-of-distribution (OOD) detection in 3D point cloud data" |
| REC-001329 | General multimodal reasoning framework, no assessment-of-learner application. | High | "Hypothesis-Verification Graphs for Multimodal Reasoning in Vision-Language Models" |
| REC-001385 | General VLM robustness method (test-time adaptation), no learner assessment. | High | "Test-time adaptation (TTA)... maintaining performance of Vision Language Models" |
| REC-001406 | Assesses/generates e-commerce product content, not learners. | High | "Generative product content using vision-language models: Transforming e-commerce experiences" |
| REC-001421 | General VLM visual-reasoning survey (robotics-oriented), no learner assessment. | High | "structure-aware visual reasoning: foundations, representations, and consistency checking" |
| REC-001434 | Edge-deployed VLM for satellite/disaster assessment, not learners. | High | "real-time disaster assessment... Satellite IoT scenarios" |
| REC-001547 | Counter-narrative generation for hate speech, no learner assessment. | High | "fact-based counter narratives for Tamil hate speech" |
| REC-001662 | Assesses photo/portrait image quality, not learner work. | High | "Attribute-specific Portrait Quality Assessment" |
| REC-001842 | Assesses code-translation quality in industrial software engineering, not a learner. | High | "Case Study on a C-to-Rust Translation System" |
| REC-002020 | General MLLM reasoning benchmark toward AGI, no learner assessment. | High | "Multi-Modal Multi-Step Reasoning Benchmark for MLLMs Toward AGI" |
| REC-002614 | Assesses agile user-story quality in industrial software development, not learners. | High | "LLM-Assisted INVEST Evaluation... Industrial Replication Study" |
| REC-002681 | Generates feedback on scientific peer-review rebuttals (researchers), not student learners. | High | "Rebuttal as Supervision for Actionable Review Feedback Generation" |
| REC-002768 | General RAG robustness method, no learner assessment. | High | "Counterfactual Risk Minimization for Robust Retrieval-Augmented Generation" |
| REC-003189 | Assesses contact-center employee performance, not learners. | High | "LLM-Based Contact Center Agent Quality Assurance System" |
| REC-003379 | Assesses LLM-judge stability on customer-support dialogues, not learners. | High | "synthetic customer-support dialogues" |
| REC-003417 | Assesses retail conversational-commerce UX, not learners. | High | "Testing Conversational Commerce Interfaces for Compliance, Clarity, and Consistency" |
| REC-004125 | Forecasts film-industry sustainability, no assessment-of-learner application at all. | High | "Forecasting Film Industry Sustainability Across National Economies" |
| REC-004260 | Assesses RAG systems for government services, not learners. | High | "Automated Assessment of RAG Systems in Government Services" |
| REC-004312 | Assesses AI-generated medical responses (clinical QA), not learners. | High | "Fine-Grained Medical Response Assessment" |
| REC-004387 | Assesses tobacco-misinformation credibility, not learners. | High | "automated credibility assessment of tobacco misinformation" |
| REC-004481 | Benchmarks LLM domain knowledge of telecom (tests the AI's knowledge, not a learner). | High | "evaluates two open-source LLMs... on factual and reasoning-based questions derived from advanced wireless communications" |
| REC-004505 | Governance/compliance framework for agentic LLMs, not learner assessment. | High | "Electronic Governance Controls for AI-Enabled Agentic Large Language Models" |
| REC-004519 | Benchmarks document layout-error detection, general document AI not learners. | High | "Benchmark for Evaluating Layout Error Detection in Document Analysis" |
| REC-004543 | Agricultural counterfeit-product monitoring VLM, not learners. | High | "Counterfeit-product monitoring in agriculture" |
| REC-004585 | Assesses drug-drug interaction claims (pharmacology), not learners. | High | "Drug-Drug Interaction Verification" |
| REC-004670 | Analyzes political-discourse editorials, not learners. | High | "87 editorials from Rodong Sinmun, North Korea's official newspaper" |
| REC-004824 | SQL generation/schema validation (data engineering), not learners. | High | "Automated SQL Generation, Schema Validation, and Anomaly Detection" |
| REC-004951 | Benchmarks VLM manga-reading comprehension, no learner assessment. | High | "Can Your VLM Read a Manga?" |
| REC-004995 | General statistical-theory review of LLMs, not even an assessment application. | High | "Statistical Foundations of Large Language Models" |
| REC-005129 | Assists scientific hypothesis generation for researchers, not learner assessment. | High | "Accelerating Scientific Discovery" |
| REC-005256 | Robotic learning system, no learner-assessment application. | High | "Symbolic/Non-symbolic Robotic System that Learns Through Multi-modal Interaction" |
| REC-006110 | Clinical dataset of fetal ultrasound descriptions, not learners. | High | "Expert Sonographer Clinical Descriptions for Fetal Ultrasound" |
| REC-006246 | Wrong document type (editorial, E04) AND off-topic domain (healthcare) — fails on two independent grounds. | High | "Editorial: GenAI in healthcare" |
| REC-007924 | Assesses AI-generated medical QA responses (dermatology), not learners. | High | "Automated Evaluation of Visual Medical Question Answering" |
| REC-008168 | Assesses AI-generated medical answers, not learners. | High | "MEDIQA-Eval 2026... Medical Answer Grading" |
| REC-008572 | Cancer-diagnostics evidence mapping, no learner assessment. | High | "exhaled breathomics in cancer diagnostics" |
| REC-002024 | General VQA-grounding annotation pipeline for VLM training data, no learner assessment. | High | "facilitate more robust VLM training and evaluation" |
| REC-004564 | General knowledge-augmented VQA reranking method, no learner assessment. | High | "knowledge augmented visual question answering" |
| REC-004747 | VLM-as-judge for general subjective/image-style scoring, no learner or education context anywhere in full text. | High | "Vision-language models (VLMs) are increasingly adopted as judges for subjective assessment" |
| REC-004821 | Benchmarks LLM domain knowledge of fermentation science; 'education' is one throwaway motivating sentence, not the study's target or method. | High | "created FermBench, a dataset of fermentation knowledge, which can be used to benchmark various large language models" |
| REC-005924 | Full text confirms target is expert/researcher scientific writing (research papers), explicitly not student writing. | High | "Scientific writing is an expert-domain task that demands deep domain knowledge" |

## Review table — 4 borderline (your call)

| Record ID | Analysis | Confidence | Evidence quote |
|---|---|---|---|
| REC-004787 | BORDERLINE — reconsidered per your challenge. Explicitly says 'assessment' and 'feedback' and cites fairness-in-ASR as related work; full text also says 'a feedback mechanism in the learning process... immediate, data-driven feedback provision leads to... improvement of learning outcomes.' But the target is job-interview/employability skill practice using resumes, not a course/curriculum/academic-work assessment, and there is no institution, rubric, or academic content involved. Genuinely sits on the line between 'educational assessment' (skill/feedback loop) and 'career-services/HR tool.' Your call. | Medium | "a feedback mechanism in the learning process... immediate, data-driven feedback provision leads to a significant improvement of learning outcomes and communication confidence" |
| REC-001355 | Reconsidered per your challenge (medical trainees). This is a secondary systematic review of LLM applications in physician point-of-care support and training, not a primary empirical study with its own multimodal assessment task. Even under a generous 'educational' reading, it likely fails has_evaluable_outcomes/sufficient_method_detail (review paper, not original assessment data) and has_multimodal_component (no multimodal system of its own). Leaning exclude, but for a structural reason (review paper, not primary study) rather than 'wrong domain.' | Medium | "Primary care physicians (PCPs) are a critical first contact for eye-health screening... ophthalmology training and point-of-care support in primary care remain insufficient" |
| REC-003544 | Reconsidered per your framing. 'E-learning' names the category of app under test; the paper's actual contribution and metrics (test-oracle accuracy, defect-escape rate, regression-cycle duration) are software-QA metrics, not measures of learner performance or learning outcomes. Leaning exclude, but flagged since 'e-learning' does appear verbatim in the text. | Medium | "AI-augmented testing framework for LLM-integrated e-learning mobile applications... authoring effort, regression-cycle duration, defect-escape rate, and oracle false-negative rate" |
| REC-005634 | Reconsidered per your framing (assessment of learner outputs) — but the disqualifying issue is different from domain: the method is Random Forest / Gradient Boosted Trees / Decision Trees on linguistic features, not a generative AI model (LLM/VLM/MLLM). This fails core_inclusion_requires_all's has_generative_ai_component regardless of whether the story-writers were students. Recommend exclude for this precise protocol reason, not a domain judgment. | Medium (reclassified reason) | "we compared the performance of Random Forest (RF), Gradient Boosted Trees, and Decision Tree models... to predict expert CAT ratings" |

## RESOLVED 2026-07-22 — PA-004 issued

Final researcher decisions:
- `REC-004787` (AI mock-interview agent) — **include** (researcher call).
- `REC-001355` (ophthalmic education review) — **exclude** (researcher call).
- `REC-003544` (mobile-app testing) — **exclude** (researcher call).
- `REC-005634` (creativity rating, classical ML) — **exclude** (researcher call).
- `REC-003189` (contact-center QA fairness) — pulled out of the 50 for
  reconsideration under the researcher's own "who is assessed, not
  where" framing (workplace-training-style assessment of a human agent)
  — **include**.
- Remaining 49 of the 50 high-confidence candidates — blind 10-record
  spot-check (seed 20260722: REC-004951, REC-004260, REC-000308,
  REC-004821, REC-004995, REC-000265, REC-001547, REC-000954,
  REC-000316, REC-004312) passed 10/10 — **all 49 exclude**.

**Total: 52 confirmed exclusions, 2 reconsidered to include.** Corpus:
146 → 94. Logged as PA-004 in `outputs/logs/protocol_amendments.md`,
applied to `master_records.csv` and
`title_abstract_screening_worklist.csv` (decision fields only — no
extraction/appraisal rows deleted, same policy as PA-002). All downstream
documents (reproducibility report, PRISMA flow, synthesis draft,
bibliography, README, CONTEXT) regenerated from the new corpus. See
`outputs/CORPUS_FREEZE_v1.1.md` for the frozen snapshot.