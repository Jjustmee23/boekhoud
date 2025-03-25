from app import app
from routes_document import document_bp  # Import the document blueprint

# Register the document blueprint
app.register_blueprint(document_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
