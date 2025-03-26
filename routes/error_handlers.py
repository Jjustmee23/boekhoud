from datetime import datetime
from flask import render_template

# Error handlers
def not_found_error(error):
    return render_template('base.html', error='Page not found', now=datetime.now()), 404

def internal_error(error):
    return render_template('base.html', error='An internal error occurred', now=datetime.now()), 500