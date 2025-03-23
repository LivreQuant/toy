When deploying to production, consider these additional security measures:

HTTPS Only: Ensure all API communications use HTTPS
Token Storage: Consider using browser IndexedDB for more secure token storage
Rate Limiting: Implement rate limiting on token refresh endpoints
Monitoring: Add monitoring for suspicious token activity
Token Revocation: Implement a blacklist for revoked tokens on the server
IP Tracking: Consider tracking and validating user IP addresses during refresh

This implementation should provide a solid foundation for token-based authentication in your trading application, with special considerations for the AWS EKS environment.