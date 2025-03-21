# auth_service.py
import grpc
import jwt
import datetime
from concurrent import futures
import auth_pb2
import auth_pb2_grpc

SECRET_KEY = "dev-secret-key"  # Would be environment variable in production

class AuthServicer(auth_pb2_grpc.AuthServiceServicer):
    def __init__(self):
        # In a real app, you'd connect to a database
        self.users = {
            "testuser": {
                "password": "password123",
                "user_id": "user1"
            }
        }
        self.active_tokens = {}
        
    def Login(self, request, context):
        username = request.username
        password = request.password
        
        if username not in self.users or self.users[username]["password"] != password:
            return auth_pb2.LoginResponse(
                success=False,
                error_message="Invalid username or password"
            )
        
        # Generate JWT token
        user_id = self.users[username]["user_id"]
        expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        token = jwt.encode(
            {
                "user_id": user_id,
                "exp": expiry
            },
            SECRET_KEY,
            algorithm="HS256"
        )
        
        self.active_tokens[token] = user_id
        
        return auth_pb2.LoginResponse(
            success=True,
            token=token
        )
    
    def Logout(self, request, context):
        token = request.token
        
        if token in self.active_tokens:
            del self.active_tokens[token]
            
        return auth_pb2.LogoutResponse(success=True)
    
    def ValidateToken(self, request, context):
        token = request.token
        
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = decoded.get("user_id")
            
            if token in self.active_tokens and self.active_tokens[token] == user_id:
                return auth_pb2.ValidateTokenResponse(
                    valid=True,
                    user_id=user_id
                )
        except jwt.PyJWTError:
            pass
        
        return auth_pb2.ValidateTokenResponse(valid=False)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()