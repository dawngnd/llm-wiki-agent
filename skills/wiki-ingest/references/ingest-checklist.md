# Ingest Quality Checklist

## Pre-Ingest
- [ ] Source file readable and complete
- [ ] Wiki directory structure exists (`wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/synthesis/`)
- [ ] `wiki/index.md` and `wiki/log.md` exist
- [ ] Searched existing wiki pages for duplicates (grep)

## During Ingest
- [ ] Source summary page created in `wiki/sources/` with proper frontmatter
- [ ] All entities identified and pages created/updated in `wiki/entities/`
- [ ] All concepts identified and pages created/updated in `wiki/concepts/`
- [ ] Wikilinks added between all related pages
- [ ] Naming conventions followed (kebab-case filenames, kebab-case wikilinks)
- [ ] Content written in Vietnamese with bilingual headers
- [ ] No contradictions left unnoted

## Post-Ingest
- [ ] `wiki/index.md` updated with new entries under correct category
- [ ] `wiki/log.md` entry appended with ingest summary
- [ ] Search verification: `grep -rl "new-page-name" wiki/` returns results
- [ ] User informed of results

## Quality Gates
- [ ] Source page is factual only (no interpretation)
- [ ] Each wikilink target file exists on disk
- [ ] Frontmatter `type` field matches directory name
- [ ] No PascalCase or Title Case in wikilinks
- [ ] Tags include `open-spec` (from changelogs) or `urd` (from raw)
