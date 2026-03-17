"""Flask admin dashboard application."""
import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

    from dashboard.routes import main_bp
    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_globals():
        return {"dry_run_mode": os.getenv("SFAO_DRY_RUN", "true").lower() == "true"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5050, debug=True)
