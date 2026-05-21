#!/usr/bin/env python3
"""Nature-style grouped bar chart for the component ablation (replaces Table 5).

Conveys two findings:
  1. Tool necessity is language-dependent: in zh SER all non-vanilla conditions
     reach ~0, but in ja SER the prompt-only verifier stays high while Full drops.
  2. Rhyme driver: in zh ARI only Full reaches 0.77; the others sit near Vanilla.
"""

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 7,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
})

# Nature NPG qualitative palette
NPG = {"blue": "#3C5488", "cyan": "#4DBBD5", "teal": "#00A087", "coral": "#E64B35"}

conditions = ["Vanilla", "Prompt-only verifier", "Syllable-counter only", "Full (Phase 1+2)"]
colors = [NPG["blue"], NPG["cyan"], NPG["teal"], NPG["coral"]]

groups = ["zh SER↓", "zh ARI↑", "ja SER↓"]
# values[condition][group]; np.nan = no data (sc-only on ja)
values = {
    "Vanilla":               [0.814, 0.306, 0.987],
    "Prompt-only verifier":  [0.000, 0.296, 0.593],
    "Syllable-counter only": [0.002, 0.324, np.nan],
    "Full (Phase 1+2)":      [0.000, 0.767, 0.073],
}

n_groups = len(groups)
n_cond = len(conditions)
bar_w = 0.20
x = np.arange(n_groups)

fig, ax = plt.subplots(figsize=(3.3, 2.35))

for i, cond in enumerate(conditions):
    offset = (i - (n_cond - 1) / 2) * bar_w
    vals = values[cond]
    bars = ax.bar(x + offset, [0 if np.isnan(v) else v for v in vals], bar_w,
                  color=colors[i], label=cond, edgecolor="white", linewidth=0.3)
    for xi, v in zip(x + offset, vals):
        if np.isnan(v):
            continue
        # value label; nudge tiny bars so the number is readable
        ax.text(xi, v + 0.018, f"{v:.2f}", ha="center", va="bottom",
                fontsize=5.2, color="black")

ax.set_xticks(x)
ax.set_xticklabels(groups, fontsize=7.5)
ax.set_ylim(0, 1.08)
ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax.set_ylabel("Metric value", fontsize=7.5)
ax.tick_params(width=0.8, length=3)

# light separators between metric groups
for xs in (0.5, 1.5):
    ax.axvline(xs, color="0.85", linewidth=0.6, zorder=0)

ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.20), ncol=2,
          fontsize=5.8, handlelength=1.1, columnspacing=1.0, handletextpad=0.4)

fig.tight_layout()
out = "paper/figs/ablation"
fig.savefig(f"{out}.pdf", bbox_inches="tight")
fig.savefig(f"{out}.png", dpi=300, bbox_inches="tight")
print(f"saved {out}.pdf and {out}.png")
