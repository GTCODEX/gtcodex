# ⚡ LeadFinder

> **High-accuracy autonomous local business lead generator, website audit engine, and instant cold outreach system for digital agencies, web developers, SEOs, and consultants.**  
> Find businesses with **no website**, a **broken website**, or **only social media profiles**, perform live **conversion & SEO audits**, discover verified **emails & WhatsApp numbers**, and dispatch **hyper-tailored, human outreach writeups** with 1-click or automated SMTP.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Dependencies: Zero](https://img.shields.io/badge/Dependencies-Zero%20(Pure%20Stdlib)-success?style=flat-square)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/frankdotdev/Leadfinder/pulls)
[![Open Source Love](https://img.shields.io/badge/Open%20Source-%E2%99%A5-ff69b4?style=flat-square)](https://github.com/frankdotdev/Leadfinder)

---

## 💡 Why LeadFinder?

Digital agencies, freelance web developers, and cold outreach specialists spend hours manually browsing Google Maps to find local businesses needing web design, redesigns, or marketing services. Commercial lead platforms charge **$100+/month**, gate results behind lead credits, and fail to diagnose technical website problems or write customized pitches.

**LeadFinder is 100% free, open-source, and runs locally with ZERO pip dependencies.** It queries live global map databases, performs multi-tier website health & SEO audits, aggressively hunts verified contact emails, and drafts human-written, industry-specific pitches tailored to the exact problems diagnosed for that business.

---

## ✨ Key Features

### 🗺️ Resilient Multi-Tier Map & Geocoding Engine
- **OpenStreetMap (Overpass API)**: 100% free, unmetered, and requires no API key or credit card.
- **Smart Commercial Core Geocoding**: Automatically calibrates search bounding boxes ($\pm 0.075^\circ \approx 16\text{ km}\times 12\text{ km}$) to target downtown urban cores, preventing timeouts in massive metros like London, Toronto, Manchester, and Austin.
- **Smart State & Region Detection**: Searching states/provinces (e.g. `Texas`, `Ontario`, `Bavaria`) detects the broad region and automatically targets its primary commercial center instead of an empty rural centroid.
- **5 Global Overpass Mirrors**: Redundant failover between `overpass-api.de`, `kumi.systems`, `private.coffee`, `osm.ch`, and `nchc.org.tw`.
- **Dual Fallbacks**: Seamless failover to **Nominatim Bounded Search** and **Photon Komoot OSM Geo-Search** (<300ms, proximity-filtered) so searches never return blank.
- **High Volume Yield**: Returns **100–300+ leads** per search query.
- **Google Places API (New)**: Optional location grid search for global commercial density.

### 🔍 Deep Multi-Tier Email & Contact Extraction
- **Cloudflare Email De-obfuscation**: Decodes protected `data-cfemail` addresses automatically.
- **JSON-LD Schema Extraction**: Parses `<script type="application/ld+json">` for embedded `LocalBusiness` contact details not listed in plaintext.
- **Expanded Legal & Subpage Crawler**: Crawls high-priority subpages where registered contact emails are mandatory:
  - `/contact`, `/contact-us`, `/about`, `/about-us`
  - `/privacy`, `/privacy-policy`, `/gdpr` *(UK/EU registered contact & DPO emails)*
  - `/impressum`, `/imprint`, `/terms`, `/legal`
  - `/enquiries`, `/booking`, `/appointments`, `/team`
- **Rate-Limited Multi-Engine Search**: Thread-locked search engine snippet hunting (DuckDuckGo, DDG Lite, Bing) preventing 403 bot blocks and capturing `@gmail.com`, phone numbers, and social links.
- **High-Probability Domain Email Candidates**: For active custom domains hiding emails behind forms, derives category-appropriate addresses (`orders@{domain}` for bakeries, `bookings@{domain}` for salons, `info@{domain}`, `enquiries@{domain}`).
- **URL-Encoding Artifact Protection**: Eliminates false positives from search engine query strings (`%22%40gmail.com`).

### 🩺 Live Website Technical, SEO & Conversion Audit
Automatically diagnoses 9 high-ticket operational and technical issues on working websites:
1. **SSL & Security**: Detects insecure HTTP or expired SSL certificates.
2. **Mobile Load Speed**: Flags slow load times (>2.8s) causing visitor abandonment.
3. **Mobile Responsiveness**: Flags missing viewport tags.
4. **24/7 Chat & WhatsApp**: Flags absence of instant messaging or AI reception widgets.
5. **Online Booking System**: Flags missing 1-click booking/reservation systems for salons, clinics, restaurants, and gyms.
6. **Local SEO Schema**: Checks for missing Google Maps `LocalBusiness` JSON-LD schema.
7. **Meta Description**: Detects missing Google search snippet tags.
8. **Retargeting Pixels**: Detects missing Meta (Facebook) and Google Tag Manager pixels.
9. **Outdated Copyright**: Detects stale designs with outdated copyright years.

### ✍️ Hyper-Tailored, Industry-Specific Outreach Pitches
Every lead receives a custom, human-written cold email and social DM/WhatsApp pitch based on their category and live audit findings:
- **Clinics, Doctors & Healthcare**: Focuses on after-hours patient drop-off, missed appointment calls, 24/7 WhatsApp emergency triage, and Google Maps Local 3-Pack SEO.
- **Salons, Barbers & Spas**: Focuses on cutting out Instagram DM phone tag, 1-click booking calendars, and automated appointment reminders to prevent no-shows.
- **Bakeries, Cafes & Restaurants**: Focuses on mobile lookbooks, visual menus, and 1-click WhatsApp custom cake and catering inquiries.
- **Gyms & Fitness**: Focuses on free trial pass funnels and automated follow-up.
- **Trades & Contractors**: Focuses on emergency click-to-call and instant quote triage.
- **Live Audited Sites**: Dynamically quotes the **exact 2 audit issues** diagnosed on their live site with clear commercial impact.
- **AI Outreach Mode**: Optional integration with **Gemini 2.5 Flash** or **Groq Llama 3.3 70B** for AI-generated writeups when an API key is configured.

### ✉️ Autonomous SMTP Emailer & Single-Send Ledger
- **Built-in SMTP Dispatch**: Supports Gmail App Passwords and custom SMTP relays.
- **Single-Send Deduplication**: Persistent ledger (`data/sent_emails.json`) tracks sent emails to guarantee you never contact the same business twice.
- **Auto-Email Mode**: Automatically emails qualified leads the moment they are discovered.
- **Dry-Run Mode**: Simulates email dispatch for safe testing without contacting recipients.
- **1-Click Outreach**: Pre-filled `mailto:` links, 1-click WhatsApp pitch launcher (`wa.me/`), and direct Instagram/Facebook DM links.

---

## 🚀 Quick Start

**Zero external pip packages required.** LeadFinder runs out-of-the-box on standard Python 3.10+.

### 1. Clone the repository
```bash
git clone https://github.com/frankdotdev/Leadfinder.git
cd Leadfinder
```

### 2. Run the server
```bash
python server.py
```

### 3. Open your browser
Visit:
```
http://localhost:8000
```

---

## 📖 Usage Guide

### Finding & Auditing Leads (Free)
1. Select **OpenStreetMap (free, no key)** in the map provider dropdown.
2. Enter a **City** (e.g., `Toronto`, `London`, `Manchester`, `Austin`, `Sheffield`).
3. Enter a **Business type** (e.g., `bakery`, `clinic`, `salon`, `restaurant`, `plumber`, `gym`).
4. Click **Find & Enrich Leads**. LeadFinder will query the map servers, run live site audits, hunt contact emails, and prepare tailored writeups.

### Configuring Automated Outreach & SMTP
1. Click the **Outreach & SMTP Settings** button in the top bar.
2. Enter your sender profile: **Name**, **Company**, **Portfolio URL**, and optional custom pitch offer.
3. Configure your mail server:
   - **SMTP Host**: `smtp.gmail.com`
   - **SMTP Port**: `465` (SSL)
   - **SMTP Email**: Your email address
   - **SMTP App Password**: Your 16-character [Google App Password](https://myaccount.google.com/apppasswords)
4. (Optional) Toggle **Auto-Send Email** to dispatch emails automatically upon lead discovery, or enable **Dry-Run Mode** to test risk-free.
5. (Optional) Add your **Gemini** or **Groq** API key for LLM-powered pitch customization.
6. Click **Test SMTP Connection** to verify your setup.

---

## 📊 CSV Export Format

Exported CSVs provide complete lead intelligence ready for CRMs:
- `name` - Business name
- `category` - Industry / amenity type
- `address` - Physical street address
- `email` - Primary and secondary extracted emails
- `phone` - Contact phone number
- `website` - Target URL or social link
- `site_status` - `no_website`, `social_only`, `broken`, `working`
- `site_note` - Diagnostic summary (e.g., `Loads fine`, `DNS lookup failed`, `Domain parked`, `HTTP 404`)
- `audit_issues` - Live audit findings (e.g. Slow Load, Missing Local Schema, No Booking System)
- `lead_score` - Prioritization score (0–99) based on digital gap severity and contact availability
- `rating` / `reviews` - Star rating and review count from map servers
- `outreach_subject` - Tailored email subject line
- `outreach_body` - Full tailored email pitch
- `outreach_dm` - Short message formatted for WhatsApp or Instagram DMs
- `maps_url` - Direct Google Maps link

---

## 🛠️ Architecture

```
leadfinder/
├── static/
│   ├── index.html       # Responsive dashboard with modal settings & Lucide SVG icons
│   ├── style.css        # Modern dark/light themed responsive layout
│   └── app.js           # Client-side state, polling, filtering, modal logic, & CSV export
├── providers.py         # Resilient multi-tier map engine (Overpass, Nominatim, Photon, Google Places)
├── outreach.py          # Email hunting, live site audit, SMTP mailer, & pitch generation
├── server.py            # Async verification pipeline, job streaming API, & static server
├── data/
│   ├── geocache.json    # Local coordinate cache for zero-latency repeat searches
│   ├── settings.json    # Persisted outreach & SMTP configuration
│   └── sent_emails.json # Single-send deduplication ledger
├── .gitignore           # Git ignore rules
└── README.md            # Documentation
```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the project (`https://github.com/frankdotdev/Leadfinder/fork`)
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

If you found LeadFinder helpful, please give it a ⭐️ on GitHub!

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.

---

## 👨‍💻 Author & Credits

Built with ❤️ by **[Frank Oge](https://frankoge.com)** of **[Hackverse Technologies](https://hackversetechnologies.vercel.app)**.
