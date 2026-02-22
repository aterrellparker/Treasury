# import smtplib
# from email.mime.text import MIMEText

# # Email configuration
# sender_email = "your_email@example.com"
# sender_password = "your_email_password"  # Use an app-specific password if using Gmail
# receiver_email = "recipient_email@example.com"
# subject = "Python Email Test"
# body = "This is a test email sent from Python."

# # Create the email message
# msg = MIMEText(body)
# msg['Subject'] = subject
# msg['From'] = sender_email
# msg['To'] = receiver_email

# try:
#     # Connect to the SMTP server (e.g., Gmail)
#     # For Gmail, use 'smtp.gmail.com' and port 587
#     with smtplib.SMTP('smtp.gmail.com', 587) as server:
#         server.starttls()  # Secure the connection with TLS
#         server.login(sender_email, sender_password)  # Authenticate with your credentials
#         server.send_message(msg)  # Send the email
#     print("Email sent successfully!")
# except Exception as e:
#     print(f"Error sending email: {e}")
