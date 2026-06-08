from flask import Blueprint
gigs_bp = Blueprint('gigs', __name__)
from app.gigs import routes