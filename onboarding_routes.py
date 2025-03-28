"""
Onboarding routes voor gebruikerstutorials
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

@onboarding_bp.route('/complete-tutorial', methods=['POST'])
@login_required
def complete_tutorial():
    """
    Markeer een gebruiker als niet meer nieuw, na het voltooien van de tutorial.
    """
    try:
        if current_user.is_new_user:
            current_user.is_new_user = False
            db.session.commit()
        
        return jsonify({"success": True, "message": "Tutorial status bijgewerkt"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
        
@onboarding_bp.route('/status', methods=['GET'])
@login_required
def get_tutorial_status():
    """
    Haal de tutorial status op voor de huidige gebruiker
    """
    try:
        return jsonify({
            "is_new_user": current_user.is_new_user,
            "user_role": "superadmin" if current_user.is_super_admin else "admin" if current_user.is_admin else "user"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@onboarding_bp.route('/reset', methods=['POST'])
@login_required
def reset_tutorial_status():
    """
    Reset de tutorial status (alleen voor testdoeleinden)
    """
    try:
        current_user.is_new_user = True
        db.session.commit()
        
        return jsonify({"success": True, "message": "Tutorial status gereset"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500