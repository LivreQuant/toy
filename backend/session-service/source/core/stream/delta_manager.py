# source/core/stream/delta_manager.py
"""
Delta compression manager for exchange data streaming.
FIXED: Does exactly what's configured - no fallback logic.
"""
import json
import logging
import zlib
import time
from typing import Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('delta_manager')


class DeltaType(str, Enum):
    """Types of delta operations"""
    FULL = "FULL"           # Full payload (first message or after reset)
    DELTA = "DELTA"         # Delta payload with changes only


@dataclass
class DeltaMessage:
    """Container for delta messages with optional compression"""
    type: DeltaType
    sequence: int
    timestamp: int
    payload: Dict[str, Any]
    compressed: bool = False
    compression_ratio: Optional[float] = None
    delta_size: Optional[int] = None
    original_size: Optional[int] = None


class DeltaManager:
    """
    Manages delta calculation and optional compression for exchange data streaming.
    FIXED: No fallback logic - does exactly what's configured.
    """

    def __init__(self, 
                 enable_delta: bool = True,
                 enable_compression: bool = True, 
                 compression_threshold: int = 100, 
                 compression_level: int = 6):
        """
        Initialize delta manager
        
        Args:
            enable_delta: Whether to calculate deltas (FULL vs DELTA)
            enable_compression: Whether to apply zlib compression
            compression_threshold: Minimum payload size to apply compression
            compression_level: zlib compression level (1-9, higher = better compression)
        """
        self.enable_delta = enable_delta
        self.enable_compression = enable_compression
        self.compression_threshold = compression_threshold
        self.compression_level = compression_level
        
        # Store last complete state for each client (only if delta enabled)
        self.client_states: Dict[str, Dict[str, Any]] = {}
        
        # Sequence tracking
        self.client_sequences: Dict[str, int] = {}
        
        # Statistics tracking
        self.stats = {
            'messages_processed': 0,
            'full_messages_sent': 0,
            'delta_messages_sent': 0,
            'compressed_messages_sent': 0,
            'total_original_bytes': 0,
            'total_transmitted_bytes': 0,
            'compression_ratio_sum': 0.0
        }
        
        logger.info(f"Delta manager initialized - Delta: {'ON' if enable_delta else 'OFF'}, Compression: {'ON' if enable_compression else 'OFF'}")

    def process_message(self, client_id: str, data: Dict[str, Any]) -> DeltaMessage:
        """
        Process incoming exchange data and create delta message
        FIXED: No fallback logic - strictly follows configuration
        
        Args:
            client_id: Unique identifier for the client connection
            data: Complete exchange data message
            
        Returns:
            DeltaMessage with delta or full payload, optionally compressed
        """
        current_sequence = self.client_sequences.get(client_id, 0) + 1
        self.client_sequences[client_id] = current_sequence
        
        # Get original size for statistics
        original_json = json.dumps(data, separators=(',', ':'))
        original_size = len(original_json.encode('utf-8'))
        self.stats['total_original_bytes'] += original_size
        self.stats['messages_processed'] += 1
        
        # STEP 1: Determine if this should be FULL or DELTA
        if not self.enable_delta:
            # Delta disabled - always send full
            logger.debug(f"Delta disabled - sending FULL payload for client {client_id}")
            return self._create_message(client_id, data, DeltaType.FULL, current_sequence, original_size)
        
        # Delta enabled - check if this is the first message for this client
        if client_id not in self.client_states:
            logger.info(f"First message for client {client_id} - sending FULL payload (sequence: {current_sequence})")
            return self._create_message(client_id, data, DeltaType.FULL, current_sequence, original_size)
        
        # Calculate delta from previous state
        previous_state = self.client_states[client_id]
        delta_payload = self._calculate_delta(previous_state, data)
        
        # Update stored state
        self.client_states[client_id] = data.copy()
        
        # SEND DELTA - NO FALLBACK LOGIC
        logger.debug(f"Sending DELTA payload for client {client_id}")
        return self._create_message(client_id, delta_payload, DeltaType.DELTA, current_sequence, original_size)

    def _calculate_delta(self, previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate delta between two data states
        
        Args:
            previous: Previous complete state
            current: Current complete state
            
        Returns:
            Dictionary containing only the changes
        """
        delta = {}
        
        # Track all keys that exist in either version
        all_keys = set(previous.keys()) | set(current.keys())
        
        for key in all_keys:
            prev_value = previous.get(key)
            curr_value = current.get(key)
            
            if prev_value != curr_value:
                if curr_value is None:
                    # Key was deleted
                    delta[key] = None
                elif isinstance(curr_value, dict) and isinstance(prev_value, dict):
                    # Nested dictionary - recurse
                    nested_delta = self._calculate_delta(prev_value, curr_value)
                    if nested_delta:
                        delta[key] = nested_delta
                elif isinstance(curr_value, list) and isinstance(prev_value, list):
                    # List comparison - replace entire list if different
                    delta[key] = curr_value
                else:
                    # Value changed or added
                    delta[key] = curr_value
        
        return delta

    def _create_message(self, client_id: str, payload: Dict[str, Any], 
                       delta_type: DeltaType, sequence: int, original_size: int) -> DeltaMessage:
        """Create a message with optional compression"""
        
        # Store the complete state if this is a FULL message and delta is enabled
        if delta_type == DeltaType.FULL and self.enable_delta:
            self.client_states[client_id] = payload.copy()
        
        # STEP 2: Apply compression if enabled
        final_payload = payload.copy()
        compressed = False
        compression_ratio = None
        
        payload_json = json.dumps(payload, separators=(',', ':'))
        payload_size = len(payload_json.encode('utf-8'))
        transmitted_size = payload_size
        
        # COMPRESS IF ENABLED AND ABOVE THRESHOLD - NO FALLBACK
        if self.enable_compression and payload_size > self.compression_threshold:
            compressed_payload, compression_ratio = self._compress_payload(payload)
            if compressed_payload:  # Use compression if it worked
                final_payload = compressed_payload
                compressed = True
                transmitted_size = len(json.dumps(final_payload, separators=(',', ':')).encode('utf-8'))
                logger.debug(f"Compressed {delta_type.value} payload: {payload_size}→{transmitted_size} bytes")
        
        # Update statistics
        if delta_type == DeltaType.FULL:
            self.stats['full_messages_sent'] += 1
        else:
            self.stats['delta_messages_sent'] += 1
            
        if compressed:
            self.stats['compressed_messages_sent'] += 1
            
        self.stats['total_transmitted_bytes'] += transmitted_size
        
        return DeltaMessage(
            type=delta_type,
            sequence=sequence,
            timestamp=int(time.time() * 1000),
            payload=final_payload,
            compressed=compressed,
            compression_ratio=compression_ratio,
            original_size=original_size,
            delta_size=transmitted_size
        )

    def _compress_payload(self, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
        """
        Compress payload using zlib
        
        Args:
            payload: Dictionary to compress
            
        Returns:
            Tuple of (compressed_payload_dict, compression_ratio) or (None, None) if compression failed
        """
        try:
            # Serialize to JSON
            json_str = json.dumps(payload, separators=(',', ':'))
            original_bytes = json_str.encode('utf-8')
            original_size = len(original_bytes)
            
            # Compress
            compressed_bytes = zlib.compress(original_bytes, level=self.compression_level)
            compressed_size = len(compressed_bytes)
            
            # Calculate compression ratio
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            
            # Return compressed data as base64-encoded string in a wrapper
            import base64
            compressed_payload = {
                '__compressed__': True,
                '__algorithm__': 'zlib',
                '__original_size__': original_size,
                '__data__': base64.b64encode(compressed_bytes).decode('ascii')
            }
            
            return compressed_payload, compression_ratio
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return None, None

    def reset_client(self, client_id: str):
        """Reset client state - next message will be full payload"""
        if client_id in self.client_states:
            del self.client_states[client_id]
        if client_id in self.client_sequences:
            del self.client_sequences[client_id]
        logger.info(f"Reset delta state for client {client_id}")

    def get_client_info(self, client_id: str) -> Dict[str, Any]:
        """Get information about a client's delta state"""
        return {
            'has_state': client_id in self.client_states,
            'sequence': self.client_sequences.get(client_id, 0),
            'state_keys': list(self.client_states.get(client_id, {}).keys()),
            'delta_enabled': self.enable_delta,
            'compression_enabled': self.enable_compression
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get compression and delta statistics"""
        if self.stats['messages_processed'] == 0:
            return {
                **self.stats,
                'delta_enabled': self.enable_delta,
                'compression_enabled': self.enable_compression
            }
        
        avg_compression_ratio = (self.stats['compression_ratio_sum'] / 
                               max(1, self.stats['compressed_messages_sent']))
        
        overall_compression = (self.stats['total_original_bytes'] / 
                             max(1, self.stats['total_transmitted_bytes']))
        
        return {
            **self.stats,
            'delta_enabled': self.enable_delta,
            'compression_enabled': self.enable_compression,
            'average_compression_ratio': avg_compression_ratio,
            'overall_bandwidth_savings': f"{((overall_compression - 1) * 100):.1f}%",
            'overall_compression_ratio': overall_compression,
            'delta_percentage': f"{(self.stats['delta_messages_sent'] / max(1, self.stats['messages_processed']) * 100):.1f}%"
        }

    def cleanup_old_clients(self, active_client_ids: Set[str]):
        """Remove state for clients that are no longer active"""
        clients_to_remove = set(self.client_states.keys()) - active_client_ids
        for client_id in clients_to_remove:
            self.reset_client(client_id)
        
        if clients_to_remove:
            logger.info(f"Cleaned up delta state for {len(clients_to_remove)} inactive clients")