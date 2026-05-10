# Wiki content (preview)

This directory contains the **wiki content** prepared for `https://github.com/KouemouSah/facil-framework/wiki`.

## Why isn't the wiki populated automatically?

GitHub does not provide an API to create the **first** wiki page. The wiki repository (`facil-framework.wiki.git`) only exists after the maintainer manually clicks "Create the first page" via the Wiki tab in the browser.

Once initialized, this directory's content can be pushed to the wiki repo:

```bash
# After clicking "Create the first page" in browser (any content is OK)
cd /tmp
git clone https://github.com/KouemouSah/facil-framework.wiki.git
cp ../facil_framework/docs/wiki/*.md facil-framework.wiki/
cd facil-framework.wiki
git add . && git commit -m "Sync wiki from repo" && git push
```

## Files in this directory

| File | Wiki page |
|------|-----------|
| `Home.md` | Wiki homepage (the navigation hub) |
| `_Sidebar.md` | Persistent sidebar visible on every wiki page |
| `_Footer.md` | Persistent footer visible on every wiki page |

## Why keep wiki content here?

- **Version controlled**: changes follow normal PR review workflow
- **Backup**: if the wiki gets corrupted or deleted, this is the source
- **Discoverable**: contributors find the content via the main repo

## When to update

When you add a new wiki page:

1. Create the file in this directory (e.g., `Architecture-Deep-Dive.md`)
2. Add a link to it in `_Sidebar.md`
3. Commit + push to main
4. Manually copy the file to the wiki repo (or set up a sync workflow)

A future workflow `wiki-sync.yml` could automate this — not implemented in V0 to keep things simple.
