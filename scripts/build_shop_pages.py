#!/usr/bin/env python3
"""Builds react/src/data/shopPages.json: one entry per shop page at
/brands/<slug>/ — the pages Google sends people to when they search
"<shop> gift card discount".

Each entry carries today's rate from every seller side by side (Dealo's own
voucher through Hubble, then Gyftr, Maximize and BuyHatke), the cheapest
marked, plus the fine print the voucher data knows (online or in store,
UPI vs card rate, single- or multi-use, what the voucher cannot buy, how to
redeem). The live page and scripts/prerender.mjs both read this file, so
the static HTML a crawler sees and the page a visitor sees say the same
thing.

Partner rates come from the three master files the voucher refresh keeps.
Dealo's own rate comes from the live backend (Hubble's catalogue has no
rates in the repo; the production keys live only on the server), so run
this with the network on. A shop whose Hubble lookup fails keeps its last
known Hubble rate from the previous shopPages.json.

Which shops: SHOPS below — the ones people search most on Dealo
(Mixpanel, 90 days to 3 Nov 2026) plus the big names deal hunters search
Google for. A shop makes it onto a page only when some seller gives at
least MIN_PCT, or it already had a hand-written page in brandDeals.js.

Run after every voucher refresh (see VOUCHER_REFRESH.md):
    python3 scripts/build_shop_pages.py
It also runs by itself every morning (.github/workflows/refresh-shop-pages.yml)
so the rate and the "Checked <date>" on each page are today's.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "react" / "src" / "data" / "shopPages.json"
API = "https://dealo-backend.onrender.com"
MIN_PCT = 3.0
CURATED = {"amazon", "flipkart", "myntra", "croma", "reliance-digital", "ajio"}
# Owner's call, 24 Nov 2026: these get a page below MIN_PCT because people
# search for them by name (quick-commerce groceries, about 2%).
BELOW_MIN_OK = {"zepto", "blinkit"}

# (slug, display name, website for the logo, extra names the sellers list it under). Exact
# normalized-name matching only, same rule as build_all_brand_deals.py:
# a sibling like "Myntra LUXE" or "Zomato (1 Day Wait)" never merges in.
SHOPS: list[tuple[str, str, str, list[str]]] = [
    ("myntra", "Myntra", "myntra.com", []),
    ("ajio", "AJIO", "ajio.com", []),
    ("nykaa", "Nykaa", "nykaa.com", []),
    ("nykaa-fashion", "Nykaa Fashion", "nykaafashion.com", []),
    ("zomato", "Zomato", "zomato.com", []),
    ("swiggy", "Swiggy", "swiggy.com", []),
    ("amazon", "Amazon", "amazon.in", ["Amazon Pay", "Amazon Shopping"]),
    ("flipkart", "Flipkart", "flipkart.com", []),
    ("croma", "Croma", "croma.com", []),
    ("reliance-digital", "Reliance Digital", "reliancedigital.in", []),
    ("makemytrip", "MakeMyTrip", "makemytrip.com", ["MakeMyTrip Flights", "MakeMyTrip Hotels"]),
    ("yatra", "Yatra", "yatra.com", ["Yatra Flights", "Yatra Hotels"]),
    ("cleartrip", "Cleartrip", "cleartrip.com", []),
    ("pvr", "PVR", "pvrcinemas.com", ["PVR Cinemas", "PVR INOX"]),
    ("bookmyshow", "BookMyShow", "bookmyshow.com", []),
    ("uber", "Uber", "uber.com", []),
    ("bigbasket", "BigBasket", "bigbasket.com", []),
    ("blinkit", "Blinkit", "blinkit.com", []),
    ("zepto", "Zepto", "zeptonow.com", []),
    ("tata-cliq", "Tata CLiQ", "tatacliq.com", ["Tata CLiQ Fashion"]),
    ("pepperfry", "Pepperfry", "pepperfry.com", []),
    ("ikea", "IKEA", "ikea.com", []),
    ("urban-ladder", "Urban Ladder", "urbanladder.com", []),
    ("dominos", "Domino's", "dominos.co.in", ["Dominos", "Domino's Pizza"]),
    ("pizza-hut", "Pizza Hut", "pizzahut.co.in", []),
    ("kfc", "KFC", "online.kfc.co.in", []),
    ("subway", "Subway", "subway.com", []),
    ("starbucks", "Starbucks", "starbucks.in", []),
    ("lifestyle", "Lifestyle", "lifestylestores.com", []),
    ("westside", "Westside", "westside.com", []),
    ("shoppers-stop", "Shoppers Stop", "shoppersstop.com", []),
    ("decathlon", "Decathlon", "decathlon.in", []),
    ("puma", "PUMA", "in.puma.com", []),
    ("skechers", "Skechers", "skechers.in", []),
    ("bata", "Bata", "bata.in", []),
    ("lenskart", "Lenskart", "lenskart.com", []),
    ("boat", "boAt", "boat-lifestyle.com", []),
    ("titan", "Titan", "titan.co.in", []),
    ("firstcry", "FirstCry", "firstcry.com", []),
    ("netmeds", "Netmeds", "netmeds.com", []),
    ("jockey", "Jockey", "jockey.in", []),
    ("airbnb", "Airbnb", "airbnb.co.in", []),
    # Added 10 Nov 2026: searched on Dealo (Mixpanel, Aug–Nov) or a well-known
    # brand, and a real gift card discount that day. Exact names only, so a
    # hotels-only card (ixigo hotel, Goibibo Hotel) never becomes the headline.
    ("frido", "Frido", "myfrido.com", []),
    ("dailyobjects", "DailyObjects", "dailyobjects.com", ["Daily Objects"]),
    ("beyoung", "Beyoung", "beyoung.in", []),
    ("ixigo", "Ixigo", "ixigo.com", []),
    ("third-wave-coffee", "Third Wave Coffee", "thirdwavecoffee.in", []),
    ("philips", "Philips", "philips.co.in", []),
    ("birkenstock", "Birkenstock", "birkenstock.com/in", []),
    ("goibibo", "Goibibo", "goibibo.com", []),
    ("easemytrip", "EaseMyTrip", "easemytrip.com", []),
    ("woodland", "Woodland", "woodlandworldwide.com", []),
    ("giva", "GIVA", "giva.co", []),
    ("mokobara", "Mokobara", "mokobara.com", []),
    ("snitch", "Snitch", "snitch.co.in", []),
    ("max-fashion", "Max Fashion", "maxfashion.in", ["Max"]),
    ("biba", "BIBA", "biba.in", []),
    # Added 18 Nov 2026: shops people opened a Dealo voucher for in the last
    # 60 days (Mixpanel "Dealo Voucher Shown") that had no page yet.
    ("nykaa-luxe", "Nykaa Luxe", "nykaa.com/luxe", ["Nykaa LUXE"]),
    ("tata-cliq-luxury", "Tata CLiQ Luxury", "luxury.tatacliq.com", []),
    ("cinepolis", "Cinepolis", "cinepolisindia.com", []),
    ("duroflex", "Duroflex", "duroflexworld.com", []),
    ("archies", "Archies", "archiesonline.com", []),
    ("hamleys", "Hamleys", "hamleys.in", []),
    ("ajio-luxe", "AJIO Luxe", "luxe.ajio.com", ["Ajio Luxe"]),
    # Added 23 Nov 2026: Domino's (16% off) is where the sales came from, and
    # its buyers arrive on this kind of page. So: well-known shops where Dealo
    # itself gives 8% or more (read from the live Hubble list that day) that
    # had no page yet. Gift-card shops only; subscriptions (SonyLIV, ZEE5,
    # Amazon Prime) need their own wording and are left for a later round.
    ("eazydiner", "EazyDiner", "eazydiner.com", []),
    ("bakingo", "Bakingo", "bakingo.com", []),
    ("blue-tokai", "Blue Tokai", "bluetokaicoffee.com", ["Blue Tokai Coffee"]),
    ("baskin-robbins", "Baskin Robbins", "baskinrobbinsindia.com", []),
    ("cafe-coffee-day", "Cafe Coffee Day", "cafecoffeeday.com", ["CCD"]),
    ("makemytrip-hotels", "MakeMyTrip Hotels", "makemytrip.com/hotels", ["MakeMyTrip Hotel"]),
    ("goibibo-hotels", "Goibibo Hotels", "goibibo.com/hotels", ["Goibibo Hotel"]),
    ("igp", "IGP", "igp.com", []),
    ("ferns-n-petals", "Ferns N Petals", "fnp.com", ["FNP"]),
    ("rare-rabbit", "Rare Rabbit", "thehouseofrare.com", []),
    ("marks-and-spencer", "Marks & Spencer", "marksandspencer.in", []),
    ("blissclub", "Blissclub", "blissclub.com", []),
    ("freecultr", "Freecultr", "freecultr.com", []),
    ("foxtale", "Foxtale", "foxtale.in", []),
    ("kama-ayurveda", "Kama Ayurveda", "kamaayurveda.in", []),
    ("ray-ban", "Ray-Ban", "ray-ban.com", []),
    ("wonderchef", "Wonderchef", "wonderchef.com", []),
    ("healthians", "Healthians", "healthians.com", []),
    # Added 23 Nov 2026: subscriptions and memberships Dealo sells at 8% or
    # more. Not gift cards, so the page says "subscription" / "membership"
    # (see SUBSCRIPTIONS) and lists what each plan voucher costs.
    ("sonyliv", "SonyLIV", "sonyliv.com", ["SonyLiv", "Sony LIV"]),
    ("zee5", "ZEE5", "zee5.com", []),
    ("amazon-prime", "Amazon Prime", "primevideo.com", []),
    ("swiggy-one", "Swiggy One", "swiggy.com", []),
    # Added 23 Nov 2026 (second round): Search Console showed the searches
    # Dealo appears for are nearly all "<shop> gift card discount", and the
    # buyers came from shops with a big discount. So every recognisable shop
    # Dealo sells at 8% or more (live Hubble rates, 23 Nov) gets a page.
    # Left out on purpose: shops nobody searches by name, donation cards,
    # game top-ups, and cards split into tiers (Times Prime, Taj).
    ("hoichoi", "Hoichoi", "hoichoi.tv", []),
    ("gaana", "Gaana", "gaana.com", []),
    ("lionsgate-play", "Lionsgate Play", "lionsgateplay.com", []),
    ("livemint", "Mint", "livemint.com", ["Live Mint", "Livemint"]),
    ("fitpass", "FITPASS", "fitpass.co.in", ["FitPass"]),
    ("nua", "Nua", "nuawoman.com", ["Nua Women"]),
    ("auric", "Auric", "theauric.com", []),
    ("just-lil-things", "Just Lil Things", "justlilthings.in", []),
    ("shiva-organic", "Shiva Organic", "shivaorganic.com", []),
    ("hammer", "Hammer", "hammeronline.in", []),
    ("kimirica", "Kimirica", "kimirica.shop", []),
    ("photojaanic", "Photojaanic", "photojaanic.com", []),
    ("sri-jagdamba-pearls", "Sri Jagdamba Pearls", "jpearls.com", []),
    ("tattva-spa", "Tattva Spa", "tattvaspa.com", []),
    ("soulflower", "Soulflower", "soulflower.in", []),
    ("hoora", "Hoora", "hoora.in", []),
    ("typsy-beauty", "Typsy Beauty", "typsybeauty.com", []),
    ("apollo-diagnostics", "Apollo Diagnostics", "apollo247.com", []),
    ("nat-habit", "Nat Habit", "nathabit.in", []),
    ("soch", "Soch", "soch.com", ["SOCH"]),
    ("flower-aura", "FlowerAura", "floweraura.com", ["Flower Aura"]),
    ("miraggio", "Miraggio", "miraggiolife.com", []),
    ("speedo", "Speedo", "speedo.com", []),
    ("wellbeing-nutrition", "Wellbeing Nutrition", "wellbeingnutrition.com", []),
    ("cgh-earth", "CGH Earth", "cghearth.com", []),
    ("chicco", "Chicco", "chicco.in", []),
    ("kalki", "Kalki", "kalkifashion.com", []),
    ("tego", "TEGO", "tego.fit", []),
    ("boditive", "Boditive", "boditive.com", []),
    ("cosmus", "Cosmus", "cosmus.in", []),
    ("estele", "Estele", "estele.co", []),
    ("femmella", "Femmella", "femmella.com", []),
    ("ornaz", "Ornaz", "ornaz.com", []),
    ("vitamin-haat", "Vitamin Haat", "vitaminhaat.com", []),
    ("whats-up-wellness", "What's Up Wellness", "whatsupwellness.in", []),
    ("fabhotels", "FabHotels", "fabhotels.com", ["Fab Hotels"]),
    ("skullcandy", "Skullcandy", "skullcandy.in", []),
    ("cello", "Cello", "celloworld.com", []),
    ("cordelia-cruises", "Cordelia Cruises", "cordeliacruises.com", ["Cordelia"]),
    ("lohono-stays", "Lohono Stays", "lohono.com", []),
    ("me-n-moms", "Me N Moms", "menmoms.in", []),
    ("haute-sauce", "Haute Sauce", "buyhautesauce.com", []),
    ("french-accent", "French Accent", "getfrenchaccent.com", []),
    ("cloud-tailor", "Cloud Tailor", "cloudtailor.in", ["Cloud tailor"]),
    ("mediwheel", "Mediwheel", "mediwheel.in", []),
    ("pure-home-living", "Pure Home + Living", "purehomeandliving.com", ["Pure Home+Living"]),
    ("at-home", "@home", "at-home.co.in", ["@Home"]),
    ("ixigo-hotels", "Ixigo Hotels", "ixigo.com/hotels", []),
    ("makemytrip-holidays", "MakeMyTrip Holidays", "makemytrip.com/holidays-india", []),
    ("yatra-hotels", "Yatra Hotels & Holidays", "yatra.com/hotels", []),
    ("easemytrip-hotels", "EaseMyTrip Hotels", "easemytrip.com/hotels", ["EaseMyTrip Hotel"]),
    ("sterling-holidays", "Sterling Holiday Resorts", "sterlingholidays.com", []),
    ("bath-and-body-works", "Bath & Body Works", "bathandbodyworks.in", []),
    ("victorias-secret", "Victoria's Secret", "victoriassecret.in", []),
    ("aldo", "ALDO", "aldoshoes.in", []),
    ("charles-and-keith", "Charles & Keith", "charleskeith.in", ["CHARLES & KEITH"]),
    ("superdry", "Superdry", "superdry.in", ["Superdry-Luxe Gift Card"]),
    ("steve-madden", "Steve Madden", "stevemadden.in", ["Steve Madden-Luxe Gift Card"]),
    ("diesel", "Diesel", "dieselindia.com", ["DIESEL-Luxe Gift Card"]),
    ("armani-exchange", "Armani Exchange", "armaniexchange.in", ["Armani Exchange-Luxe Gift Card"]),
    ("michael-kors", "Michael Kors", "michaelkors.com", ["Michael Kors-Luxe Gift Card"]),
    ("coach", "Coach", "coach.com", ["Coach-Luxe Gift Card"]),
    ("hugo-boss", "Hugo Boss", "hugoboss.com", ["Hugo Boss-Luxe Gift Card"]),
    ("kate-spade", "Kate Spade", "katespade.com", ["Kate Spade-Luxe Gift Card"]),
    ("tumi", "Tumi", "tumi.in", ["Tumi-Luxe Brand Card"]),
    ("brooks-brothers", "Brooks Brothers", "brooksbrothers.in", ["Brooks Brothers-Luxe Gift Card"]),
    ("ritu-kumar", "Ritu Kumar", "ritukumar.com", ["Ritu Kumar-Luxe Gift Card"]),
    ("satya-paul", "Satya Paul", "satyapaul.com", ["Satya Paul-Luxe Gift Card"]),
    ("mothercare", "Mothercare", "mothercare.in", ["Mothercare-Luxe Gift Card"]),
    ("pottery-barn", "Pottery Barn", "potterybarn.in", ["Pottery Barn Luxe Gift Card"]),
    ("west-elm", "West Elm", "westelm.in", ["West Elm Luxe Gift Card"]),
    ("muji", "Muji", "muji.com", ["Muji Luxe Gift Card"]),
    ("sunglass-hut", "Sunglass Hut", "sunglasshut.com", []),
    ("health-and-glow", "Health & Glow", "healthandglow.com", []),
    ("indian-terrain", "Indian Terrain", "indianterrain.com", []),
    ("linen-club", "Linen Club", "linenclub.com", []),
    ("raymond", "The Raymond Shop", "myraymond.com", []),
    ("chumbak", "Chumbak", "chumbak.com", []),
    ("naturals-salon", "Naturals Salon", "naturals.in", ["Naturals Salons"]),
    ("timezone", "Timezone", "timezonegames.com", ["TimeZone"]),
    ("punjab-grill", "Punjab Grill", "punjabgrill.in", []),
    ("bikanervala", "Bikanervala", "bikanervala.com", []),
    ("helios", "Helios", "helioswatchstore.com", []),
    # Added 24 Nov 2026: ChatGPT sends people straight to a shop page when
    # they ask "where can I buy a <shop> gift card at a discount" (71 of 81
    # ChatGPT visits in two weeks landed on one; a Giva buyer asked exactly
    # that). A shop with no page cannot be the answer, so every well-known
    # shop Dealo sells at MIN_PCT or more now has one. Still left out:
    # tiered cards (jewellers' coin/gold/diamond, Times Prime, Taj, ITC,
    # Marriott), game top-ups, donation cards, "Fixed"/"Offline" copies of a
    # shop that already has a page, and names nobody searches.
    ("mainland-china", "Mainland China", "speciality.co.in", []),
    ("oh-calcutta", "Oh! Calcutta", "speciality.co.in", []),
    ("tgi-fridays", "TGI Friday's", "tgifridays.com", []),
    ("cafe-delhi-heights", "Cafe Delhi Heights", "cafedelhiheights.com", []),
    ("eatsure", "EatSure", "eatsure.com", []),
    ("behrouz-biryani", "Behrouz Biryani", "behrouzbiryani.com", []),
    ("faasos", "Faasos", "faasos.com", []),
    ("ovenstory", "Ovenstory", "ovenstory.in", []),
    ("sweet-truth", "Sweet Truth", "sweettruth.in", []),
    ("costa-coffee", "Costa Coffee", "costacoffee.in", []),
    ("wendys", "Wendy's", "wendys.com", []),
    ("absolute-barbecues", "Absolute Barbecues", "absolutebarbecues.com", []),
    ("barbeque-nation", "Barbeque Nation", "barbequenation.com", []),
    ("beer-cafe", "The Beer Cafe", "beercafe.in", ["Beer Cafe"]),
    ("tim-hortons", "Tim Hortons", "timhortons.in", []),
    ("wow-momo", "Wow! Momo", "wowmomo.com", ["Wow Momo"]),
    ("wow-china", "Wow! China", "wowmomo.com", ["Wow China"]),
    ("wow-chicken", "Wow! Chicken", "wowmomo.com", ["Wow Chicken"]),
    ("vaango", "Vaango", "vaango.in", []),
    ("freshmenu", "FreshMenu", "freshmenu.com", []),
    ("organic-india", "Organic India", "organicindia.com", []),
    ("spar-hypermarket", "SPAR Hypermarket", "sparindia.com", ["Spar Hypermart"]),
    ("reliance-smart-bazaar", "Reliance Smart Bazaar", "relianceretail.com", []),
    ("aeropostale", "Aeropostale", "aeropostale.com", []),
    ("call-it-spring", "Call It Spring", "aldoshoes.in", []),
    ("forever-new", "Forever New", "forevernew.co.in", []),
    ("hush-puppies", "Hush Puppies", "bata.com", []),
    ("liberty-shoes", "Liberty Shoes", "libertyshoesonline.com", []),
    ("pantaloons", "Pantaloons", "pantaloons.com", []),
    ("aurelia", "Aurelia", "shopforaurelia.com", []),
    ("campus", "Campus", "campusshoes.com", []),
    ("fastrack", "Fastrack", "titan.co.in", []),
    ("neemans", "Neeman's", "neemans.com", ["Neemans"]),
    ("rangriti", "Rangriti", "rangriti.com", []),
    ("relaxo", "Relaxo", "relaxofootwear.com", []),
    ("taneira", "Taneira", "taneira.com", []),
    ("v-mart", "V-Mart", "vmart.co.in", ["VMart"]),
    ("new-balance", "New Balance", "newbalance.com", []),
    ("rareism", "Rareism", "rareism.com", []),
    ("columbia", "Columbia Sportswear", "columbiasportswear.co.in", ["Columbia"]),
    ("hidesign", "Hidesign", "hidesign.com", []),
    ("reliance-trends", "Reliance Trends", "trends.ajio.com", []),
    ("tasva", "Tasva", "tasva.com", []),
    ("w-for-woman", "W", "wforwoman.com", []),
    ("wildcraft", "Wildcraft", "wildcraft.com", []),
    ("shiv-naresh", "Shiv Naresh", "shivnaresh.in", []),
    ("libas", "Libas", "libas.in", []),
    ("myntra-luxe", "Myntra Luxe", "myntra.com", ["Myntra LUXE"]),
    ("nautica", "Nautica", "nautica.in", []),
    ("mango", "Mango", "mango.com", []),
    ("next", "NEXT", "nextdirect.com", []),
    ("the-bear-house", "The Bear House", "thebearhouse.com", ["Bear House"]),
    ("hunkemoller", "Hunkemöller", "hunkemoller.in", ["Hunkemoller"]),
    ("balenciaga", "Balenciaga", "balenciaga.com", ["Balenciaga Luxe Gift Card"]),
    ("bally", "Bally", "bally.com", ["Bally-Luxe Gift Card"]),
    ("bottega-veneta", "Bottega Veneta", "bottegaveneta.com", ["Bottega Veneta-Luxe Gift Card"]),
    ("canali", "Canali", "canali.com", ["Canali-Luxe Gift Card"]),
    ("charles-tyrwhitt", "Charles Tyrwhitt", "charlestyrwhitt.com", ["Charles Tyrwhitt Luxe Gift Card"]),
    ("dune-london", "Dune London", "dunelondon.com", ["Dune London-Luxe Gift Card"]),
    ("emporio-armani", "Emporio Armani", "armani.com", ["Emporio Armani-Luxe Gift Card"]),
    ("giorgio-armani", "Giorgio Armani", "armani.com", ["Giorgio Armani-Luxe Gift Card"]),
    ("ea7", "EA7", "armani.com", []),
    ("jimmy-choo", "Jimmy Choo", "jimmychoo.com", ["Jimmy Choo-Luxe Gift Card"]),
    ("maje", "Maje", "maje.com", ["Maje Luxe Gift Card"]),
    ("paul-and-shark", "Paul & Shark", "paulandshark.com", ["Paul & Shark-Luxe Gift Card"]),
    ("paul-smith", "Paul Smith", "paulsmith.com", []),
    ("sandro", "Sandro", "sandro-paris.com", ["Sandro-Luxe Gift Card"]),
    ("scotch-and-soda", "Scotch & Soda", "scotch-soda.com", ["Scotch & Soda-Luxe Gift Card"]),
    ("tods", "Tod's", "tods.com", ["Tods Luxe Gift Card"]),
    ("tory-burch", "Tory Burch", "toryburch.com", ["Tory Burch-Luxe Gift Card"]),
    ("valentino", "Valentino", "valentino.com", ["Valentino Luxe Gift Card"]),
    ("versace", "Versace", "versace.com", ["Versace-Luxe Gift Card"]),
    ("ferragamo", "Ferragamo", "ferragamo.com", []),
    ("g-star-raw", "G-Star RAW", "g-star.com", ["G-Star Raw"]),
    ("replay", "Replay", "replayjeans.com", []),
    ("gas-jeans", "GAS", "gasjeans.com", ["Gas-Luxe Gift Card"]),
    ("adidas-kids", "Adidas Kids", "adidas.co.in", ["Adidas Kids Luxe Gift Card"]),
    ("inglot", "Inglot", "inglotcosmetics.com", []),
    ("skinn", "Skinn", "skinn.in", []),
    ("the-man-company", "The Man Company", "themancompany.com", []),
    ("tira", "Tira", "tirabeauty.com", []),
    ("nykaa-man", "Nykaa Man", "nykaaman.com", []),
    ("lakme-salon", "Lakmé Salon", "lakmesalon.in", []),
    ("mia-by-tanishq", "Mia by Tanishq", "miabytanishq.com", ["Mia"]),
    ("the-body-shop", "The Body Shop", "thebodyshop.in", []),
    ("himalaya", "Himalaya", "himalayawellness.in", []),
    ("titan-eye-plus", "Titan Eye+", "titaneyeplus.com", []),
    ("lawrence-and-mayo", "Lawrence & Mayo", "lawrenceandmayo.co.in", []),
    ("bodycraft", "Bodycraft", "bodycraft.co.in", ["BodyCraft"]),
    ("truefitt-and-hill", "Truefitt & Hill", "truefittandhill.in", ["TrueFitt & Hill"]),
    ("black-and-decker", "Black+Decker", "appliancesblackanddecker.in", ["Black + Decker"]),
    ("cleartrip-hotels", "Cleartrip Hotels", "cleartrip.com/hotels", ["ClearTrip Hotel"]),
    ("zoomcar", "Zoomcar", "zoomcar.com", ["Zoom Car"]),
    ("air-india", "Air India", "airindia.com", []),
    ("klook", "Klook", "klook.com", []),
    ("sotc", "SOTC", "sotc.in", []),
    ("porter", "Porter", "porter.in", []),
    ("district", "District", "district.in", []),
    ("playo", "Playo", "playo.co", []),
    ("jiohotstar", "JioHotstar", "jiohotstar.com", []),
    ("epic-on", "EPIC ON", "epicon.in", ["Epic On"]),
    ("home-centre", "Home Centre", "homecentre.in", ["Home Center"]),
    ("le-creuset", "Le Creuset", "lecreuset.co.in", []),
    ("milton", "Milton", "milton.in", []),
    ("pigeon", "Pigeon", "stovekraft.com", []),
    ("prestige", "Prestige", "prestige.com", []),
    ("villeroy-and-boch", "Villeroy & Boch", "villeroy-boch.com", ["Villeroy & Boch-Luxe Gift Card"]),
    ("superbottoms", "SuperBottoms", "superbottoms.com", ["Superbottoms"]),
    ("william-penn", "William Penn", "williampenn.net", []),
    ("crossword", "Crossword", "crossword.in", []),
    ("miniklub", "MiniKlub", "miniklub.in", []),
    ("toscano", "Toscano", "toscano.in", []),
    # Added 25 Nov 2026: ChatGPT sends people mostly to store-only cards that
    # few other sites cover (Westside, Charles & Keith). These are well-known
    # names Dealo sells that are used at the counter. The other name is the
    # one the card is listed under (checked against the live service).
    ("taj-hotels", "Taj Hotels", "tajhotels.com", ["Taj Experiences"]),
    ("itc-hotels", "ITC Hotels", "itchotels.com", []),
    ("marriott-hotels", "Marriott Hotels", "marriott.com", ["Marriot Hotels", "Marriott Hotels India"]),
    ("the-leela", "The Leela", "theleela.com", ["Moments by The Leela"]),
    ("apollo-pharmacy", "Apollo Pharmacy", "apollopharmacy.in", ["Apollo"]),
    ("o2-spa", "O2 Spa", "o2spa.in", ["O2 Spa Salon"]),
    ("kalyan-jewellers", "Kalyan Jewellers", "kalyanjewellers.net", []),
    ("joyalukkas", "Joyalukkas", "joyalukkas.in", []),
]

# slug -> the word people search with ("sonyliv subscription offer",
# "amazon prime membership offer"). These pages never say "gift card".
SUBSCRIPTIONS = {
    "sonyliv": "subscription", "zee5": "subscription", "amazon-prime": "membership", "swiggy-one": "membership",
    "hoichoi": "subscription", "gaana": "subscription", "lionsgate-play": "subscription", "livemint": "subscription",
    "fitpass": "membership",
    "jiohotstar": "subscription", "epic-on": "subscription",
}

SOURCES = [("gyftr", "Gyftr"), ("maximize", "Maximize"), ("buyhatke", "BuyHatke")]
_SUFFIX = re.compile(r"(egiftcard|giftcard|egiftvoucher|giftvoucher|evoucher|voucher|ecard|online)$")


def norm(name: str | None) -> str:
    n = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return _SUFFIX.sub("", n)


def load(source: str) -> dict:
    with open(DATA / f"{source}_master.json") as f:
        return json.load(f)


def partner_row(source: str, label: str, brand: dict, slug: str) -> dict | None:
    products = [p for p in brand.get("products") or [] if (p.get("status") or "active") == "active"]
    if not products:
        return None
    best = max(products, key=lambda p: p.get("best_discount_pct") or 0)
    pct = best.get("best_discount_pct")
    if not pct:
        return None
    url = best.get("source_url")
    if url:
        url = quote(url, safe="/:")
    elif source == "gyftr":
        url = f"https://www.gyftr.com/{slug}"
    if not url:
        return None
    discounts = best.get("discounts") or {}
    rtype = (best.get("redemption_type") or "").lower()
    denoms = best.get("denominations") or []
    return {
        "source": source,
        "label": label,
        "pct": float(pct),
        "upi_pct": discounts.get("UPI"),
        "card_pct": discounts.get("Credit Card"),
        "url": url,
        "online": "online" in rtype or "both" in rtype or rtype == "",
        "offline": "offline" in rtype or "store" in rtype or "both" in rtype,
        "denominations": sorted({int(d) for d in denoms if isinstance(d, (int, float))})[:8],
        "typed": bool(best.get("is_custom_denom")),
        "typed_min": best.get("custom_min") or best.get("typed_min"),
        "typed_max": best.get("custom_max") or best.get("typed_max"),
        "stack_limit": best.get("stack_limit"),
        "value_cap": best.get("value_cap"),
        # The day this seller's rate was last read (the voucher refresh), shown
        # beside its row: only Dealo's own rate is re-read every morning.
        "checked": str(best.get("last_scraped") or "")[:10] or None,
    }


def hubble_rate(name: str) -> dict | None:
    """Dealo's own rate from the live backend; None when Hubble doesn't sell it
    or the server can't be reached."""
    try:
        url = f"{API}/hubble/brand?" + urllib.parse.urlencode({"merchant": name})
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
    except Exception as exc:  # noqa: BLE001 — a missing rate must not stop the build
        print(f"  hubble {name}: {exc}", file=sys.stderr)
        return {"error": True}
    b = data.get("brand") if data.get("available") else None
    if not b or not b.get("discount_pct"):
        return None
    return {
        "pct": float(b["discount_pct"]),
        "brand_name": b.get("brand_name") or name,
        "in_store": bool(b.get("in_store")),
        "works": [w for w in b.get("works") or [] if isinstance(w, str)],
        "cards": b.get("cards") or [],
        "min_amount": b.get("min_amount"),
        "max_amount": b.get("max_amount"),
        "typed": bool(b.get("typed")),
        # The service's own redeem steps and terms, word for word.
        "steps": [x for x in (b.get("card") or {}).get("steps") or [] if isinstance(x, str)][:6],
        "terms": [x for x in (b.get("card") or {}).get("terms") or [] if isinstance(x, str)][:6],
    }


def hubble_rate_for(name: str, aliases: list[str]) -> dict | None:
    """Dealo's rate under the page's name, else under one of its other names
    (Hubble lists "MakeMyTrip Hotel"; the page is "MakeMyTrip Hotels"). A
    server error on the page's own name is kept as an error, so the last
    known rate is used instead of a guess."""
    found = hubble_rate(name)
    if found:
        return found
    for other in aliases:
        alt = hubble_rate(other)
        if alt and not alt.get("error"):
            return alt
    return found


def pick_terms(brands: list[dict]) -> dict:
    """Fine print from whichever seller states it; sellers agree far more
    often than they differ, and a stated value beats a blank."""
    steps: list[str] = []
    restrictions: list[str] = []
    one_time = None
    can_club = None
    for b in brands:
        if not steps and b.get("how_to_redeem_steps"):
            steps = [s for s in b["how_to_redeem_steps"] if isinstance(s, str)][:4]
        for r in b.get("redemption_restrictions") or []:
            # Short, named exclusions only ("Gold & Silver coins"), never a
            # numbered clause copied out of the terms.
            if isinstance(r, str) and r not in restrictions and 3 < len(r) < 70 and not re.match(r"^\s*\d", r) and "valid" not in r.lower():
                restrictions.append(r.strip().rstrip("."))
        if one_time is None and b.get("one_time_use") is not None:
            one_time = bool(b["one_time_use"])
        if can_club is None and b.get("can_club_with_offers") is not None:
            can_club = bool(b["can_club_with_offers"])
    return {"steps": steps, "restrictions": restrictions[:3], "multiUse": None if one_time is None else not one_time, "canClub": can_club}


def main() -> None:
    masters = {src: load(src) for src, _ in SOURCES}
    previous = {}
    if OUT.exists():
        previous = {s["slug"]: s for s in json.load(open(OUT))}

    with ThreadPoolExecutor(6) as ex:
        hubble = dict(zip([s[0] for s in SHOPS], ex.map(lambda s: hubble_rate_for(s[1], s[3]), SHOPS)))

    pages = []
    failed = 0
    for slug, name, website, aliases in SHOPS:
        wanted = {norm(name)} | {norm(a) for a in aliases}
        sellers = []
        matched_brands = []
        for src, label in SOURCES:
            candidates = [(s, b) for s, b in masters[src].items() if norm(b.get("brand_name")) in wanted]
            rows = [r for s, b in candidates if (r := partner_row(src, label, b, s))]
            matched_brands += [b for _, b in candidates]
            if rows:
                sellers.append(max(rows, key=lambda r: r["pct"]))
        h = hubble.get(slug)
        # "Checked <date>" is shown on the page and read by Google and
        # ChatGPT, so it moves only when Dealo's rate was really read today.
        checked = date.today().isoformat()
        if h and h.get("error"):
            h = previous.get(slug, {}).get("hubble")
            checked = previous.get(slug, {}).get("checked") or checked
            failed += 1
            print(f"  {name}: kept last Hubble rate")
        best_partner = max(sellers, key=lambda r: r["pct"]) if sellers else None
        top = max([r["pct"] for r in sellers] + ([h["pct"]] if h else []), default=0)
        if top < MIN_PCT and slug not in CURATED and slug not in BELOW_MIN_OK:
            print(f"  skip {name}: best {top}%")
            continue
        if not sellers and not h:
            print(f"  skip {name}: no seller")
            continue
        terms = pick_terms(matched_brands)
        limits = [int(r["stack_limit"]) for r in sellers if r.get("stack_limit")]
        stack = None
        # Where Dealo sells the voucher the page describes Dealo's card, so a
        # partner's limit is stated only when every partner gives the same
        # one. (Flipkart said "one voucher per order" from BuyHatke's limit
        # and "up to 15" from Flipkart's own steps, on the same page.)
        if limits and (not h or len(set(limits)) == 1):
            n = min(limits)
            stack = "One voucher per order" if n == 1 else f"Yes, up to {n} in one order"
        best = {"source": "dealo", "pct": h["pct"]} if h and (not best_partner or h["pct"] >= best_partner["pct"]) else (
            {"source": best_partner["source"], "pct": best_partner["pct"]} if best_partner else None)
        pages.append({
            "slug": slug,
            "name": name,
            "website": f"https://www.{website}/",
            "checked": checked,
            "hubble": h,
            "sellers": sorted(sellers, key=lambda r: -r["pct"]),
            "best": best,
            # Where Dealo sells the voucher the page shows Dealo's card alone,
            # so "works online / in store" must be true of that card, not of
            # a partner's (Superdry: Gyftr's works online, Dealo's is in store).
            "online": ("ONLINE" in h["works"]) if h and h.get("works") else (any(r["online"] for r in sellers) or bool(h and not h["in_store"])),
            "offline": ("OFFLINE" in h["works"]) if h and h.get("works") else (any(r["offline"] for r in sellers) or bool(h and h["in_store"])),
            "stack": stack,
            **terms,
            **({"kind": "subscription", "noun": SUBSCRIPTIONS[slug]} if slug in SUBSCRIPTIONS else {}),
        })
        print(f"  {name}: dealo {h['pct'] if h else '-'}%  " + "  ".join(f"{r['label']} {r['pct']}%" for r in sellers))

    # The daily refresh (.github/workflows/refresh-shop-pages.yml) runs this
    # unattended, so a bad day must leave the live pages alone: the server
    # asleep or down, or a run that would drop a tenth of the pages.
    if "--force" not in sys.argv:
        if failed > len(SHOPS) // 4:
            sys.exit(f"stopped: Dealo's rate could not be read for {failed} of {len(SHOPS)} shops; nothing written")
        if previous and len(pages) < 0.9 * len(previous):
            sys.exit(f"stopped: {len(pages)} pages, down from {len(previous)}; nothing written (--force to write anyway)")
    OUT.write_text(json.dumps(pages, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(pages)} shop pages -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
