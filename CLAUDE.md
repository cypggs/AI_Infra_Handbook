# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **AI Infra Handbook**, a VitePress-based Chinese documentation site covering AI infrastructure topics (Kubernetes, LLMOps, Agent, RAG, AI SRE, etc.). Each theme follows a fixed 11-chapter structure: background → core ideas → architecture → workflow → modules → source analysis → mini demo → production practice → best practices → interview questions → further reading.

The site auto-deploys to Vercel on pushes to `main`. There is no backend or database.

## Common Commands

```bash
# Install dependencies
pnpm install

# Start local dev server
pnpm docs:dev

# Build the site (also checks for dead links by default)
pnpm docs:build

# Preview the production build
pnpm docs:preview
```

### Mini Demo Tests

Many themes include a self-contained Python mini-demo under `docs/<section>/<theme>/mini-demo/`.

```bash
cd docs/<section>/<theme>/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m <pkg>.demo
```

For example, for the Operator theme:

```bash
cd docs/02-cloud-native/operator/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m operator_mini.demo
```

## High-Level Architecture

### Content Organization

- `docs/` — All source content.
  - `<section>/` — Top-level chapters (`02-cloud-native`, `03-ai-platform`, `04-llmops`, etc.).
  - `<section>/<theme>/` — Individual themes with 11 markdown chapters plus `index.md`.
  - `<section>/<theme>/mini-demo/` — Optional CPU-runnable Python demos.
  - `index.md` — Home page.
  - `guide.md` — Reading guide.
  - `10-roadmap/` — Learning path and interview guide.
- `docs/.vitepress/` — VitePress configuration.
  - `config.ts` — Site config, top navigation (`nav`), theme settings, sitemap.
  - `sidebar.ts` — Sidebar structure. **Must be updated when adding a new theme.**
- `vercel.json` — Vercel deployment settings (`cleanUrls`, rewrites for case-study themes).

### Adding a New Theme

1. Create `docs/<section>/<theme>/` with `index.md` and `01-background.md` … `11-further-reading.md`.
2. Add the theme block to `docs/.vitepress/sidebar.ts` in the correct section.
3. Add entries to the top `nav` in `docs/.vitepress/config.ts` if it should appear in the header dropdown.
4. Update cross-links:
   - `docs/<section>/index.md` — move from “计划中” to “已上线”.
   - `docs/index.md` — add a hero action and progress checkbox.
   - `docs/guide.md` — add a “按主题查阅” bullet.
   - `docs/10-roadmap/learning-path.md` — add to the relevant stage.
   - `README.md` — add to the “已上线主题” list.
   - Add back-links in adjacent themes’ `11-further-reading.md`.
5. Build and test:
   - `pnpm docs:build` must pass with no dead links.
   - Run the mini-demo tests if present.
6. Commit and push to `main`; Vercel auto-deploys.

### Critical Build Constraints

- **Vue mustache in Markdown**: Inline code containing `{{ }}` breaks the build. Use `<code v-pre>{{ ... }}</code>` instead of backticks for Go template / mustache-like placeholders.
- **Dead links**: VitePress fails the build on dead internal links. Do not link to `mini-demo/README.md` as a page; reference it as a backtick code path.
- **Tables**: Markdown tables must not contain `<tag>`-like placeholders; the Vue compiler parses them as HTML.
- **Mermaid**: Supported via `vitepress-plugin-mermaid`. Fenced `mermaid` blocks render as diagrams.

### Deployment Verification

After pushing, verify the live page with `curl -sL` and a content check. For example:

```bash
curl -sL https://ai-infra-handbook.vercel.app/03-ai-platform/kserve/ | grep -o "KServe" | head -1
```

Vercel uses `cleanUrls`, so a non-following poll may return a 308; always use `curl -sL`.

## Git Conventions

- Branch: `main`.
- Commit messages are in Chinese for theme additions.
- End commits with:

```
Co-Authored-By: Claude <noreply@anthropic.com>
```

## Repository Metadata

- License: CC-BY-SA-4.0
- Production URL: https://ai-infra-handbook.vercel.app
- GitHub: https://github.com/cypggs/AI_Infra_Handbook
