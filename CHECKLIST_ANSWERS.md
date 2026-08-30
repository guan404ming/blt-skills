# Responsible NLP Checklist: answers to paste on the OpenReview camera-ready page

Where: OpenReview submission 3382 -> Edit -> Camera-Ready Revision. The checklist is a form on that
page, not a file in the paper. The organizers generate a PDF from it and publish it on ACL Anthology.

Every section reference below matches the current camera-ready. The submitted version pointed at the
old numbering (old §5.1 Setup is now §6.1, old §5.6 Human Evaluation is now §6.3) and at line numbers,
which no longer exist in `final` mode. Changes from the submitted answers are marked CHANGED.

---

**A1 Limitations Section:** This paper has a limitations section.

**A2 Potential Risks:** Yes
**A2 Elaboration** (CHANGED: line numbers removed): The "Ethical considerations" paragraph in the
Limitations section discusses copyright risk, eSpeak-NG's uneven coverage of dialectal and
low-resource languages, and the risk of producing singable derivatives without rights-holder consent.

**B Use Or Create Scientific Artifacts:** Yes

**B1 Cite Creators Of Artifacts:** Yes
**B1 Elaboration** (CHANGED: section numbers): §2.4 and §4 cite Phonemizer (Bernard and Titeux, 2021)
and PanPhon (Mortensen et al., 2016); §6.1 and Appendix E cite the dataset and CLT checkpoint
(Ou et al., 2023).

**B2 Discuss The License For Artifacts:** Yes
**B2 Elaboration** (CHANGED): §6.1 states that the open-source software is Apache-2.0; the "Ethical
considerations" paragraph states that sampled en-zh evaluation windows and associated benchmark
artifacts are distributed separately under the source dataset's CC BY-NC-SA 4.0 license.

**B3 Artifact Use Consistent With Intended Use:** Yes
**B3 Elaboration** (CHANGED: line numbers removed): The "Ethical considerations" paragraph explains
that the sampled dataset windows are used for research evaluation and redistributed under the source
license; the complete corpus is not bundled, and users applying the software to new lyrics supply
their own input and bear the rights responsibility.

**B4 Data Contains Personally Identifying Info Or Offensive Content:** No
**B4 Elaboration** (unchanged): The evaluation data is published commercial song lyrics (the public
Ou et al. 2023 benchmark), that is, public artistic works rather than personal or identifying
information, so no PII screening was performed; as a standard public benchmark, it was not separately
screened for offensive content.

**B5 Documentation Of Artifacts:** Yes
**B5 Elaboration** (CHANGED): §6.1 documents the language pairs and test split; Appendix A gives the
prompts and the top-level skill file, Appendix B the skill algorithms, and Appendix C the
hyperparameters.

**B6 Statistics For Data:** Yes
**B6 Elaboration** (CHANGED: windows, not songs): §6.1 reports 100 en-zh test items, each a window of
five consecutive non-empty lines from the public test split (479 distinct source lines in 500 slots,
8 overlapping window pairs); en-es and en-ja use 30 items each. Appendix F reports line-pair
statistics.

**C Computational Experiments:** Yes

**C1 Model Size And Budget:** Yes
**C1 Elaboration** (CHANGED: model IDs, appendix, latency, cost): Appendix E reports CLT as a
600M-parameter mBART run on Apple Silicon MPS (num_beams=5, max_length=36). Table 3 reports median
per-item latency for each orchestrator (63-107 s via API) and Appendix F reports per-item cost and
token counts (for example, 8.1k output and 393k input tokens per Haiku item). The Claude orchestrators
(claude-haiku-4-5-20251001, claude-sonnet-5, claude-opus-5) are API models whose parameter counts are
not public.

**C2 Experimental Setup And Hyperparameters:** Yes
**C2 Elaboration** (CHANGED: parameters that no longer exist removed): §6.1 and the Appendix C
hyperparameter table list all settings: reasoning effort medium, at most 3 attempts per item, at most
10 Phase 2 attempts per line, 5 lines per item, the allowed tool set, and the tokenizers.

**C3 Descriptive Statistics:** Yes
**C3 Elaboration** (CHANGED: seed scope, new human-eval statistics): Table 3 reports a single run per
system over 100 items; the seed (42) fixes only the test-window sample, not LLM decoding, as stated in
the Limitations. §6.2 reports paired bootstrap confidence intervals for the phase ablation and the
COMET differences, §5.4 reports item-cluster bootstrap intervals for the metric-validity correlations,
§6.3 reports a sign test at the judgment and item level plus a two-way cluster bootstrap over raters
and items and Krippendorff's alpha, and Appendix F reports a metric-sensitivity analysis.

**C4 Parameters For Packages:** Yes
**C4 Elaboration** (CHANGED: jieba, not HanLP; pyphen scope): §4 and Appendices B and C report the use
and settings of Phonemizer/eSpeak-NG, PanPhon, pykakasi (Japanese mora), jieba (Chinese segmentation),
PyPinyin, and pyphen (used only inside the CCVO adapter).

**D Human Subjects Including Annotators:** Yes

**D1 Instructions Given To Participants:** Yes
**D1 Elaboration** (CHANGED: three axes, new round): §6.3 describes the rating task: for each of 10
items the rater picks the more singable of two anonymized versions (side randomized) and rates each
1-5 on singability, naturalness, and meaning preservation.

**D2 Recruitment And Payment:** Yes
**D2 Elaboration** (unchanged in substance): The "Ethical considerations" paragraph states that the six
raters were fluent-Mandarin volunteers recruited from the authors' acquaintances who participated
without monetary compensation; given the small scale (60 paired judgments) and the volunteer nature,
no payment was provided.

**D3 Data Consent:** Yes
**D3 Elaboration** (unchanged): The "Ethical considerations" paragraph states that raters were informed
in advance that their anonymized judgments would be used for research evaluation and consented prior
to participating.

**D4 Ethics Review Board Approval:** N/A
**D4 Elaboration** (unchanged): The "Ethical considerations" paragraph states that the study collected
only anonymized pairwise preferences and 1-5 ratings with no personal data, and was determined exempt
under institutional guidelines.

**E Ai Assistants In Research Or Writing:** Yes

**E1 Information About Use Of Ai Assistants:** Yes
**E1 Elaboration** (CHANGED: model IDs and sections): The LLMs (claude-haiku-4-5-20251001,
claude-sonnet-5, claude-opus-5) are the object of study and serve as the orchestrator of the method.
Their role, interface (Claude Code CLI, one `claude -p` call per item), allowed tools, and settings are
documented in §4, §6.1, Appendix A, and Appendix C, and every run is logged as a tool-call trace
released with the code.

---

## Things to double-check while filling the form

- If the form asks for a scientific-artifacts license, ours is Apache-2.0 and the repository is
  https://github.com/guan404ming/blt-skills
- Do not reuse the old line-number references (L486-491 and so on); `final` mode has no line numbers.
- The paper reports three failure categories for lost items (API content filter, model refusal,
  unparsable reply); if the form asks about incomplete data, that is the place to point to
  (Table 3 caption and the Limitations).
