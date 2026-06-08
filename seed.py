from app import create_app, db
from app.models import Category

app = create_app()

with app.app_context():
    categories = [
        Category(name='Design', icon='palette'),
        Category(name='Development', icon='code-slash'),
        Category(name='Writing', icon='pencil'),
        Category(name='Video & Animation', icon='camera-video'),
        Category(name='Music & Audio', icon='music-note'),
        Category(name='Marketing', icon='megaphone'),
        Category(name='Data & Analytics', icon='bar-chart'),
        Category(name='Tutoring', icon='book'),
    ]
    db.session.add_all(categories)
    db.session.commit()
    print("Categories seeded successfully!")