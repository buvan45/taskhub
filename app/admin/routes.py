from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Gig, Order, Review, Category
from app.admin import admin_bp
from datetime import datetime
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('gigs.home'))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_gigs = Gig.query.filter_by(is_active=True).count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.amount)).filter_by(status='completed').scalar() or 0
    disputed_orders = Order.query.filter_by(status='disputed').count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
        total_users=total_users,
        total_gigs=total_gigs,
        total_orders=total_orders,
        total_revenue=total_revenue,
        disputed_orders=disputed_orders,
        recent_orders=recent_orders,
        recent_users=recent_users
    )

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)

@admin_bp.route('/users/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot ban an admin.', 'danger')
        return redirect(url_for('admin.users'))
    user.is_verified = False
    db.session.commit()
    flash(f'{user.name} has been banned.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/unban', methods=['POST'])
@login_required
@admin_required
def unban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = True
    db.session.commit()
    flash(f'{user.name} has been unbanned.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/gigs')
@login_required
@admin_required
def gigs():
    all_gigs = Gig.query.order_by(Gig.created_at.desc()).all()
    return render_template('admin/gigs.html', gigs=all_gigs)

@admin_bp.route('/gigs/<int:gig_id>/remove', methods=['POST'])
@login_required
@admin_required
def remove_gig(gig_id):
    gig = Gig.query.get_or_404(gig_id)
    gig.is_active = False
    db.session.commit()
    flash('Gig removed.', 'success')
    return redirect(url_for('admin.gigs'))

@admin_bp.route('/gigs/<int:gig_id>/feature', methods=['POST'])
@login_required
@admin_required
def feature_gig(gig_id):
    gig = Gig.query.get_or_404(gig_id)
    gig.is_featured = not getattr(gig, 'is_featured', False)
    db.session.commit()
    flash('Gig featured status updated.', 'success')
    return redirect(url_for('admin.gigs'))

@admin_bp.route('/orders')
@login_required
@admin_required
def orders():
    status = request.args.get('status', '')
    query = Order.query
    if status:
        query = query.filter_by(status=status)
    all_orders = query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=all_orders, status=status)

@admin_bp.route('/disputes')
@login_required
@admin_required
def disputes():
    disputed = Order.query.filter_by(status='disputed').order_by(Order.created_at.desc()).all()
    return render_template('admin/disputes.html', orders=disputed)

@admin_bp.route('/disputes/<int:order_id>/release', methods=['POST'])
@login_required
@admin_required
def release_payment(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = 'completed'
    order.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f'Order #{order_id} payment released to seller.', 'success')
    return redirect(url_for('admin.disputes'))

@admin_bp.route('/disputes/<int:order_id>/refund', methods=['POST'])
@login_required
@admin_required
def refund_payment(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = 'cancelled'
    order.cancelled_at = datetime.utcnow()
    db.session.commit()
    flash(f'Order #{order_id} refunded to buyer.', 'success')
    return redirect(url_for('admin.disputes'))

@admin_bp.route('/categories')
@login_required
@admin_required
def categories():
    all_categories = Category.query.all()
    return render_template('admin/categories.html', categories=all_categories)

@admin_bp.route('/categories/add', methods=['POST'])
@login_required
@admin_required
def add_category():
    name = request.form.get('name', '').strip()
    icon = request.form.get('icon', 'briefcase').strip()
    if not name:
        flash('Category name required.', 'danger')
        return redirect(url_for('admin.categories'))
    category = Category(name=name, icon=icon)
    db.session.add(category)
    db.session.commit()
    flash(f'Category "{name}" added.', 'success')
    return redirect(url_for('admin.categories'))

@admin_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin.categories'))

@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    from app.models import Report
    all_reports = Report.query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=all_reports)

@admin_bp.route('/reports/<int:report_id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_report(report_id):
    from app.models import Report
    report = Report.query.get_or_404(report_id)
    action = request.form.get('action')
    report.status = 'resolved'
    if action == 'ban':
        report.reported.is_verified = False
        flash(f'{report.reported.name} has been banned.', 'success')
    elif action == 'dismiss':
        flash(f'Report dismissed.', 'info')
    db.session.commit()
    return redirect(url_for('admin.reports'))