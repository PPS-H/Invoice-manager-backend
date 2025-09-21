"""
Stripe Checkout Session endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
import stripe
from core.config import settings
from core.jwt import get_current_user
from models.user import UserModel
from services.subscription_service import SubscriptionService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/checkout", tags=["checkout"])

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

class CheckoutRequest(BaseModel):
    priceId: str  # Accept camelCase from frontend
    mode: str  # 'payment' or 'subscription'
    
    class Config:
        # Allow both camelCase and snake_case
        populate_by_name = True

class CheckoutResponse(BaseModel):
    session_id: str
    session_url: str

@router.post("/create-session", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Create a Stripe Checkout Session for a price ID
    """
    try:
        # Validate mode
        if request.mode not in ['payment', 'subscription']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mode must be 'payment' or 'subscription'"
            )
        
        # Get user's Stripe customer ID if exists
        customer_id = current_user.stripe_customer_id
        
        # Prepare checkout session parameters
        session_params = {
            'mode': request.mode,
            'line_items': [{
                'price': request.priceId,
                'quantity': 1,
            }],
            'success_url': f"{settings.DOMAIN}/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url': f"{settings.DOMAIN}/cancel",
            'metadata': {
                'userId': current_user.id
            },
            'client_reference_id': current_user.id,
            'allow_promotion_codes': True,
        }
        
        # Add customer if exists
        if customer_id:
            session_params['customer'] = customer_id
        else:
            # Create customer if doesn't exist
            session_params['customer_email'] = current_user.email
        
        # Create the checkout session
        checkout_session = stripe.checkout.Session.create(**session_params)
        
        logger.info(f"Created checkout session {checkout_session.id} for user {current_user.id}")
        
        return CheckoutResponse(
            session_id=checkout_session.id,
            session_url=checkout_session.url
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )

@router.get("/session/{session_id}")
async def get_checkout_session(
    session_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Retrieve a checkout session by ID
    """
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Verify the session belongs to the current user
        if session.metadata.get('userId') != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return {
            "id": session.id,
            "status": session.status,
            "payment_status": session.payment_status,
            "customer_email": session.customer_email,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "created": session.created
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error retrieving checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve checkout session"
        )