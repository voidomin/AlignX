# StructScope: Positioning & Go-to-Market Plan

Keeping the name (see rationale below) — this is a plan for problem framing, audience
targeting, and distribution, not a rebrand. Nothing here requires code changes; it's a
guide for README/landing copy and where to actually put this in front of students and
researchers.

## Why the name stays

`StructScope` was already chosen deliberately in v3 (see `docs/ROADMAP_V3.md` §3.3) when
the product's scope genuinely broadened from an alignment calculator to a
structure-to-function platform. Nothing in v4 is a similar category change, there's no
established audience yet to confuse, and the name itself carries no baggage — the actual
barrier between this tool and its audience isn't what it's called.

## 1. The problem, stated sharply

Structure-prediction databases (AlphaFold DB, ESM Metagenomic Atlas) have produced
**hundreds of millions of protein structures with no known function.** Sequence search
(BLAST-style) is the default first move for "what is this protein" — and it fails
precisely on the structures that need it most, because sequence identity decays past
recognition over evolutionary time while 3D fold is conserved far longer.

**The hook**: *"You have one structure and no idea what it does. Sequence search came up
empty. Now what?"* — that's the exact situation StructScope's Discover mode is built for,
and it's a real, common dead end, not a hypothetical.

Compare mode (multi-structure alignment, RMSD, clustering, phylogeny) is the other half —
useful on its own, but it's the *familiar* half. Discover is the actual differentiator and
should lead every pitch, README hero, and demo — Compare is the depth behind it, not the
headline.

## 2. Audience: two segments, two different pitches

Don't write one generic pitch — students and researchers are looking for different proof.

| Segment | What they actually need to see | Where the doubt will come from |
|---|---|---|
| **Researchers** | Real hit tables, match probabilities, citations for every data source used (already in README's Citation section), a way to verify the method isn't a black box | "Is this rigorous enough to reference in my own work, or just a toy?" |
| **Students** | A guided *why* — not just an answer, but the reasoning ("this neighbor matched at prob 0.9 and carries a thionin-family domain, so...") | "Can I actually understand what this is telling me, or do I need a PhD to read the output?" |

This maps directly to something already built: the **Public/Student/Researcher detail
levels** in Discover mode (`docs/FEATURES.md` §3.4) aren't just a UI nicety — they're
already the answer to both segments' actual doubt. Lead with that in any pitch: *"the same
result, at the depth you actually need."*

## 3. Elevator pitch (for README hero, landing copy, a forum post)

> Got a protein structure with no known function — your own AlphaFold model, an
> unannotated PDB entry, a metagenomic "dark matter" sequence? StructScope searches it
> against structural databases (not just sequence databases) to find related proteins
> sequence search would miss, then pulls real domain/GO-term/pathway annotations for what
> it finds — explained at whatever depth you need, from a plain-language summary to raw
> hit tables.

Cut this down further for a one-line summary (bio.tools listing, GitHub description):

> Structure-to-function inference for orphan protein structures — find what a structure
> is related to when sequence search comes up empty, then aggregate real annotations for
> the hits.

## 4. Credibility signals to make more visible

These already exist in the codebase/docs but aren't surfaced where a skeptical
researcher would look first:

- **Citations already exist** (README's bottom section) but are buried after
  install/config instructions — move a condensed version much higher, ideally right
  under the elevator pitch, since "does this cite its data sources properly" is often
  the first thing a researcher checks.
- **`SECURITY.md`'s honest "what's actually been checked" section** is a genuine trust
  signal (most student/portfolio projects don't have this) — worth a one-line callout
  in the README, not just a link in a table.
- **Test count (227 backend + 105 frontend) and CI status** are proof-of-rigor signals
  a researcher deciding whether to trust a tool's output would want — currently
  mentioned only in the Testing section; a badge (already have version/Python/license
  badges) or a one-line mention near the top would surface this earlier.
- **A live, triable deployment** (still pending from the earlier deploy decision) is the
  single biggest credibility lever — "try it right now" beats every paragraph of
  description. Nothing else in this plan matters much until that's live.

## 5. README/landing changes this implies

Concrete edit list for whenever this gets actioned (not done yet — this doc is the plan):

1. Replace the current opening paragraph (dense, feature-list-first) with the elevator
   pitch from §3, Discover-mode-first, Compare mode as the supporting half.
2. Move a condensed "data sources & methods" credibility line up near the top, not
   buried after installation instructions.
3. Add a one-line "227 backend + 105 frontend tests, CI-verified" trust signal near the
   top badges.
4. Link `docs/FEATURES.md` prominently near the top (already added to the doc table,
   but a direct "see everything it can do" link belongs in the hero section too).
5. Once deployed: a "Try it live" link is the single highest-value addition to the top
   of the README — everything else here is secondary to that.

## 6. Distribution: where this audience actually looks

Ranked by fit for a structural-biology tool aimed at students/researchers, not generic
"post it everywhere" advice:

1. **[bio.tools](https://bio.tools)** — the actual registry researchers search when
   looking for a bioinformatics tool for a specific task. Listing here is high-effort-to-
   payoff: one submission, indexed permanently, exactly the audience that's already
   looking for something like this.
2. **r/bioinformatics** and **r/AskAcademia** — real traffic from the target audience,
   but framing matters: lead with the problem ("sequence search failed me on this
   structure, so I built...") not a feature dump, or it reads as an ad.
3. **A relevant GitHub Topic tag** (`bioinformatics`, `structural-biology`,
   `protein-structure`) on the repo itself — free, and it's how a lot of researchers
   browsing GitHub actually discover tools.
4. **A university bioinformatics/computational-biology mailing list or Slack**, if the
   maintainer has access to one (department, course, or program affiliation) — direct
   line to the exact audience, worth more than broad social posting.
5. **A short demo video or GIF in the README** showing a real Discover run end-to-end
   (upload → hits → annotation → plain-language summary) — most researchers deciding
   whether to try a tool from a GitHub README make that call from the README's visuals
   before reading a word of text.

## 7. What "working" looks like

Concrete, checkable signals instead of vague success — revisit this list once the app
is actually live and distributed:

- GitHub stars/forks from outside the maintainer's own network.
- Any bio.tools listing traffic or citation of the tool in a forum/paper/thread.
- Real Discover-mode usage against structures that aren't the demo examples (4RLT,
  1CRN, AF-P69905-F1) already used throughout this project's own testing.
