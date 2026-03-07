import os
import uuid
import json
import random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Design, Furniture, Booking, ChatHistory
from ai_engine import generate_design_suggestions

import pyotp
import qrcode
import base64
from io import BytesIO
from flask_socketio import SocketIO, emit, join_room, leave_room


try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

try:
    from flask_wtf.csrf import CSRFProtect
    CSRF_AVAILABLE = True
except ImportError:
    CSRF_AVAILABLE = False

try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False

IMAGE_MAGIC_BYTES = [
    (b'\xff\xd8\xff', 'jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'png'),
    (b'GIF87a', 'gif'),
    (b'GIF89a', 'gif'),
    (b'RIFF', 'webp'),
]

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")


if LIMITER_AVAILABLE:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per hour"],
        storage_uri="memory://",
    )
else:
    limiter = None

if CSRF_AVAILABLE:
    csrf = CSRFProtect(app)
    app.config.setdefault('WTF_CSRF_TIME_LIMIT', 3600)

# ─────────────────────────────────────────
# Ensure required directories exist
# ─────────────────────────────────────────
required_dirs = [
    app.config['UPLOAD_FOLDER'],
    os.path.join(app.root_path, 'database'),
    os.path.join(app.root_path, 'static', 'css'),
    os.path.join(app.root_path, 'static', 'js'),
    os.path.join(app.root_path, 'templates'),
]
for d in required_dirs:
    os.makedirs(d, exist_ok=True)
    print(f'✓ Directory checked/created: {os.path.relpath(d, app.root_path)}')


def sanitize(text, max_length=200):
    """Strip HTML tags and cap length for user inputs."""
    if BLEACH_AVAILABLE:
        cleaned = bleach.clean(str(text), tags=[], strip=True)
    else:
        import html
        cleaned = html.escape(str(text))
    return cleaned[:max_length].strip()


def allowed_file(filename, file_stream=None):
    """
    Two-layer validation:
    1. Extension check.
    2. Magic-byte check of the first 16 bytes (if file_stream provided).
    """
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in app.config['ALLOWED_EXTENSIONS']:
        return False
    if file_stream is not None:
        header = file_stream.read(16)
        file_stream.seek(0)
        if not any(header.startswith(sig) for sig, _ in IMAGE_MAGIC_BYTES):
            return False
    return True


# ─────────────────────────────────────────
# Furniture Catalogue Data (seeded once)
# ─────────────────────────────────────────
FURNITURE_DATA = [
    # Bedroom
    {"name": "Royal Teak King Bed", "category": "Bedroom", "style": "Traditional", "price": 45000,
     "description": "Handcrafted solid teak wood king bed with ornate brass inlays.", "image_url": "furniture/bed_teak.jpg"},
    {"name": "Nordic Floating Bed", "category": "Bedroom", "style": "Modern", "price": 32000,
     "description": "Minimalist platform bed with LED underlight and walnut finish.", "image_url": "furniture/bed_nordic.jpg"},
    {"name": "Zen Low Platform Bed", "category": "Bedroom", "style": "Minimal", "price": 18000,
     "description": "Low Japanese-style platform bed in natural bamboo.", "image_url": "furniture/bed_zen.jpg"},

    # Living Room
    {"name": "Maharaja Chesterfield Sofa", "category": "Hall", "style": "Traditional", "price": 85000,
     "description": "Deep-button plush velvet Chesterfield with carved rosewood legs.", "image_url": "furniture/sofa_chesterfield.jpg"},
    {"name": "Modular L-Shape Sectional", "category": "Hall", "style": "Modern", "price": 62000,
     "description": "Contemporary modular sectional in premium grey fabric.", "image_url": "furniture/sofa_lshape.jpg"},
    {"name": "Rattan Accent Chair", "category": "Hall", "style": "Minimal", "price": 12000,
     "description": "Lightweight rattan lounge chair with natural linen cushion.", "image_url": "furniture/chair_rattan.jpg"},
    {"name": "Mid-Century Coffee Table", "category": "Hall", "style": "Modern", "price": 15000,
     "description": "Walnut and brass hairpin leg coffee table.", "image_url": "furniture/table_coffee.jpg"},
    {"name": "Brass Floor Lamp", "category": "Hall", "style": "Traditional", "price": 8500,
     "description": "Antique brass arc floor lamp with ivory shade.", "image_url": "furniture/lamp_floor.jpg"},

    # Kitchen
    {"name": "Sheesham Wood Dining Set", "category": "Kitchen", "style": "Traditional", "price": 38000,
     "description": "6-seater solid sheesham dining table with carved chairs.", "image_url": "furniture/dining_sheesham.jpg"},
    {"name": "Scandinavian Dining Table", "category": "Kitchen", "style": "Minimal", "price": 24000,
     "description": "Clean-line oak dining table with matching bench.", "image_url": "furniture/dining_scandi.jpg"},
    {"name": "Industrial Bar Stools Set", "category": "Kitchen", "style": "Modern", "price": 9500,
     "description": "Set of 3 metal and wood counter-height bar stools.", "image_url": "furniture/stools_bar.jpg"},

    # Storage
    {"name": "Mandala Wardrobe", "category": "Bedroom", "style": "Traditional", "price": 55000,
     "description": "4-door sheesham wardrobe with hand-painted mandala motifs.", "image_url": "furniture/wardrobe_mandala.jpg"},
    {"name": "Floating Wall Shelves", "category": "Hall", "style": "Minimal", "price": 6000,
     "description": "Set of 5 mango wood floating wall shelves.", "image_url": "furniture/shelves_wall.jpg"},
    {"name": "Japandi Bookshelf", "category": "Hall", "style": "Modern", "price": 14000,
     "description": "Open-back bamboo bookshelf with black metal frame.", "image_url": "furniture/shelf_japandi.jpg"},
]


# ─────────────────────────────────────────
# AI Recommendation Engine (Rule-Based)
# ─────────────────────────────────────────
RECOMMENDATIONS = {
    ("Bedroom", "Modern", "Low"):       {"items": ["Nordic Floating Bed", "Floating Wall Shelves"],    "tip": "Use monochrome bedding and minimal décor for a clean look."},
    ("Bedroom", "Modern", "Medium"):    {"items": ["Nordic Floating Bed", "Japandi Bookshelf"],        "tip": "Pair with warm LED lighting and neutral tones."},
    ("Bedroom", "Modern", "High"):      {"items": ["Nordic Floating Bed", "Mandala Wardrobe"],         "tip": "Invest in smart lighting and built-in storage."},
    ("Bedroom", "Traditional", "Low"):  {"items": ["Zen Low Platform Bed", "Floating Wall Shelves"],   "tip": "Use cotton drapes and wooden photo frames."},
    ("Bedroom", "Traditional", "Medium"):{"items": ["Royal Teak King Bed", "Floating Wall Shelves"],   "tip": "Add brass artifacts for authentic Indian flair."},
    ("Bedroom", "Traditional", "High"): {"items": ["Royal Teak King Bed", "Mandala Wardrobe"],         "tip": "Layer silk cushions and hand-knotted rugs for opulence."},
    ("Bedroom", "Minimal", "Low"):      {"items": ["Zen Low Platform Bed"],                            "tip": "Keep surfaces clear. One plant, one lamp."},
    ("Bedroom", "Minimal", "Medium"):   {"items": ["Zen Low Platform Bed", "Floating Wall Shelves"],   "tip": "Choose a muted capsule colour palette."},
    ("Bedroom", "Minimal", "High"):     {"items": ["Zen Low Platform Bed", "Mandala Wardrobe"],        "tip": "Opt for built-in wardrobes painted wall-colour."},

    ("Hall", "Modern", "Low"):          {"items": ["Rattan Accent Chair", "Floating Wall Shelves"],    "tip": "Use area rugs to define zones in an open-plan hall."},
    ("Hall", "Modern", "Medium"):       {"items": ["Modular L-Shape Sectional", "Mid-Century Coffee Table"], "tip": "Accent with a geometric patterned rug."},
    ("Hall", "Modern", "High"):         {"items": ["Modular L-Shape Sectional", "Mid-Century Coffee Table", "Brass Floor Lamp"], "tip": "Install a statement ceiling light as a focal point."},
    ("Hall", "Traditional", "Low"):     {"items": ["Rattan Accent Chair", "Brass Floor Lamp"],         "tip": "Hang a Madhubani art piece on the feature wall."},
    ("Hall", "Traditional", "Medium"):  {"items": ["Maharaja Chesterfield Sofa", "Brass Floor Lamp"],  "tip": "Use warm amber lighting and jaali-pattern dividers."},
    ("Hall", "Traditional", "High"):    {"items": ["Maharaja Chesterfield Sofa", "Mid-Century Coffee Table", "Brass Floor Lamp"], "tip": "Commission custom upholstery in royal hues."},
    ("Hall", "Minimal", "Low"):         {"items": ["Rattan Accent Chair"],                             "tip": "White walls + one piece of art = timeless minimal hall."},
    ("Hall", "Minimal", "Medium"):      {"items": ["Modular L-Shape Sectional", "Floating Wall Shelves"], "tip": "Limit colour palette to 3 tones maximum."},
    ("Hall", "Minimal", "High"):        {"items": ["Modular L-Shape Sectional", "Japandi Bookshelf"],  "tip": "Invest in bespoke joinery with concealed storage."},

    ("Kitchen", "Modern", "Low"):       {"items": ["Industrial Bar Stools Set"],                       "tip": "Subway tiles and stainless steel accessories refresh any kitchen."},
    ("Kitchen", "Modern", "Medium"):    {"items": ["Scandinavian Dining Table", "Industrial Bar Stools Set"], "tip": "Open shelving with styled dishware adds character."},
    ("Kitchen", "Modern", "High"):      {"items": ["Scandinavian Dining Table", "Industrial Bar Stools Set"], "tip": "Smart appliances with matte black hardware elevate the space."},
    ("Kitchen", "Traditional", "Low"):  {"items": ["Sheesham Wood Dining Set"],                        "tip": "Copper vessels and terracotta pots add warmth."},
    ("Kitchen", "Traditional", "Medium"):{"items": ["Sheesham Wood Dining Set"],                       "tip": "Mosaic tiles backsplash with brass fixtures work beautifully."},
    ("Kitchen", "Traditional", "High"): {"items": ["Sheesham Wood Dining Set"],                        "tip": "Hand-painted Kalamkari curtains complete a heritage kitchen."},
    ("Kitchen", "Minimal", "Low"):      {"items": ["Scandinavian Dining Table"],                       "tip": "Clear countertops with one hero appliance."},
    ("Kitchen", "Minimal", "Medium"):   {"items": ["Scandinavian Dining Table", "Industrial Bar Stools Set"], "tip": "Handleless cabinet fronts maximise clean lines."},
    ("Kitchen", "Minimal", "High"):     {"items": ["Scandinavian Dining Table"],                       "tip": "Integrated appliances and a waterfall island for ultimate minimal look."},
}

AGENT_THINKING = [
    "Analysing room dimensions from image metadata…",
    "Cross-referencing style preferences with cultural aesthetics…",
    "Evaluating budget constraints against premium material options…",
    "Prioritising ergonomics and vastu-compliant furniture placement…",
    "Finalising palette: warm undertones match your chosen style…",
]

BUDDY_RESPONSES = {
    "en": {
        "greet":    "Namaste! 🙏 I'm Buddy, your personal interior design assistant. How can I help create your dream home today?",
        "book":     "Great choice! I'm booking the {item} for you right now. You'll receive a confirmation shortly.",
        "suggest":  "Based on your preferences, I'd recommend exploring our {style} collection — especially the {item}. Want me to book it?",
        "confirm":  "✅ Booking confirmed! Your {item} will be delivered in 7-10 business days. Booking ID: #{booking_id}",
        "default":  "I'm here to help with furniture recommendations and bookings. Tell me your room type and style preference!",
    },
    "hi": {
        "greet":    "नमस्ते! 🙏 मैं बडी हूँ, आपका व्यक्तिगत इंटीरियर डिज़ाइन सहायक। आज आपके सपनों के घर को सजाने में कैसे मदद करूँ?",
        "book":     "बहुत अच्छा विकल्प! मैं अभी आपके लिए {item} बुक कर रहा/रही हूँ।",
        "suggest":  "आपकी पसंद के आधार पर, मैं {style} कलेक्शन — खासकर {item} की सिफारिश करूँगा/करूँगी।",
        "confirm":  "✅ बुकिंग की पुष्टि हो गई! आपका {item} 7-10 कार्यदिवसों में डिलीवर होगा। बुकिंग ID: #{booking_id}",
        "default":  "मैं फर्नीचर की सिफारिश और बुकिंग में मदद करने के लिए यहाँ हूँ!",
    },
    "te": {
        "greet":    "Namaskaram! 🙏 Nenu Buddy, mi vyaktigata interior design sahayakudini. Eeroju mi dream home ni alankaridam!",
        "book":     "Chala manchidi! Nenu ippude mi kosam {item} book chestunnanu.",
        "suggest":  "Mi abhiruchi aadharam ga, {style} collection - mukhyamga {item} ni sifarasu chestanu.",
        "confirm":  "✅ Booking confirmed! Mi {item} 7-10 pani dinalalo delivery avutundi. Booking ID: #{booking_id}",
        "default":  "Nenu furniture sifarasulu mariyu bookings lo sahayam cheyyadaniki ikkade unnanu!",
    },
    "kn": {
        "greet":    "Namaskara! 🙏 Naanu Buddy, nimma vyaktigata interior design sahayakaru. Indhu nimma kanasina mane alankarisuva?",
        "book":     "Tumba olleya aayke! Naanu ijje nimmagaagi {item} book maaduttiddeene.",
        "suggest":  "Nimma asakti aadharada mele, {style} sangrah - vishesha vaagi {item} sifaarasu maaduttane.",
        "confirm":  "✅ Booking dashti padisalaagide! Nimma {item} 7-10 kelasada dinalalli delivery aaguttade. Booking ID: #{booking_id}",
        "default":  "Naanu furniture sifarasugalu mattu bookingallalli sahayisalu ikkade ideene!",
    },
    "ta": {
        "greet":    "Vanakkam! 🙏 Naanum Buddy, ungal thaanipatta ulluurai vadivamaiyppu udaviyaalar. Indru ungal kanavil veedu alangaricha?",
        "book":     "Mikavum sirantha theervvu! Naanum ungalukkaaga {item} book seigiren.",
        "suggest":  "Ungal viruppatthin adippadaiyil, {style} thoguppu - kurippaaga {item} parindhurai seigiren.",
        "confirm":  "✅ Booking urudhi paduttapattadhu! Ungal {item} 7-10 vaniga naatkalil vitarikkappadum. Booking ID: #{booking_id}",
        "default":  "Thalappidam parinthurigal matrum bookingalil udava ingke irukiren!",
    },
}

KEYWORD_INTENTS = {
    "greet":   ["hello", "hi", "namaste", "namaskara", "vanakkam", "namaskaram", "hey", "start"],
    "book":    ["book", "order", "buy", "purchase", "buk", "konu"],
    "suggest": ["suggest", "recommend", "what", "which", "show", "sifarasu", "parindhurai"],
}


def detect_intent(text):
    text_lower = text.lower()
    for intent, keywords in KEYWORD_INTENTS.items():
        if any(k in text_lower for k in keywords):
            return intent
    return "default"


def get_buddy_response(message, language="en", context=None):
    lang_responses = BUDDY_RESPONSES.get(language, BUDDY_RESPONSES["en"])
    intent = detect_intent(message)

    all_names = [f["name"] for f in FURNITURE_DATA]
    random_item  = random.choice(all_names)
    random_style = random.choice(["Modern", "Traditional", "Minimal"])

    if intent == "book":
        # Simulate booking
        booking_id = random.randint(10000, 99999)
        response = lang_responses["confirm"].format(item=random_item, booking_id=booking_id)
        return {"response": response, "intent": "book", "booking_id": booking_id, "item": random_item}
    elif intent == "suggest":
        response = lang_responses["suggest"].format(style=random_style, item=random_item)
        return {"response": response, "intent": "suggest"}
    elif intent == "greet":
        return {"response": lang_responses["greet"], "intent": "greet"}
    else:
        return {"response": lang_responses["default"], "intent": "default"}


# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────

@app.route("/")
def home():
    design_count = Design.query.count() + 127  # seed offset for display polish
    return render_template("index.html", design_count=design_count)


# ─────────────────────────────────────────
# Authentication Routes
# ─────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration with rate limiting and input sanitization."""
    if session.get("user_id"):
        return redirect(url_for("design"))

    if request.method == "POST":
        username         = sanitize(request.form.get("username", ""), 100)
        email            = sanitize(request.form.get("email", ""), 120).lower()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # ── Validation ──
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Please log in.", "error")
            return render_template("register.html")

        # ── Create user ──
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        flash("Account created! Welcome aboard — please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate user, establish session."""
    if session.get("user_id"):
        return redirect(url_for("design"))

    if request.method == "POST":
        email    = sanitize(request.form.get("email", ""), 120).lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password. Please try again.", "error")
            return render_template("login.html")

        # 2FA check
        if getattr(user, 'is_2fa_enabled', False) and user.totp_secret:
            session["pending_2fa_user_id"] = user.id
            return redirect(url_for("verify_2fa"))

        session.permanent = False
        session["user_id"]  = user.id
        session["username"] = user.username

        flash(f"Welcome back, {user.username}! 🏠", "success")
        return redirect(url_for("design"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Clear session and redirect home."""
    session.clear()
    flash("You've been logged out. Come back soon! 👋", "success")
    return redirect(url_for("home"))


@app.route("/design", methods=["GET", "POST"])
def design():
    """
    AI Design Studio — requires authentication.
    Integrates rule-based + transformer AI recommendations.
    """
    # ── Auth guard ──
    if not session.get("user_id"):
        flash("Please log in to access the Design Studio. ✨", "error")
        return redirect(url_for("login"))

    suggestion = None
    explanation = None
    confidence = None
    agent_thinking = None
    image_filename = None
    image_path_full = None
    recommended_items = []
    color_scheme = []
    placement_tips = []
    ai_source = None
    saved_designs = Design.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Design.created_at.desc()).limit(5).all()

    if request.method == "POST":
        room_type = request.form.get("room_type", "Hall")
        style     = request.form.get("style", "Modern")
        budget    = request.form.get("budget", "Medium")

        # -- Handle image upload with magic-byte validation --
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename, file.stream):
            ext = secure_filename(file.filename).rsplit('.', 1)[1]
            image_filename = f"{uuid.uuid4().hex}.{ext}"
            image_path_full = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            file.save(image_path_full)
        elif file and file.filename:
            flash("Invalid image file. Please upload a real PNG/JPG/WEBP image.", "error")

        # ── AI Engine ──
        ai_result = generate_design_suggestions(
            image_path=image_path_full,
            style_theme=style,
            room_type=room_type,
            budget=budget,
        )

        ai_furniture        = ai_result.get("furniture", [])
        color_scheme        = ai_result.get("color_scheme", [])
        placement_tips      = ai_result.get("placement_tips", [])
        ai_confidence_val   = ai_result.get("confidence", 0.88)
        ai_source           = ai_result.get("source", "rule-based")

        # ── Resolve furniture DB objects ──
        ai_names = [f["name"] for f in ai_furniture]
        recommended_items = Furniture.query.filter(Furniture.name.in_(ai_names)).all()
        if not recommended_items:
            # Fallback: also try legacy RECOMMENDATIONS dict
            key = (room_type, style, budget)
            rec = RECOMMENDATIONS.get(key, {
                "items": ["Mid-Century Coffee Table"],
                "tip": "A great space starts with a statement piece."
            })
            recommended_items = Furniture.query.filter(
                Furniture.name.in_(rec["items"])
            ).all() or Furniture.query.limit(2).all()
            ai_names = [i.name for i in recommended_items]

        suggestion     = "\n".join([f"• {n}" for n in ai_names])
        explanation    = placement_tips[0] if placement_tips else "Build around a focal furniture piece."
        confidence_pct = int(ai_confidence_val * 100)
        confidence     = f"AI Confidence: {confidence_pct}%"
        agent_thinking = random.choice(AGENT_THINKING)

        # ── Save to DB ──
        design_entry = Design(
            user_id=session["user_id"],
            image_path=image_filename or "",
            room_type=room_type,
            style=style,
            budget=budget,
            suggestion=suggestion,
            confidence=float(ai_confidence_val),
        )
        db.session.add(design_entry)
        db.session.commit()

        saved_designs = Design.query.filter_by(
            user_id=session["user_id"]
        ).order_by(Design.created_at.desc()).limit(5).all()

    return render_template("design.html",
                           suggestion=suggestion,
                           explanation=explanation,
                           confidence=confidence,
                           agent_thinking=agent_thinking,
                           image_filename=image_filename,
                           recommended_items=recommended_items,
                           color_scheme=color_scheme,
                           placement_tips=placement_tips,
                           ai_source=ai_source,
                           saved_designs=saved_designs)


@app.route("/ar")
def ar():
    furniture_list = Furniture.query.all()
    return render_template("ar.html", furniture_list=furniture_list)


@app.route("/catalog")
def catalog():
    style_filter    = request.args.get("style", "")
    category_filter = request.args.get("category", "")
    page            = request.args.get("page", 1, type=int)
    per_page        = 12

    query = Furniture.query
    if style_filter:
        query = query.filter_by(style=style_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)

    pagination     = query.paginate(page=page, per_page=per_page, error_out=False)
    furniture_list = pagination.items
    styles         = db.session.query(Furniture.style).distinct().all()
    categories     = db.session.query(Furniture.category).distinct().all()
    return render_template("catalog.html",
                           furniture_list=furniture_list,
                           styles=[s[0] for s in styles],
                           categories=[c[0] for c in categories],
                           selected_style=style_filter,
                           selected_category=category_filter,
                           pagination=pagination)


@app.route("/buddy", methods=["GET"])
def buddy():
    return render_template("buddy.html")


# ─────────────────────────────────────────
# Export & Share Routes
# ─────────────────────────────────────────

@app.route("/export-design/<int:design_id>")
def export_design(design_id):
    """Print-friendly design plan for PDF export via browser."""
    if not session.get("user_id"):
        flash("Please log in to export designs.", "error")
        return redirect(url_for("login"))

    design       = Design.query.get_or_404(design_id)
    ai_names     = [n.strip().lstrip("\u2022 ") for n in (design.suggestion or "").splitlines() if n.strip()]
    furniture_list = Furniture.query.filter(Furniture.name.in_(ai_names)).all()

    from ai_engine import COLOR_PALETTES
    color_scheme = COLOR_PALETTES.get(design.style or "Modern", COLOR_PALETTES["Modern"])

    return render_template(
        "export_design.html",
        design=design,
        furniture_list=furniture_list,
        color_scheme=color_scheme,
        placement_tips=[],
        username=session.get("username", "Guest"),
        now=datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC"),
    )


@app.route("/api/share-design/<int:design_id>")
def api_share_design(design_id):
    """Returns share metadata for a design (Web Share API / social links)."""
    design = Design.query.get_or_404(design_id)
    title  = f"{design.room_type} — {design.style} Style | Gruha Alankara"
    url    = request.host_url + f"export-design/{design_id}"
    text   = f"I just designed my {design.room_type} in {design.style} style with Gruha Alankara AI!"
    return jsonify({
        "title": title,
        "url":   url,
        "text":  text,
        "whatsapp": f"https://wa.me/?text={text}%20{url}",
        "twitter":  f"https://twitter.com/intent/tweet?text={text}&url={url}",
    })

# ─────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────

@app.route("/api/ai-design", methods=["POST"])
def api_ai_design():
    """
    JSON endpoint for AI design generation.
    Accepts: { room_type, style, budget, image_filename (optional) }
    Returns: structured design suggestion JSON.
    """
    data      = request.get_json() or {}
    room_type = data.get("room_type", "Hall")
    style     = data.get("style", "Modern")
    budget    = data.get("budget", "Medium")

    # Resolve optional image path
    img_filename = data.get("image_filename")
    image_path   = None
    if img_filename:
        candidate = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(img_filename))
        if os.path.exists(candidate):
            image_path = candidate

    try:
        result = generate_design_suggestions(
            image_path=image_path,
            style_theme=style,
            room_type=room_type,
            budget=budget,
        )
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    data      = request.get_json()
    room_type = data.get("room_type", "Hall")
    style     = data.get("style", "Modern")
    budget    = data.get("budget", "Medium")
    key = (room_type, style, budget)
    rec = RECOMMENDATIONS.get(key, {"items": ["Mid-Century Coffee Table"], "tip": "Start with a focal piece."})
    confidence = random.randint(82, 97)
    return jsonify({
        "items":          rec["items"],
        "tip":            rec["tip"],
        "confidence":     confidence,
        "agent_thinking": random.choice(AGENT_THINKING),
    })


@app.route("/api/book", methods=["POST"])
def api_book():
    data         = request.get_json()
    furniture_id = data.get("furniture_id")
    customer_name  = data.get("customer_name", "Guest")
    customer_phone = data.get("customer_phone", "")

    furniture = Furniture.query.get(furniture_id)
    if not furniture:
        return jsonify({"success": False, "message": "Furniture not found"}), 404

    booking = Booking(
        furniture_id=furniture_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        status="confirmed",
    )
    db.session.add(booking)
    db.session.commit()

    return jsonify({
        "success":    True,
        "booking_id": booking.id,
        "item":       furniture.name,
        "message":    f"✅ Booking confirmed for {furniture.name}! ID: #{booking.id}",
    })


@app.route("/api/buddy-chat", methods=["POST"])
def api_buddy_chat():
    data     = request.get_json()
    message  = data.get("message", "")
    language = data.get("language", "en")
    session_id = data.get("session_id", str(uuid.uuid4()))

    # Save user message
    user_msg = ChatHistory(session_id=session_id, role="user", message=message, language=language)
    db.session.add(user_msg)

    result = get_buddy_response(message, language)

    # Save buddy message
    buddy_msg = ChatHistory(session_id=session_id, role="buddy", message=result["response"], language=language)
    db.session.add(buddy_msg)
    db.session.commit()

    return jsonify({**result, "session_id": session_id})


# ─────────────────────────────────────────
# Two-Factor Authentication (2FA) Routes
# ─────────────────────────────────────────
@app.route("/setup-2fa")
def setup_2fa():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    if not user.totp_secret:
        user.totp_secret = pyotp.random_base32()
        db.session.commit()
    
    totp = pyotp.TOTP(user.totp_secret)
    qr_uri = totp.provisioning_uri(name=user.email, issuer_name="Gruha Alankara")
    
    img = qrcode.make(qr_uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    
    return render_template("setup_2fa.html", qr_b64=qr_b64, secret=user.totp_secret)

@app.route("/verify-setup-2fa", methods=["POST"])
def verify_setup_2fa():
    if not session.get("user_id"):
        return jsonify({"success": False, "message": "Not logged in"}), 401
    
    code = request.json.get("code")
    user = User.query.get(session["user_id"])
    totp = pyotp.TOTP(user.totp_secret)
    
    if totp.verify(code):
        user.is_2fa_enabled = True
        db.session.commit()
        return jsonify({"success": True, "message": "2FA strictly enabled!"})
    return jsonify({"success": False, "message": "Invalid code. Try again."})

@app.route("/verify-2fa", methods=["GET", "POST"])
def verify_2fa():
    if "pending_2fa_user_id" not in session:
        return redirect(url_for("login"))
        
    if request.method == "POST":
        code = request.form.get("code", "")
        user = User.query.get(session["pending_2fa_user_id"])
        
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code):
            session.permanent = False
            session["user_id"] = user.id
            session["username"] = user.username
            session.pop("pending_2fa_user_id", None)
            flash(f"Welcome back, {user.username}! 🏠", "success")
            return redirect(url_for("design"))
        else:
            flash("Invalid 2FA code. Please try again.", "error")
            
    return render_template("verify_2fa.html")


# ─────────────────────────────────────────
# Collaborative Design (WebSockets)
# ─────────────────────────────────────────
@app.route("/collab/<room_id>")
def collab_room(room_id):
    if not session.get("user_id"):
        flash("Please log in to join a collaborative session.", "error")
        return redirect(url_for("login"))
    return render_template("collab.html", room_id=room_id, username=session.get("username"))

@socketio.on('join')
def on_join(data):
    room = data['room']
    username = data['username']
    join_room(room)
    emit('status', {'msg': f"{username} has entered the room."}, to=room)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    username = data['username']
    leave_room(room)
    emit('status', {'msg': f"{username} has left the room."}, to=room)

@socketio.on('chat_message')
def handle_chat_message(data):
    room = data['room']
    emit('chat_message', {'user': data['username'], 'msg': data['msg']}, to=room)

@socketio.on('design_update')
def handle_design_update(data):
    room = data['room']
    emit('design_update', data, to=room, include_self=False)


# ─────────────────────────────────────────
# DB Init + Seed
# ─────────────────────────────────────────
def seed_furniture():
    if Furniture.query.count() == 0:
        for item in FURNITURE_DATA:
            furniture = Furniture(**item)
            db.session.add(furniture)
        db.session.commit()
        print(f"✅ Seeded {len(FURNITURE_DATA)} furniture items.")


with app.app_context():
    db.create_all()
    seed_furniture()


if __name__ == "__main__":
    app.run(debug=True)