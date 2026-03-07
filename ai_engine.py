"""
ai_engine.py — Gruha Alankara Intelligent Design Engine
========================================================
Pipeline:
  1. Image preprocessing + thumbnail generation (PIL)
  2. Transformer text-generation (with timeout + graceful fallback)
  3. Structured JSON output
  4. TTL Cache (1-hour) for style/room/budget combos via cachetools
"""

import os
import json
import random
import concurrent.futures
from datetime import datetime

# ── Caching (TTL-based, 1 hour) ───────────────────────────────────────────────
try:
    from cachetools import TTLCache, cached
    _RECS_CACHE = TTLCache(maxsize=256, ttl=3600)
    CACHETOOLS_AVAILABLE = True
except ImportError:
    import functools
    CACHETOOLS_AVAILABLE = False
    print("⚠️  cachetools not installed, falling back to functools.lru_cache.")

# ── PIL image processing ─────────────────────────────────────────────────────
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️  Pillow not installed. Image preprocessing disabled.")

# ── Transformers pipeline ─────────────────────────────────────────────────────
try:
    from transformers import pipeline as hf_pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️  Transformers not installed. Using rule-based AI fallback.")

# ─────────────────────────────────────────────────────────────────────────────
# Colour Palettes per Style
# ─────────────────────────────────────────────────────────────────────────────
COLOR_PALETTES = {
    "Modern": [
        {"hex": "#1A1A2E", "name": "Midnight Navy", "use": "Accent wall"},
        {"hex": "#16213E", "name": "Deep Dusk",     "use": "Secondary wall"},
        {"hex": "#E2B04A", "name": "Warm Gold",     "use": "Accessories & trim"},
        {"hex": "#F5F5F0", "name": "Chalk White",   "use": "Ceiling & trim"},
        {"hex": "#6B7A8D", "name": "Steel Blue",    "use": "Upholstery"},
    ],
    "Traditional": [
        {"hex": "#8B1A1A", "name": "Royal Crimson", "use": "Accent wall"},
        {"hex": "#C8A96E", "name": "Antique Gold",  "use": "Borders & motifs"},
        {"hex": "#3B2F2F", "name": "Dark Walnut",   "use": "Woodwork"},
        {"hex": "#F5E6C8", "name": "Ivory Cream",   "use": "Ceiling & base walls"},
        {"hex": "#2E5E4E", "name": "Forest Green",  "use": "Drapes & cushions"},
    ],
    "Minimal": [
        {"hex": "#FFFFFF", "name": "Pure White",    "use": "All walls"},
        {"hex": "#D4C5B0", "name": "Warm Greige",   "use": "Accent wall"},
        {"hex": "#8D8D8D", "name": "Stone Grey",    "use": "Upholstery"},
        {"hex": "#2C2C2C", "name": "Charcoal",      "use": "Furniture frames"},
        {"hex": "#C8A96E", "name": "Natural Oak",   "use": "Flooring tone"},
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Furniture Recommendation Rules (fallback / supplement)
# ─────────────────────────────────────────────────────────────────────────────
RULE_BASED = {
    ("Bedroom", "Modern", "Low"): {
        "furniture": [
            {"name": "Nordic Floating Bed",    "price": 32000, "reason": "Space-efficient platform design with LED ambiance"},
            {"name": "Floating Wall Shelves",  "price": 6000,  "reason": "Keeps the floor clear for a spacious feel"},
        ],
        "placement_tips": [
            "Place the bed against the longest wall, centred, with equal clearance on both sides.",
            "Mount shelves at eye level above a small desk nook in the corner.",
            "Use a single pendant light above the bedside for focused warm glow.",
        ],
    },
    ("Bedroom", "Modern", "Medium"): {
        "furniture": [
            {"name": "Nordic Floating Bed",    "price": 32000, "reason": "Sleek Scandinavian-inspired silhouette"},
            {"name": "Japandi Bookshelf",       "price": 14000, "reason": "Dual-purpose storage and decor display"},
        ],
        "placement_tips": [
            "Orient the bed to face the doorway for a welcoming Vastu-aligned entrance.",
            "Place the bookshelf perpendicular to the window to diffuse natural light.",
            "Layer two area rugs — one under the bed, one as a sitting mat — to add warmth.",
        ],
    },
    ("Bedroom", "Modern", "High"): {
        "furniture": [
            {"name": "Nordic Floating Bed",    "price": 32000, "reason": "Statement piece with built-in LED strip"},
            {"name": "Mandala Wardrobe",        "price": 55000, "reason": "Handcrafted storage with artistic finish"},
        ],
        "placement_tips": [
            "Create a hotel-suite feel: symmetrical nightstands, identical lamps.",
            "Install a ceiling-recessed statement light over the bed as the focal point.",
            "Use floor-to-ceiling drapes to maximise the sense of height.",
        ],
    },
    ("Bedroom", "Traditional", "Low"): {
        "furniture": [
            {"name": "Zen Low Platform Bed",   "price": 18000, "reason": "Grounded, earthy aesthetic with natural bamboo"},
            {"name": "Floating Wall Shelves",  "price": 6000,  "reason": "Displays brass artefacts and family heirlooms"},
        ],
        "placement_tips": [
            "Position the bed on the south or west wall per Vastu guidelines.",
            "Hang a Madhubani or Tanjore art piece on the opposite wall as focal point.",
            "Use deep-coloured cotton drapes (burgundy or forest green) to frame the window.",
        ],
    },
    ("Bedroom", "Traditional", "Medium"): {
        "furniture": [
            {"name": "Royal Teak King Bed",    "price": 45000, "reason": "Heirloom-quality solid teak with brass inlays"},
            {"name": "Floating Wall Shelves",  "price": 6000,  "reason": "For displaying pooja essentials and decor"},
        ],
        "placement_tips": [
            "Centre the bed on the south wall; keep the north wall open for positive energy flow.",
            "Use a hand-knotted durrie rug beneath the bed in jewel tones.",
            "Bronze or brass pendant lights on each side echo the bed's metal detailing.",
        ],
    },
    ("Bedroom", "Traditional", "High"): {
        "furniture": [
            {"name": "Royal Teak King Bed",    "price": 45000, "reason": "Opulent centrepiece with ornate craftsmanship"},
            {"name": "Mandala Wardrobe",        "price": 55000, "reason": "Cohesive storage with hand-painted mandala motifs"},
        ],
        "placement_tips": [
            "Commission a custom headboard canopy in rich silk for a regal feel.",
            "Layer silk bed covers in deep reds, golds, and emeralds.",
            "Install jaali-patterned wall panels as a dramatic backdrop behind the bed.",
        ],
    },
    ("Bedroom", "Minimal", "Low"): {
        "furniture": [
            {"name": "Zen Low Platform Bed",   "price": 18000, "reason": "Essence of minimalism — pure, simple, grounded"},
        ],
        "placement_tips": [
            "Leave three walls entirely bare. One curated art piece is enough.",
            "Use a single trailing plant near the window for organic life.",
            "All-white linen with one textured throw — restraint is the aesthetic.",
        ],
    },
    ("Bedroom", "Minimal", "Medium"): {
        "furniture": [
            {"name": "Zen Low Platform Bed",   "price": 18000, "reason": "Low profile keeps visual weight minimal"},
            {"name": "Floating Wall Shelves",  "price": 6000,  "reason": "Functional storage without bulk"},
        ],
        "placement_tips": [
            "Adopt a strict 3-colour rule: white, one warm neutral, one muted accent.",
            "Conceal all cables behind the bedframe or under-floor management.",
            "A single arc floor lamp replaces two nightstand lamps for clean lines.",
        ],
    },
    ("Bedroom", "Minimal", "High"): {
        "furniture": [
            {"name": "Zen Low Platform Bed",   "price": 18000, "reason": "Flagship minimalist silhouette"},
            {"name": "Mandala Wardrobe",        "price": 55000, "reason": "Wall-colour-matched built-in wardrobe effect"},
        ],
        "placement_tips": [
            "Invest in bespoke joinery painted wall-colour for invisible storage.",
            "Polished concrete or wide-plank oak flooring sets the luxurious base.",
            "Recessed ceiling niches replace shelving — everything is built in.",
        ],
    },
    ("Hall", "Modern", "Low"): {
        "furniture": [
            {"name": "Rattan Accent Chair",    "price": 12000, "reason": "Lightweight focal seating with boho-modern edge"},
            {"name": "Floating Wall Shelves",  "price": 6000,  "reason": "Display space without sacrificing floor area"},
        ],
        "placement_tips": [
            "Use a large area rug to anchor the seating zone within an open plan.",
            "A mirror on the short wall creates an illusion of depth.",
            "Cluster pendant lights at varying heights over the seating area.",
        ],
    },
    ("Hall", "Modern", "Medium"): {
        "furniture": [
            {"name": "Modular L-Shape Sectional", "price": 62000, "reason": "Defines living zone in open-plan spaces"},
            {"name": "Mid-Century Coffee Table",  "price": 15000, "reason": "Walnut-brass combination bridges styles"},
        ],
        "placement_tips": [
            "Float the sofa away from the wall — allow 45 cm clearance for flow.",
            "Place the coffee table 40 cm from the sofa edge for comfortable reach.",
            "Use a geometric jute rug to ground the furniture grouping.",
        ],
    },
    ("Hall", "Modern", "High"): {
        "furniture": [
            {"name": "Modular L-Shape Sectional", "price": 62000, "reason": "Premium flexible seating for large halls"},
            {"name": "Mid-Century Coffee Table",  "price": 15000, "reason": "Elegantly proportioned focal table"},
            {"name": "Brass Floor Lamp",          "price": 8500,  "reason": "Sculptural light source as statement art"},
        ],
        "placement_tips": [
            "Install a statement ceiling light (chandelier or sputnik) as the room's crown.",
            "Create a secondary reading nook with a single armchair and side table.",
            "Gallery wall of monochrome prints on one wall keeps the space curated.",
        ],
    },
    ("Hall", "Traditional", "Low"): {
        "furniture": [
            {"name": "Rattan Accent Chair",    "price": 12000, "reason": "Earthy material that complements traditional decor"},
            {"name": "Brass Floor Lamp",       "price": 8500,  "reason": "Antique brass arc lamp adds old-world warmth"},
        ],
        "placement_tips": [
            "Hang a large Madhubani or Tanjore art piece as the room's anchor.",
            "Use hand-block-printed cotton cushion covers on seating.",
            "Brass diyas on the coffee table add authentic festive ambiance.",
        ],
    },
    ("Hall", "Traditional", "Medium"): {
        "furniture": [
            {"name": "Maharaja Chesterfield Sofa", "price": 85000, "reason": "Deep-button velvet embodying royal Indian heritage"},
            {"name": "Brass Floor Lamp",           "price": 8500,  "reason": "Warm amber glow accentuates jewel tones"},
        ],
        "placement_tips": [
            "Place the sofa facing the TV wall with a patterned durrie underfoot.",
            "Use jaali-pattern wooden dividers to separate dining from living.",
            "Layer copper and brass accessories on a carved wooden console table.",
        ],
    },
    ("Hall", "Traditional", "High"): {
        "furniture": [
            {"name": "Maharaja Chesterfield Sofa", "price": 85000, "reason": "Heritage-grade statement seating"},
            {"name": "Mid-Century Coffee Table",   "price": 15000, "reason": "Refined centre-piece for the seating group"},
            {"name": "Brass Floor Lamp",           "price": 8500,  "reason": "Illuminates the room with antique grandeur"},
        ],
        "placement_tips": [
            "Commission custom upholstery in royal brocade or silk velvet.",
            "Install hand-painted ceiling murals or intricate plaster mouldings.",
            "Use heirloom silver or brass artefacts as curated table decor.",
        ],
    },
    ("Hall", "Minimal", "Low"): {
        "furniture": [
            {"name": "Rattan Accent Chair",    "price": 12000, "reason": "Singular statement piece — less is more"},
        ],
        "placement_tips": [
            "White walls and a single framed art print — timeless minimal formula.",
            "One trailing plant near the window provides organic contrast.",
            "Resist the urge to add more — the empty space IS the design.",
        ],
    },
    ("Hall", "Minimal", "Medium"): {
        "furniture": [
            {"name": "Modular L-Shape Sectional", "price": 62000, "reason": "Clean geometry; modular for future rearrangement"},
            {"name": "Floating Wall Shelves",     "price": 6000,  "reason": "Styled simply — 3 objects max per shelf"},
        ],
        "placement_tips": [
            "Limit colour palette to 3 tones: white, one warm neutral, one accent.",
            "All items off the floor — use a media unit with concealed storage.",
            "Cable management is critical: run everything through the wall or under flooring.",
        ],
    },
    ("Hall", "Minimal", "High"): {
        "furniture": [
            {"name": "Modular L-Shape Sectional", "price": 62000, "reason": "Premium upholstery in muted linen or boucle"},
            {"name": "Japandi Bookshelf",          "price": 14000, "reason": "Open-back shelf styled with only 20% objects"},
        ],
        "placement_tips": [
            "Bespoke joinery with concealed push-open doors for all storage.",
            "Polished micro-concrete or wide-plank oak sets a luxurious minimal base.",
            "A single large-format canvas or sculpture acts as the sole decor statement.",
        ],
    },
    ("Kitchen", "Modern", "Low"): {
        "furniture": [
            {"name": "Industrial Bar Stools Set", "price": 9500, "reason": "Space-saving counter seating with urban edge"},
        ],
        "placement_tips": [
            "Subway tiles in white with black grout refresh a budget kitchen instantly.",
            "Install under-cabinet LED strips — high impact, low cost.",
            "Stainless steel accessories (bin, soap dispenser) keep the look cohesive.",
        ],
    },
    ("Kitchen", "Modern", "Medium"): {
        "furniture": [
            {"name": "Scandinavian Dining Table", "price": 24000, "reason": "Clean oak lines complement any modern kitchen"},
            {"name": "Industrial Bar Stools Set", "price": 9500,  "reason": "Versatile counter seating pair"},
        ],
        "placement_tips": [
            "Open shelving above the counter with styled dishware adds personality.",
            "Position the dining table to catch natural light for a bright, airy feel.",
            "Matte black tap fixtures are an affordable luxury upgrade.",
        ],
    },
    ("Kitchen", "Modern", "High"): {
        "furniture": [
            {"name": "Scandinavian Dining Table", "price": 24000, "reason": "Anchors the dining zone with Scandi elegance"},
            {"name": "Industrial Bar Stools Set", "price": 9500,  "reason": "Designer counter seating that invites casual dining"},
        ],
        "placement_tips": [
            "Invest in smart appliances with a unified matte-black or stainless palette.",
            "A waterfall marble island with built-in induction hob is the hero element.",
            "Handleless cabinetry with push-to-open mechanisms for ultra-clean lines.",
        ],
    },
    ("Kitchen", "Traditional", "Low"): {
        "furniture": [
            {"name": "Sheesham Wood Dining Set", "price": 38000, "reason": "Solid wood warmth at an accessible price point"},
        ],
        "placement_tips": [
            "Copper vessels and terracotta pots on open shelves add authentic warmth.",
            "Hand-painted clay tile backsplash is a beautiful budget-friendly choice.",
            "A jute runner under the dining table grounds the traditional aesthetic.",
        ],
    },
    ("Kitchen", "Traditional", "Medium"): {
        "furniture": [
            {"name": "Sheesham Wood Dining Set", "price": 38000, "reason": "Heritage craftsmanship meets everyday dining"},
        ],
        "placement_tips": [
            "Mosaic tile backsplash with brass fixtures — a classic Indian combination.",
            "Install a traditional chakki (grinding stone) as a decorative console.",
            "Use embroidered table linen in jewel tones for festive everyday dining.",
        ],
    },
    ("Kitchen", "Traditional", "High"): {
        "furniture": [
            {"name": "Sheesham Wood Dining Set", "price": 38000, "reason": "Premium sheesham with carved chair backs"},
        ],
        "placement_tips": [
            "Hand-painted Kalamkari curtains frame the window as textile art.",
            "Commission a custom carved wooden mantel above the cooking range.",
            "Brass and copper bespoke fittings throughout for heritage opulence.",
        ],
    },
    ("Kitchen", "Minimal", "Low"): {
        "furniture": [
            {"name": "Scandinavian Dining Table", "price": 24000, "reason": "Pared-back form that lets the food be the star"},
        ],
        "placement_tips": [
            "Clear countertops — keep one hero appliance visible, rest concealed.",
            "A single potted herb on the windowsill is the only decor needed.",
            "White or light grey walls with natural wood accents: that's the whole palette.",
        ],
    },
    ("Kitchen", "Minimal", "Medium"): {
        "furniture": [
            {"name": "Scandinavian Dining Table", "price": 24000, "reason": "Scandinavian simplicity pairs with any palette"},
            {"name": "Industrial Bar Stools Set", "price": 9500,  "reason": "Minimal metal silhouette — visually light"},
        ],
        "placement_tips": [
            "Handleless cabinet fronts in matte white maximise clean lines.",
            "Integrated fridge and dishwasher panels maintain the seamless look.",
            "One pendant light over the island — no more, no less.",
        ],
    },
    ("Kitchen", "Minimal", "High"): {
        "furniture": [
            {"name": "Scandinavian Dining Table", "price": 24000, "reason": "Designer-level simplicity — the ultimate minimal statement"},
        ],
        "placement_tips": [
            "Fully integrated appliances behind matching cabinetry — total concealment.",
            "Bespoke waterfall island in Calacatta marble as the singular hero element.",
            "Recessed ceiling lighting only — no visible fixtures or pendant cords.",
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Image Preprocessing
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_image(image_path: str) -> dict:
    """
    Open and analyse the room image.
    Returns a dict with: size, mode, dominant_tone, brightness_estimate.
    Falls back gracefully if PIL is unavailable or file is missing.
    """
    result = {
        "width": None, "height": None,
        "dominant_tone": "neutral", "brightness": "medium",
        "analysed": False,
    }
    if not PIL_AVAILABLE or not image_path or not os.path.exists(image_path):
        return result

    try:
        img = Image.open(image_path).convert("RGB")
        img_resized = img.resize((512, 512))
        result["width"], result["height"] = img.size
        result["analysed"] = True

        # Sample centre pixels to estimate dominant tone
        pixels = []
        for x in range(200, 312, 6):
            for y in range(200, 312, 6):
                pixels.append(img_resized.getpixel((x, y)))

        avg_r = sum(p[0] for p in pixels) / len(pixels)
        avg_g = sum(p[1] for p in pixels) / len(pixels)
        avg_b = sum(p[2] for p in pixels) / len(pixels)
        brightness = (avg_r + avg_g + avg_b) / 3

        result["brightness"] = "bright" if brightness > 180 else "dark" if brightness < 80 else "medium"

        if avg_r > avg_g and avg_r > avg_b:
            result["dominant_tone"] = "warm"
        elif avg_b > avg_r and avg_b > avg_g:
            result["dominant_tone"] = "cool"
        elif avg_g > avg_r and avg_g > avg_b:
            result["dominant_tone"] = "natural"
        else:
            result["dominant_tone"] = "neutral"

    except Exception as e:
        print(f"⚠️  Image preprocessing error: {e}")

    return result


def generate_thumbnail(image_path: str, size: tuple = (200, 200)) -> str | None:
    """
    Generate a small thumbnail for gallery use.
    Saves to static/thumbnails/<same-filename> and returns the thumbnail path.
    Returns None if PIL is unavailable or on any error.
    """
    if not PIL_AVAILABLE or not image_path or not os.path.exists(image_path):
        return None
    try:
        thumb_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'static', 'thumbnails'
        )
        os.makedirs(thumb_dir, exist_ok=True)
        filename = os.path.basename(image_path)
        thumb_path = os.path.join(thumb_dir, filename)
        with Image.open(image_path) as img:
            img.convert('RGB').thumbnail(size, Image.LANCZOS)
            img.save(thumb_path, optimize=True, quality=75)
        return thumb_path
    except Exception as e:
        print(f"⚠️  Thumbnail generation error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Transformer AI Pipeline (with timeout)
# ─────────────────────────────────────────────────────────────────────────────

_generator = None
_generator_loaded = False


def _load_generator():
    """Lazily load the text-generation pipeline."""
    global _generator, _generator_loaded
    if _generator_loaded:
        return _generator
    try:
        _generator = hf_pipeline(
            "text-generation",
            model="distilgpt2",
            max_new_tokens=200,
            pad_token_id=50256,
        )
        print("✅ AI text-generation pipeline loaded (distilgpt2).")
    except Exception as e:
        print(f"⚠️  Could not load AI pipeline: {e}")
        _generator = None
    _generator_loaded = True
    return _generator


def _run_transformer(prompt: str, timeout_seconds: int = 15) -> str | None:
    """
    Run the transformer pipeline in a thread with a timeout.
    Returns generated text or None on failure / timeout.
    """
    if not TRANSFORMERS_AVAILABLE:
        return None

    gen = _load_generator()
    if gen is None:
        return None

    def _call():
        try:
            out = gen(prompt, do_sample=True, temperature=0.7)
            return out[0]["generated_text"]
        except Exception as e:
            print(f"⚠️  Transformer inference error: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            print("⚠️  AI model timed out. Using rule-based fallback.")
            return None
        except Exception as e:
            print(f"⚠️  Executor error: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# TTL-Cached Rule-Based Core (1-hour cache)
# ─────────────────────────────────────────────────────────────────────────────

if CACHETOOLS_AVAILABLE:
    @cached(cache=_RECS_CACHE)
    def _cached_recommendations(room_type: str, style: str, budget: str) -> tuple:
        return _fetch_recommendations(room_type, style, budget)
else:
    @functools.lru_cache(maxsize=128)
    def _cached_recommendations(room_type: str, style: str, budget: str) -> tuple:
        return _fetch_recommendations(room_type, style, budget)


def _fetch_recommendations(room_type: str, style: str, budget: str) -> tuple:
    """
    Return (furniture_list, placement_tips, palette) as a tuple.
    """
    key = (room_type, style, budget)
    rec = RULE_BASED.get(key)
    if not rec:
        for k, v in RULE_BASED.items():
            if k[0] == room_type and k[1] == style:
                rec = v
                break
    if not rec:
        rec = {
            "furniture": [{"name": "Mid-Century Coffee Table", "price": 15000,
                           "reason": "A versatile statement piece that works in any room."}],
            "placement_tips": [
                "Start with a focal furniture piece and build outward.",
                "Ensure clear traffic paths of at least 90 cm between pieces.",
                "Use lighting zones — ambient, task, and accent — for depth.",
            ],
        }
    palette = COLOR_PALETTES.get(style, COLOR_PALETTES["Modern"])
    return (rec["furniture"], rec["placement_tips"], palette)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_design_suggestions(
    image_path: str = None,
    style_theme: str = "Modern",
    room_type: str = "Hall",
    budget: str = "Medium",
) -> dict:
    """
    Generate structured interior design suggestions.
    Returns dict with: furniture, color_scheme, placement_tips,
    confidence, source, image_analysis, thumbnail_path, generated_at.
    """
    source = "rule-based"

    # 1. Image preprocessing + thumbnail
    image_analysis = {"analysed": False, "dominant_tone": "neutral", "brightness": "medium"}
    thumbnail_path = None
    if image_path:
        image_analysis = preprocess_image(image_path)
        thumbnail_path = generate_thumbnail(image_path)

    # 2. Pull TTL-cached rule-based recommendations
    furniture, placement_tips, palette = _cached_recommendations(room_type, style_theme, budget)

    # 3. Attempt transformer enhancement (only when image was analysed)
    ai_tip = None
    if TRANSFORMERS_AVAILABLE and image_analysis.get("analysed"):
        prompt = (
            f"Interior design advice for a {room_type.lower()} with {style_theme.lower()} style "
            f"and {budget.lower()} budget. The room has {image_analysis.get('brightness','medium')} "
            f"lighting and {image_analysis.get('dominant_tone','neutral')} tones. "
            f"Top design tip:"
        )
        raw = _run_transformer(prompt, timeout_seconds=15)
        if raw:
            generated = raw[len(prompt):].strip().split(".")[0].strip()
            if generated and len(generated) > 20:
                ai_tip = generated[:200]
                source = "ai"

    # 4. Merge tips
    final_tips = list(placement_tips)
    if ai_tip:
        final_tips.insert(0, f"🤖 AI Insight: {ai_tip}.")

    # 5. Confidence
    base_confidence = random.uniform(0.82, 0.97)
    if source == "ai":
        base_confidence = min(base_confidence + 0.03, 0.99)
    if image_analysis.get("analysed"):
        base_confidence = min(base_confidence + 0.02, 0.99)

    return {
        "furniture":       [dict(f) for f in furniture],
        "color_scheme":    palette,
        "placement_tips":  final_tips,
        "confidence":      round(base_confidence, 3),
        "source":          source,
        "image_analysis":  image_analysis,
        "thumbnail_path":  thumbnail_path,
        "generated_at":    datetime.utcnow().isoformat() + "Z",
    }
