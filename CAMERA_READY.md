# Camera-ready checklist (EMNLP 2026, due Aug 30 AoE)

## Paper status

| Item | State |
|---|---|
| Template mode | `\usepackage[final]{acl}` (authors and emails visible, no line numbers) |
| Main content | ends on page 9 (limit: 9 pages for a long camera-ready) |
| Limitations | page 10, required, does not count |
| References | page 11 |
| Appendices | pages 12-16 |
| LaTeX | 0 overfull boxes, 0 undefined citations or references |
| Authors | Guan-Ming Chiu (gmchiu@arbor.ee.ntu.edu.tw), Chiao-Chih Cheng (r14921040@ntu.edu.tw), Kuan-Wei Lee (r14921101@ntu.edu.tw), all National Taiwan University |
| License | Software: Apache-2.0 (`LICENSE`); sampled lyric windows and benchmark artifacts: CC BY-NC-SA 4.0 |

## References

All 36 cited works were resolved against ACL Anthology, CrossRef, OpenAlex, arXiv, or the publisher's
proceedings page. 36 citations = 36 bibliography entries, no undefined or missing keys. Corrections made:

- Franzon (2008) DOI `10.1080/13556509.2008.10799244` (404) -> `10.1080/13556509.2008.10799263`
- Chen et al. (2025) pages `23431--23446` -> `23420--23435` (per the Anthology PDF)
- Added verified DOIs to 7 entries and missing page ranges to 5

The bibliography now contains exactly the 36 cited entries: there are no missing, duplicate, or unused keys.

## Section numbers for the Responsible NLP Checklist

The structure changed since submission. Use these numbers:

| Topic | Section |
|---|---|
| Limitations | Limitations (unnumbered, after §7) |
| Ethics / risks | "Ethical considerations" paragraph inside Limitations |
| Artifacts used and cited | §2.4 Phonetic Resources; §4 IPA-Augmented Skill Framework; §6.1 Setup; Appendix E |
| License of artifacts we release | §6.1 Setup (Apache-2.0); dataset redistribution in Ethical considerations |
| Intended use of artifacts | Ethical considerations |
| PII / offensive content | Ethical considerations |
| Documentation of artifacts | §6.1 Setup; Appendices A and C |
| Data statistics | §6.1 Setup (en-zh n=100 five-line windows; en-es and en-ja n=30) |
| Computational experiments | §6, Appendix E (CLT), Appendix F (turns, cost, tokens) |
| Model size and budget | Appendix E (CLT 600M mBART on MPS); Appendix F (per-item cost and tokens); Table 3 (latency) |
| Experimental setup and hyperparameters | §6.1 Setup; Appendix C Hyperparameters |
| Descriptive statistics | Table 3 (single run, seed 42 for sampling only); §6.3 Human Evaluation; Appendix F |
| Parameters for packages | §4; Appendices B and C |
| Human subjects / annotators | §6.3 Human Evaluation; Ethical considerations |
| Instructions to participants | §6.3 Human Evaluation |
| Recruitment and payment | Ethical considerations (volunteers, no payment) |
| Data consent | Ethical considerations |
| Ethics review board | Ethical considerations (exempt, anonymized ratings only) |
| Use of AI assistants | §4-§6 and Appendix A: the Claude models are the object of study and the orchestrator |

Two answers changed since the submission checklist and must be updated:

1. The orchestrators are `claude-haiku-4-5-20251001`, `claude-sonnet-5`, and `claude-opus-5` (the
   submission said Haiku 4.5 / Sonnet 4.6 / Opus 4.7).
2. The human evaluation is a new round on the current Opus outputs: 6 raters, 10 items, 60 judgments,
   three rated axes (singability, naturalness, meaning).

## Information the organizers still need from the authors

- Who registers the paper for presentation (name and email)
- Presenting author email, country of residence, visa status, invitation letter needed or not
- In-person or virtual; oral or poster preference
- Travel dates if presenting in person
- ORCID for each author on OpenReview

## Reproducing the numbers

```bash
uv run scripts/eval_fixed.py --songs <run>/test_songs.json --out out.json vanilla=<van>/partial agent=<run>/partial
uv run scripts/analyze_human_eval.py
uv run --with cmudict scripts/validate_counter.py --songs <run>/test_songs.json --spanish <es_run>/partial
uv run scripts/make_human_eval.py --manifest data/human_eval/human_eval_key.csv   # rebuilds the published sheet
```
