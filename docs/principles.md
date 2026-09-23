# Design principles

The rules this codebase is built to. Code comments cite them by number
("Rule 8"), so the numbering is stable.

1. **Claude is called only through the Claude Agent SDK.** There is no raw API
   client in the codebase. Each installation authenticates with its own
   Claude account through a one-time `claude /login`, so usage counts against
   whoever runs it. That login model is meant for personal use (see the README).
   If the SDK can't do something, the feature waits; there is no silent
   fallback to another route.
2. **A user's data never leaves their machine.** The database, uploaded
   documents and notes live in a local data directory. The code host (GitHub)
   holds code only, never data, and nothing proxies Claude calls.
3. **Web research respects its sources.** Terms, robots.txt and rate limits are
   checked before any new source is used. Google Scholar is never used (it has
   no API and disallows automated access). Official APIs and public pages come
   first. Each research pass has a deliberate scope:
   * *Program research* is locked to the institution's own domain by a
     `can_use_tool` callback. No search, no off-domain fetches.
   * *Faculty dossiers* may search, and may fetch any host except a deny-list
     (Scholar under any TLD, search-engine result pages), because a lab often
     runs on its own domain and a grant is recorded by its funder. There is no
     scraping library: fetching uses the SDK's own WebFetch tool, which honours
     robots.txt. Every claim must quote its source or it is dropped.
4. **No third-party copyrighted assets** (university logos, crests, photos)
   unless the source explicitly allows reuse. Names as plain text are fine.
5. **Everything Claude produces is a draft for human review.** It is flagged
   `needs_human_verification`, never presented as final, and never sent
   anywhere automatically.
6. **No artificial spend ceilings on research.** A research pass returns its
   whole result at the end, so cutting it off part-way spends the tokens and
   stores nothing. Passes run to completion; the only limit is the user's own
   Claude plan.
7. **No fabrication.** Claude must never invent a faculty member's work,
   papers, grants, students or shared history. "Not stated publicly" is always
   a better answer than a plausible guess. Every prompt contract says so
   explicitly and offers a `needs_human_verification` escape hatch.
8. **Provenance is tracked, not guessed.** A fact's `source` records whether
   Claude found it (`researched`) or the program stated it
   (`confirmed_by_program`). Confirmed facts override researched ones, and the
   UI shows which is which.
9. **Cross-platform code.** `pathlib` throughout, with no shell-specific logic
   in core code. OS-specific code lives only in the launcher scripts.
10. **Migrations are forward-only and tested before release.** Schema changes
    ship on their own, are tested against a copy of a *populated* database, and
    archive anything they drop. A bad migration would hit a user's only copy of
    their data.
