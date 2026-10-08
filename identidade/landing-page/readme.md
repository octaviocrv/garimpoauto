# Garimpo Auto — Design System

> Fusão Brasil × Japão: a energia do garimpo brasileiro com a precisão e estética oriental do Han, nosso mascote.

## About

**Garimpo Auto** is a Brazilian tech startup for car dealers — a daily work tool for "revendedores" to manage car listings, find good deals, and communicate with buyers. The brand merges two cultural aesthetics: the Brazilian "amigo do povo" directness with Japanese precision and street-culture cool, embodied by **Han**, the mascot inspired by street racing culture.

### Sources

- Mascot images: AI-generated 3D Pixar-style character (`assets/mascot-han-face.jpeg`, `assets/mascot-han-fullbody.jpeg`)
- Brand guide: user-provided markdown (Garimpo Auto identity)
- Fonts: Google Fonts (Zen Kaku Gothic New, Plus Jakarta Sans, Inter)

---

## Content Fundamentals

- **Language:** Brazilian Portuguese, casual register
- **Tone:** Direct, friendly, trustworthy. "Amigo do povo" — like a friend who knows cars
- **Casing:** Sentence case for UI, title case for brand name only
- **Person:** "Você" (informal you). The app talks TO the dealer, not AT them
- **Humor:** Light, natural, never forced. Mineiro humor undertone
- **Emoji:** No emoji in UI. Only in marketing/social if appropriate
- **Vocabulary:** Always "carro" (never "veículo"), "anúncio" (never "listing"). Brand is always "Garimpo Auto"
- **Error messages:** Human and calm: "Não achei esse carro agora, tenta de novo?"
- **Avoid:** Technical jargon, long text, exaggerated promises ("o melhor do Brasil")

---

## Visual Foundations

### Color System

The palette is built from Han's jacket — a classic complementary pair of **teal** and **burnt orange** — grounded on a **black + white** base.

| Role | Color | Hex | Token |
|------|-------|-----|-------|
| Base dark | Preto Carbono | `#0A0A0A` | `--color-black` |
| Base light | Branco Neve | `#FFFFFF` | `--color-white` |
| Primary | Azul-Petróleo (Teal) | `#0F766E` | `--color-teal-700` |
| Primary light | Teal Claro | `#14B8A6` | `--color-teal-500` |
| Accent | Laranja-Terracota | `#C2410C` | `--color-orange-700` |
| Accent warm | Laranja Quente | `#EA580C` | `--color-orange-600` |
| Special | Ouro Garimpo | `#FBBF24` | `--color-gold-400` |
| Text primary | Cinza Grafite | `#1E293B` | `--color-slate-800` |
| Text secondary | Cinza Médio | `#64748B` | `--color-slate-500` |
| Surface alt | Cinza Prata | `#E2E8F0` | `--color-slate-200` |

**Rules:**
- Light mode: white background, slate text, teal + orange accents
- Dark mode: black background, white text, lighter teal + orange
- Teal + Orange always appear together as the brand signature
- Ouro Garimpo reserved for special moments (deals, premium badges, price highlights)
- Never use pure black `#000000` for large text areas — use `--color-slate-800`

### Typography

Three fonts, each with a cultural purpose:

| Font | Role | Why |
|------|------|-----|
| **Zen Kaku Gothic New** | Display titles, brand name, hero text | Japanese font with clean personality — brings oriental aesthetic without cliché |
| **Plus Jakarta Sans** | Subtitles, prices, car model names, data | Modern geometric — precision for numbers and data |
| **Inter** | Body copy, buttons, UI elements | Maximum legibility, monospaced numbers for KM/year comparison |

**Weights:** Bold/Black for titles, SemiBold for subtitles, Medium for labels, Regular for body.

**Minimum sizes:** 14px body text, 12px captions, 24px+ for slide/presentation text.

### Spacing & Layout

- Mobile-first, designed to fit in a quick phone glance
- 4px base grid, 8px incremental steps
- Cards: `--radius-md` (8px) default, `--radius-lg` (12px) for larger cards
- Badges/pills: `--radius-full` (999px)
- Shadows: subtle and functional (`--shadow-sm` for cards), never decorative

### Backgrounds & Surfaces

- Primary: solid white or solid black. No patterns, no textures
- Cards float on `--color-slate-50` or `--color-slate-100` backgrounds
- No full-bleed imagery in app UI — imagery is always contained in cards
- Marketing/social may use teal or dark backgrounds with white text

### Animation & Interaction

- Transitions: `150ms ease` for micro-interactions (hover, focus)
- No bounces, no spring physics — clean and fast
- Hover states: slight background shift or opacity change
- Press/active: darken by one shade step
- Focus rings: `2px solid var(--border-focus)` with 2px offset
- Loading: "Garimpando..." text with subtle pulse animation

### Borders & Shadows

- Borders: `1px solid var(--border-default)` — clean, subtle, organizational only
- Card shadows: `--shadow-sm` default, `--shadow-md` on hover
- No inner shadows, no colored shadows, no dramatic drop shadows
- Protection gradients: only for text over mascot images

### Corner Radii

- Small elements (badges, chips): `--radius-full` (999px)
- Buttons: `--radius-md` (8px)
- Cards: `--radius-md` (8px) to `--radius-lg` (12px)
- Modals/sheets: `--radius-xl` (16px) top corners
- App icon: `--radius-2xl` (24px) or circle

### Imagery

- Mascot Han is the only illustration element
- No stock photos in UI — car photos are user-uploaded listing content
- No decorative illustrations, no hand-drawn elements
- Color treatment: natural, warm tones (matching Han's palette)

---

## Mascot — Han

Han is the face of Garimpo Auto. A 3D Pixar-style character: Asian male, medium dark hair, confident half-smirk, wearing a teal + orange jacket.

- **App icon:** Han's face in a circle with white border over teal or black background
- **Empty states:** Full-body Han, casual and friendly
- **Loading:** "Garimpando..." with Han
- **Never:** distort, recolor outside palette, use smaller than 32px

Assets: `assets/mascot-han-face.jpeg`, `assets/mascot-han-fullbody.jpeg`

---

## Iconography

- Style: outline/stroke icons, 1.5px–2px stroke weight
- Recommended set: Lucide Icons (CDN: `https://unpkg.com/lucide@latest`)
- No emoji in UI
- No car clichés: no wheels, gears, speedometers, checkered flags, roads
- Icons should feel neutral and functional, not playful

---

## What NEVER to do

- Corporate cold aesthetic or luxury dealership appearance
- Car clichés: wheels, speedometers, checkered flags, roads
- Heavy or complicated screens
- Technical language, long text, or exaggerated promises
- Decorative kanji or oriental elements without function — the influence is structural, not ornamental
- Pure black `#000000` in large text areas
- Flashy gradients or neon colors
- Emoji in UI elements

---

## Logo

- **File:** `identidade/logo.svg` (TBD — not yet created)
- **Dark background version:** `identidade/logo-branco.svg` (TBD)
- **Usage:** App header, phone icon, empty states, "Garimpando..." loading
- **Suggested size:** 120–200px width in HTML

---

## File Index

```
├── readme.md              ← This file
├── styles.css             ← Global CSS entry (imports only)
├── tokens/
│   ├── colors.css         ← Color custom properties
│   ├── typography.css     ← Font imports + type tokens
│   └── spacing.css        ← Spacing, radius, shadow tokens
├── assets/
│   ├── mascot-han-face.jpeg
│   └── mascot-han-fullbody.jpeg
├── guidelines/            ← Foundation specimen cards
├── components/            ← Reusable UI primitives
└── SKILL.md               ← Agent skill file
```
