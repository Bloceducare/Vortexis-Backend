import cloudinary
import cloudinary.uploader
from django.conf import settings
from rest_framework.exceptions import ValidationError


def upload_image_to_cloudinary(image_file, folder=None):
    """
    Upload an image file to Cloudinary and return the URL.
    
    Args:
        image_file: The image file from request.FILES
        folder: Optional folder name to organize uploads in Cloudinary
        
    Returns:
        str: The Cloudinary URL of the uploaded image
        
    Raises:
        ValidationError: If upload fails or file is invalid
    """
    try:
        # Configure cloudinary (this will use settings.CLOUDINARY_STORAGE)
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
            api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
            api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
        )
        
        # Upload options
        upload_options = {
            'resource_type': 'auto',  # Automatically detect file type
            'quality': 'auto',  # Optimize quality
            'fetch_format': 'auto',  # Optimize format
        }
        
        # Add folder if specified
        if folder:
            upload_options['folder'] = folder
            
        # Upload the image
        result = cloudinary.uploader.upload(image_file, **upload_options)
        
        # Return the secure URL
        return result.get('secure_url')
        
    except Exception as e:
        raise ValidationError(f"Failed to upload image to Cloudinary: {str(e)}")


def delete_image_from_cloudinary(image_url):
    """
    Delete an image from Cloudinary using its URL.
    
    Args:
        image_url: The Cloudinary URL of the image to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Configure cloudinary
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
            api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
            api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
        )
        
        # Extract public_id from URL
        # Cloudinary URLs format: https://res.cloudinary.com/{cloud_name}/image/upload/{transformations}/{public_id}.{extension}
        if image_url and 'cloudinary.com' in image_url:
            # Split URL and extract public_id
            url_parts = image_url.split('/')
            if len(url_parts) >= 7:
                # Get the part after 'upload/' and remove file extension
                public_id_with_ext = '/'.join(url_parts[7:])
                public_id = public_id_with_ext.rsplit('.', 1)[0]  # Remove extension
                
                # Delete the image
                result = cloudinary.uploader.destroy(public_id)
                return result.get('result') == 'ok'
                
        return False
        
    except Exception:
        return False