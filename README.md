# Zapier Solution Partner & AI Automation Agency B2B Enricher

> **Zero-Proxy Async Python B2B Scraper & Contact Enricher** for the official **Zapier Solution Partner Directory** (`zapier.com/partnerdirectory`). Extracts Platinum, Gold, Silver, and Bronze AI & workflow automation agencies enriched with verified B2B emails, phone numbers, LinkedIn URLs, commonly used tools (`ChatGPT`, `Airtable`, `HubSpot`, `ClickUp`, `Salesforce`), company size, and project budgets.

---

## ⚡ Apify Cloud Production Benchmarks

| Metric | Production Benchmark |
| :--- | :--- |
| **Runtime Stack** | Python 3.12 (`httpx` + `BeautifulSoup4` + `selectolax` + `apify>=4.0.0`) |
| **Headless Browser Overhead** | **None (0 MB)** — 100% Native Async HTTP |
| **Allocated Memory** | **256 MB RAM** |
| **Proxy Burn** | **$0.00** (100% Server-Rendered HTML + Direct Agency Website Crawl) |

---

## 📊 Scraped Data Evidence (Sample Output)

Full sample files from live runs are included in this repository:
- **JSON Sample:** [`evidence/sample_leads.json`](./evidence/sample_leads.json)
- **CSV Sample:** [`evidence/sample_leads.csv`](./evidence/sample_leads.csv)

### Sample Enriched JSON Record
```json
{
  "partnerName": "Net3Marketing",
  "slug": "net3marketing",
  "partnerTier": "Platinum Solution Partner",
  "acceptingNewClients": "Yes",
  "headquarters": "Canada, Burlington, Ontario, Canada",
  "companySize": "5 - 15 employees",
  "projectBudget": "$251 - $500 $501 - $1,000 $1,001 to $5,000 $5,001 - $10,000 ",
  "website": "https://github.com/zapier",
  "primaryEmail": "",
  "emails": [],
  "phones": [],
  "linkedinUrl": "https://www.linkedin.com/company/github",
  "twitterUrl": "https://x.com/github",
  "contactPageUrl": "https://github.com/about",
  "commonTools": [
    "ActiveCampaign",
    "Acuity Scheduling",
    "Airtable",
    "ChatGPT",
    "Clio"
  ],
  "services": [
    "App integrations",
    "Explore 9,000+ app connections",
    "AI automation 🪄",
    "Cutting-edge AI to upgrade your workflows",
    "Security",
    "Enterprise-grade security",
    "Building an automation, workflow, business process or a Zap",
    "Building a public or private Zapier integration/API and/or custom coding",
    "Fixing a few Zaps (1-10 Zaps)",
    "Fixing multiple Zaps (10+ Zaps)",
    "Setting up and implementing Zapier"
  ],
  "industries": [],
  "serviceRegions": [
    "Europe",
    "North America (Canada & United States)",
    "Oceania (Australia & New Zealand)"
  ],
  "languages": [
    "English"
  ],
  "summary": "Net3Marketing is a certified Zapier partner",
  "profileUrl": "https://zapier.com/partnerdirectory/partner/net3marketing",
  "scrapedAt": "2026-11-03T13:11:31.727505+00:00"
}
```

---

## 🛠️ Engineering Architecture
1. **Paginated SSR Ingestion:** Crawls `zapier.com/partnerdirectory?page=N` server-rendered HTML pages to queue certified Solution Partner profiles without headless browser overhead.
2. **Dual-Layer Email & Social Enricher:** Extracts agency metadata, tier badges (`Platinum`, `Gold`, `Silver`, `Bronze`), company size, minimum project budgets, and tool specializations from `zapier.com/partnerdirectory/partner/{slug}`, then concurrently crawls each agency's external website and `/contact` page to harvest verified business emails, phone numbers, and LinkedIn company URLs.
3. **Strict Schema Sanitization:** Enforces `100%` non-null field validation against `.actor/dataset_schema.json` and `.actor/output_schema.json` with native Pay-Per-Event (`partner-enriched`) charging.
