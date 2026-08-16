# Pocket Pratyush Website Execution Plan

This execution plan is based on the generated `Pocket_Pratyush_Complete_Website_Master_Plan_v3`, `Pocket_Pratyush_PRD_v1`, and `Pocket_Pratyush_TRD_v1`.

Use this plan after converting the three source documents into Markdown.

Recommended source document names:

- `docs/MASTER_PLAN.md`
- `docs/PRD.md`
- `docs/TRD.md`
- `docs/POCKET_PRATYUSH_EXECUTION_PLAN.md`

Core rule for every phase:

Do not build a giant game and hope people discover the portfolio. Build a sharp portfolio that happens to be alive. The game layer should make the work unforgettable. The professional layer should make the work undeniable.

---

## How To Use This Execution Plan

Work phase by phase. Do not ask the coding agent to build the entire website in one prompt.

For each phase:

1. Read the phase brief.
2. Copy the implementation prompt for that phase.
3. Give it to your coding agent with the Markdown source files available.
4. Let the agent implement only that phase.
5. Run the testing steps listed for that phase.
6. Fix all critical issues before moving forward.

Every implementation prompt assumes the agent can read:

- `docs/MASTER_PLAN.md`
- `docs/PRD.md`
- `docs/TRD.md`
- `docs/POCKET_PRATYUSH_EXECUTION_PLAN.md`

---

# Phase 0 - Documentation, Scope Lock, And Project Setup

## Brief

This phase prepares the project before any serious website implementation. The goal is to prevent scope explosion. You will convert the master plan, PRD, and TRD into Markdown, place them in the repo, create the initial Next.js project structure if it does not already exist, and define the exact MVP boundaries.

This phase should not build the full Play Mode yet.

## What You Have To Do

- Convert the generated master plan into `docs/MASTER_PLAN.md`.
- Convert the generated PRD into `docs/PRD.md`.
- Convert the generated TRD into `docs/TRD.md`.
- Add this execution plan as `docs/POCKET_PRATYUSH_EXECUTION_PLAN.md`.
- Create or confirm a Next.js + TypeScript app structure.
- Confirm Tailwind CSS is available.
- Confirm package scripts exist for linting, type checking, building, and development.
- Create a basic project folder structure for app routes, components, data, stores, game code, and public assets.
- Define MVP content placeholders for three featured projects and three smaller project cards.

## Steps

1. Put the source Markdown files in the `docs` folder.
2. Create or verify the Next.js app.
3. Add TypeScript if missing.
4. Add Tailwind if missing.
5. Create folders:
   - `app`
   - `components`
   - `components/play`
   - `components/pro`
   - `components/projects`
   - `data`
   - `game`
   - `game/scenes`
   - `stores`
   - `lib/dialogue`
   - `lib/storage`
   - `lib/analytics`
   - `public/sprites`
   - `public/rooms`
   - `public/og`
   - `public/audio`
6. Add placeholder data files:
   - `data/projects.ts`
   - `data/dialogue.ts`
   - `data/outfits.ts`
   - `data/items.ts`
   - `data/roomObjects.ts`
7. Do not add guestbook, Supabase, cloud sync, save codes, full audio, all rooms, or seasonal events yet.

## Implementation Prompt

```text
You are building the Pocket Pratyush website.

Use these documents as the only product and technical source of truth:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 0 only.

Goal:
Prepare the repository for the Pocket Pratyush website without building the full experience yet.

Tasks:
1. Inspect the current repo structure.
2. If a Next.js + TypeScript app already exists, work with it. If it does not exist, create the minimal app structure needed for the project.
3. Ensure Tailwind CSS is configured if the project uses Tailwind.
4. Add or verify scripts for:
   - dev
   - build
   - lint
   - typecheck
5. Create the planned folders:
   - app
   - components
   - components/play
   - components/pro
   - components/projects
   - data
   - game
   - game/scenes
   - stores
   - lib/dialogue
   - lib/storage
   - lib/analytics
   - public/sprites
   - public/rooms
   - public/og
   - public/audio
6. Add placeholder typed data files for projects, dialogue, outfits, items, and room objects.
7. Add a short README section explaining that the MVP must not include guestbook, cloud sync, save codes, full audio, all rooms, seasonal events, or Supabase.

Constraints:
- Do not implement Play Mode yet.
- Do not implement Phaser yet unless the dependency is already present and needed for setup.
- Do not build optional Phase 2-4 features.
- Keep the setup clean and minimal.

After implementation, report:
- Files created or changed.
- Scripts available.
- Any missing dependency or blocker.
```

## Testing Steps

Run:

```bash
npm install
npm run lint
npm run typecheck
npm run build
```

Manual checks:

- Confirm the app starts with `npm run dev`.
- Confirm the repo contains the expected folders.
- Confirm the docs are present as Markdown files.
- Confirm no optional systems were accidentally introduced.
- Confirm the project can build before moving to Phase 1.

Definition of done:

- The project foundation exists.
- The source docs are in the repo.
- Build/lint/typecheck are available.
- No major feature work has started yet.

---

# Phase 1 - Core Web Shell, Routing, Design Tokens, And Layout

## Brief

This phase creates the basic website skeleton. The visitor should see the Pocket Pratyush identity, the direct professional CTAs, and working routes. This phase proves the site can behave like a real portfolio before becoming a game.

## What You Have To Do

- Build the global app shell.
- Add routes:
  - `/`
  - `/pro`
  - `/projects`
  - `/projects/[slug]`
  - `/about`
  - `/privacy`
  - `/play`
  - `/resume`
- Add top-level navigation.
- Add visual design tokens based on the retro handheld identity.
- Add responsive layout foundations.
- Add placeholder page content.
- Add metadata for key pages.

## Steps

1. Build `AppShell`.
2. Add top navigation:
   - Play Mode
   - Pro Mode
   - Projects
   - Resume
   - GitHub
   - LinkedIn
   - Contact
3. Add homepage with:
   - name
   - role/positioning
   - Play CTA
   - Pro Mode CTA
   - Resume CTA
   - Contact CTA
4. Add static page shells for Pro Mode, projects, about, privacy, play, and resume.
5. Add CSS variables:
   - Game Boy-inspired green base colors
   - readable paper/ink colors
   - code, music, burnout, and night mood accents
6. Make the layout mobile-safe from the beginning.

## Implementation Prompt

```text
You are building Phase 1 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 1 only: Core Web Shell, Routing, Design Tokens, and Layout.

Product goal:
Create a credible portfolio website shell before building the game layer. Recruiters must immediately see who Pratyush is and how to reach projects, resume, GitHub, LinkedIn, and contact.

Required routes:
- /
- /pro
- /projects
- /projects/[slug]
- /about
- /privacy
- /play
- /resume

Required UI:
1. Global AppShell.
2. Top navigation with:
   - Play Mode
   - Pro Mode
   - Projects
   - Resume
   - GitHub
   - LinkedIn
   - Contact
3. Homepage with:
   - Pocket Pratyush identity.
   - One-line positioning.
   - Clear CTAs for Play, Pro Mode, Resume, Contact.
4. Basic responsive layout.
5. Retro handheld visual direction using original styling, not direct franchise copying.
6. CSS variables/design tokens for:
   - retro green base
   - readable paper/ink surface
   - code blue
   - music gold
   - burnout red
   - night mode

Constraints:
- Do not implement Phaser yet.
- Do not implement the dialogue engine yet.
- Do not implement full project case studies yet beyond placeholder route support.
- Do not add guestbook, Supabase, cloud sync, save codes, or seasonal events.
- Ensure Pro Mode is not treated as a joke or cheat code.

After implementation, report:
- Routes created.
- Components created.
- Styling system added.
- Any missing content placeholders.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
npm run dev
```

Manual browser checks:

- Visit `/`.
- Visit `/pro`.
- Visit `/projects`.
- Visit one placeholder `/projects/[slug]`.
- Visit `/about`.
- Visit `/privacy`.
- Visit `/play`.
- Visit `/resume`.
- Confirm top nav works.
- Confirm Pro Mode is visible from homepage and nav.
- Resize to mobile width and check no navigation or CTA overlap.

Definition of done:

- All core routes exist.
- Homepage is clear.
- Navigation works.
- Build passes.
- The site already feels like a portfolio, even before Play Mode exists.

---

# Phase 2 - Project Data, Static Project Pages, And Pro Mode MVP

## Brief

This phase builds the professional proof layer. It is one of the most important phases. The site must show real capability through featured projects, static case studies, project index, resume/contact links, skills, timeline, and about content.

## What You Have To Do

- Implement structured project data.
- Build the project index page.
- Build static project detail pages.
- Build Pro Mode as a complete direct portfolio.
- Include three featured projects and three smaller project cards.
- Include all required project fields from the PRD/TRD.
- Add metadata and Open Graph placeholders.

## Steps

1. Define the `Project` data model.
2. Add three featured project entries.
3. Add three smaller experiment/project entries.
4. Implement `/projects`.
5. Implement `/projects/[slug]`.
6. Implement `/pro` with:
   - intro
   - featured projects
   - skills
   - timeline
   - about/profile card
   - resume/contact links
7. Make project cards reusable for Play Mode later.
8. Add metadata for project pages.

## Implementation Prompt

```text
You are building Phase 2 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 2 only: Project Data, Static Project Pages, and Pro Mode MVP.

Product goal:
Make Pocket Pratyush work as a serious professional portfolio before the game layer is added.

Required work:
1. Create a typed project data model based on the TRD:
   - slug
   - number
   - name
   - type
   - status
   - rarity
   - featured
   - role
   - impact
   - stack
   - specialMove
   - weakness
   - summary
   - visuals
   - links
   - case study sections
2. Add placeholder-but-realistic data for:
   - 3 featured projects
   - 3 smaller experiments
3. Build /projects as a static project index.
4. Build /projects/[slug] as static project case-study pages.
5. Build /pro as a polished direct portfolio with:
   - short intro
   - featured projects
   - skills grouped by domain
   - timeline
   - about/profile card
   - resume link
   - GitHub link
   - LinkedIn link
   - contact CTA
6. Create reusable ProjectCard components that can later be used in Play Mode.
7. Add page metadata and Open Graph-ready fields where possible.

Constraints:
- Top three projects must be visible without unlocks.
- Do not hide essential project details behind game mechanics.
- Do not implement Phaser or Play Mode systems in this phase.
- Do not add backend, guestbook, Supabase, cloud save, or save codes.
- Keep Pro Mode clear and professional with only light retro flavor.

After implementation, report:
- Project model created.
- Project pages created.
- Pro Mode sections completed.
- Any placeholder content that still needs real project details.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Manual checks:

- `/pro` clearly shows who Pratyush is.
- `/pro` includes resume, GitHub, LinkedIn, and contact.
- `/pro` shows three featured projects.
- `/projects` lists all six projects.
- Every project card links to `/projects/[slug]`.
- Every project detail page shows:
  - title
  - summary
  - role
  - stack
  - impact
  - status
  - special move
  - weakness
  - visuals or placeholder visual area
  - links
  - case-study sections
- Build does not fail on static routes.
- Project pages are readable without Play Mode.

Definition of done:

- The website works as a direct portfolio.
- A recruiter can find project proof and contact information quickly.
- Static project pages are ready for SEO expansion.

---

# Phase 3 - Play Mode Shell, Phaser Setup, And Main Hub MVP

## Brief

This phase introduces the living cartridge layer. The goal is not to build the full game. The goal is to create the Play Mode shell, mount Phaser safely, render a Main Hub room, show the creature, and connect basic object clicks to React UI.

## What You Have To Do

- Add Phaser 3.
- Create `PlayShell`.
- Create `PhaserGame`.
- Create `BootScene`.
- Create `MainRoomScene`.
- Render the room and creature.
- Add hit areas for MVP objects:
  - creature
  - CRT monitor
  - bookshelf
  - keyboard/desk
- Keep dialogue text in React, not only canvas.

## Steps

1. Install Phaser.
2. Create a React wrapper for the Phaser game.
3. Create BootScene for loading assets.
4. Create MainRoomScene with placeholder room background if final art is missing.
5. Add a placeholder original creature sprite or CSS/asset fallback.
6. Add object hit areas.
7. Emit events from Phaser to React.
8. Add Play Mode layout with:
   - scene area
   - dialogue panel placeholder
   - action bar placeholder
   - status bar placeholder
   - settings/mode toggle
9. Ensure `/play` and homepage Play CTA open the Play Mode experience.

## Implementation Prompt

```text
You are building Phase 3 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 3 only: Play Mode Shell, Phaser Setup, and Main Hub MVP.

Product goal:
Create the first playable shell of the living cartridge experience while preserving the professional portfolio routes.

Required work:
1. Add Phaser 3 if it is not already installed.
2. Create:
   - components/play/PlayShell
   - game/PhaserGame
   - game/scenes/BootScene
   - game/scenes/MainRoomScene
3. Render a Main Hub scene with:
   - room background or polished placeholder
   - creature placeholder/sprite
   - object hit areas for creature, CRT monitor, bookshelf, keyboard/desk
4. Phaser must emit events to React when objects are clicked.
5. React must own:
   - dialogue panel
   - action controls
   - status display
   - settings/mode toggle
6. Important text must be rendered in React/HTML, not only inside the Phaser canvas.
7. Keep Pro Mode accessible from Play Mode.

Constraints:
- Do not build the full dialogue engine yet.
- Do not build all rooms.
- Do not build all objects.
- Do not add audio yet unless needed as a silent placeholder.
- Do not add guestbook, cloud sync, Supabase, save codes, or seasonal events.
- Use original names and visuals; do not copy protected game branding.

After implementation, report:
- Phaser files created.
- React/Phaser event bridge behavior.
- Main Hub objects implemented.
- Known placeholder assets.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
npm run dev
```

Manual browser checks:

- Visit `/play`.
- Confirm Play Mode loads without breaking `/pro` or `/projects`.
- Confirm the Main Hub appears.
- Confirm creature appears.
- Click the creature, monitor, bookshelf, and keyboard/desk.
- Confirm clicks trigger React-side visible responses or logged events.
- Confirm Pro Mode remains visible.
- Resize to mobile width and confirm the scene and controls do not overlap.

Optional visual checks:

- Take desktop and mobile screenshots.
- Confirm canvas is not blank.
- Confirm text is not trapped only inside canvas.

Definition of done:

- Play Mode exists.
- Phaser is safely integrated.
- Main Hub MVP renders.
- React and Phaser communicate.
- Professional routes still work.

---

# Phase 4 - Dialogue Engine, Personality Bible, And Creature Animations

## Brief

This phase makes the site feel alive. You will implement the authored zero-API dialogue system, connect it to the creature, and add the MVP animation states.

## What You Have To Do

- Implement dialogue data.
- Implement intent parser.
- Implement state injector.
- Implement template engine.
- Implement light personality filters.
- Implement dialogue box typing and instant reveal.
- Add 30-50 launch dialogue nodes.
- Connect dialogue to creature animations.

## Steps

1. Create dialogue node schema.
2. Add launch nodes for:
   - first greeting
   - return greeting
   - late-night greeting
   - who are you
   - what do you build
   - projects
   - best project
   - stack
   - contact
   - resume
   - Pro Mode
   - music
   - AI
   - accessibility/minimal mode
   - unknown input fallback
   - debug hint
3. Build parser:
   - exact match
   - keyword match
   - regex match
   - fallback
4. Build token replacement.
5. Build basic state filters.
6. Add DialogueBox with:
   - typing animation
   - instant reveal
   - follow-up choices
7. Add creature animation state registry.

## Implementation Prompt

```text
You are building Phase 4 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 4 only: Dialogue Engine, Personality Bible, and Creature Animations.

Product goal:
Make the creature feel alive through authored, zero-API dialogue and animation. The dialogue must be fast, local, consistent, and specific.

Required work:
1. Create a typed DialogueNode schema based on the TRD:
   - id
   - triggers
   - conditions
   - priority
   - baseText
   - variants
   - followUps
   - effects
   - animation
   - typingSpeed
2. Add 30-50 launch dialogue nodes covering:
   - first greeting
   - return greeting
   - late-night greeting
   - who are you
   - what do you build
   - show projects
   - best project
   - stack
   - contact
   - resume
   - Pro Mode
   - music
   - AI
   - what should I click first
   - unknown input fallback
   - accessibility/minimal mode
   - secret/debug hint
3. Implement:
   - intentParser
   - templateEngine
   - personalityFilter
   - state injection from local memory/settings/stats
4. Dialogue must support tokens:
   - [NAME]
   - [VISIT_COUNT]
   - [TIME_OF_DAY]
   - [DAYS_SINCE_LAST]
   - [ENERGY_STATE]
   - [STRESS_STATE]
   - [FRIENDSHIP_LEVEL]
   - [CURRENT_OUTFIT]
   - [UNLOCKED_PROJECTS]
   - [RANDOM_TIP]
   - [BEAT]
5. Implement DialogueBox with:
   - typed reveal
   - instant reveal
   - follow-up options
6. Connect dialogue effects to:
   - creature animation
   - friendship/stat changes
   - project hints where relevant
7. Add MVP creature animations:
   - idle_bounce
   - idle_blink
   - talking
   - typing
   - happy_dance
   - sleeping

Constraints:
- No LLM or external AI API.
- Do not store raw user dialogue input in analytics.
- Do not make vulnerable/burnout content mandatory.
- Do not implement the full relationship system yet beyond basic friendship state.
- Do not add all rooms or all secrets.

After implementation, report:
- Dialogue files created.
- Number of dialogue nodes added.
- Parser behavior.
- Tokens supported.
- Animation states wired.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Manual dialogue tests:

- Type or select greeting.
- Ask who Pratyush is.
- Ask what he builds.
- Ask for projects.
- Ask for best project.
- Ask for stack.
- Ask for contact.
- Ask for resume.
- Ask about music.
- Ask about AI.
- Type unknown input and confirm fallback works.
- Trigger return visit state by reloading.
- Confirm `[VISIT_COUNT]` or equivalent memory logic works.
- Confirm typing effect can be skipped or instantly revealed.
- Confirm the creature changes animation during dialogue.

Accessibility checks:

- Dialogue text is actual HTML text.
- Follow-up buttons are keyboard reachable.
- Instant reveal works.
- Reduced text animation setting works if implemented.

Definition of done:

- Creature can hold a basic conversation.
- Dialogue is local and authored.
- Main professional questions are answered clearly.
- Dialogue changes visible animation/state.

---

# Phase 5 - Local Memory, Settings, Stats, And Accessibility Core

## Brief

This phase implements persistence and comfort controls. The site should remember visits and settings, while giving users control over animation, audio, readable fonts, and saved data.

## What You Have To Do

- Implement localStorage memory.
- Implement settings store.
- Implement stats store.
- Implement Minimal Mode.
- Implement reduced motion support.
- Implement reset save.
- Add visible status bar for Energy, Mood, Stress, and Friendship.

## Steps

1. Create local memory schema.
2. Save:
   - firstVisitAt
   - lastVisitAt
   - visitCount
   - friendship
   - stats
   - settings
   - unlockedProjects
   - unlockedEvents
   - equippedOutfit
   - dialogueHistory
3. Add reset flow.
4. Add settings panel:
   - Minimal Mode
   - Audio enabled/muted placeholder
   - Reduce text animation
   - Reset save
5. Add status display:
   - Energy
   - Mood
   - Stress
   - Friendship level
6. Apply Minimal Mode styling.
7. Respect `prefers-reduced-motion`.

## Implementation Prompt

```text
You are building Phase 5 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 5 only: Local Memory, Settings, Stats, and Accessibility Core.

Product goal:
Make the site remember basic progress while remaining comfortable, readable, and accessible.

Required work:
1. Implement localStorage persistence using the TRD local save schema:
   - version
   - firstVisitAt
   - lastVisitAt
   - visitCount
   - friendship
   - stats: energy, mood, stress
   - settings: audio, minimalMode, reduceTextAnimation
   - unlockedProjects
   - unlockedEvents
   - equippedOutfit
   - dialogueHistory
2. Add stores or state modules for:
   - settingsStore
   - memoryStore
   - creatureStore
   - dialogueStore
   - projectStore
3. Add SettingsPanel with:
   - Minimal Mode toggle
   - audio enabled/muted placeholder
   - reduce text animation toggle
   - reset save button
4. Implement reset flow with confirmation.
5. Add visible StatusBar:
   - Energy
   - Mood
   - Stress
   - Friendship level
6. Minimal Mode must:
   - use readable/system fonts
   - reduce or remove CRT/glitch effects
   - simplify intense visuals
7. Respect prefers-reduced-motion:
   - disable nonessential animation
   - disable shimmer/glitch/heavy particles
   - allow instant text reveal

Constraints:
- Do not add cloud sync.
- Do not add save codes.
- Do not require accounts.
- Do not make stats decay harshly.
- Friendship must not decay.
- Essential content must remain accessible with or without localStorage.

After implementation, report:
- State stores added.
- localStorage keys used.
- Settings implemented.
- Accessibility behavior implemented.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Manual checks:

- Open site in Play Mode.
- Interact with dialogue or objects.
- Reload page.
- Confirm visit count or memory changes persist.
- Toggle Minimal Mode.
- Confirm fonts/effects become more readable.
- Toggle reduced text animation.
- Confirm dialogue can be shown instantly.
- Click reset save.
- Confirm saved data clears.
- Confirm Pro Mode and project pages still work after reset.
- Test with browser/device reduced-motion setting if possible.

Definition of done:

- Basic memory works.
- User can control readability and motion.
- Reset is available.
- Stats and friendship display without becoming annoying.

---

# Phase 6 - Project Cards Inside Play Mode And Main Hub Object Depth

## Brief

This phase connects the professional proof layer into Play Mode. Visitors should be able to discover project cards through the room while still being able to open full static case studies.

## What You Have To Do

- Add project cards to Play Mode.
- Make the CRT monitor and desk point to projects.
- Add room object responses for MVP objects.
- Track viewed/unlocked projects locally.
- Keep featured projects immediately available.

## Steps

1. Reuse `ProjectCard`.
2. Add project card modal/panel in Play Mode.
3. Connect CRT monitor to project hints.
4. Connect keyboard/desk to coding/project dialogue.
5. Connect bookshelf to learning/early project lore.
6. Store viewed/unlocked projects.
7. Add links from Play Mode cards to static project case studies.

## Implementation Prompt

```text
You are building Phase 6 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 6 only: Project Cards Inside Play Mode and Main Hub Object Depth.

Product goal:
Connect the playful world to the serious project proof. Play Mode should reveal projects, but the best projects must never be locked away.

Required work:
1. Reuse the ProjectCard component inside Play Mode.
2. Add a project card panel/modal that can open from:
   - CRT monitor
   - keyboard/desk
   - dialogue follow-up
   - action controls
3. Show the 3 featured projects without requiring unlocks.
4. Show smaller projects as additional cards.
5. Each Play Mode project card must link to its static /projects/[slug] case study.
6. Update local memory when a project is viewed.
7. Let dialogue reference unlocked/viewed projects through [UNLOCKED_PROJECTS].
8. Add or improve object responses for:
   - creature
   - CRT monitor
   - bookshelf
   - keyboard/desk

Constraints:
- Do not hide essential project proof behind friendship, 3AM, or secrets.
- Do not build the full Lab room yet unless explicitly needed as a lightweight placeholder.
- Do not add guestbook, cloud sync, save codes, full audio, or seasonal events.

After implementation, report:
- How projects are opened in Play Mode.
- How viewed projects are saved.
- Which objects trigger project-related responses.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Manual checks:

- Open Play Mode.
- Click CRT monitor.
- Click keyboard/desk.
- Ask the creature about projects.
- Confirm featured project cards appear.
- Open each card.
- Click through to static case-study pages.
- Return to Play Mode.
- Reload and confirm viewed/unlocked project memory persists.
- Confirm Pro Mode still shows the same projects clearly.

Definition of done:

- Play Mode and project pages are connected.
- Project discovery feels playful but not obstructive.
- Static case studies remain the authoritative detail pages.

---

# Phase 7 - Items, Outfits, Stats Reactions, And Core Reactivity

## Brief

This phase adds life-sim flavor. Interactions should affect Energy, Mood, Stress, Friendship, and creature animations. Keep it simple and gentle.

## What You Have To Do

- Add item system.
- Add first alternate outfits.
- Add stat effects.
- Add mood/room state changes.
- Add friendship thresholds for bonus content only.

## Steps

1. Add items:
   - coffee
   - water
   - book
   - rubber duck
2. Add outfits:
   - Default Hoodie
   - Hackathon Survivor
   - Musician
3. Add stat effects:
   - coffee: Energy up, Stress up
   - water: Energy up, Stress down
   - book: learning/project lore
   - rubber duck: debugging monologue
4. Add room states:
   - Chill
   - Coding
   - Music
   - Sleep
   - light Stress/Burnout preview only if tasteful
5. Add friendship levels:
   - Stranger
   - Visitor
   - Friend
   - Close Friend
   - Inner Circle
6. Keep all essential projects visible regardless of friendship.

## Implementation Prompt

```text
You are building Phase 7 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 7 only: Items, Outfits, Stats Reactions, and Core Reactivity.

Product goal:
Make the creature and room feel more alive through gentle interaction systems without overcomplicating the MVP.

Required work:
1. Implement item data and item interactions for:
   - Coffee: energy up, stress up
   - Water: energy up, stress down
   - Book: learning/project lore
   - Rubber Duck: debugging monologue
2. Implement outfits:
   - Default Hoodie
   - Hackathon Survivor
   - Musician
3. Add outfit selection UI through Dress action.
4. Add Feed/Item action UI.
5. Implement stat effects on:
   - Energy
   - Mood
   - Stress
   - Friendship
6. Add simple room states:
   - Chill
   - Coding
   - Music
   - Sleep
   - light stress state
7. Add friendship levels:
   - Stranger
   - Visitor
   - Friend
   - Close Friend
   - Inner Circle
8. Friendship can unlock bonus dialogue, skins, or hints only.

Constraints:
- Friendship must not hide the top three projects.
- Do not implement harsh passive decay.
- Do not make the creature needy.
- Do not implement full Burnout event unless it is tasteful and optional.
- Do not add all outfits yet.
- Do not add cloud sync, guestbook, save codes, or seasonal events.

After implementation, report:
- Items added.
- Outfits added.
- Stat effects implemented.
- Friendship levels implemented.
- Any bonus unlocks added.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Manual checks:

- Use Feed/Item action.
- Give coffee and confirm Energy/Stress change.
- Give water and confirm Energy/Stress change.
- Use book and confirm project/learning dialogue.
- Use rubber duck and confirm debugging dialogue.
- Open Dress action.
- Switch outfit to Hackathon Survivor.
- Switch outfit to Musician.
- Confirm outfit changes affect dialogue or visuals.
- Confirm stats persist after reload.
- Confirm project pages are still accessible without friendship.

Definition of done:

- Interactions affect state.
- Outfits and items feel meaningful.
- The system remains simple and professional content is not blocked.

---

# Phase 8 - Lab, Archive, Expanded Rooms, And Content Depth

## Brief

This phase expands beyond the Main Hub. The Lab deepens project discovery. The Archive deepens profile/about content. These rooms should reuse existing content rather than inventing disconnected systems.

## What You Have To Do

- Build Lab room.
- Build Archive room.
- Add room navigation.
- Add Project Field Guide in the Lab.
- Add creator/profile card and timeline in the Archive.
- Keep static routes as canonical content.

## Steps

1. Add Explore menu.
2. Add room selection:
   - Main Hub
   - Lab
   - Archive
3. Build Lab:
   - project cabinet
   - project cards
   - demo/screenshot panels
   - links to case studies
4. Build Archive:
   - creator/profile card
   - skills
   - timeline
   - memories
5. Add dialogue for room transitions.
6. Save current room if useful.

## Implementation Prompt

```text
You are building Phase 8 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 8 only: Lab, Archive, Expanded Rooms, and Content Depth.

Product goal:
Expand the Play Mode world with rooms that deepen existing portfolio content.

Required work:
1. Add Explore action/menu.
2. Add room navigation between:
   - Main Hub
   - Lab
   - Archive
3. Build Lab room:
   - Project Field Guide style project cabinet/list
   - project cards
   - demo/screenshot preview area if available
   - links to static case studies
4. Build Archive room:
   - creator/profile card
   - skills grouped by domain
   - timeline
   - memory/profile details
5. Add dialogue for entering Lab and Archive.
6. Keep Pro Mode and static pages as the canonical professional reading experience.

Constraints:
- Do not build Stage, Attic, guestbook, cloud save, seasonal events, or full audio in this phase.
- Do not duplicate long project case-study text inside canvas.
- Use React/HTML for important text.
- Room expansion must not break mobile layout.

After implementation, report:
- Room navigation added.
- Lab features added.
- Archive features added.
- Static content reused.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Manual checks:

- Open Play Mode.
- Click Explore.
- Enter Lab.
- Open project cards in Lab.
- Click through to static case studies.
- Return to Main Hub.
- Enter Archive.
- Confirm profile card, skills, and timeline are readable.
- Confirm keyboard navigation works.
- Confirm mobile layout is usable.
- Confirm Pro Mode is still the fastest direct portfolio path.

Definition of done:

- Play Mode has meaningful room navigation.
- Lab strengthens project discovery.
- Archive strengthens personal/professional context.
- The website still does not feel bloated.

---

# Phase 9 - SEO, Metadata, Analytics, Privacy, And Production Hardening

## Brief

This phase prepares the site for real public use. The goal is to make it discoverable, measurable, shareable, privacy-respecting, and stable.

## What You Have To Do

- Add SEO metadata.
- Add sitemap and robots.
- Add JSON-LD where useful.
- Add Open Graph images/placeholders.
- Add privacy-friendly analytics events.
- Finish privacy page.
- Audit performance and accessibility.

## Steps

1. Add metadata for:
   - homepage
   - Pro Mode
   - project index
   - each project page
   - about
2. Add sitemap.
3. Add robots.
4. Add canonical URLs.
5. Add JSON-LD:
   - Person
   - WebSite
   - CreativeWork
   - SoftwareSourceCode where appropriate
6. Add noindex for debug/easter egg pages.
7. Add analytics events:
   - `mode_pro_opened`
   - `play_started`
   - `project_card_opened`
   - `project_case_study_clicked`
   - `resume_clicked`
   - `contact_clicked`
   - `github_clicked`
   - `dialogue_node_hit`
   - `secret_found`
   - `minimal_mode_enabled`
   - `audio_enabled`
8. Ensure raw dialogue input is not stored.
9. Complete privacy page.

## Implementation Prompt

```text
You are building Phase 9 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 9 only: SEO, Metadata, Analytics, Privacy, and Production Hardening.

Product goal:
Make the website discoverable, shareable, measurable, and safe for public launch.

Required work:
1. Add complete metadata for:
   - /
   - /pro
   - /projects
   - /projects/[slug]
   - /about
2. Add Open Graph-ready metadata and image references.
3. Add sitemap.xml.
4. Add robots.txt.
5. Add canonical URLs where appropriate.
6. Add JSON-LD where useful:
   - Person
   - WebSite
   - CreativeWork
   - SoftwareSourceCode
7. Ensure /debug or easter egg routes are noindex if they exist.
8. Add privacy-friendly analytics event wrappers for:
   - mode_pro_opened
   - play_started
   - project_card_opened
   - project_case_study_clicked
   - resume_clicked
   - contact_clicked
   - github_clicked
   - dialogue_node_hit
   - secret_found
   - minimal_mode_enabled
   - audio_enabled
9. Do not store raw user dialogue input.
10. Complete /privacy with:
   - localStorage explanation
   - reset explanation
   - analytics explanation
   - note that no account/cloud save is required in MVP

Constraints:
- Do not add guestbook or cloud sync in this phase.
- Do not send sensitive user input to analytics.
- Keep static project pages readable and linked from navigation.

After implementation, report:
- Metadata added.
- Sitemap/robots status.
- Analytics events added.
- Privacy page updates.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Manual checks:

- Inspect page titles and descriptions.
- Confirm project pages have unique metadata.
- Confirm sitemap exists.
- Confirm robots exists.
- Confirm debug/easter egg routes are noindex if present.
- Confirm project pages are linked from Pro Mode and `/projects`.
- Trigger analytics events in development and confirm event names only contain safe metadata.
- Confirm raw dialogue text is not stored or sent.
- Confirm `/privacy` explains localStorage and analytics.

Definition of done:

- Site is ready for indexing and sharing.
- Analytics are useful but privacy-safe.
- Privacy page is honest and understandable.

---

# Phase 10 - Audio, Stage, Devlog, Secrets, And Optional Polish

## Brief

This phase adds delight after the core site works. Do not start this phase before the portfolio, Play Mode MVP, accessibility, SEO, and production hardening are complete.

## What You Have To Do

- Add opt-in audio.
- Add Stage room if still valuable.
- Add devlog/newspaper.
- Add limited secrets.
- Add shareable card moments.
- Add Attic/debug only if the rest is stable.

## Steps

1. Add Howler.js audio manager.
2. Add opt-in UI sound effects:
   - cursor/select
   - confirm
   - back
   - unlock
3. Add BGM/ambience only after mute/enable is stable.
4. Add Stage room:
   - music/creative work
   - optional simple piano interaction
5. Add devlog/newspaper static pages.
6. Add limited secrets:
   - `/debug`
   - `/sleep`
   - late-night/3AM atmosphere
   - burnout event only if tasteful and optional
7. Add shareable project/profile cards if useful.

## Implementation Prompt

```text
You are building Phase 10 of Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement Phase 10 only: Audio, Stage, Devlog, Secrets, and Optional Polish.

Product goal:
Add delight and replay value after the core portfolio and Play Mode are already stable.

Required work:
1. Add an AudioManager using Howler.js only if audio is not already implemented.
2. Audio must be opt-in or muted by default.
3. Persist audio preference.
4. Add small original UI SFX:
   - select
   - confirm
   - back
   - unlock
5. Add Stage room only if it does not destabilize existing rooms:
   - music/creative work
   - optional simple piano interaction
6. Add devlog/newspaper static section if content exists.
7. Add limited harmless secrets:
   - /debug terminal-style overlay
   - /sleep command
   - late-night atmosphere
   - optional burnout event, tasteful and recoverable
8. Add shareable project/profile card generation only if the core build is stable.

Constraints:
- Do not use recognizable franchise sounds.
- Do not autoplay loud audio.
- Do not make audio required for understanding content.
- Do not add guestbook/cloud sync unless explicitly approved as a separate phase.
- Burnout/vulnerable content must remain optional.
- All secret commands must be harmless client behavior.

After implementation, report:
- Audio behavior.
- Stage/devlog/secrets added.
- Any optional items skipped and why.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Manual checks:

- Confirm site loads muted or silent by default.
- Enable audio and confirm sound works.
- Mute audio and reload; confirm preference persists.
- Confirm audio is not required for any content.
- Visit Stage if implemented.
- Confirm Stage is readable and mobile-safe.
- Visit devlog if implemented.
- Trigger `/debug` if implemented.
- Trigger `/sleep` if implemented.
- Test late-night/3AM logic using controlled time mocking if available.
- Confirm reduced motion/minimal mode still reduce effects.

Definition of done:

- Optional polish improves the experience without harming clarity.
- Audio and secrets are safe and controllable.
- Core portfolio remains fast and usable.

---

# Phase 11 - Guestbook, Cloud Save, Save Codes, Streaks, And Seasonal Events

## Brief

This is a future expansion phase. These features are intentionally excluded from MVP because they introduce moderation, privacy, backend, and maintenance responsibilities.

Do not implement this phase unless the launched site has enough traffic and return usage to justify it.

## What You Have To Do

Only after explicit approval:

- Add moderated guestbook.
- Add Supabase.
- Add cloud save.
- Add save code import/export.
- Add streaks.
- Add seasonal events.

## Steps

1. Decide if the feature is justified by usage.
2. Add privacy policy updates first.
3. Add backend safely.
4. Add moderation/admin flow for guestbook.
5. Add rate limiting.
6. Add Supabase row-level security if Supabase is used.
7. Add deletion/reset path for user data.
8. Test abuse cases.

## Implementation Prompt

```text
You are building a future optional expansion for Pocket Pratyush.

Read and follow:
- docs/MASTER_PLAN.md
- docs/PRD.md
- docs/TRD.md
- docs/POCKET_PRATYUSH_EXECUTION_PLAN.md

Implement only the explicitly approved Phase 11 feature. Do not implement all Phase 11 features at once.

Approved feature:
[PASTE ONE FEATURE HERE: guestbook / cloud save / save codes / streaks / seasonal events]

Before implementation:
1. Explain the privacy, security, and maintenance impact.
2. Confirm the minimal safe implementation.
3. Update /privacy if data collection changes.

If guestbook:
- Use moderation before public display.
- Escape all user content.
- Rate-limit submissions.
- Use Supabase row-level security if Supabase is used.
- Do not collect unnecessary personal information.

If cloud save:
- Use optional magic-link style auth only.
- Do not require account for normal use.
- Provide reset/delete path.
- Keep localStorage as default.

If save codes:
- Keep codes small and versioned.
- Validate imports.
- Do not rely on save codes for essential access.

If streaks:
- Keep them gentle.
- Do not make the creature needy.
- Do not punish missed days.

If seasonal events:
- Keep content optional.
- Respect reduced motion and minimal mode.

Constraints:
- Do not break MVP flows.
- Do not add sensitive analytics.
- Do not make accounts required.
- Do not expose backend secrets.

After implementation, report:
- Feature added.
- Data stored.
- Privacy updates.
- Security controls.
- Testing performed.
```

## Testing Steps

Run:

```bash
npm run lint
npm run typecheck
npm run build
```

Feature-specific checks:

- Guestbook:
  - Submit valid message.
  - Submit too-long message.
  - Submit unsafe HTML/script and confirm it is escaped.
  - Confirm message is not public before moderation.
  - Confirm rate limiting exists.
- Cloud save:
  - Use site without account.
  - Opt into cloud save.
  - Sync state.
  - Reset/delete state.
- Save codes:
  - Export save.
  - Import valid save.
  - Reject invalid save.
  - Reject wrong version safely.
- Streaks:
  - Simulate return days.
  - Confirm no punishment for missed streak.
- Seasonal events:
  - Simulate event date.
  - Confirm reduced motion works.

Definition of done:

- Optional feature is safe, private, and does not harm the core portfolio.

---

# Final Pre-Launch Checklist

Before public launch, verify:

- A visitor can understand who Pratyush is within 10 seconds.
- A recruiter can find resume/contact/project proof within 30 seconds.
- Top three projects are visible without unlocks.
- Project pages are static, readable, and shareable.
- Play Mode loads and does not break Pro Mode.
- Pro Mode is visible from Play Mode.
- No essential text exists only inside canvas.
- Dialogue is authored and zero-API.
- localStorage reset exists.
- Minimal Mode works.
- Reduced motion works.
- Audio is optional.
- Mobile layout has no overlap.
- Sitemap and metadata exist.
- Analytics do not store raw dialogue input.
- Guestbook/cloud sync/save codes are not in MVP unless intentionally approved.
- The website still feels like a serious portfolio, not only a toy.

---

# Suggested Build Order Summary

1. Phase 0 - Docs and setup.
2. Phase 1 - Shell and routes.
3. Phase 2 - Pro Mode and project pages.
4. Phase 3 - Play Mode shell and Main Hub.
5. Phase 4 - Dialogue and creature animation.
6. Phase 5 - Memory, settings, accessibility.
7. Phase 6 - Project cards inside Play Mode.
8. Phase 7 - Items, outfits, stats.
9. Phase 8 - Lab and Archive.
10. Phase 9 - SEO, analytics, privacy, hardening.
11. Phase 10 - Audio, Stage, devlog, secrets.
12. Phase 11 - Guestbook/cloud/save/streaks/seasonal only if justified.

