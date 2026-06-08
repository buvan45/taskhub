from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

scheduler = BackgroundScheduler()

def start_scheduler(app):
    from app import db
    from app.models import Order

    def check_orders():
        with app.app_context():
            now = datetime.utcnow()

            # Auto cancel — seller didn't start in time
            pending_orders = Order.query.filter_by(status='paid').all()
            for order in pending_orders:
                if order.auto_cancel_at and now > order.auto_cancel_at:
                    order.status = 'cancelled'
                    order.cancelled_at = now
                    print(f'[Scheduler] Order #{order.id} auto cancelled — seller did not start in time')

            # Auto release — buyer didn't approve in time
            delivered_orders = Order.query.filter_by(status='delivered').all()
            for order in delivered_orders:
                if order.auto_release_at and now > order.auto_release_at:
                    order.status = 'completed'
                    order.completed_at = now
                    print(f'[Scheduler] Order #{order.id} auto completed — payment released to seller')

            db.session.commit()

    scheduler.add_job(check_orders, 'interval', minutes=30)
    scheduler.start()
    print('[Scheduler] Started — checking orders every 30 minutes')