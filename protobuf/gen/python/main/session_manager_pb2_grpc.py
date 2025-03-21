# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from main import session_manager_pb2 as main_dot_session__manager__pb2


class SessionManagerServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.CreateSession = channel.unary_unary(
                '/SessionManagerService/CreateSession',
                request_serializer=main_dot_session__manager__pb2.CreateSessionRequest.SerializeToString,
                response_deserializer=main_dot_session__manager__pb2.CreateSessionResponse.FromString,
                )
        self.GetSession = channel.unary_unary(
                '/SessionManagerService/GetSession',
                request_serializer=main_dot_session__manager__pb2.GetSessionRequest.SerializeToString,
                response_deserializer=main_dot_session__manager__pb2.GetSessionResponse.FromString,
                )
        self.EndSession = channel.unary_unary(
                '/SessionManagerService/EndSession',
                request_serializer=main_dot_session__manager__pb2.EndSessionRequest.SerializeToString,
                response_deserializer=main_dot_session__manager__pb2.EndSessionResponse.FromString,
                )
        self.KeepAlive = channel.unary_unary(
                '/SessionManagerService/KeepAlive',
                request_serializer=main_dot_session__manager__pb2.KeepAliveRequest.SerializeToString,
                response_deserializer=main_dot_session__manager__pb2.KeepAliveResponse.FromString,
                )
        self.GetSessionState = channel.unary_unary(
                '/SessionManagerService/GetSessionState',
                request_serializer=main_dot_session__manager__pb2.GetSessionStateRequest.SerializeToString,
                response_deserializer=main_dot_session__manager__pb2.GetSessionStateResponse.FromString,
                )


class SessionManagerServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def CreateSession(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetSession(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def EndSession(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def KeepAlive(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetSessionState(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_SessionManagerServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'CreateSession': grpc.unary_unary_rpc_method_handler(
                    servicer.CreateSession,
                    request_deserializer=main_dot_session__manager__pb2.CreateSessionRequest.FromString,
                    response_serializer=main_dot_session__manager__pb2.CreateSessionResponse.SerializeToString,
            ),
            'GetSession': grpc.unary_unary_rpc_method_handler(
                    servicer.GetSession,
                    request_deserializer=main_dot_session__manager__pb2.GetSessionRequest.FromString,
                    response_serializer=main_dot_session__manager__pb2.GetSessionResponse.SerializeToString,
            ),
            'EndSession': grpc.unary_unary_rpc_method_handler(
                    servicer.EndSession,
                    request_deserializer=main_dot_session__manager__pb2.EndSessionRequest.FromString,
                    response_serializer=main_dot_session__manager__pb2.EndSessionResponse.SerializeToString,
            ),
            'KeepAlive': grpc.unary_unary_rpc_method_handler(
                    servicer.KeepAlive,
                    request_deserializer=main_dot_session__manager__pb2.KeepAliveRequest.FromString,
                    response_serializer=main_dot_session__manager__pb2.KeepAliveResponse.SerializeToString,
            ),
            'GetSessionState': grpc.unary_unary_rpc_method_handler(
                    servicer.GetSessionState,
                    request_deserializer=main_dot_session__manager__pb2.GetSessionStateRequest.FromString,
                    response_serializer=main_dot_session__manager__pb2.GetSessionStateResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'SessionManagerService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class SessionManagerService(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def CreateSession(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/SessionManagerService/CreateSession',
            main_dot_session__manager__pb2.CreateSessionRequest.SerializeToString,
            main_dot_session__manager__pb2.CreateSessionResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetSession(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/SessionManagerService/GetSession',
            main_dot_session__manager__pb2.GetSessionRequest.SerializeToString,
            main_dot_session__manager__pb2.GetSessionResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def EndSession(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/SessionManagerService/EndSession',
            main_dot_session__manager__pb2.EndSessionRequest.SerializeToString,
            main_dot_session__manager__pb2.EndSessionResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def KeepAlive(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/SessionManagerService/KeepAlive',
            main_dot_session__manager__pb2.KeepAliveRequest.SerializeToString,
            main_dot_session__manager__pb2.KeepAliveResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetSessionState(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/SessionManagerService/GetSessionState',
            main_dot_session__manager__pb2.GetSessionStateRequest.SerializeToString,
            main_dot_session__manager__pb2.GetSessionStateResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
