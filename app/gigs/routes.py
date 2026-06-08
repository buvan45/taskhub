from flask import render_template, redirect, url_for, flash, request,current_app,jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Gig, Category, User
from app.gigs import gigs_bp

@gigs_bp.route('/')
def home():
    category_id = request.args.get('category', type=int)
    search = request.args.get('q', '').strip()
    query = Gig.query.filter_by(is_active=True)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if search:
        query = query.filter(Gig.title.ilike(f'%{search}%') | Gig.description.ilike(f'%{search}%'))
    gigs = query.order_by(Gig.created_at.desc()).all()
    categories = Category.query.all()
    return render_template('gigs/home.html', gigs=gigs, categories=categories, search=search)

@gigs_bp.route('/gigs/new', methods=['GET', 'POST'])
@login_required
def new_gig():
    import os
    from werkzeug.utils import secure_filename
    from datetime import datetime
    categories = Category.query.all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', 0)
        delivery_days = request.form.get('delivery_days', 3)
        category_id = request.form.get('category_id')
        if not title or not description or not price:
            flash('Please fill all required fields.', 'danger')
            return render_template('gigs/new_gig.html', categories=categories)
        gig = Gig(
            title=title,
            description=description,
            price=float(price),
            delivery_days=int(delivery_days),
            category_id=int(category_id) if category_id else None,
            seller_id=current_user.id
        )
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                unique_name = f"gig_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'gigs')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, unique_name))
                gig.image = f"/static/uploads/gigs/{unique_name}"
        db.session.add(gig)
        db.session.commit()
        flash('Gig created successfully!', 'success')
        return redirect(url_for('gigs.gig_detail', gig_id=gig.id))
    return render_template('gigs/new_gig.html', categories=categories)

@gigs_bp.route('/gigs/<int:gig_id>')
def gig_detail(gig_id):
    gig = Gig.query.get_or_404(gig_id)
    return render_template('gigs/gig_detail.html', gig=gig)

@gigs_bp.route('/gigs/<int:gig_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_gig(gig_id):
    import os
    from werkzeug.utils import secure_filename
    from datetime import datetime
    gig = Gig.query.get_or_404(gig_id)
    if gig.seller_id != current_user.id:
        flash('You can only edit your own gigs.', 'danger')
        return redirect(url_for('gigs.gig_detail', gig_id=gig_id))
    categories = Category.query.all()
    if request.method == 'POST':
        gig.title = request.form.get('title', '').strip()
        gig.description = request.form.get('description', '').strip()
        gig.price = float(request.form.get('price', gig.price))
        gig.delivery_days = int(request.form.get('delivery_days', gig.delivery_days))
        category_id = request.form.get('category_id')
        gig.category_id = int(category_id) if category_id else None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                unique_name = f"gig_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'gigs')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, unique_name))
                gig.image = f"/static/uploads/gigs/{unique_name}"
        db.session.commit()
        flash('Gig updated successfully!', 'success')
        return redirect(url_for('gigs.gig_detail', gig_id=gig_id))
    return render_template('gigs/new_gig.html', categories=categories, gig=gig)

@gigs_bp.route('/gigs/<int:gig_id>/delete', methods=['POST'])
@login_required
def delete_gig(gig_id):
    gig = Gig.query.get_or_404(gig_id)
    if gig.seller_id != current_user.id:
        flash('You can only delete your own gigs.', 'danger')
        return redirect(url_for('gigs.gig_detail', gig_id=gig_id))
    gig.is_active = False
    db.session.commit()
    flash('Gig deleted.', 'info')
    return redirect(url_for('gigs.profile', user_id=current_user.id))

@gigs_bp.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get_or_404(user_id)
    gigs = Gig.query.filter_by(seller_id=user_id, is_active=True).all()
    return render_template('gigs/profile.html', profile_user=user, gigs=gigs)

@gigs_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    import os
    from werkzeug.utils import secure_filename
    from datetime import datetime
    if request.method == 'POST':
        current_user.name = request.form.get('name', '').strip()
        current_user.bio = request.form.get('bio', '').strip()
        current_user.skills = request.form.get('skills', '').strip()
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                unique_name = f"avatar_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, unique_name))
                current_user.avatar = f"/static/uploads/avatars/{unique_name}"
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('gigs.profile', user_id=current_user.id))
    return render_template('gigs/edit_profile.html')

@gigs_bp.route('/my-gigs')
@login_required
def my_gigs():
    gigs = Gig.query.filter_by(seller_id=current_user.id, is_active=True).order_by(Gig.created_at.desc()).all()
    return render_template('gigs/my_gigs.html', gigs=gigs)

@gigs_bp.route('/gigs/generate', methods=['POST'])
@login_required
def generate_gig():
    from groq import Groq
    import json
    keywords = request.form.get('keywords', '').strip()
    if not keywords:
        return jsonify({'error': 'Please enter some keywords'}), 400
    prompt = f"""You are a professional freelance gig writer for TaskHub, an Indian freelance marketplace.

A seller wants to create a gig based on these keywords: {keywords}

Generate a professional gig listing. Respond ONLY with a JSON object, no markdown, no explanation:
{{
  "title": "I will [specific service] for [target customer]",
  "description": "5-6 sentence professional description of the service, what's included, and why to hire this seller",
  "price": <suggested price in INR as integer, between 500 and 10000>,
  "delivery_days": <realistic delivery days as integer between 1 and 14>
}}"""
    try:
        client = Groq(api_key=current_app.config['GROQ_API_KEY'])
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=500
        )
        text = response.choices[0].message.content.strip()
        # Strip markdown if present
        text = text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@gigs_bp.route('/report/<int:user_id>', methods=['GET', 'POST'])
@login_required
def report_user(user_id):
    from app.models import Report
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot report yourself.', 'danger')
        return redirect(url_for('gigs.profile', user_id=user_id))
    if request.method == 'POST':
        reason = request.form.get('reason', '').strip()
        details = request.form.get('details', '').strip()
        if not reason:
            flash('Please select a reason.', 'danger')
            return render_template('gigs/report_user.html', user=user)
        existing = Report.query.filter_by(
            reporter_id=current_user.id,
            reported_id=user_id,
            status='pending'
        ).first()
        if existing:
            flash('You have already reported this user.', 'warning')
            return redirect(url_for('gigs.profile', user_id=user_id))
        report = Report(
            reporter_id=current_user.id,
            reported_id=user_id,
            reason=reason,
            details=details
        )
        db.session.add(report)
        db.session.commit()
        flash('Report submitted. Our team will review it shortly.', 'success')
        return redirect(url_for('gigs.profile', user_id=user_id))
    return render_template('gigs/report_user.html', user=user)