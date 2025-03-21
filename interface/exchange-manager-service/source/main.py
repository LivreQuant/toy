# simulator_manager.py
import uuid
import grpc
import subprocess
import time
from concurrent import futures
import simulator_manager_pb2
import simulator_manager_pb2_grpc
import auth_pb2
import auth_pb2_grpc
import session_manager_pb2
import session_manager_pb2_grpc

class SimulatorManagerServicer(simulator_manager_pb2_grpc.SimulatorManagerServiceServicer):
    def __init__(self, auth_channel, session_manager_channel):
        self.auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
        self.session_manager_stub = session_manager_pb2_grpc.SessionManagerServiceStub(session_manager_channel)
        self.simulators = {}  # simulator_id -> {session_id, pod_name, status, endpoint}
        
        # In production, this would interact with Kubernetes API
        self.simulate_kubernetes = True
    
    def StartSimulator(self, request, context):
        session_id = request.session_id
        
        # Validate token
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            return simulator_manager_pb2.StartSimulatorResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        # Validate session
        session_response = self.session_manager_stub.GetSession(
            session_manager_pb2.GetSessionRequest(
                session_id=session_id,
                token=request.token
            )
        )
        
        if not session_response.session_active:
            return simulator_manager_pb2.StartSimulatorResponse(
                success=False,
                error_message="Invalid or inactive session"
            )
        
        # Check if simulator already exists for this session
        for sim_id, sim_info in self.simulators.items():
            if sim_info["session_id"] == session_id:
                return simulator_manager_pb2.StartSimulatorResponse(
                    success=True,
                    simulator_id=sim_id,
                    simulator_endpoint=sim_info["endpoint"]
                )
        
        # Create new simulator
        simulator_id = str(uuid.uuid4())
        pod_name = f"simulator-{simulator_id[:8]}"
        
        if self.simulate_kubernetes:
            # In a real K8s environment, this would create a pod
            print(f"Starting simulator pod: {pod_name}")
            
            # Simulate pod startup time
            time.sleep(1)
            
            # K8s would assign an endpoint
            endpoint = f"simulator-{simulator_id[:8]}:50053"
            
            self.simulators[simulator_id] = {
                "session_id": session_id,
                "pod_name": pod_name,
                "status": "RUNNING",
                "endpoint": endpoint
            }
            
            # Update session with simulator endpoint
            # In real implementation, this would be handled by the simulator pod registering itself
            
            return simulator_manager_pb2.StartSimulatorResponse(
                success=True,
                simulator_id=simulator_id,
                simulator_endpoint=endpoint
            )
        else:
            # Local development with docker-compose
            # This would start a new container
            try:
                # This is just an example for local dev
                container_id = subprocess.check_output([
                    "docker", "run", "-d", "--name", pod_name,
                    "--network", "trading-simulator_default",
                    "-e", f"SIMULATOR_ID={simulator_id}",
                    "-e", f"SESSION_ID={session_id}",
                    "-p", "0:50053",
                    "trading-simulator/exchange-simulator"
                ]).decode().strip()
                
                # Get assigned port
                port_info = subprocess.check_output([
                    "docker", "port", container_id, "50053"
                ]).decode().strip()
                
                # Format: 0.0.0.0:12345
                endpoint = f"localhost:{port_info.split(':')[1]}"
                
                self.simulators[simulator_id] = {
                    "session_id": session_id,
                    "pod_name": pod_name,
                    "status": "RUNNING",
                    "endpoint": endpoint,
                    "container_id": container_id
                }
                
                return simulator_manager_pb2.StartSimulatorResponse(
                    success=True,
                    simulator_id=simulator_id,
                    simulator_endpoint=endpoint
                )
                
            except Exception as e:
                print(f"Failed to start simulator: {e}")
                return simulator_manager_pb2.StartSimulatorResponse(
                    success=False,
                    error_message=f"Failed to start simulator: {str(e)}"
                )
    
    def StopSimulator(self, request, context):
        simulator_id = request.simulator_id
        
        # Validate token
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            return simulator_manager_pb2.StopSimulatorResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        # Check if simulator exists
        if simulator_id not in self.simulators:
            return simulator_manager_pb2.StopSimulatorResponse(
                success=False,
                error_message="Simulator not found"
            )
        
        simulator = self.simulators[simulator_id]
        session_id = simulator["session_id"]
        
        # Validate session
        session_response = self.session_manager_stub.GetSession(
            session_manager_pb2.GetSessionRequest(
                session_id=session_id,
                token=request.token
            )
        )
        
        if not session_response.session_active:
            return simulator_manager_pb2.StopSimulatorResponse(
                success=False,
                error_message="Invalid or inactive session"
            )
        
        # Stop simulator
        if self.simulate_kubernetes:
            # In a real K8s environment, this would delete the pod
            print(f"Stopping simulator pod: {simulator['pod_name']}")
            
            # Simulate pod termination time
            time.sleep(1)
            
            del self.simulators[simulator_id]
            
            return simulator_manager_pb2.StopSimulatorResponse(success=True)
        else:
            # Local development with docker-compose
            try:
                # Stop and remove container
                subprocess.check_call(["docker", "stop", simulator["container_id"]])
                subprocess.check_call(["docker", "rm", simulator["container_id"]])
                
                del self.simulators[simulator_id]
                
                return simulator_manager_pb2.StopSimulatorResponse(success=True)
                
            except Exception as e:
                print(f"Failed to stop simulator: {e}")
                return simulator_manager_pb2.StopSimulatorResponse(
                    success=False,
                    error_message=f"Failed to stop simulator: {str(e)}"
                )
    
    def GetSimulatorStatus(self, request, context):
        simulator_id = request.simulator_id
        
        # Validate token
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            return simulator_manager_pb2.GetSimulatorStatusResponse(
                status=simulator_manager_pb2.GetSimulatorStatusResponse.Status.ERROR,
                error_message="Invalid authentication token"
            )
        
        # Check if simulator exists
        if simulator_id not in self.simulators:
            return simulator_manager_pb2.GetSimulatorStatusResponse(
                status=simulator_manager_pb2.GetSimulatorStatusResponse.Status.UNKNOWN,
                error_message="Simulator not found"
            )
        
        simulator = self.simulators[simulator_id]
        
        # Map internal status to protobuf status
        status_map = {
            "STARTING": simulator_manager_pb2.GetSimulatorStatusResponse.Status.STARTING,
            "RUNNING": simulator_manager_pb2.GetSimulatorStatusResponse.Status.RUNNING,
            "STOPPING": simulator_manager_pb2.GetSimulatorStatusResponse.Status.STOPPING,
            "STOPPED": simulator_manager_pb2.GetSimulatorStatusResponse.Status.STOPPED,
            "ERROR": simulator_manager_pb2.GetSimulatorStatusResponse.Status.ERROR
        }
        
        return simulator_manager_pb2.GetSimulatorStatusResponse(
            status=status_map.get(simulator["status"], 
                  simulator_manager_pb2.GetSimulatorStatusResponse.Status.UNKNOWN)
        )

def serve():
    auth_channel = grpc.insecure_channel('auth:50051')
    session_manager_channel = grpc.insecure_channel('session-manager:50052')
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    simulator_manager_pb2_grpc.add_SimulatorManagerServiceServicer_to_server(
        SimulatorManagerServicer(auth_channel, session_manager_channel), server
    )
    server.add_insecure_port('[::]:50053')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()