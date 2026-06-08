import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import redirect, url_for, flash, request, render_template
from flask_login import login_user, logout_user, login_required, current_user
from flask_dance.contrib.google import make_google_blueprint, google
from app import db
from app.models import User
from app.auth import auth_bp

google_bp = make_google_blueprint(
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    redirect_to='auth.google_login',
    scope=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
)

auth_bp.register_blueprint(google_bp, url_prefix='/google_auth')

@auth_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('gigs.home'))
    return redirect(url_for('auth.google.login'))

@auth_bp.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if username == 'admin123' and password == '123456':
            admin = User.query.filter_by(email='taskhub.admin@internal.com').first()
            if not admin:
                admin = User(
                    name='Admin',
                    email='taskhub.admin@internal.com',
                    password='',
                    is_verified=True,
                    is_admin=True
                )
                db.session.add(admin)
                db.session.commit()
                admin.is_superadmin = True
                db.session.commit()
            login_user(admin, remember=True)
            flash('Welcome, Admin!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid admin credentials.', 'danger')
    return render_template('auth/admin_login.html')

@auth_bp.route('/google/authorized')
def google_login():
    if not google.authorized:
        flash('Google login failed. Try again.', 'danger')
        return redirect(url_for('gigs.home'))
    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        flash('Failed to fetch Google account info.', 'danger')
        return redirect(url_for('gigs.home'))
    info = resp.json()
    email = info['email']
    name = info.get('name', email.split('@')[0])
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            name=name,
            email=email,
            password='',
            is_verified=True
        )
        db.session.add(user)
        db.session.commit()
        flash(f'Welcome to TaskHub, {name}!', 'success')
    else:
        if not user.is_verified:
            flash('Your account has been banned. Contact support.', 'danger')
            return redirect(url_for('gigs.home'))
        flash(f'Welcome back, {name}!', 'success')
    login_user(user, remember=True)
    return redirect(url_for('gigs.home'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('auth.login'))