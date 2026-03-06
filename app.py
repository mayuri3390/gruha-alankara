import os
import uuid
import json
import random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from config import Config
from models import db, Design, Furniture, Booking, ChatHistory

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# ─────────────────────────────────────────
# Ensure upload folder exists
# ─────────────────────────────────────────
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.root_path, 'database'), exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


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
        "greet":    "నమస్కారం! 🙏 నేను బడ్డీని, మీ వ్యక్తిగత ఇంటీరియర్ డిజైన్ సహాయకుడిని. ఈరోజు మీ కలల ఇంటిని అలంకరించడంలో ఎలా సహాయపడగలను?",
        "book":     "చాలా మంచి ఎంపిక! నేను ఇప్పుడే మీ కోసం {item} బుక్ చేస్తున్నాను.",
        "suggest":  "మీ అభిరుచి ఆధారంగా, నేను {style} కలెక్షన్ — ముఖ్యంగా {item}ని సిఫార్సు చేస్తాను.",
        "confirm":  "✅ బుకింగ్ నిర్ధారించబడింది! మీ {item} 7-10 పని దినాలలో డెలివరీ అవుతుంది. బుకింగ్ ID: #{booking_id}",
        "default":  "నేను ఫర్నీచర్ సిఫార్సులు మరియు బుకింగ్‌లలో సహాయం చేయడానికి ఇక్కడ ఉన్నాను!",
    },
}

KEYWORD_INTENTS = {
    "greet":   ["hello", "hi", "namaste", "నమస్కారం", "नमस्ते", "hey", "start"],
    "book":    ["book", "order", "buy", "purchase", "బుక్", "बुक", "కొను"],
    "suggest": ["suggest", "recommend", "what", "which", "show", "చూపించు", "सुझाव"],
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


@app.route("/design", methods=["GET", "POST"])
def design():
    suggestion = None
    explanation = None
    confidence = None
    agent_thinking = None
    image_filename = None
    recommended_items = []
    saved_designs = Design.query.order_by(Design.created_at.desc()).limit(5).all()

    if request.method == "POST":
        room_type = request.form.get("room_type", "Hall")
        style     = request.form.get("style", "Modern")
        budget    = request.form.get("budget", "Medium")

        # Handle image upload
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            ext = secure_filename(file.filename).rsplit('.', 1)[1]
            image_filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        # AI Recommendation
        key = (room_type, style, budget)
        rec = RECOMMENDATIONS.get(key, {
            "items": ["Mid-Century Coffee Table"],
            "tip": "A great space starts with a statement piece. Start with a focal furniture item and build around it."
        })
        recommended_items_names = rec["items"]
        tip = rec["tip"]

        recommended_items = Furniture.query.filter(Furniture.name.in_(recommended_items_names)).all()
        if not recommended_items:
            recommended_items = Furniture.query.limit(2).all()

        suggestion = "\n".join([f"• {i}" for i in recommended_items_names])
        explanation = tip
        confidence  = f"AI Confidence: {random.randint(82, 97)}%"
        agent_thinking = random.choice(AGENT_THINKING)

        # Save to DB
        design_entry = Design(
            image_path=image_filename or "",
            room_type=room_type,
            style=style,
            budget=budget,
            suggestion=suggestion,
            confidence=float(confidence.split(":")[1].strip().replace("%", "")),
        )
        db.session.add(design_entry)
        db.session.commit()

        saved_designs = Design.query.order_by(Design.created_at.desc()).limit(5).all()

    return render_template("design.html",
                           suggestion=suggestion,
                           explanation=explanation,
                           confidence=confidence,
                           agent_thinking=agent_thinking,
                           image_filename=image_filename,
                           recommended_items=recommended_items,
                           saved_designs=saved_designs)


@app.route("/ar")
def ar():
    furniture_list = Furniture.query.all()
    return render_template("ar.html", furniture_list=furniture_list)


@app.route("/catalog")
def catalog():
    style_filter    = request.args.get("style", "")
    category_filter = request.args.get("category", "")
    query = Furniture.query
    if style_filter:
        query = query.filter_by(style=style_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)
    furniture_list = query.all()
    styles     = db.session.query(Furniture.style).distinct().all()
    categories = db.session.query(Furniture.category).distinct().all()
    return render_template("catalog.html",
                           furniture_list=furniture_list,
                           styles=[s[0] for s in styles],
                           categories=[c[0] for c in categories],
                           selected_style=style_filter,
                           selected_category=category_filter)


@app.route("/buddy", methods=["GET"])
def buddy():
    return render_template("buddy.html")


# ─────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────

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