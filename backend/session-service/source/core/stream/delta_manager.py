# source/core/stream/delta_manager.py
"""
Delta compression manager for exchange data streaming.
Calculates and applies deltas to minimize bandwidth usage.
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
    COMPRESSED = "COMPRESSED"  # Compressed delta payload


@dataclass
class DeltaMessage:
    """Container for delta-compressed messages"""
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
    Manages delta compression for exchange data streaming.
    
    Features:
    - Calculates deltas between sequential messages
    - Compresses delta payloads using zlib
    - Handles full payload transmission for first message or reset
    - Tracks compression statistics
    """

    def __init__(self, compression_threshold: int = 100, compression_level: int = 6):
        """
        Initialize delta manager
        
        Args:
            compression_threshold: Minimum payload size to apply compression
            compression_level: zlib compression level (1-9, higher = better compression)
        """
        self.compression_threshold = compression_threshold
        self.compression_level = compression_level
        
        # Store last complete state for each client
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
        
        logger.info(f"Delta manager initialized with compression threshold: {compression_threshold}")

    def process_message(self, client_id: str, data: Dict[str, Any]) -> DeltaMessage:
        """
        Process incoming exchange data and create delta message
        
        Args:
            client_id: Unique identifier for the client connection
            data: Complete exchange data message
            
        Returns:
            DeltaMessage with delta or full payload
        """
        current_sequence = self.client_sequences.get(client_id, 0) + 1
        self.client_sequences[client_id] = current_sequence
        
        # Get original size for statistics
        original_json = json.dumps(data, separators=(',', ':'))
        original_size = len(original_json.encode('utf-8'))
        self.stats['total_original_bytes'] += original_size
        self.stats['messages_processed'] += 1
        
        # Check if this is the first message for this client
        if client_id not in self.client_states:
            logger.info(f"Sending full payload for new client {client_id} (sequence: {current_sequence})")
            return self._create_full_message(client_id, data, current_sequence, original_size)
        
        # Calculate delta from previous state
        previous_state = self.client_states[client_id]
        delta_payload = self._calculate_delta(previous_state, data)
        
        # Update stored state
        self.client_states[client_id] = data.copy()
        
        # If delta is too large or empty, send full payload
        if not delta_payload or self._should_send_full(delta_payload, data):
            logger.debug(f"Delta too large or empty for client {client_id}, sending full payload")
            return self._create_full_message(client_id, data, current_sequence, original_size)
        
        # Create delta message
        return self._create_delta_message(client_id, delta_payload, current_sequence, original_size)

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
                    # List comparison - for now, replace entire list if different
                    # Could be optimized further for large lists
                    delta[key] = curr_value
                else:
                    # Value changed or added
                    delta[key] = curr_value
        
        return delta

    def _should_send_full(self, delta: Dict[str, Any], full_data: Dict[str, Any]) -> bool:
        """
        Determine if we should send full payload instead of delta
        
        Args:
            delta: Calculated delta
            full_data: Complete data
            
        Returns:
            True if full payload should be sent
        """
        delta_json = json.dumps(delta, separators=(',', ':'))
        full_json = json.dumps(full_data, separators=(',', ':'))
        
        delta_size = len(delta_json.encode('utf-8'))
        full_size = len(full_json.encode('utf-8'))
        
        # If delta is more than 70% the size of full data, send full
        return delta_size > (full_size * 0.7)

    def _create_full_message(self, client_id: str, data: Dict[str, Any], 
                           sequence: int, original_size: int) -> DeltaMessage:
        """Create a full payload message"""
        # Store the complete state
        self.client_states[client_id] = data.copy()
        
        # Try compression if payload is large enough
        payload = data.copy()
        compressed = False
        compression_ratio = None
        transmitted_size = original_size
        
        if original_size > self.compression_threshold:
            compressed_payload, compression_ratio = self._compress_payload(payload)
            if compressed_payload and compression_ratio > 1.2:  # Only use if >20% savings
                payload = compressed_payload
                compressed = True
                transmitted_size = len(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
        
        self.stats['full_messages_sent'] += 1
        if compressed:
            self.stats['compressed_messages_sent'] += 1
        self.stats['total_transmitted_bytes'] += transmitted_size
        
        return DeltaMessage(
            type=DeltaType.COMPRESSED if compressed else DeltaType.FULL,
            sequence=sequence,
            timestamp=int(time.time() * 1000),
            payload=payload,
            compressed=compressed,
            compression_ratio=compression_ratio,
            original_size=original_size,
            delta_size=transmitted_size
        )

    def _create_delta_message(self, client_id: str, delta: Dict[str, Any], 
                            sequence: int, original_size: int) -> DeltaMessage:
        """Create a delta payload message"""
        delta_json = json.dumps(delta, separators=(',', ':'))
        delta_size = len(delta_json.encode('utf-8'))
        
        # Try compression on delta
        payload = delta.copy()
        compressed = False
        compression_ratio = None
        transmitted_size = delta_size
        
        if delta_size > self.compression_threshold:
            compressed_payload, compression_ratio = self._compress_payload(delta)
            if compressed_payload and compression_ratio > 1.2:
                payload = compressed_payload
                compressed = True
                transmitted_size = len(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
        
        self.stats['delta_messages_sent'] += 1
        if compressed:
            self.stats['compressed_messages_sent'] += 1
        self.stats['total_transmitted_bytes'] += transmitted_size
        
        logger.debug(f"Delta for client {client_id}: {original_size}→{transmitted_size} bytes "
                    f"({(transmitted_size/original_size)*100:.1f}% of original)")
        
        return DeltaMessage(
            type=DeltaType.COMPRESSED if compressed else DeltaType.DELTA,
            sequence=sequence,
            timestamp=int(time.time() * 1000),
            payload=payload,
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
            'state_keys': list(self.client_states.get(client_id, {}).keys())
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get compression and delta statistics"""
        if self.stats['messages_processed'] == 0:
            return self.stats.copy()
        
        avg_compression_ratio = (self.stats['compression_ratio_sum'] / 
                               max(1, self.stats['compressed_messages_sent']))
        
        overall_compression = (self.stats['total_original_bytes'] / 
                             max(1, self.stats['total_transmitted_bytes']))
        
        return {
            **self.stats,
            'average_compression_ratio': avg_compression_ratio,
            'overall_bandwidth_savings': f"{((overall_compression - 1) * 100):.1f}%",
            'overall_compression_ratio': overall_compression
        }

    def cleanup_old_clients(self, active_client_ids: Set[str]):
        """Remove state for clients that are no longer active"""
        clients_to_remove = set(self.client_states.keys()) - active_client_ids
        for client_id in clients_to_remove:
            self.reset_client(client_id)
        
        if clients_to_remove:
            logger.info(f"Cleaned up delta state for {len(clients_to_remove)} inactive clients")