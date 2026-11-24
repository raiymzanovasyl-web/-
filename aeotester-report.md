# AEOTester report

Generated 2026-11-24 by the [AEOTester](https://aeotester.com/?utm_source=plugin&utm_medium=report) plugin, rubric v1.2.0.

| | |
|---|---|
| Live site | https://metal.kg |
| Audited | 6 page(s): a sample, one page per template, from 34 URLs found |

> Sampled 6 page(s), one per template (homepage, top-level pages, and a listing plus an item from each section), from 34 URLs found. Use --pages N to change the sample size or --all to audit every page.

> Fetched live from https://metal.kg with the user agent "Mozilla/5.0 (compatible; AEOTester-Audit/0.2; +https://github.com/shapito27/aeotester-site-audit)".

<details><summary>Pages in the sample</summary>

| Page | Stands in for |
|---|---|
| https://metal.kg/ | homepage |
| https://metal.kg/catalog | section listing /catalog/ |
| https://metal.kg/catalog/washer | section item /catalog/ |
| https://metal.kg/services | static page |
| https://metal.kg/about | static page |
| https://metal.kg/contacts | static page |

</details>

## Summary

**Score: 102 / 127 (80%) - Nearly Optimized**

6 points do not apply to this site and are left out of the total (max 133).

| Category | Score |
|---|---:|
| AI crawler access | 12 / 18 |
| Crawlability and indexing | 18 / 18 |
| Structured data | 17.7 / 20 |
| Meta and social tags | 19.2 / 22 |
| Content structure and quality | 25.2 / 36 |
| Agent readiness | 10 / 13 (6 pts n/a) |

## Issues by points lost

### FAIL llms.txt Detection - 0 / 6 (-6)

`ai-access.llms-txt` | auto-fix

llms.txt not found

- No llms.txt (HTTP 404) - `https://metal.kg/llms.txt`

Fix: Create an llms.txt at the site root with "# Site Name", a "> summary" line and "## Section" lists of [Title](url) links. See https://llmstxt.org/

### FAIL Content Freshness - 0 / 5 (-5)

`content.freshness` | assisted

No publish or modified dates found

- No publish or modified date (article:published_time, JSON-LD datePublished or <time datetime>) - `https://metal.kg/:1`, `https://metal.kg/catalog:1`, `https://metal.kg/catalog/washer:1`, `https://metal.kg/services:1`, `https://metal.kg/about:1` and 1 more
- Pages losing points: 6 of 6

Fix: Add article:published_time and article:modified_time meta tags, or JSON-LD datePublished/dateModified.

### FAIL Author Signals - 1 / 5 (-4)

`content.author` | assisted

Missing: author attribution, expertise credentials. Found: author link

- No author attribution (JSON-LD author, meta name="author" or byline) - `https://metal.kg/:1`, `https://metal.kg/catalog:1`, `https://metal.kg/catalog/washer:1`, `https://metal.kg/services:1`, `https://metal.kg/about:1` and 1 more
- No expertise signals (credentials, job title, years of experience) near the author or in the page text - `https://metal.kg/:1`, `https://metal.kg/catalog:1`, `https://metal.kg/catalog/washer:1`, `https://metal.kg/services:1`, `https://metal.kg/about:1` and 1 more
- Fewer than 3 trust signals; missing: /privacy, /terms, <address> - `https://metal.kg/:1`, `https://metal.kg/catalog:1`, `https://metal.kg/catalog/washer:1`, `https://metal.kg/services:1`, `https://metal.kg/about:1` and 1 more
- Pages losing points: 6 of 6

Fix: Add author attribution: a JSON-LD Person as the Article author, or <meta name="author">. Add credentials (certifications, degrees, years of experience) to establish expertise

### FAIL Markdown for Agents - 0 / 3 (-3)

`agent-readiness.markdown` | assisted

No Markdown representation for agents: "Accept: text/markdown" returns HTML

- A request with "Accept: text/markdown" got text/html; charset=utf-8 (HTTP 200) and no working markdown alternate is advertised - `https://metal.kg/:1`, `https://metal.kg/catalog:1`, `https://metal.kg/catalog/washer:1`, `https://metal.kg/services:1`, `https://metal.kg/about:1` and 1 more
- Pages losing points: 6 of 6

Fix: Answer "Accept: text/markdown" with a Markdown version and Content-Type: text/markdown (Cloudflare offers this as "Markdown for Agents", or use edge middleware), and advertise it with <link rel="alternate" type="text/markdown" href="..."> or a Link header.

### WARN Meta Title - 3.7 / 5 (-1.3)

`meta.title` | auto-fix

Title: 66 chars - 1 issue(s)

- Title slightly long (66 chars, optimal 50-60): "Металлоизделия в Бишкеке от производителя — анкерные болты и шайбы" - `https://metal.kg/:1`
- Title too long (84 chars, may be truncated): "Каталог продукции — анкерные болты, шайбы, ванночки, тайроты \| ИП Райымжанов, Бишкек" - `https://metal.kg/catalog:1`
- Title slightly long (67 chars, optimal 50-60): "Анкерные шайбы АШ в Бишкеке — цены от производителя \| ИП Райымжанов" - `https://metal.kg/catalog/washer:1`
- Title too long (81 chars, may be truncated): "Услуги — изготовление металлоизделий и плазменная резка в Бишкеке \| ИП Райымжанов" - `https://metal.kg/services:1`
- Title slightly long (66 chars, optimal 50-60): "О компании \| ИП Райымжанов — Производство металлоизделий в Бишкеке" - `https://metal.kg/about:1`
- Title slightly long (68 chars, optimal 50-60): "Контакты — +996 779 592 026 \| ИП Райымжанов, Профсоюзная 2/1, Бишкек" - `https://metal.kg/contacts:1`
- Pages losing points: 6 of 6

Fix: Rewrite the title to 50-60 characters, specific to the page, as "Page Topic \| Brand".

### WARN Open Graph - 2.2 / 3 (-0.8)

`meta.open-graph` | auto-fix

Missing 1 required OG tag(s)

- Missing og:image - `https://metal.kg/catalog:1`, `https://metal.kg/catalog/washer:1`, `https://metal.kg/services:1`, `https://metal.kg/about:1`, `https://metal.kg/contacts:1`
- Missing og:type (use "website" or "article") - `https://metal.kg/catalog:1`, `https://metal.kg/services:1`, `https://metal.kg/about:1`, `https://metal.kg/contacts:1`
- Pages losing points: 5 of 6

Fix: Add og:title, og:description, og:image (absolute URL), og:type and og:url (equal to the canonical URL) as <meta property="og:..."> in the shared head.

## Advice (no points)

Worth knowing, but not scored: these can be deliberate choices.

### Content Signals

`ai-access.content-signals`

- robots.txt has no Content-Signal line - `https://metal.kg/robots.txt:1`

Suggestion: Add a line such as "Content-Signal: search=yes, ai-input=yes, ai-train=no" to robots.txt to state how AI may use your content (the yes/no values are your policy choice). See https://contentsignals.org/

## All checks

| Check | Status | Score | Fix |
|---|---|---:|---|
| AI Bot Crawlability | PASS | 12 / 12 | auto-fix |
| llms.txt Detection | FAIL | 0 / 6 | auto-fix |
| Content Signals | ADVICE | not scored | auto-fix |
| Indexability | PASS | 8 / 8 | auto-fix |
| Sitemap Detection | PASS | 5 / 5 | auto-fix |
| SSL / HTTPS | PASS | 2 / 2 | assisted |
| HTTP Behavior | PASS | 3 / 3 | assisted |
| Structured Data | PASS | 12.7 / 15 | auto-fix |
| Schema Validation | PASS | 5 / 5 | auto-fix |
| Meta Title | WARN | 3.7 / 5 | auto-fix |
| Meta Description | PASS | 4.3 / 5 | auto-fix |
| Open Graph | WARN | 2.2 / 3 | auto-fix |
| Twitter Cards | PASS | 3 / 3 | auto-fix |
| Language Tags | PASS | 3 / 3 | auto-fix |
| Mobile Friendly | PASS | 3 / 3 | auto-fix |
| Semantic Headings | PASS | 7 / 8 | auto-fix |
| Content Quality | PASS | 4.2 / 5 | assisted |
| Content Freshness | FAIL | 0 / 5 | assisted |
| Author Signals | FAIL | 1 / 5 | assisted |
| Image Alt Text | PASS | 5 / 5 | assisted |
| Internal Linking | PASS | 4 / 4 | assisted |
| Accessibility | PASS | 4 / 4 | auto-fix |
| Server-Rendered Content | PASS | 6 / 6 | assisted |
| Markdown for Agents | FAIL | 0 / 3 | assisted |
| Agent-Usable Controls | PASS | 4 / 4 | assisted |
| Agent Protocol Discovery | N/A | - | assisted |

## Notes

- Scores come from the live site as a crawler sees it: the HTML the server sends, before any JavaScript runs. Checks marked "inconclusive" could not be read (blocked, rate limited or timed out) and were not scored down.
- To fix issues, open the site's code in your coding agent (Claude Code, Codex) and run the AEOTester fix skill (`/aeotester:fix` in Claude Code) there. It shows a diff and asks before writing anything.

---

Check a live URL: https://aeotester.com/?utm_source=plugin&utm_medium=report
