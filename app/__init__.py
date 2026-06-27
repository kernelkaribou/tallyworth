"""Application factory for Tallyworth."""
from __future__ import annotations

from flask import Flask

from .config import Config
from .extensions import db, migrate


def create_app(config_object: type[Config] | Config = Config) -> Flask:
    """Create and configure a Flask application instance."""
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)

    from .blueprints.main import bp as main_bp

    app.register_blueprint(main_bp)

    return app
