# Flagship brand logos

Drop the 6 flagship store logos here, named exactly as below. The frontend
asks for `.webp` specifically (`BrandsIndexPage` / `BrandPage` build the path
from the slug), so convert before dropping one in — a `.png` sitting here
under the right name will not be found. A
square-ish mark or icon works best; the frontend fits it into a rounded
square with `object-fit: contain`, so a wide wordmark will letterbox rather
than fill edge-to-edge.

| File | Store |
|---|---|
| `amazon.webp` | Amazon |
| `flipkart.webp` | Flipkart |
| `myntra.webp` | Myntra |
| `croma.webp` | Croma |
| `reliance-digital.webp` | Reliance Digital |
| `ajio.webp` | AJIO |

If a file is missing (or fails to load), `BrandAvatar` automatically falls
back to a colored-initials badge — nothing breaks, it just won't show a
logo for that one store until the file is added.

These render at 72px at the largest, so there's no reason to keep a big file:
resize to about 216px on the long edge (3x, for high-density screens) and
encode as WebP. That's what the current set is —

    cwebp -q 82 -resize 216 0 -metadata none logo.png -o logo.webp
