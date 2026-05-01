# GEMMA — Stitch Design Prompt
> Paste this into Google Stitch (labs.google/stitch) to generate the GEMMA UI.

---

## App Overview

Design a mobile-first Progressive Web App (PWA) called **GEMMA** — *Guided Emergency & Medical Management Assistant*. It is used by Barangay Health Workers (BHWs) in the Philippines to triage patients at community health centers. The app runs on Android Chrome and must be usable by non-clinical users in a busy, noisy health center environment.

**Platform:** Android mobile (390px viewport), installable PWA  
**Language:** Filipino / Taglish labels throughout the UI  
**Tone:** Trustworthy, calm, clinical — not playful or gamified  
**Accessibility:** Outdoor/fluorescent lighting, low digital literacy users  

---

## Brand & Color Palette

| Token | Hex | Use |
|---|---|---|
| Navy | `#1B3A6B` | Primary headers, nav bar, primary buttons |
| Forest Green | `#2D6A2D` | Success states, GREEN triage badge |
| Gold | `#F5C518` | Highlights, YELLOW triage badge background |
| Danger Red | `#C0392B` | RED triage badge, urgent alerts |
| Amber | `#E67E22` | Secondary warnings, YELLOW triage text |
| Light Gray | `#F0F4F8` | App background, card surfaces |
| White | `#FFFFFF` | Card fill, input fields |

**Typography:** Clean sans-serif (e.g., Inter or Noto Sans). Body minimum 16px. Key labels 20px+. Bold weight for triage results.

**Touch targets:** All buttons and interactive elements minimum 48px tall.

---

## Screens to Design

Design all 6 screens as a mobile app flow. Show them as connected screens (like a Figma prototype walkthrough).

---

### Screen 1 — Home / Shift Start (`screen-home`)

**Purpose:** BHW starts their shift before seeing any patients.

**Layout:**
- Top: GEMMA logo + tagline *"Gabay sa Triage ng Barangay"* centered, navy background header
- Center card (white, rounded-16, shadow):
  - Label: **"Pangalan ng BHW"** (BHW Name)
  - Large text input field
  - Label: **"Email ng Coordinator"** (Coordinator Email)
  - Large text input field
  - Label: **"Petsa ng Shift"** (Shift Date) — auto-filled, read-only display
- Bottom: Large primary button, full width, navy background, white text:  
  **"SIMULAN ANG SHIFT"** (Start Shift)
- Footer text tiny: *"GEMMA — Barangay Platero Health Center"*

---

### Screen 2 — New Patient Intake (`screen-intake`)

**Purpose:** BHW collects patient info and chief complaint.

**Layout:**
- Top nav bar (navy): Back arrow + **"Bagong Pasyente"** (New Patient) title
- Section header: **"Impormasyon ng Pasyente"** (Patient Info) — small gray label
- Card 1 — Patient Profiling (white, rounded):
  - Row: **Pangalan** (Name) — text input, optional badge shown
  - Row: **Edad** (Age) — number input
  - Row: **Kasarian** (Sex) — segmented toggle: **Lalaki / Babae**
  - Row: **Tirahan** (Address/Barangay) — text input, optional
- Card 2 — Vital Signs (white, rounded, collapsible):
  - Label: **"Vital Signs (opsyonal)"**
  - Row: **Presyon ng Dugo** (Blood Pressure) — text input, placeholder "120/80"
  - Row: **Temperatura** (Temperature) — text input, placeholder "37.0°C"
- Card 3 — Chief Complaint (white, rounded):
  - Label: **"Pangunahing Reklamo"** (Chief Complaint) — required, red asterisk
  - Large multiline text area, placeholder: *"Ilarawan ang sintomas ng pasyente..."*
  - Min height: 120px
- Camera section:
  - Label: **"May makikitang kondisyon?"** (Visible condition?)
  - Large secondary button with camera icon: **"Kumuha ng Litrato"** (Take Photo)
  - Shows thumbnail preview if photo taken, with ✕ to remove
- Bottom: Primary CTA button, full-width, forest green:  
  **"I-ASSESS NG GEMMA"** (Assess with GEMMA)
  - Shows loading spinner with text *"Sinusuri..."* while AI processes

---

### Screen 3 — Triage Result (`screen-result`)

**Purpose:** Display the AI triage output. This is the most important screen.

**Layout:**
- Top nav bar (navy): Back arrow + patient name or **"Resulta ng Triage"**
- **Triage Badge — FULL WIDTH, high contrast:**
  - RED variant: `#C0392B` background, white text, large bold: **"🔴 AGARANG DALHIN SA RHU"** (Refer to RHU Urgently)
  - YELLOW variant: `#E67E22` background, white text: **"🟡 IPAKITA SA DOKTOR"** (Show to Doctor)
  - GREEN variant: `#2D6A2D` background, white text: **"🟢 MAAARING PANGASIWAAN"** (Can Be Managed at Home)
  - Below badge text in smaller font: triage reason in Filipino
- Card — **"Top 5 Posibleng Kondisyon"** (Top 5 Possible Conditions):
  - Numbered list (1–5), each item has: condition name (bold) + plain Filipino explanation below
  - Disclaimer in italics, small font, gray: *"Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor."*
- Card — **"Mga Katanungan para sa Pasyente"** (Follow-up Questions):
  - 3 question rows, each with:
    - Question text in Filipino
    - Short text input for BHW to record patient answer
  - Button: **"I-update ang Resulta"** (Update Result) — re-runs assessment with answers
- Bottom button row (two buttons, equal width):
  - Left: secondary outline button — **"I-save ang Pasyente"** (Save Patient)
  - Right: primary navy button — **"SOAP Note →"**

---

### Screen 4 — Handoff Summary (`screen-summary`)

**Purpose:** Doctor handoff SOAP note, printable/shareable.

**Layout:**
- Top nav bar: **"Handoff Summary"**
- Patient header card (light navy background, white text):
  - Patient name, age, sex — left column
  - Triage badge (small, color-coded) — right column
  - Timestamp below
- SOAP Note card (white):
  - **S — Subjective:** complaint as reported
  - **O — Objective:** vitals + image findings if any
  - **A — Assessment:** top conditions + triage level
  - **P — Plan:** recommended next step in Filipino
  - Each section clearly separated with a thin divider and bold label
- Disclaimer box (amber background, rounded): small text, italic —  
  *"Hindi ito opisyal na medikal na rekord. Para sa gabay ng doktor lamang."*
- Bottom action buttons (stacked, full width):
  - Primary: **"I-GENERATE NG PDF"** (Generate PDF) — navy, with download icon
  - Secondary: **"Ibahagi"** (Share) — outline button with share icon

---

### Screen 5 — Patient Log (`screen-log`)

**Purpose:** Running table of all patients triaged this shift.

**Layout:**
- Top nav bar: **"Listahan ng Pasyente"** (Patient Log) + patient count badge (e.g., "12")
- Filter row: small pill buttons — **Lahat / RED / YELLOW / GREEN** (All / RED / YELLOW / GREEN)
- Patient list (scrollable, card per row):
  - Each card: 
    - Left: triage color dot (large) + patient number
    - Center: Chief complaint (bold, 1 line) + name/age if available (smaller, gray)
    - Right: Status badge (Pending / Seen / Referred / Sent Home) + time
  - Tap to expand card: shows top condition + action buttons (Mark Seen / Refer / Send Home)
- Floating action button (bottom right, navy circle): **"+"** — starts new patient intake

---

### Screen 6 — End Shift (`screen-endshift`)

**Purpose:** Shift summary, export, and email confirmation.

**Layout:**
- Top nav bar (navy): **"Tapusin ang Shift"** (End Shift)
- Shift header: BHW name + date, centered
- Stats grid (2×2, white cards with colored tops):
  - Total Patients — large number, navy
  - 🔴 RED — count + percentage, red
  - 🟡 YELLOW — count + percentage, amber
  - 🟢 GREEN — count + percentage, green
- Top Conditions card: numbered list, top 3 most common conditions this shift
- Email confirmation card (light gray):
  - Label: **"Ipadala ang ulat sa:"** (Send report to:)
  - Shows coordinator email (read-only)
  - Toggle: **"Magpadala ng Excel report"** (checked by default)
- Bottom buttons (stacked, full width):
  - Primary: **"TAPUSIN AT IPADALA"** (End Shift & Send) — danger red background (emphasize finality)
  - Secondary: **"I-download ang Excel"** — outline, forest green
- Small footer: *"GEMMA — Guided Emergency & Medical Management Assistant"*

---

## Navigation Pattern

Bottom navigation bar (fixed, white, navy icons/text, 56px tall):
- 🏠 **Home** — shift info
- ➕ **Pasyente** — new patient (center, larger button, navy circle)
- 📋 **Listahan** — patient log
- 📤 **Shift** — end shift / export

---

## UI Component Rules

- **Card style:** white background, `border-radius: 16px`, subtle drop shadow
- **Input fields:** white, 1px navy border, 16px font, 48px min height, rounded-8
- **Buttons:**
  - Primary: navy fill, white text, rounded-12, 52px height, full-width on mobile
  - Secondary: white fill, navy border + text, same sizing
  - Danger: `#C0392B` fill, white text — only for irreversible actions
- **Badges:** rounded-full, colored fill, white text, 14px font, uppercase
- **Triage badge (main):** full-width, 72px height, large bold text, corner-radius 12px
- **Icons:** use Material Symbols or similar — outline style, 24px default

---

## App Shell

- Status bar: navy background
- Bottom nav: white background, `border-top: 1px solid #E2E8F0`
- Page background: `#F0F4F8` (light gray)
- Consistent 16px horizontal padding on all screens
- Safe area insets respected (Android bottom nav)

---

*GEMMA — Guided Emergency & Medical Management Assistant*
*Para sa mga Barangay Health Worker ng Pilipinas*
