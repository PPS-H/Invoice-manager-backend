from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
import stripe
from core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])

def get_stripe_client():
    """Get Stripe client with API key from settings"""
    if not settings.STRIPE_SECRET_KEY:
        logger.error("Stripe API key is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe API key not configured. Please set STRIPE_SECRET_KEY environment variable."
        )
    
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe

@router.get("/products")
async def get_products():
    """
    Fetch all products from Stripe with their marketing features
    """
    try:
        stripe_client = get_stripe_client()
        
        # Fetch all products with their marketing features
        products = stripe_client.Product.list(active=True)
        prices = stripe_client.Price.list(active=True)
        
        combined_products = []
        
        for product in products.data:
            # Find prices for this product
            product_prices = [price for price in prices.data if price.product == product.id]
            
            if not product_prices:
                continue
            
            default_price = product_prices[0]
            
            # Extract features from product metadata
            features = []
            
            # Check metadata for features (this is the correct way in Stripe)
            if product.metadata:
                if 'marketing_features' in product.metadata:
                    # Features stored in marketing_features metadata
                    features = [f.strip() for f in product.metadata['marketing_features'].split(',') if f.strip()]
                elif 'features' in product.metadata:
                    # Fallback to features metadata
                    features = [f.strip() for f in product.metadata['features'].split(',') if f.strip()]
            
            # Default features only if absolutely no features found
            if not features:
                features = [
                    'AI-powered invoice processing',
                    'Google Drive integration', 
                    'Email support'
                ]
            
            price_display = f"${default_price.unit_amount / 100:.0f}" if default_price.unit_amount else "Contact Sales"
            
            combined_product = {
                'id': product.id,
                'name': product.name,
                'description': product.description or '',
                'features': features,
                'price': price_display,
                'currency': default_price.currency.upper(),
                'price_id': default_price.id,
                'recurring': default_price.recurring is not None,
                'popular': product.metadata.get('popular', 'false').lower() == 'true' if product.metadata else False
            }
            
            combined_products.append(combined_product)
        
        combined_products.sort(key=lambda x: float(x['price'].replace('$', '').replace(',', '')) if x['price'] != 'Contact Sales' else float('inf'))
        
        return {
            'products': combined_products,
            'count': len(combined_products)
        }
        
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch products")


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    """
    Fetch a specific product by ID
    """
    try:
        # Get Stripe client with API key
        stripe_client = get_stripe_client()
        
        product = stripe_client.Product.retrieve(product_id)
        prices = stripe_client.Price.list(product=product_id, active=True)
        
        if not prices.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active prices found for this product"
            )
        
        default_price = prices.data[0]
        
        # Extract features from product metadata
        features = []
        
        # Check metadata for features (this is the correct way in Stripe)
        if product.metadata:
            if 'marketing_features' in product.metadata:
                # Features stored in marketing_features metadata
                features = [f.strip() for f in product.metadata['marketing_features'].split(',') if f.strip()]
            elif 'features' in product.metadata:
                # Fallback to features metadata
                features = [f.strip() for f in product.metadata['features'].split(',') if f.strip()]
        
        # Default features only if absolutely no features found
        if not features:
            features = [
                'AI-powered invoice processing',
                'Google Drive integration',
                'Email support'
            ]
        
        price_display = f"${default_price.unit_amount / 100:.0f}" if default_price.unit_amount else "Contact Sales"
        
        return {
            'id': product.id,
            'name': product.name,
            'description': product.description or '',
            'features': features,
            'price': price_display,
            'currency': default_price.currency.upper(),
            'price_id': default_price.id,
            'recurring': default_price.recurring is not None,
            'popular': product.metadata.get('popular', 'false').lower() == 'true' if product.metadata else False
        }
        
    except stripe.error.InvalidRequestError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch product"
        )