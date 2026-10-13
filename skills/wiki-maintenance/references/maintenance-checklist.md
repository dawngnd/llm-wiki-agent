# Maintenance Checklist

## Weekly Maintenance
- [ ] Check for broken wikilinks (`grep -roh '\[\[[^]]*\]\]' wiki/ | sort -u`)
- [ ] Verify `wiki/index.md` is up to date with all pages
- [ ] Review recently ingested sources for quality
- [ ] Check for orphan pages (no inbound links)

## Monthly Maintenance
- [ ] Full lint pass (10-point check via `wiki-lint` skill)
- [ ] Stale content check (source dates vs. wiki claims)
- [ ] Knowledge gap analysis (topics mentioned but lacking depth)
- [ ] Graph connectivity review (find clusters and orphans)
- [ ] Language consistency check (Vietnamese with bilingual headers)
- [ ] Frontmatter validation on all pages

## After Every 10 Ingests
- [ ] Run wiki-lint skill
- [ ] Check cross-reference completeness
- [ ] Verify index completeness
- [ ] Review graph for new clusters/orphans
- [ ] Check for duplicate pages across directories
