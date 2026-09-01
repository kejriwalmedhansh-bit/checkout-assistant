# Flagship brand logos

Drop the 6 flagship store logos here, named exactly as below (any of `.png`,
`.svg`, `.jpg`, `.webp` — just match the extension in the filename). A
square-ish mark or icon works best; the frontend fits it into a rounded
square with `object-fit: contain`, so a wide wordmark will letterbox rather
than fill edge-to-edge.

| File | Store |
|---|---|
| `amazon.png` | Amazon |
| `flipkart.png` | Flipkart |
| `myntra.png` | Myntra |
| `croma.png` | Croma |
| `reliance-digital.png` | Reliance Digital |
| `ajio.png` | AJIO |

If a file is missing (or fails to load), `BrandAvatar` automatically falls
back to a colored-initials badge — nothing breaks, it just won't show a
logo for that one store until the file is added.
