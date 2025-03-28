"""
Admin routes voor het workspace dashboard
"""
import logging
import sys
import os
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from app import app, db

# Voeg root directory toe zodat de imports werken
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from models import User, Customer, Invoice, Workspace