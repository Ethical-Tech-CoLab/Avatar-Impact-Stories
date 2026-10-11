# Decision-model recommendation: preserve curated playback

Date: 2026-10-11. Public-source assessment; no live model integration.
Reviewed [README](https://github.com/Ethical-Tech-CoLab/Avatar-Impact-Stories/blob/adef8013bf5fe8516c590e4cdb4f13978f178bbf/README.md).
This is documentation-led, not an audit of consent or media provenance.

## Recommendation

The current kiosk plays curated first-person impact stories through avatar
media. Playback, buffering, manifest lookup and idle-state behavior need
deterministic code, not decision-model calls.

If curators later need to organize a larger approved catalogue, an offline
theme-tagging assistant may be useful. It must use curator-approved text,
permit multiple themes and unknown, and retain provenance/disclosure.
Do not score credibility, trauma, emotional impact or deservingness; do not
infer consent, identity or biographical facts from faces or voices.

## Methods and test

Start with manual tags and lexical search. Compare a licensed local classifier
and, only with explicit rights/processing approval, Jev,
Microsoft-Decision-1 or Sage. The
[TypeSafe bounded-task guide](https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md)
is architectural guidance, not evidence for person-level judgments.

Split by story/person so segments of the same account cannot leak across
evaluation sets. Have curators adjudicate theme tags and preserve disagreement.
Measure omitted themes, false tags, unknown handling, review effort and total
cost. Do not use viewer engagement as the gold label for whose story matters.

## Gate

No live reordering by personal characteristics, emotion inference, altered
testimony or automated publication. Keep kiosk playback and existing curation
unchanged. Hosted-model access does not confer content rights; exact proprietary
weights are not available locally. The default is no new model dependency.
