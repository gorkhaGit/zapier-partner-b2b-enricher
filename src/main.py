from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
from urllib.parse import quote, urljoin, urlparse, urlunparse

from apify import Actor
from bs4 import BeautifulSoup
import httpx

PROTO = "https" + "://"
HTTP_PROTO = "http" + "://"
ZAPIER_BASE = f"{PROTO}zapier.com"
DIR_PATH = "/partnerdirectory"

SEED_SLUGS = [
    "automation-consulting-services",
    "flow-digital",
    "connex-digital",
    "getuwired",
    "debesis",
    "ai-first-partners",
    "promopilot",
    "ground-team-solutions",
    "big-red-jelly",
    "work-horse-integrations",
    "allsherpas",
    "delightful-automations",
    "consultevo",
    "step-7-consulting",
    "korix",
    "toki",
    "flowmondo",
    "isales-solutions",
    "that-automation-agency",
    "hypelocal",
    "expreso-agencia-digital",
    "the-joinary",
    "pineo",
    "automatemybiz",
    "mercology",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,12}")
BAD_EMAIL_EXT = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp|css|js|woff|ttf|ico|pdf)$", re.I)
BAD_EMAIL_WORDS = re.compile(
    r"(sentry|example|domain|email\.com|yoursite|wixpress|cloudflare|placeholder|u00|zapier\.com|partnerpage\.io)",
    re.I,
)


def clean_email(raw: str) -> str:
    e = re.sub(r"^mailto:", "", raw or "", flags=re.I).split("?")[0].strip().lower()
    if not re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,12}$", e):
        return ""
    if BAD_EMAIL_EXT.search(e) or BAD_EMAIL_WORDS.search(e):
        return ""
    return e


def normalize_url(raw_url: str) -> str:
    u = str(raw_url or "").strip().rstrip(".,;)")
    if not u:
        return ""
    if not u.startswith((PROTO, HTTP_PROTO)):
        u = f"{PROTO}{u}"
    try:
        p = urlparse(u)
        if not p.netloc or "." not in p.netloc:
            return ""
        return urlunparse((p.scheme, p.netloc.lower(), p.path, "", "", ""))
    except Exception:
        return ""


async def fetch_html(client: httpx.AsyncClient, url: str, timeout: float = 10.0) -> str:
    try:
        resp = await client.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return ""


async def resolve_clearbit_domain(client: httpx.AsyncClient, company_name: str) -> str:
    cleaned = re.sub(r"\|.*$", "", company_name or "").strip()
    if not cleaned or len(cleaned) < 2:
        return ""
    try:
        cb_url = f"{PROTO}autocomplete.clearbit.com/v1/companies/suggest?query={quote(cleaned)}"
        resp = await client.get(cb_url, timeout=4.0)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                domain = data[0].get("domain")
                if domain and "zapier.com" not in domain:
                    return f"{PROTO}{domain}"
    except Exception:
        pass
    return ""


def extract_section_list(soup: BeautifulSoup, heading_keywords: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    targets = [k.lower() for k in heading_keywords]
    for el in soup.find_all(["h2", "h3", "h4", "h5", "div", "p", "span"]):
        txt = el.get_text(strip=True).lower()
        if txt in targets and el.parent:
            for child in el.parent.find_all(["li", "span", "div", "p"]):
                if child.find(["ul", "ol", "div"]):
                    continue
                val = child.get_text(strip=True)
                if (
                    val
                    and val.lower() not in targets
                    and len(val) < 90
                    and "show more" not in val.lower()
                ):
                    if val not in seen:
                        seen.add(val)
                        items.append(str(val))
    return items[:15]


def extract_single_metric(full_text: str, label: str, stop_words: list[str]) -> str:
    stop_pat = "|".join(re.escape(w) for w in stop_words)
    pattern = rf"{re.escape(label)}\s+(.+?)(?=\s+(?:{stop_pat})\b|$)"
    m = re.search(pattern, full_text, flags=re.I)
    if m:
        val = m.group(1).strip()
        return val[:60]
    return ""


def scan_soup_for_contacts(
    soup: BeautifulSoup,
    base_url: str,
    emails: set[str],
    phones: set[str],
    socials: dict[str, str],
) -> None:
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        if not href:
            continue
        low = href.lower()
        if low.startswith("mailto:"):
            ce = clean_email(href)
            if ce:
                emails.add(ce)
        elif low.startswith("tel:"):
            ph = re.sub(r"^tel:", "", href, flags=re.I).strip()
            if 7 <= len(ph) <= 22:
                phones.add(str(ph))
        elif re.search(r"linkedin\.com/(company|in)/", href, re.I) and not socials["linkedinUrl"]:
            if "zapier" not in low:
                socials["linkedinUrl"] = str(href.split("?")[0])
        elif (
            re.search(r"(twitter\.com|x\.com)/[a-z0-9_]+", href, re.I)
            and not re.search(r"intent|share|zapier", href, re.I)
            and not socials["twitterUrl"]
        ):
            socials["twitterUrl"] = str(href.split("?")[0])
        elif not socials["contactPageUrl"] and re.search(
            r"/(contact|about|get-in-touch|talk-to-us|book|schedule)", href, re.I
        ):
            try:
                resolved = urljoin(base_url, href)
                if "zapier.com" not in resolved.lower():
                    socials["contactPageUrl"] = str(resolved)
            except Exception:
                pass

    for raw in EMAIL_RE.findall(soup.get_text(" ", strip=True)):
        ce = clean_email(raw)
        if ce:
            emails.add(ce)


async def enrich_external_website(
    client: httpx.AsyncClient,
    website_url: str,
    initial_emails: set[str] | None = None,
    initial_linkedin: str = "",
) -> dict:
    emails: set[str] = set(initial_emails or set())
    phones: set[str] = set()
    socials: dict[str, str] = {
        "linkedinUrl": str(initial_linkedin or ""),
        "twitterUrl": "",
        "contactPageUrl": "",
    }

    if website_url and "linkedin.com" not in website_url.lower():
        html = await fetch_html(client, website_url, timeout=8.0)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            scan_soup_for_contacts(soup, website_url, emails, phones, socials)

            if not emails and socials["contactPageUrl"]:
                contact_html = await fetch_html(client, socials["contactPageUrl"], timeout=6.0)
                if contact_html:
                    scan_soup_for_contacts(
                        BeautifulSoup(contact_html, "html.parser"),
                        socials["contactPageUrl"],
                        emails,
                        phones,
                        socials,
                    )

    sorted_emails = sorted(emails)[:10]
    return {
        "primaryEmail": sorted_emails[0] if sorted_emails else "",
        "emails": sorted_emails,
        "phones": sorted(phones)[:5],
        "linkedinUrl": str(socials["linkedinUrl"] or ""),
        "twitterUrl": str(socials["twitterUrl"] or ""),
        "contactPageUrl": str(socials["contactPageUrl"] or ""),
    }


def sanitize_record(record: dict) -> dict:
    clean: dict = {}
    for k, v in record.items():
        if v is None:
            clean[k] = ""
        elif isinstance(v, list):
            clean[k] = [str(x) for x in v if x is not None and str(x).strip() != ""]
        elif isinstance(v, int):
            clean[k] = int(v)
        else:
            clean[k] = str(v)
    return clean


async def process_zapier_partner(
    slug: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    partner_tier_filter: str,
    search_query: str,
    enrich_contacts: bool,
) -> dict | None:
    profile_url = f"{ZAPIER_BASE}{DIR_PATH}/partner/{slug}"
    async with semaphore:
        html = await fetch_html(client, profile_url, timeout=12.0)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        title_tag = soup.find("title")
        raw_title = title_tag.get_text(strip=True) if title_tag else ""
        partner_name = (
            h1.get_text(strip=True)
            if h1 and h1.get_text(strip=True)
            else raw_title.split("|")[0].strip() or slug
        )

        main_el = soup.find("main") or soup
        full_text = re.sub(r"\s+", " ", main_el.get_text(" ", strip=True))

        # 1. Partner Tier
        partner_tier = "Solution Partner"
        for badge in ["Platinum", "Gold", "Silver", "Bronze"]:
            if re.search(r"\b" + re.escape(badge) + r"\b", full_text, re.I):
                partner_tier = f"{badge} Solution Partner"
                break

        if partner_tier_filter != "all" and partner_tier_filter.lower() not in partner_tier.lower():
            return None

        accepting_clients = (
            "Yes" if re.search(r"Accepting new clients", full_text, re.I) else "Unspecified"
        )

        # 2. Extract Company Size & Project Budget
        company_size = extract_single_metric(
            full_text,
            "Solution Partner Company Size",
            ["Project Budget", "Services", "Service Regions", "Tools Most Commonly", "Industries"],
        )
        project_budget = extract_single_metric(
            full_text,
            "Project Budget",
            ["Services", "Service Regions", "Tools Most Commonly", "Industries", "Language"],
        )

        # 3. Extract External Website, LinkedIn & Profile Emails
        profile_emails: set[str] = set()
        for raw_e in EMAIL_RE.findall(full_text):
            ce = clean_email(raw_e)
            if ce:
                profile_emails.add(ce)

        external_website = ""
        profile_linkedin = ""
        for a in main_el.find_all("a", href=True):
            txt = a.get_text(strip=True).lower()
            href = (a["href"] or "").strip()
            low = href.lower()
            if not href.startswith((PROTO, HTTP_PROTO)):
                continue
            if re.search(r"linkedin\.com/(company|in)/", low) and "zapier" not in low:
                if not profile_linkedin:
                    profile_linkedin = href.split("?")[0]
                continue
            if (
                ("visit" in txt or "website" in txt or "site" in txt)
                and "zapier.com" not in low
                and "partnerpage.io" not in low
            ):
                external_website = normalize_url(href)
                if external_website:
                    break

        if not external_website:
            for a in main_el.find_all("a", href=True):
                href = (a["href"] or "").strip()
                low = href.lower()
                if href.startswith((PROTO, HTTP_PROTO)) and not re.search(
                    r"zapier\.com|partnerpage\.io|privacy|cookie|linkedin\.com|twitter\.com|x\.com|facebook\.com|instagram\.com|youtube\.com",
                    low,
                ):
                    external_website = normalize_url(href)
                    if external_website:
                        break

        if not external_website and enrich_contacts:
            external_website = await resolve_clearbit_domain(client, partner_name)

        # 4. Extract Tools, Services, Industries, Service Regions, Languages
        common_tools = extract_section_list(
            soup, ("Tools Most Commonly Worked With", "Tools", "Apps")
        )
        services = extract_section_list(soup, ("Services", "Capabilities"))
        industries = extract_section_list(soup, ("Industries", "Industry"))
        service_regions = extract_section_list(soup, ("Service Regions", "Regions"))
        languages = extract_section_list(soup, ("Language", "Languages"))

        # 5. Extract Headquarters
        headquarters = service_regions[0] if service_regions else "Global"
        loc_match = re.search(
            r"(?:Platinum|Gold|Silver|Bronze)\s+([A-Z][A-Za-z0-9\s,.-]{3,55}?)(?=\s+(?:\d\.\d|\(\d+\)|Contact|Write a review|Resources|Services))",
            full_text,
        )
        if loc_match:
            hq_candidate = loc_match.group(1).strip(" .,-")
            if hq_candidate and len(hq_candidate) < 60:
                headquarters = hq_candidate

        meta_desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"}
        )
        meta_description = (
            meta_desc_tag["content"].strip()
            if meta_desc_tag and meta_desc_tag.get("content")
            else ""
        )

        if search_query:
            hay = (
                f"{partner_name} {partner_tier} {headquarters} {' '.join(common_tools)} "
                f"{' '.join(services)} {' '.join(industries)} {meta_description}"
            ).lower()
            if search_query.lower() not in hay:
                return None

        if enrich_contacts:
            contact_data = await enrich_external_website(
                client, external_website, profile_emails, profile_linkedin
            )
        else:
            sorted_pe = sorted(profile_emails)[:10]
            contact_data = {
                "primaryEmail": sorted_pe[0] if sorted_pe else "",
                "emails": sorted_pe,
                "phones": [],
                "linkedinUrl": profile_linkedin,
                "twitterUrl": "",
                "contactPageUrl": "",
            }

        record = {
            "partnerName": str(partner_name or slug),
            "slug": str(slug),
            "partnerTier": str(partner_tier),
            "acceptingNewClients": str(accepting_clients),
            "headquarters": str(headquarters),
            "companySize": str(company_size or "Unspecified"),
            "projectBudget": str(project_budget or "Unspecified"),
            "website": str(external_website or ""),
            "primaryEmail": str(contact_data["primaryEmail"] or ""),
            "emails": list(contact_data["emails"]),
            "phones": list(contact_data["phones"]),
            "linkedinUrl": str(contact_data["linkedinUrl"] or ""),
            "twitterUrl": str(contact_data["twitterUrl"] or ""),
            "contactPageUrl": str(contact_data["contactPageUrl"] or ""),
            "commonTools": common_tools,
            "services": services,
            "industries": industries,
            "serviceRegions": service_regions,
            "languages": languages,
            "summary": str(meta_description or ""),
            "profileUrl": str(profile_url),
            "scrapedAt": datetime.now(timezone.utc).isoformat(),
        }
        return sanitize_record(record)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        search_query = str(actor_input.get("searchQuery") or "").strip()
        partner_tier_filter = str(actor_input.get("partnerTierFilter") or "all").strip()
        max_items = int(actor_input.get("maxItems") or 25)
        max_pages = int(actor_input.get("maxPages") or 5)
        enrich_contacts = bool(actor_input.get("enrichWebsiteContacts", True))

        Actor.log.info(
            f"Starting Zapier Solution Partner Enricher "
            f"(maxItems={max_items}, maxPages={max_pages}, tier='{partner_tier_filter}', enrich={enrich_contacts})"
        )

        discovered_slugs: list[str] = []
        seen_slugs: set[str] = set()

        async with httpx.AsyncClient() as client:
            for page in range(1, max_pages + 1):
                if len(discovered_slugs) >= max_items * 3:
                    break
                page_url = (
                    f"{ZAPIER_BASE}{DIR_PATH}"
                    if page == 1
                    else f"{ZAPIER_BASE}{DIR_PATH}?page={page}"
                )
                html = await fetch_html(client, page_url)
                if not html:
                    continue
                for m in re.finditer(r"/partnerdirectory/partner/([a-zA-Z0-9_-]+)", html):
                    slug = m.group(1).strip()
                    if slug.lower() not in seen_slugs:
                        seen_slugs.add(slug.lower())
                        discovered_slugs.append(slug)

            for s in SEED_SLUGS:
                if s.lower() not in seen_slugs:
                    seen_slugs.add(s.lower())
                    discovered_slugs.append(s)

            Actor.log.info(f"Total unique Zapier Solution Partner profiles queued: {len(discovered_slugs)}")

            semaphore = asyncio.Semaphore(8)
            saved_count = 0
            batch_size = 10

            for i in range(0, len(discovered_slugs), batch_size):
                if saved_count >= max_items:
                    break
                chunk = discovered_slugs[i : i + batch_size]
                tasks = [
                    process_zapier_partner(
                        slug,
                        client,
                        semaphore,
                        partner_tier_filter,
                        search_query,
                        enrich_contacts,
                    )
                    for slug in chunk
                ]
                results = await asyncio.gather(*tasks)
                for record in results:
                    if not record or saved_count >= max_items:
                        continue
                    try:
                        await Actor.push_data(record)
                        saved_count += 1
                        try:
                            await Actor.charge(event_name="partner-enriched", count=1)
                        except Exception:
                            pass
                        Actor.log.info(
                            f"[{saved_count}/{max_items}] Enriched Zapier Partner: "
                            f"{record['partnerName']} ({record['partnerTier']}) | "
                            f"Site: {record['website'] or 'no-site'} | Emails: {len(record['emails'])}"
                        )
                    except Exception as exc:
                        Actor.log.warning(f"Skipped invalid record: {exc}")

        Actor.log.info(f"Finished run! Total Zapier Solution Partner B2B leads pushed: {saved_count}")
