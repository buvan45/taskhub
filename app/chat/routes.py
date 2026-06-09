import os
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from werkzeug.utils import secure_filename
from app import db, socketio
from app.models import Message, Order
from app.chat import chat_bp
from datetime import datetime

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_image(filename):
    return filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@chat_bp.route('/<int:order_id>')
@login_required
def chat(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id not in [order.buyer_id, order.seller_id]:
        flash('Access denied.', 'danger')
        return redirect(url_for('gigs.home'))
    messages = Message.query.filter_by(order_id=order_id).order_by(Message.created_at.asc()).all()
    return render_template('chat/chat.html', order=order, messages=messages)

@chat_bp.route('/gig/<int:gig_id>/user/<int:other_user_id>')
@login_required
def gig_chat(gig_id, other_user_id):
    from app.models import Gig, User
    gig = Gig.query.get_or_404(gig_id)
    other_user = User.query.get_or_404(other_user_id)
    if current_user.id not in [gig.seller_id, other_user_id]:
        flash('Access denied.', 'danger')
        return redirect(url_for('gigs.home'))
    messages = Message.query.filter(
        Message.gig_id == gig_id,
        db.or_(
            Message.sender_id == current_user.id,
            Message.sender_id == other_user_id
        )
    ).order_by(Message.created_at.asc()).all()
    room = f"gig_{gig_id}_user_{min(current_user.id, other_user_id)}_{max(current_user.id, other_user_id)}"
    return render_template('chat/gig_chat.html', gig=gig, messages=messages, room=room, other_user=other_user)

@chat_bp.route('/inbox')
@login_required
def inbox():
    from app.models import Gig
    sent = Message.query.filter(
        Message.gig_id != None,
        Message.sender_id == current_user.id
    ).all()
    received = Message.query.filter(
        Message.gig_id != None,
        Message.sender_id != current_user.id
    ).join(Gig, Message.gig_id == Gig.id).filter(
        db.or_(
            Gig.seller_id == current_user.id,
            Message.sender_id == current_user.id
        )
    ).all()
    conversations = {}
    for msg in sent + received:
        if not msg.gig_id:
            continue
        gig = Gig.query.get(msg.gig_id)
        if not gig:
            continue
        other_id = gig.seller_id if current_user.id != gig.seller_id else msg.sender_id
        key = f"{msg.gig_id}_{min(current_user.id, other_id)}_{max(current_user.id, other_id)}"
        if key not in conversations:
            from app.models import User
            other_user = User.query.get(other_id)
            conversations[key] = {
                'gig': gig,
                'other_user': other_user,
                'last_message': msg,
                'room': f"gig_{msg.gig_id}_user_{min(current_user.id, other_id)}_{max(current_user.id, other_id)}"
            }
        else:
            if msg.created_at > conversations[key]['last_message'].created_at:
                conversations[key]['last_message'] = msg
    convos = sorted(conversations.values(), key=lambda x: x['last_message'].created_at, reverse=True)
    return render_template('chat/inbox.html', conversations=convos)

@chat_bp.route('/gig/<int:gig_id>/user/<int:other_user_id>/upload', methods=['POST'])
@login_required
def gig_upload_file(gig_id, other_user_id):
    from app.models import Gig
    from app.utils import upload_image
    gig = Gig.query.get_or_404(gig_id)
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('chat.gig_chat', gig_id=gig_id, other_user_id=other_user_id))
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        flash('Invalid file.', 'danger')
        return redirect(url_for('chat.gig_chat', gig_id=gig_id, other_user_id=other_user_id))
    filename = secure_filename(file.filename)
    file_type = 'image' if is_image(filename) else 'document'
    file_url = upload_image(file, folder='taskhub/chat')
    room = f"gig_{gig_id}_user_{min(current_user.id, other_user_id)}_{max(current_user.id, other_user_id)}"
    message = Message(
        gig_id=gig_id,
        sender_id=current_user.id,
        content='',
        file_url=file_url,
        file_type=file_type,
        file_name=filename
    )
    db.session.add(message)
    db.session.commit()
    socketio.emit('receive_message', {
        'sender': current_user.name,
        'sender_id': current_user.id,
        'content': '',
        'file_url': file_url,
        'file_type': file_type,
        'file_name': filename,
        'time': datetime.utcnow().strftime('%I:%M %p')
    }, room=room)
    return redirect(url_for('chat.gig_chat', gig_id=gig_id, other_user_id=other_user_id))

@chat_bp.route('/<int:order_id>/upload', methods=['POST'])
@login_required
def upload_file(order_id):
    from app.utils import upload_image
    order = Order.query.get_or_404(order_id)
    if current_user.id not in [order.buyer_id, order.seller_id]:
        return {'error': 'Access denied'}, 403
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('chat.chat', order_id=order_id))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('chat.chat', order_id=order_id))
    if not allowed_file(file.filename):
        flash('File type not allowed.', 'danger')
        return redirect(url_for('chat.chat', order_id=order_id))
    filename = secure_filename(file.filename)
    file_type = 'image' if is_image(filename) else 'document'
    file_url = upload_image(file, folder='taskhub/chat')
    message = Message(
        order_id=order_id,
        sender_id=current_user.id,
        content='',
        file_url=file_url,
        file_type=file_type,
        file_name=filename
    )
    db.session.add(message)
    db.session.commit()
    socketio.emit('receive_message', {
        'sender': current_user.name,
        'sender_id': current_user.id,
        'content': '',
        'file_url': file_url,
        'file_type': file_type,
        'file_name': filename,
        'time': datetime.utcnow().strftime('%I:%M %p')
    }, room=str(order_id))
    return redirect(url_for('chat.chat', order_id=order_id))

@socketio.on('join')
def on_join(data):
    room = str(data['order_id'])
    join_room(room)

@socketio.on('leave')
def on_leave(data):
    room = str(data['order_id'])
    leave_room(room)

@socketio.on('send_message')
def handle_message(data):
    order_id = data.get('order_id')
    content = data.get('content', '').strip()
    if not content or not order_id:
        return
    order = Order.query.get(order_id)
    if not order:
        return
    if current_user.id not in [order.buyer_id, order.seller_id]:
        return
    message = Message(
        order_id=order_id,
        sender_id=current_user.id,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    emit('receive_message', {
        'sender': current_user.name,
        'sender_id': current_user.id,
        'content': content,
        'file_url': None,
        'file_type': None,
        'file_name': None,
        'time': datetime.utcnow().strftime('%I:%M %p')
    }, room=str(order_id))

@socketio.on('send_gig_message')
def handle_gig_message(data):
    from app.models import Gig
    gig_id = data.get('gig_id')
    content = data.get('content', '').strip()
    room = data.get('room')
    other_user_id = data.get('other_user_id')
    if not content or not gig_id:
        return
    gig = Gig.query.get(gig_id)
    if not gig:
        return
    message = Message(
        gig_id=gig_id,
        sender_id=current_user.id,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    emit('receive_message', {
        'sender': current_user.name,
        'sender_id': current_user.id,
        'content': content,
        'file_url': None,
        'file_type': None,
        'file_name': None,
        'time': datetime.utcnow().strftime('%I:%M %p')
    }, room=room)