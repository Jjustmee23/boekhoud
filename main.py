from app import app
from routes_ai import ai_bp  # Import the AI blueprint

# Register the AI blueprint
app.register_blueprint(ai_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
