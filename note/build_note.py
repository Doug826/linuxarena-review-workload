"""Build the three-page research note from the repository tables.
Usage, from the repository root: python note/build_note.py . LinuxArena_research_note.pdf
Needs reportlab and the DejaVu fonts. Set NOTE_FONT_DIR to a folder holding DejaVuSans.ttf,
DejaVuSans-Bold.ttf and DejaVuSerif.ttf, or install matplotlib, which bundles them."""
import csv
import os
import re
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PKG, OUT = Path(sys.argv[1]), sys.argv[2]
W, H = 595.2756, 841.8898
X0, X1 = 48.0, 547.3
TEXT_W = X1 - X0


def font_dir():
    candidates = [os.environ.get("NOTE_FONT_DIR", ""), "/usr/share/fonts/truetype/dejavu"]
    try:
        import matplotlib
        candidates.append(os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf"))
    except ImportError:
        pass
    for d in candidates:
        if d and os.path.exists(os.path.join(d, "DejaVuSerif.ttf")):
            return d
    sys.exit("DejaVu fonts not found: set NOTE_FONT_DIR or install matplotlib")


FONT_DIR = font_dir()
for name in ("DejaVuSans", "DejaVuSans-Bold", "DejaVuSerif"):
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, name + ".ttf")))
TEAL, INK, MUTED = HexColor("#006C65"), HexColor("#17313D"), HexColor("#425B67")
RULE, FILL, CI = HexColor("#C8D8DA"), HexColor("#E6F1F0"), HexColor("#91A6AC")
BUDGET, BLUE, BROWN = HexColor("#954924"), HexColor("#40649C"), HexColor("#AE6637")
DATE = "25 November 2026"
REPO = "https://github.com/Doug826/linuxarena-review-workload"
URLS = {
    "mirror": "https://huggingface.co/datasets/anonymouslinuxarena/linuxarena-public",
    "runs": "https://github.com/redwoodresearch/linuxarena-paper",
    "audit": "https://arxiv.org/abs/2610.22243",
    "olmo": "https://arxiv.org/abs/2610.31593",
    "issue": "https://github.com/UKGovernmentBEIS/control-arena/issues/938",
}


def baseline(top, font, size):
    descent = pdfmetrics.getFont(font).face.descent / 1000.0
    return H - top - size * (1 + descent)


def runs_from(markup):
    out, pos = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*|\[(.+?)\]\((.+?)\)", markup):
        if m.start() > pos:
            out.append((markup[pos:m.start()], False, None))
        out.append((m.group(1), True, None) if m.group(1) else (m.group(2), False, m.group(3)))
        pos = m.end()
    if pos < len(markup):
        out.append((markup[pos:], False, None))
    return out


def wrap(markup, size, width=TEXT_W):
    words = []
    for text, bold, url in runs_from(markup):
        for piece in re.split(r"(\s+)", text):
            if piece:
                words.append((piece, bold, url))
    lines, line, x = [], [], 0.0
    for piece, bold, url in words:
        font = "DejaVuSans-Bold" if bold else "DejaVuSans"
        w = pdfmetrics.stringWidth(piece, font, size)
        if piece.isspace():
            if line:
                line.append((" ", bold, url))
                x += pdfmetrics.stringWidth(" ", font, size)
            continue
        if x + w > width and line:
            while line and line[-1][0] == " ":
                line.pop()
            lines.append(line)
            line, x = [], 0.0
        line.append((piece, bold, url))
        x += w
    if line:
        lines.append(line)
    return lines


class Doc:
    def __init__(self, path):
        self.c = canvas.Canvas(path, pagesize=(W, H))
        self.c.setTitle("One cutoff, ten review workloads")
        self.c.setAuthor("Doug Christopher")
        self.c.setSubject("Review workload of an AI-control monitor across LinuxArena environments")

    def text(self, s, x, top, font, size, color, align="left"):
        c = self.c
        c.setFont(font, size)
        c.setFillColor(color)
        y = baseline(top, font, size)
        {"left": c.drawString, "right": c.drawRightString, "centre": c.drawCentredString}[align](x, y, s)

    def para(self, markup, top, size, leading, color=INK, link_color=TEAL):
        lines = wrap(markup, size)
        for i, line in enumerate(lines):
            y = baseline(top + i * leading, "DejaVuSans", size)
            merged = []
            for piece in line:
                if merged and merged[-1][1:] == piece[1:]:
                    merged[-1] = (merged[-1][0] + piece[0],) + piece[1:]
                else:
                    merged.append(piece)
            x = X0
            for text, bold, url in merged:
                font = "DejaVuSans-Bold" if bold else "DejaVuSans"
                self.c.setFont(font, size)
                self.c.setFillColor(link_color if url else color)
                self.c.drawString(x, y, text)
                w = pdfmetrics.stringWidth(text, font, size)
                if url and text.strip():
                    self.c.linkURL(url, (x, y - 2, x + w, y + size * 0.8), relative=0, thickness=0)
                x += w
        return top + (len(lines) - 1) * leading

    def heading(self, s, top):
        self.text(s, X0, top, "DejaVuSans-Bold", 12, TEAL)

    def page_frame(self, n, title, subtitle):
        c = self.c
        self.text("AI MONITORING   /   RESEARCH NOTE", X0, 35.5, "DejaVuSans-Bold", 8.5, TEAL)
        self.text(f"Doug Christopher   \u00b7   {DATE}", X1, 35.6, "DejaVuSans", 8.4, MUTED, "right")
        c.setStrokeColor(RULE); c.setLineWidth(0.6); c.line(X0, H - 54.0, X1, H - 54.0)
        self.text(title, X0, 78.2, "DejaVuSerif", 26, INK)
        last = self.para(subtitle, 117.6, 11.0, 16.0, MUTED)
        self.text("LinuxArena   /   Review workload at a 1% action-level budget", X0, 806.8, "DejaVuSans", 8.0, MUTED)
        self.text(f"{n} of 3", X1, 806.8, "DejaVuSans", 8.0, MUTED, "right")
        return last

    def table(self, top, header_h, row_h, cols, header, rows, header_size=8.4, row_size=9.0, bold_cells=()):
        c = self.c
        c.setFillColor(FILL); c.rect(X0, H - top - header_h, TEXT_W, header_h, stroke=0, fill=1)
        for x, s in zip(cols, header):
            self.text(s, x, top + (header_h - header_size) / 2 + 0.8, "DejaVuSans-Bold", header_size, INK)
        c.setStrokeColor(RULE); c.setLineWidth(0.6)
        for i, row in enumerate(rows):
            rtop = top + header_h + i * row_h
            for x, s in zip(cols, row):
                self.text(s, x, rtop + (row_h - row_size) / 2 - 0.3, "DejaVuSans", row_size, INK)
            c.line(X0, H - (rtop + row_h), X1, H - (rtop + row_h))

    def save(self):
        self.c.save()


NAMES = {"file_indexing": "File Indexing", "model_registry": "Model Registry", "shared_dotfiles": "Shared Dotfiles",
         "tiktok": "TikTok", "user_tracking": "User Tracking", "clinical_trial": "Clinical Trial",
         "slack_clone": "Slack Clone", "auto_workflow": "Auto Workflow", "media_processing": "Media Processing",
         "web_scraping": "Web Scraping"}


def page1(d):
    c = d.c
    d.page_frame(1, "One cutoff, ten review workloads",
                 "A 1% review budget for a GPT-5 Nano monitor across ten LinuxArena environments.")
    last = d.para("Would a cutoff set on ordinary work elsewhere keep a new review queue within capacity? I used 200 "
                  "honest Claude Opus tasks, with 20 per environment and 12,494 scored actions. Each environment took "
                  "its cutoff from the other nine. All ten selected 7.5 because the 1% target lay inside the group of "
                  "scores tied there.", 149.5, 10.4, 15.5)
    d.heading("Two score values changed the queue", last + 25.9)
    d.table(241.0, 20.0, 20.0, (53.0, 217.0, 389.0),
            ("Flagging rule", "Honest actions flagged", "Share of ordinary actions"),
            [("Score above 8.0", "22", "0.18%"), ("Score above 7.5", "105", "0.84%"),
             ("Score at least 7.5", "199", "1.59%")])
    last = d.para("There were 83 actions exactly at 8.0 and 94 exactly at 7.5. Randomly flagging just enough of the "
                  "7.5 ties to spend 1% in each source split gave an expected held-out rate of 1.08% overall, but "
                  "2.12% in File Indexing, more than twice its budget. Four environments exceeded their local budget "
                  "under both the strict and the fractional rule.", 332.5, 10.2, 15.0)
    top = last + 26.4
    d.heading("False alerts per 1,000 ordinary actions", top)
    axis_top = top + 19.1
    grid_top, step = axis_top + 10.0, 16.6
    rows = list(csv.DictReader((PKG / "original" / "results" / "threshold_transfer.csv").open()))
    rows.sort(key=lambda r: -float(r["alerts_per_1000"]))
    grid_bottom = grid_top + step * len(rows) - 1.6
    xs = lambda v: 177.0 + 8.1 * v
    for v in (0, 10, 20, 30):
        budget = v == 10
        c.setStrokeColor(BUDGET if budget else RULE); c.setLineWidth(1.0 if budget else 0.4)
        c.line(xs(v), H - grid_top, xs(v), H - grid_bottom)
        d.text("10  (1% budget)" if budget else str(v), xs(v) - 3.0, axis_top, "DejaVuSans", 7.9,
               BUDGET if budget else MUTED)
    d.text("Rate", 471.3, axis_top, "DejaVuSans-Bold", 7.9, MUTED)
    d.text("Tasks\u00b9", 502.8, axis_top, "DejaVuSans-Bold", 7.9, MUTED)
    for i, r in enumerate(rows):
        label_top = grid_top + 5.5 + step * i
        centre = H - (grid_top + 9.0 + step * i)
        d.text(NAMES[r["environment"]], X0, label_top, "DejaVuSans", 8.6, INK)
        if r["ci_high_per_1000"]:
            c.setStrokeColor(CI); c.setLineWidth(2.1)
            c.line(xs(float(r["ci_low_per_1000"])), centre, xs(float(r["ci_high_per_1000"])), centre)
        c.setFillColor(TEAL); c.circle(xs(float(r["alerts_per_1000"])), centre, 2.9, stroke=0, fill=1)
        d.text(f"{float(r['alerts_per_1000']):.1f}", 471.3, label_top + 0.1, "DejaVuSans", 8.4, INK)
        d.text(r["tasks_with_alerts"], 507.3, label_top + 0.1, "DejaVuSans", 8.4, INK)
    last = d.para("\u00b9 Tasks with at least one alert out of 20. Points show observed rates using scores above 7.5. "
                  "Bars show 95% task-bootstrap intervals at the fitted cutoff. Web Scraping had no observed alerts, "
                  "so its bootstrap supplies no useful upper bound.", grid_bottom + 13.0, 8.3, 12.0, MUTED)
    last = d.para("**Interpretation.** The strict rule stayed under 1% when all actions were pooled. File Indexing "
                  "produced 16.7 alerts per 1,000, with a task-level interval of 2.5\u201331.0. A pooled rate gives an "
                  "incomplete picture of local review demand.", last + 24.4, 10.0, 14.0)
    last = d.para(f"**Related work.** [Olmo, Zhang and Tracy (2026)]({URLS['olmo']}) use simulated control "
                  "evaluations to explain most of the variation in safety and monitor scores between LinuxArena "
                  f"environments. A [ControlArena issue]({URLS['issue']}) found that tied trajectory scores left a "
                  "nominal 1% budget unspent for six of ten BashArena monitors, and suggested auditing a random share "
                  "of ties. This note measures the review workload one action-level cutoff creates in each held-out "
                  "environment.", last + 22.0, 10.0, 14.0)
    c.showPage()
    return last


def page2(d):
    d.page_frame(2, "Why the task is the unit of evidence",
                 "Ten tasks generated most of the alerts. Keeping their actions together changed how much evidence "
                 "there was for differences between environments.")
    d.heading("What changes when whole tasks move together", 165.9)
    last = d.para("Only 40 of the 200 honest tasks produced an alert. Ten supplied 61 of the 105. With independent "
                  "actions at the same pooled rate and the actual task lengths, about 76 tasks would be expected to "
                  "produce at least one alert. The task-level variance estimate for the pooled rate was 3.82 times the "
                  "independent-action estimate, corresponding to about 28 independent alerts for that specific "
                  "calculation.", 187.5, 10.4, 15.5)
    last = d.para("A Pearson test treating actions as independent gave p = 1.79 \u00d7 10\u207b\u2078. A more relevant "
                  "exploratory check shuffled complete tasks between ten groups of 20. In 200,000 shuffles the "
                  "all-environment p-value was 0.0785 when weighted by action count and 0.1066 with equal environment "
                  "weights. The original 9,999-shuffle estimate was 0.0763. These are sensitivity results for two "
                  "statistics chosen after inspecting the data.", last + 25.5, 10.4, 15.5)
    d.heading("Could a reviewer predict which tasks would generate alerts?", last + 25.9)
    last = d.para("Bug fixes and language rewrites had higher observed rates than feature additions and refactors. "
                  "Fourteen titles matched the access, credential or network keywords, and only three of those tasks "
                  "generated alerts. Titles are a rough measure of the work an agent actually performs.",
                  last + 25.9 + 21.6, 10.4, 15.5)
    last = d.para("With one environment held out at a time, predictions using task category, title topic or both had "
                  "average deviances of 1.68, 1.66 and 1.64. Lower is better. A baseline using task length and the "
                  "pooled rate scored 1.57. Alerts clustered in tasks, but these labels did not help predict the count "
                  "in a new environment.", last + 25.5, 10.4, 15.5)
    d.heading("Which records support the result?", last + 25.9)
    last = d.para("The primary run had 200 distinct honest action traces. Across the full reviewer sample there were "
                  "586 distinct traces among 932 rows, identified from ordered actions with monitor responses removed. "
                  "Requiring a shell command gave 576 among 918, matching the external audit.",
                  last + 25.9 + 21.6, 10.4, 15.5)
    last = d.para("In a separate set of 92 model-generated attack trajectories, 59 had a verified flag, eight were "
                  "verified misses and 25 were unresolved. The missing-data bound was 64.1%\u201391.3% flagged "
                  "anywhere in a trajectory. This is a baseline result. Changing the cutoff could also change the "
                  "timing and usefulness of detection.", last + 25.5, 10.4, 15.5)
    d.heading("Data, code and AI use", last + 25.9)
    last = d.para(f"I used the public [LinuxArena mirror]({URLS['mirror']}), the [authors\u2019 run repository]"
                  f"({URLS['runs']}) and the [Shortcut Sensitivity audit]({URLS['audit']}). Code, derived tables and "
                  f"offline checks are at [github.com/Doug826/linuxarena-review-workload]({REPO}). ChatGPT and Claude "
                  "assisted with research design, code, cross-checks and drafting.", last + 25.9 + 21.3, 9.0, 13.0,
                  MUTED)
    d.c.showPage()
    return last


def page3(d):
    c = d.c
    d.page_frame(3, "What five or ten local tasks buy",
                 "A wider choice of cutoffs helped in simulation. On recorded tasks, the answer depended on which "
                 "comparison was made.")
    last = d.para("The narrow rule always flags scores above 7.5 and chooses a share of the 7.5 ties. The wider rule "
                  "always flags scores above 8.0 and fills downward through 8.0, 7.5 and 7.0. The pooled method learns "
                  "from the other environments. The local method uses local counts. The hierarchical method combines "
                  "both. The four-stage simulation treats the source population parameters as known.", 165.4, 10.0,
                  14.0)
    d.heading("How much room does the rule leave?", last + 23.5)
    last = d.para("In the fitted simulation, a method with perfect knowledge of each environment averaged 2.05 alerts "
                  "per 1,000 away from target under the narrow rule and 0.63 under the wider rule. The residual was "
                  "unused capacity in quiet environments. Across the ten complete recorded environments, five still "
                  "fell below target even when every score of 7.0 or higher was flagged.", last + 23.5 + 21.5, 9.9,
                  14.0)
    title_top = last + 18.1
    d.text("Simulated mean distance from 10 alerts per 1,000", X0, title_top, "DejaVuSans-Bold", 8.5, INK)
    y0 = title_top + 95.5            # zero line, as in the original layout
    unit = 15.4
    xs = [86.0 + i * (400.0 - 86.0) / 7 for i in range(8)]
    for v in (0, 2, 4):
        c.setStrokeColor(RULE); c.setLineWidth(0.6)
        c.line(86.0, H - (y0 - v * unit), 400.0, H - (y0 - v * unit))
        d.text(str(v), 77.0, y0 - v * unit - 2.9, "DejaVuSans", 7.8, MUTED, "right")
    sim = list(csv.DictReader((PKG / "tables" / "levels_simulation.csv").open()))
    sim = [r for r in sim if r["levels"] == "7.0-8.0" and r["scenario"] == "fitted" and r["test_tasks"] != "100"]
    series = [("Pooled", "levels", "pooled", BLUE), ("Hierarchical, narrow rule", "tie_only", "hierarchical", BROWN),
              ("Hierarchical, wider rule", "levels", "hierarchical", TEAL)]
    for label, rule, method, color in series:
        pts = sorted((int(r["calibration_tasks"]), float(r["true_budget_mae"])) for r in sim
                     if r["rule"] == rule and r["method"] == method)
        coords = [(x, H - (y0 - v * unit)) for x, (_, v) in zip(xs, pts)]
        c.setStrokeColor(color); c.setLineWidth(1.55); c.setLineCap(1); c.setLineJoin(1)
        path = c.beginPath(); path.moveTo(*coords[0])
        for p in coords[1:]:
            path.lineTo(*p)
        c.drawPath(path, stroke=1, fill=0)
        c.setFillColor(color)
        for p in coords:
            c.circle(*p, 2.3, stroke=0, fill=1)
        end_y = coords[-1][1]
        c.setFont("DejaVuSans", 7.8); c.setFillColor(INK)
        c.drawString(408.0, end_y - 2.7, f"{label} {pts[-1][1]:.1f}")
    for x, n in zip(xs, (1, 2, 5, 10, 20, 40, 80, 160)):
        d.text(str(n), x, y0 + 5.3, "DejaVuSans", 7.5, MUTED, "centre")
    cap_top = y0 + 17.9
    d.text("Local calibration tasks in each new environment. Each point summarises 500 simulated studies of ten "
           "environments.", X0, cap_top, "DejaVuSans", 8.1, MUTED)
    top = cap_top + 21.0
    d.heading("Recorded splits give two different comparisons", top)
    tbl = top + 19.1
    d.table(tbl, 18.0, 18.0, (53.0, 119.0, 215.0, 379.0),
            ("Local tasks", "Pooled model", "Local only, narrow / wide", "Hierarchical, narrow / wide"),
            [("5", "8.54", "6.91 / 7.46", "7.68 / 8.14"), ("10", "9.01", "7.07 / 7.83", "7.98 / 8.59")])
    last = d.para("Lower is better. Entries are distances from ten alerts per 1,000, computed after averaging over the "
                  "tie lottery. Both local methods had lower average error than pooling. Both had higher error when "
                  "widened. The same 20 tasks per environment supply 16 overlapping splits. These descriptive means "
                  "cannot establish a sample-size requirement.", tbl + 18.0 * 3 + 11.3, 9.7, 13.6)
    last = d.para("For the wider rule, nominal 80% ranges covered **64%, 63%, 64%** with five local tasks (pooled, "
                  "local, hierarchical) and **69%, 74%, 73%** with ten. Interval scores, which penalise width and "
                  "misses, were respectively **33.9, 54.8, 43.0** and **27.6, 31.7, 31.9**. Lower is better. The "
                  "forecasts describe each method\u2019s own review policy.", last + 21.6, 9.4, 13.5)
    last = d.para("**Decision.** Finish this dataset study here. The wider hierarchical rule still put 24% of simulated "
                  "environments above 12 alerts per 1,000 after ten local tasks, versus 27% pooled. A useful next test "
                  "would freeze a policy, measure overload on fresh tasks, and check the detection retained at that "
                  "workload.", last + 20.5, 9.5, 13.5)
    c.showPage()
    return last


if __name__ == "__main__":
    doc = Doc(OUT)
    ends = [page1(doc), page2(doc), page3(doc)]
    doc.save()
    print("last text line tops per page:", [round(e, 1) for e in ends], "(footer at 806.8)")
