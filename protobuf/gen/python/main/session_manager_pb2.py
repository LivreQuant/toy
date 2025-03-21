# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: main/session_manager.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1amain/session_manager.proto\"E\n\x14\x43reateSessionRequest\x12\x17\n\x07user_id\x18\x01 \x01(\tR\x06userId\x12\x14\n\x05token\x18\x02 \x01(\tR\x05token\"u\n\x15\x43reateSessionResponse\x12\x18\n\x07success\x18\x01 \x01(\x08R\x07success\x12\x1d\n\nsession_id\x18\x02 \x01(\tR\tsessionId\x12#\n\rerror_message\x18\x03 \x01(\tR\x0c\x65rrorMessage\"H\n\x11GetSessionRequest\x12\x1d\n\nsession_id\x18\x01 \x01(\tR\tsessionId\x12\x14\n\x05token\x18\x02 \x01(\tR\x05token\"\x8f\x01\n\x12GetSessionResponse\x12%\n\x0esession_active\x18\x01 \x01(\x08R\rsessionActive\x12-\n\x12simulator_endpoint\x18\x02 \x01(\tR\x11simulatorEndpoint\x12#\n\rerror_message\x18\x03 \x01(\tR\x0c\x65rrorMessage\"H\n\x11\x45ndSessionRequest\x12\x1d\n\nsession_id\x18\x01 \x01(\tR\tsessionId\x12\x14\n\x05token\x18\x02 \x01(\tR\x05token\"S\n\x12\x45ndSessionResponse\x12\x18\n\x07success\x18\x01 \x01(\x08R\x07success\x12#\n\rerror_message\x18\x02 \x01(\tR\x0c\x65rrorMessage\"G\n\x10KeepAliveRequest\x12\x1d\n\nsession_id\x18\x01 \x01(\tR\tsessionId\x12\x14\n\x05token\x18\x02 \x01(\tR\x05token\"-\n\x11KeepAliveResponse\x12\x18\n\x07success\x18\x01 \x01(\x08R\x07success\"M\n\x16GetSessionStateRequest\x12\x1d\n\nsession_id\x18\x01 \x01(\tR\tsessionId\x12\x14\n\x05token\x18\x02 \x01(\tR\x05token\"\xf9\x01\n\x17GetSessionStateResponse\x12\x18\n\x07success\x18\x01 \x01(\x08R\x07success\x12!\n\x0csimulator_id\x18\x02 \x01(\tR\x0bsimulatorId\x12-\n\x12simulator_endpoint\x18\x03 \x01(\tR\x11simulatorEndpoint\x12,\n\x12session_created_at\x18\x04 \x01(\x03R\x10sessionCreatedAt\x12\x1f\n\x0blast_active\x18\x05 \x01(\x03R\nlastActive\x12#\n\rerror_message\x18\x06 \x01(\tR\x0c\x65rrorMessage2\xbf\x02\n\x15SessionManagerService\x12>\n\rCreateSession\x12\x15.CreateSessionRequest\x1a\x16.CreateSessionResponse\x12\x35\n\nGetSession\x12\x12.GetSessionRequest\x1a\x13.GetSessionResponse\x12\x35\n\nEndSession\x12\x12.EndSessionRequest\x1a\x13.EndSessionResponse\x12\x32\n\tKeepAlive\x12\x11.KeepAliveRequest\x1a\x12.KeepAliveResponse\x12\x44\n\x0fGetSessionState\x12\x17.GetSessionStateRequest\x1a\x18.GetSessionStateResponseB\x17\x42\x13SessionManagerProtoP\x01\x62\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'main.session_manager_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'B\023SessionManagerProtoP\001'
  _CREATESESSIONREQUEST._serialized_start=30
  _CREATESESSIONREQUEST._serialized_end=99
  _CREATESESSIONRESPONSE._serialized_start=101
  _CREATESESSIONRESPONSE._serialized_end=218
  _GETSESSIONREQUEST._serialized_start=220
  _GETSESSIONREQUEST._serialized_end=292
  _GETSESSIONRESPONSE._serialized_start=295
  _GETSESSIONRESPONSE._serialized_end=438
  _ENDSESSIONREQUEST._serialized_start=440
  _ENDSESSIONREQUEST._serialized_end=512
  _ENDSESSIONRESPONSE._serialized_start=514
  _ENDSESSIONRESPONSE._serialized_end=597
  _KEEPALIVEREQUEST._serialized_start=599
  _KEEPALIVEREQUEST._serialized_end=670
  _KEEPALIVERESPONSE._serialized_start=672
  _KEEPALIVERESPONSE._serialized_end=717
  _GETSESSIONSTATEREQUEST._serialized_start=719
  _GETSESSIONSTATEREQUEST._serialized_end=796
  _GETSESSIONSTATERESPONSE._serialized_start=799
  _GETSESSIONSTATERESPONSE._serialized_end=1048
  _SESSIONMANAGERSERVICE._serialized_start=1051
  _SESSIONMANAGERSERVICE._serialized_end=1370
# @@protoc_insertion_point(module_scope)
