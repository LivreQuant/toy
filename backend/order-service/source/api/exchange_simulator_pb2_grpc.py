# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from main import exchange_simulator_pb2 as main_dot_exchange__simulator__pb2


class ExchangeSimulatorStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.StartSimulator = channel.unary_unary(
            '/exchange.ExchangeSimulator/StartSimulator',
            request_serializer=main_dot_exchange__simulator__pb2.StartSimulatorRequest.SerializeToString,
            response_deserializer=main_dot_exchange__simulator__pb2.StartSimulatorResponse.FromString,
        )
        self.StopSimulator = channel.unary_unary(
            '/exchange.ExchangeSimulator/StopSimulator',
            request_serializer=main_dot_exchange__simulator__pb2.StopSimulatorRequest.SerializeToString,
            response_deserializer=main_dot_exchange__simulator__pb2.StopSimulatorResponse.FromString,
        )
        self.StreamExchangeData = channel.unary_stream(
            '/exchange.ExchangeSimulator/StreamExchangeData',
            request_serializer=main_dot_exchange__simulator__pb2.StreamRequest.SerializeToString,
            response_deserializer=main_dot_exchange__simulator__pb2.ExchangeDataUpdate.FromString,
        )
        self.Heartbeat = channel.unary_unary(
            '/exchange.ExchangeSimulator/Heartbeat',
            request_serializer=main_dot_exchange__simulator__pb2.HeartbeatRequest.SerializeToString,
            response_deserializer=main_dot_exchange__simulator__pb2.HeartbeatResponse.FromString,
        )
        self.SubmitOrder = channel.unary_unary(
            '/exchange.ExchangeSimulator/SubmitOrder',
            request_serializer=main_dot_exchange__simulator__pb2.SubmitOrderRequest.SerializeToString,
            response_deserializer=main_dot_exchange__simulator__pb2.SubmitOrderResponse.FromString,
        )
        self.CancelOrder = channel.unary_unary(
            '/exchange.ExchangeSimulator/CancelOrder',
            request_serializer=main_dot_exchange__simulator__pb2.CancelOrderRequest.SerializeToString,
            response_deserializer=main_dot_exchange__simulator__pb2.CancelOrderResponse.FromString,
        )
        self.GetOrderStatus = channel.unary_unary(
            '/exchange.ExchangeSimulator/GetOrderStatus',
            request_serializer=main_dot_exchange__simulator__pb2.GetOrderStatusRequest.SerializeToString,
            response_deserializer=main_dot_exchange__simulator__pb2.GetOrderStatusResponse.FromString,
        )


class ExchangeSimulatorServicer(object):
    """Missing associated documentation comment in .proto file."""

    def StartSimulator(self, request, context):
        """Start a simulator for a specific session
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def StopSimulator(self, request, context):
        """Stop a simulator
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def StreamExchangeData(self, request, context):
        """Single unified stream for all exchange data
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Heartbeat(self, request, context):
        """Heartbeat to verify connection
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SubmitOrder(self, request, context):
        """Submit an order
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CancelOrder(self, request, context):
        """Cancel an order
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetOrderStatus(self, request, context):
        """Get order status
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_ExchangeSimulatorServicer_to_server(servicer, server):
    rpc_method_handlers = {
        'StartSimulator': grpc.unary_unary_rpc_method_handler(
            servicer.StartSimulator,
            request_deserializer=main_dot_exchange__simulator__pb2.StartSimulatorRequest.FromString,
            response_serializer=main_dot_exchange__simulator__pb2.StartSimulatorResponse.SerializeToString,
        ),
        'StopSimulator': grpc.unary_unary_rpc_method_handler(
            servicer.StopSimulator,
            request_deserializer=main_dot_exchange__simulator__pb2.StopSimulatorRequest.FromString,
            response_serializer=main_dot_exchange__simulator__pb2.StopSimulatorResponse.SerializeToString,
        ),
        'StreamExchangeData': grpc.unary_stream_rpc_method_handler(
            servicer.StreamExchangeData,
            request_deserializer=main_dot_exchange__simulator__pb2.StreamRequest.FromString,
            response_serializer=main_dot_exchange__simulator__pb2.ExchangeDataUpdate.SerializeToString,
        ),
        'Heartbeat': grpc.unary_unary_rpc_method_handler(
            servicer.Heartbeat,
            request_deserializer=main_dot_exchange__simulator__pb2.HeartbeatRequest.FromString,
            response_serializer=main_dot_exchange__simulator__pb2.HeartbeatResponse.SerializeToString,
        ),
        'SubmitOrder': grpc.unary_unary_rpc_method_handler(
            servicer.SubmitOrder,
            request_deserializer=main_dot_exchange__simulator__pb2.SubmitOrderRequest.FromString,
            response_serializer=main_dot_exchange__simulator__pb2.SubmitOrderResponse.SerializeToString,
        ),
        'CancelOrder': grpc.unary_unary_rpc_method_handler(
            servicer.CancelOrder,
            request_deserializer=main_dot_exchange__simulator__pb2.CancelOrderRequest.FromString,
            response_serializer=main_dot_exchange__simulator__pb2.CancelOrderResponse.SerializeToString,
        ),
        'GetOrderStatus': grpc.unary_unary_rpc_method_handler(
            servicer.GetOrderStatus,
            request_deserializer=main_dot_exchange__simulator__pb2.GetOrderStatusRequest.FromString,
            response_serializer=main_dot_exchange__simulator__pb2.GetOrderStatusResponse.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        'exchange.ExchangeSimulator', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


# This class is part of an EXPERIMENTAL API.
class ExchangeSimulator(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def StartSimulator(request,
                       target,
                       options=(),
                       channel_credentials=None,
                       call_credentials=None,
                       insecure=False,
                       compression=None,
                       wait_for_ready=None,
                       timeout=None,
                       metadata=None):
        return grpc.experimental.unary_unary(request, target, '/exchange.ExchangeSimulator/StartSimulator',
                                             main_dot_exchange__simulator__pb2.StartSimulatorRequest.SerializeToString,
                                             main_dot_exchange__simulator__pb2.StartSimulatorResponse.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def StopSimulator(request,
                      target,
                      options=(),
                      channel_credentials=None,
                      call_credentials=None,
                      insecure=False,
                      compression=None,
                      wait_for_ready=None,
                      timeout=None,
                      metadata=None):
        return grpc.experimental.unary_unary(request, target, '/exchange.ExchangeSimulator/StopSimulator',
                                             main_dot_exchange__simulator__pb2.StopSimulatorRequest.SerializeToString,
                                             main_dot_exchange__simulator__pb2.StopSimulatorResponse.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def StreamExchangeData(request,
                           target,
                           options=(),
                           channel_credentials=None,
                           call_credentials=None,
                           insecure=False,
                           compression=None,
                           wait_for_ready=None,
                           timeout=None,
                           metadata=None):
        return grpc.experimental.unary_stream(request, target, '/exchange.ExchangeSimulator/StreamExchangeData',
                                              main_dot_exchange__simulator__pb2.StreamRequest.SerializeToString,
                                              main_dot_exchange__simulator__pb2.ExchangeDataUpdate.FromString,
                                              options, channel_credentials,
                                              insecure, call_credentials, compression, wait_for_ready, timeout,
                                              metadata)

    @staticmethod
    def Heartbeat(request,
                  target,
                  options=(),
                  channel_credentials=None,
                  call_credentials=None,
                  insecure=False,
                  compression=None,
                  wait_for_ready=None,
                  timeout=None,
                  metadata=None):
        return grpc.experimental.unary_unary(request, target, '/exchange.ExchangeSimulator/Heartbeat',
                                             main_dot_exchange__simulator__pb2.HeartbeatRequest.SerializeToString,
                                             main_dot_exchange__simulator__pb2.HeartbeatResponse.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def SubmitOrder(request,
                    target,
                    options=(),
                    channel_credentials=None,
                    call_credentials=None,
                    insecure=False,
                    compression=None,
                    wait_for_ready=None,
                    timeout=None,
                    metadata=None):
        return grpc.experimental.unary_unary(request, target, '/exchange.ExchangeSimulator/SubmitOrder',
                                             main_dot_exchange__simulator__pb2.SubmitOrderRequest.SerializeToString,
                                             main_dot_exchange__simulator__pb2.SubmitOrderResponse.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def CancelOrder(request,
                    target,
                    options=(),
                    channel_credentials=None,
                    call_credentials=None,
                    insecure=False,
                    compression=None,
                    wait_for_ready=None,
                    timeout=None,
                    metadata=None):
        return grpc.experimental.unary_unary(request, target, '/exchange.ExchangeSimulator/CancelOrder',
                                             main_dot_exchange__simulator__pb2.CancelOrderRequest.SerializeToString,
                                             main_dot_exchange__simulator__pb2.CancelOrderResponse.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetOrderStatus(request,
                       target,
                       options=(),
                       channel_credentials=None,
                       call_credentials=None,
                       insecure=False,
                       compression=None,
                       wait_for_ready=None,
                       timeout=None,
                       metadata=None):
        return grpc.experimental.unary_unary(request, target, '/exchange.ExchangeSimulator/GetOrderStatus',
                                             main_dot_exchange__simulator__pb2.GetOrderStatusRequest.SerializeToString,
                                             main_dot_exchange__simulator__pb2.GetOrderStatusResponse.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
