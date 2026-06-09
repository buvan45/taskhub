import cloudinary
import cloudinary.uploader
from flask import current_app

def configure_cloudinary():
    cloudinary.config(
        cloud_name=current_app.config['CLOUDINARY_CLOUD_NAME'],
        api_key=current_app.config['CLOUDINARY_API_KEY'],
        api_secret=current_app.config['CLOUDINARY_API_SECRET']
    )

def upload_image(file, folder='taskhub'):
    configure_cloudinary()
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type='auto'
    )
    return result['secure_url']