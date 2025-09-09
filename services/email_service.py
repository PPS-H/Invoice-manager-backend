import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails including invitation emails"""
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@invoice-manager.com")
        self.app_name = os.getenv("APP_NAME", "Invoice Manager")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        
        # Check if email service is configured
        if not self.smtp_username or not self.smtp_password:
            logger.warning("⚠️ Email service not configured - SMTP credentials missing")
            logger.warning("   Set SMTP_USERNAME and SMTP_PASSWORD environment variables")
    
    def send_invitation_email(self, 
                             invited_email: str, 
                             inviter_name: str, 
                             invite_token: str, 
                             expires_at: datetime) -> bool:
        """Send invitation email to add email account"""
        try:
            logger.info(f"📧 Attempting to send invitation email to {invited_email}")
            
            if not self.smtp_username or not self.smtp_password:
                logger.error("❌ Cannot send email - SMTP not configured")
                logger.error(f"   SMTP_USERNAME: {'Set' if self.smtp_username else 'Not set'}")
                logger.error(f"   SMTP_PASSWORD: {'Set' if self.smtp_password else 'Not set'}")
                return False
            
            # Create invitation URL
            invite_url = f"{self.frontend_url}/invite/add-email/{invite_token}"
            logger.info(f"   Invite URL: {invite_url}")
            
            # Format expiration date
            expires_str = expires_at.strftime("%B %d, %Y at %I:%M %p UTC")
            logger.info(f"   Expires: {expires_str}")
            
            # Create HTML email content
            logger.info("   Creating HTML email content...")
            html_content = self._create_invitation_html(
                inviter_name=inviter_name,
                invite_url=invite_url,
                expires_at=expires_str,
                app_name=self.app_name
            )
            
            # Create plain text version
            logger.info("   Creating text email content...")
            text_content = self._create_invitation_text(
                inviter_name=inviter_name,
                invite_url=invite_url,
                expires_at=expires_str,
                app_name=self.app_name
            )
            
            # Create message
            logger.info("   Creating email message...")
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Invitation to Connect Email Account - {self.app_name}"
            msg['From'] = self.from_email
            msg['To'] = invited_email
            
            # Attach both HTML and text versions
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            logger.info(f"   Connecting to SMTP server: {self.smtp_server}:{self.smtp_port}")
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                logger.info("   Starting TLS...")
                server.starttls()
                logger.info("   Authenticating...")
                server.login(self.smtp_username, self.smtp_password)
                logger.info("   Sending email...")
                server.send_message(msg)
            
            logger.info(f"✅ Invitation email sent successfully to {invited_email}")
            logger.info(f"   Invite URL: {invite_url}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP Authentication failed: {str(e)}")
            logger.error("   Please check your SMTP_USERNAME and SMTP_PASSWORD")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send invitation email to {invited_email}: {str(e)}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False
    
    def _create_invitation_html(self, inviter_name: str, invite_url: str, expires_at: str, app_name: str) -> str:
        """Create HTML version of invitation email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Email Account Invitation</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8fafc;
                }}
                .container {{
                    background-color: white;
                    border-radius: 8px;
                    padding: 40px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #2563eb;
                    margin-bottom: 10px;
                }}
                .invite-button {{
                    display: inline-block;
                    background-color: #2563eb;
                    color: white;
                    padding: 16px 32px;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 16px;
                    margin: 20px 0;
                    text-align: center;
                }}
                .invite-button:hover {{
                    background-color: #1d4ed8;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    font-size: 14px;
                    color: #6b7280;
                }}
                .expiry-notice {{
                    background-color: #fef3c7;
                    border: 1px solid #f59e0b;
                    border-radius: 6px;
                    padding: 15px;
                    margin: 20px 0;
                    color: #92400e;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{app_name}</div>
                    <h1 style="color: #1f2937; margin: 0;">Email Account Invitation</h1>
                </div>
                
                <p>Hello!</p>
                
                <p><strong>{inviter_name}</strong> has invited you to connect your email account to <strong>{app_name}</strong>.</p>
                
                <p>By connecting your email account, you'll be able to:</p>
                <ul>
                    <li>Automatically scan for invoices in your emails</li>
                    <li>Process and organize your financial documents</li>
                    <li>Access your invoices from anywhere</li>
                    <li>Integrate with Google Drive for secure storage</li>
                </ul>
                
                <div style="text-align: center;">
                    <a href="{invite_url}" class="invite-button">
                        Connect Email Account
                    </a>
                </div>
                
                <div class="expiry-notice">
                    <strong>⚠️ Important:</strong> This invitation expires on <strong>{expires_at}</strong>
                </div>
                
                <p>If you have any questions or need assistance, please don't hesitate to reach out.</p>
                
                <div class="footer">
                    <p>This invitation was sent by {app_name}. If you didn't expect this invitation, you can safely ignore this email.</p>
                    <p>© {datetime.now().year} {app_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_invitation_text(self, inviter_name: str, invite_url: str, expires_at: str, app_name: str) -> str:
        """Create plain text version of invitation email"""
        return f"""
Email Account Invitation - {app_name}

Hello!

{inviter_name} has invited you to connect your email account to {app_name}.

By connecting your email account, you'll be able to:
- Automatically scan for invoices in your emails
- Process and organize your financial documents
- Access your invoices from anywhere
- Integrate with Google Drive for secure storage

To accept this invitation, click the link below:
{invite_url}

⚠️ Important: This invitation expires on {expires_at}

If you have any questions or need assistance, please don't hesitate to reach out.

This invitation was sent by {app_name}. If you didn't expect this invitation, you can safely ignore this email.

© {datetime.now().year} {app_name}. All rights reserved.
        """
    
    def test_connection(self) -> bool:
        """Test SMTP connection"""
        try:
            if not self.smtp_username or not self.smtp_password:
                logger.error("❌ SMTP credentials not configured")
                return False
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                logger.info("✅ SMTP connection test successful")
                return True
                
        except Exception as e:
            logger.error(f"❌ SMTP connection test failed: {str(e)}")
            return False 