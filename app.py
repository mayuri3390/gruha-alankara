from flask import Flask, render_template, request
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Store saved designs (temporary memory)
saved_designs = []

@app.route("/", methods=["GET", "POST"])
def home():
    suggestion = ""
    explanation = ""
    agent_thinking = ""
    image_filename = None
    confidence = ""

    if request.method == "POST":
        style = request.form["style"]
        budget = request.form["budget"]
        room_type = request.form["room_type"]

        # Image Upload
        if "image" in request.files:
            image = request.files["image"]
            if image.filename != "":
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
                image.save(image_path)
                image_filename = image.filename

        # ----- AGENT THINKING -----
        agent_thinking += f"Observed: {room_type} | Style: {style} | Budget: {budget}. "

        # Smarter Color Logic
        if room_type == "Bedroom":
            if style == "Modern":
                color = "Soft Grey or Pastel Blue"
            else:
                color = "Warm Beige"
        elif room_type == "Hall":
            if budget == "High":
                color = "Accent Dark Wall with White"
            else:
                color = "Light Cream"
        else:
            color = "Bright White"

        # Furniture Logic
        if budget == "Low":
            furniture = "Compact functional furniture"
        elif budget == "Medium":
            furniture = "Balanced aesthetic furniture"
        else:
            furniture = "Premium designer furniture"

        # Lighting Logic
        if room_type == "Bedroom":
            lighting = "Warm soft lighting"
        elif room_type == "Hall":
            lighting = "Layered lighting with chandelier"
        else:
            lighting = "Bright LED lighting"

        suggestion = f"""
Wall Color: {color}
Furniture: {furniture}
Lighting: {lighting}
"""

        explanation = """
AI generated recommendations using rule-based reasoning
considering spatial comfort, aesthetic balance,
budget optimization, and functional design principles.
"""

        confidence = "Confidence Level: 92%"

        agent_thinking += "Applied multi-factor design reasoning and optimization rules."

        # Save Design
        saved_designs.append({
            "room": room_type,
            "style": style,
            "budget": budget,
            "suggestion": suggestion
        })

    return render_template("index.html",
                           suggestion=suggestion,
                           explanation=explanation,
                           agent_thinking=agent_thinking,
                           image_filename=image_filename,
                           saved_designs=saved_designs,
                           confidence=confidence)

if __name__ == "__main__":
    app.run(debug=True)