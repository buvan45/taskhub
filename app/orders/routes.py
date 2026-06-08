from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Order, Gig, Review, User
from app.orders import orders_bp
from datetime import datetime, timedelta
import razorpay

def get_razorpay_client():
    return razorpay.Client(
        auth=(current_app.config['RAZORPAY_KEY_ID'],
              current_app.config['RAZORPAY_KEY_SECRET'])
    )

@orders_bp.route('/place/<int:gig_id>', methods=['POST'])
@login_required
def place_order(gig_id):
    gig = Gig.query.get_or_404(gig_id)
    if gig.seller_id == current_user.id:
        flash('You cannot order your own gig.', 'danger')
        return redirect(url_for('gigs.gig_detail', gig_id=gig_id))
    client = get_razorpay_client()
    amount_paise = int(gig.price * 100)
    razorpay_order = client.order.create({
        'amount': amount_paise,
        'currency': 'INR',
        'payment_capture': 1
    })
    order = Order(
        gig_id=gig.id,
        buyer_id=current_user.id,
        seller_id=gig.seller_id,
        amount=gig.price,
        status='pending',
        razorpay_order_id=razorpay_order['id']
    )
    db.session.add(order)
    db.session.commit()
    return render_template('orders/payment.html',
        gig=gig,
        order=order,
        razorpay_order_id=razorpay_order['id'],
        razorpay_key_id=current_app.config['RAZORPAY_KEY_ID'],
        amount=amount_paise,
        user_name=current_user.name,
        user_email=current_user.email
    )

@orders_bp.route('/payment/simulate/<int:order_id>', methods=['POST'])
@login_required
def simulate_payment(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.buyer_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('gigs.home'))
    if order.status != 'pending':
        flash('Order already paid.', 'warning')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    order.status = 'paid'
    order.razorpay_payment_id = 'simulated_test_payment'
    order.auto_cancel_at = datetime.utcnow() + timedelta(days=order.gig.delivery_days)
    db.session.commit()
    flash(f'Payment successful! Seller must start within {order.gig.delivery_days} day(s) or order will auto cancel.', 'success')
    return redirect(url_for('orders.order_detail', order_id=order_id))

@orders_bp.route('/payment/verify', methods=['POST'])
@login_required
def verify_payment():
    client = get_razorpay_client()
    data = request.form
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
        order = Order.query.filter_by(razorpay_order_id=data['razorpay_order_id']).first_or_404()
        order.status = 'paid'
        order.razorpay_payment_id = data['razorpay_payment_id']
        order.auto_cancel_at = datetime.utcnow() + timedelta(days=order.gig.delivery_days)
        db.session.commit()
        flash('Payment successful! The seller has been notified.', 'success')
        return redirect(url_for('orders.order_detail', order_id=order.id))
    except Exception:
        flash('Payment verification failed. Contact support.', 'danger')
        return redirect(url_for('gigs.home'))

@orders_bp.route('/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id not in [order.buyer_id, order.seller_id]:
        flash('Access denied.', 'danger')
        return redirect(url_for('gigs.home'))
    review = Review.query.filter_by(order_id=order_id, reviewer_id=current_user.id).first()
    return render_template('orders/order_detail.html', order=order, review=review)

@orders_bp.route('/<int:order_id>/start', methods=['POST'])
@login_required
def start_order(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.seller_id:
        flash('Only the seller can start the order.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    if order.status != 'paid':
        flash('Order is not in a valid state to start.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    order.status = 'in_progress'
    order.auto_cancel_at = None
    db.session.commit()
    flash('Order started! Get to work.', 'success')
    return redirect(url_for('orders.order_detail', order_id=order_id))

@orders_bp.route('/<int:order_id>/deliver', methods=['POST'])
@login_required
def deliver_order(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.seller_id:
        flash('Only the seller can deliver the order.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    if order.status != 'in_progress':
        flash('Order must be in progress to deliver.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    note = request.form.get('delivery_note', '').strip()
    order.status = 'delivered'
    order.delivery_note = note
    order.delivered_at = datetime.utcnow()
    order.auto_release_at = datetime.utcnow() + timedelta(days=order.gig.delivery_days)
    db.session.commit()
    flash('Work delivered! Waiting for buyer approval.', 'success')
    return redirect(url_for('orders.order_detail', order_id=order_id))

@orders_bp.route('/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.buyer_id:
        flash('Only the buyer can complete the order.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    if order.status != 'delivered':
        flash('Order must be delivered before completing.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    order.status = 'completed'
    order.completed_at = datetime.utcnow()
    order.auto_release_at = None
    db.session.commit()
    flash('Order completed! Payment released to seller.', 'success')
    return redirect(url_for('orders.order_detail', order_id=order_id))

@orders_bp.route('/<int:order_id>/dispute', methods=['POST'])
@login_required
def dispute_order(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.buyer_id:
        flash('Only the buyer can raise a dispute.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    if order.status != 'delivered':
        flash('You can only dispute a delivered order.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    order.status = 'disputed'
    order.auto_release_at = None
    db.session.commit()
    flash('Dispute raised. Our team will review shortly.', 'warning')
    return redirect(url_for('orders.order_detail', order_id=order_id))

@orders_bp.route('/<int:order_id>/review', methods=['POST'])
@login_required
def submit_review(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.buyer_id or order.status != 'completed':
        flash('You can only review a completed order.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    existing = Review.query.filter_by(order_id=order_id, reviewer_id=current_user.id).first()
    if existing:
        flash('You have already reviewed this order.', 'warning')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    rating = int(request.form.get('rating', 5))
    comment = request.form.get('comment', '').strip()
    review = Review(
        order_id=order_id,
        reviewer_id=current_user.id,
        seller_id=order.seller_id,
        rating=rating,
        comment=comment
    )
    db.session.add(review)
    seller = User.query.get(order.seller_id)
    total = seller.total_reviews + 1
    seller.rating = ((seller.rating * seller.total_reviews) + rating) / total
    seller.total_reviews = total
    db.session.commit()
    flash('Review submitted!', 'success')
    return redirect(url_for('orders.order_detail', order_id=order_id))

@orders_bp.route('/dashboard')
@login_required
def dashboard():
    buying = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    selling = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.desc()).all()
    total_earned = sum(o.amount for o in selling if o.status == 'completed')
    total_spent = sum(o.amount for o in buying if o.status == 'completed')
    return render_template('orders/dashboard.html',
        buying=buying, selling=selling,
        total_earned=total_earned, total_spent=total_spent)

@orders_bp.route('/<int:order_id>/ai-verdict', methods=['POST'])
@login_required
def ai_verdict(order_id):
    from groq import Groq
    order = Order.query.get_or_404(order_id)
    if current_user.id not in [order.buyer_id, order.seller_id]:
        flash('Access denied.', 'danger')
        return redirect(url_for('gigs.home'))
    if order.status != 'disputed':
        flash('AI verdict is only available for disputed orders.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))

    chat_history = '\n'.join([
        f"{msg.sender.name} ({'Buyer' if msg.sender_id == order.buyer_id else 'Seller'}): {msg.content}"
        for msg in order.messages
    ])

    prompt = f"""You are a fair and impartial freelance dispute resolver for TaskHub, a freelance marketplace.

Here are the order details:
- Gig: {order.gig.title}
- Price: ₹{order.amount}
- Delivery Days: {order.gig.delivery_days}
- Buyer: {order.buyer.name}
- Seller: {order.seller.name}

Delivery note from seller:
{order.delivery_note or 'No delivery note provided.'}

Chat history between buyer and seller:
{chat_history or 'No messages exchanged.'}

Based on the above information, provide a fair verdict. Your response must include:
1. VERDICT: (one of: REFUND BUYER / RELEASE TO SELLER / PARTIAL REFUND)
2. REASON: (2-3 sentences explaining why)
3. RECOMMENDATION: (one actionable sentence for both parties)

Be concise, fair, and professional."""

    try:
        client = Groq(api_key=current_app.config['GROQ_API_KEY'])
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=500
        )
        verdict_text = response.choices[0].message.content
        order.ai_verdict = verdict_text
        db.session.commit()
        flash('AI verdict generated successfully.', 'success')
    except Exception as e:
        flash(f'AI verdict failed: {str(e)}', 'danger')

    return redirect(url_for('orders.order_detail', order_id=order_id))

@orders_bp.route('/analytics')
@login_required
def analytics():
    from datetime import timedelta
    from collections import defaultdict

    selling = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.asc()).all()

    # Earnings by day
    earnings_by_day = defaultdict(float)
    for order in selling:
        if order.status == 'completed':
            day = order.created_at.strftime('%d %b')
            earnings_by_day[day] += order.amount

    # Order status counts
    status_counts = defaultdict(int)
    for order in selling:
        status_counts[order.status] += 1

    # Stats
    total_earned = sum(o.amount for o in selling if o.status == 'completed')
    total_orders = len(selling)
    completed = status_counts['completed']
    disputed = status_counts['disputed']
    completion_rate = round((completed / total_orders * 100) if total_orders > 0 else 0, 1)

    # Top gigs by orders
    gig_orders = defaultdict(int)
    gig_earnings = defaultdict(float)
    for order in selling:
        gig_orders[order.gig.title] += 1
        if order.status == 'completed':
            gig_earnings[order.gig.title] += order.amount

    top_gigs = sorted(gig_orders.items(), key=lambda x: x[1], reverse=True)[:5]

    return render_template('orders/analytics.html',
        earnings_by_day=dict(earnings_by_day),
        status_counts=dict(status_counts),
        total_earned=total_earned,
        total_orders=total_orders,
        completed=completed,
        disputed=disputed,
        completion_rate=completion_rate,
        top_gigs=top_gigs,
        gig_earnings=dict(gig_earnings),
        selling=selling
    )