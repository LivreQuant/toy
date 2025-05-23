# source/core/operation_manager.py
import logging
import time
import uuid
from typing import Dict, Any, List

from source.models.conviction import ConvictionData
from source.utils.metrics import track_conviction_submission_latency

from source.db.conviction_repository import ConvictionRepository
from source.core.session_manager import SessionManager

from source.core.conviction_manager_record import RecordManager
from source.core.conviction_manager_exchange import ExchangeManager

logger = logging.getLogger('operation_manager')


class OperationManager:
    """Manager for conviction operations that coordinates other managers"""

    def __init__(
            self,
            conviction_repository: ConvictionRepository,
            session_manager: SessionManager,
            record_manager: RecordManager,
            exchange_manager: ExchangeManager
    ):
        self.conviction_repository = conviction_repository
        self.session_manager = session_manager

        self.record_manager = record_manager
        self.exchange_manager = exchange_manager

    async def submit_convictions(self, convictions_data: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """
        Submit convictions in batch - first cancel existing open convictions for the same symbols
        
        Args:
            convictions_data: List of conviction data dictionaries
            user_id: User ID
            
        Returns:
            Batch submission result
        """
        start_time = time.time()
        
        # Extract all symbols from the new convictions
        symbols = list(set(conviction.get('symbol') for conviction in convictions_data if conviction.get('symbol')))
        
        # 1. Get simulator information for the user
        simulator = await self.session_manager.session_repository.get_session_simulator(user_id)
        simulator_id = simulator.get('simulator_id') if simulator else None
        simulator_endpoint = simulator.get('endpoint') if simulator else None
        
        logger.info(f"FOUND SIMULATOR: {simulator_endpoint}")

        # 4. Extract request IDs for duplicate checking
        request_ids = [conviction.get('requestId') for conviction in convictions_data if conviction.get('requestId')]
        
        # 5. Check all request IDs simultaneously
        duplicate_responses = {}
        if request_ids:
            duplicate_responses = await self.conviction_repository.check_duplicate_requests(
                user_id, request_ids
            )
        
        # 6. Process each conviction - validation and object creation (in memory)
        valid_convictions = []
        results = []
        
        for i, conviction_data in enumerate(convictions_data):
            # Check for duplicate request
            request_id = conviction_data.get('requestId')
            if request_id and request_id in duplicate_responses:
                cached_response = duplicate_responses[request_id]
                results.append({
                    **cached_response,
                    "index": i
                })
                continue
                
            # Validate conviction parameters
            conviction_validation = await self.conviction_repository.validate_conviction_parameters(conviction_data)
            if not conviction_validation.get('valid'):
                error_msg = conviction_validation.get('error', 'Invalid conviction parameters')
                
                result = {
                    "success": False,
                    "error": error_msg,
                    "index": i
                }
                
                results.append(result)
                continue
                
            # Create conviction object (but don't save yet)
            try:
                conviction = ConvictionData(
                    symbol=conviction_validation.get('symbol'),
                    side=Side(conviction_validation.get('side')),
                    quantity=conviction_validation.get('quantity'),
                    price=conviction_validation.get('price'),
                    user_id=user_id,
                    simulator_id=simulator_id,
                    request_id=request_id,
                    conviction_id=str(uuid.uuid4()),
                    created_at=time.time(),
                    updated_at=time.time()
                )
                
                valid_convictions.append((conviction, i))
            except Exception as e:
                logger.error(f"Error creating conviction object: {e}")
                
                result = {
                    "success": False,
                    "error": f"Conviction parsing error: {str(e)}",
                    "index": i
                }
                
                results.append(result)
        
        # 7. Save all valid convictions in a single batch operation
        if valid_convictions:
            convictions_to_save = [conviction for conviction, _ in valid_convictions]
            save_result = await self.record_manager.save_convictions(convictions_to_save)
            
            # Add results for saved convictions
            for conviction, idx in valid_convictions:
                if conviction.conviction_id in save_result["successful"]:
                    results.append({
                        "success": True,
                        "convictionId": conviction.conviction_id,
                        "index": idx
                    })
                else:
                    results.append({
                        "success": False,
                        "error": "Failed to save conviction to database",
                        "index": idx
                    })
        
        logger.info(f"VALID CONVICTIONS: {valid_convictions}")
        
        # 8. Submit to exchange if we have a simulator
        if simulator_endpoint and valid_convictions:
            successful_conviction_ids = save_result.get("successful", [])
            convictions_to_submit = [conviction for conviction, _ in valid_convictions if conviction.conviction_id in successful_conviction_ids]
            
            if convictions_to_submit:
                exchange_result = await self.exchange_manager.submit_convictions_to_exchange(
                    convictions_to_submit, simulator_endpoint
                )
                
                if not exchange_result.get('success'):
                    # All convictions rejected by exchange - record new status
                    error_msg = exchange_result.get('error', 'Batch rejected by exchange')
                    
                    for conviction in convictions_to_submit:
                        # Create new row with REJECTED status
                        await self.record_manager.save_conviction_status(
                            conviction.conviction_id, user_id, error_msg
                        )
                        
                        # Update results
                        for j, res in enumerate(results):
                            if res.get('convictionId') == conviction.conviction_id:
                                results[j] = {
                                    "success": False,
                                    "error": error_msg,
                                    "convictionId": conviction.conviction_id,
                                    "index": res.get('index')
                                }
                else:
                    # You mentioned we can assume the exchange cannot reject convictions,
                    # but I'm keeping minimal handling just in case
                    pass
        
        # 9. Record metrics
        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.get('success', False))
        track_conviction_submission_latency("batch", success_count > 0, duration)
        
        # 10. Return final results sorted by original index
        sorted_results = sorted(results, key=lambda x: x.get('index', 0))
        return {
            "success": True,  # Overall request processed
            "results": [
                {
                    "success": r.get('success', False),
                    "convictionId": r.get('convictionId'),
                    "error": r.get('error')
                }
                for r in sorted_results
            ]
        }

    async def cancel_convictions(self, conviction_ids: List[str], user_id: str) -> Dict[str, Any]:
        """
        Cancel convictions in batch
        
        Args:
            conviction_ids: List of conviction IDs to cancel
            user_id: User ID
            
        Returns:
            Batch cancellation result
        """
        start_time = time.time()
        
        # 1. Get simulator information for the user
        simulator = await self.session_manager.session_repository.get_session_simulator(user_id)
        simulator_endpoint = simulator.get('endpoint') if simulator else None
        
        # 2. Get all conviction information in a single query
        conviction_info_list = await self.record_manager.get_convictions_info(conviction_ids)
        
        # Create mapping of conviction_id to info
        conviction_info_map = {info['conviction_id']: info for info in conviction_info_list}
        
        # 3. Validate convictions and categorize them
        results = []
        valid_convictions = []
        
        for i, conviction_id in enumerate(conviction_ids):
            # Check if conviction exists and belongs to user
            if conviction_id not in conviction_info_map:
                results.append({
                    "convictionId": conviction_id,
                    "success": False,
                    "error": "Conviction not found",
                    "index": i
                })
                continue
                
            info = conviction_info_map[conviction_id]
            
            if info['user_id'] != user_id:
                results.append({
                    "oconvictionId": conviction_id,
                    "success": False,
                    "error": "Conviction does not belong to this user",
                    "index": i
                })
                continue
                
            # Conviction is valid for cancellation regardless of status
            # Create minimal Conviction object for the exchange client
            conviction = ConvictionData(
                conviction_id=conviction_id,
                user_id=user_id,
                symbol="",  # Placeholder, not needed for cancellation
                side=Side.BUY,  # Placeholder, not needed for cancellation
                quantity=0,  # Placeholder, not needed for cancellation
            )
            
            valid_convictions.append((conviction, i))
        
        # 4. Cancel convictions on exchange if we have a simulator
        if simulator_endpoint and valid_convictions:
            convictions = [conviction for conviction, _ in valid_convictions]
            
            exchange_result = await self.exchange_manager.cancel_convictions_on_exchange(convictions, simulator_endpoint)
            
            # Process individual results
            if exchange_result.get('success'):
                exchange_results = exchange_result.get('results', [])
                
                for i, ex_result in enumerate(exchange_results):
                    if i < len(valid_convictions):
                        conviction, idx = valid_convictions[i]
                        
                        if ex_result.get('success'):
                            # Create new row with CANCELED status
                            success = await self.record_manager.save_conviction_status(
                                conviction.conviction_id, user_id
                            )
                            
                            results.append({
                                "convictionId": conviction.conviction_id,
                                "success": success,
                                "index": idx
                            })
                        else:
                            error_msg = ex_result.get('error', 'Failed to cancel on exchange')
                            
                            results.append({
                                "convictionId": conviction.conviction_id,
                                "success": False,
                                "error": error_msg,
                                "index": idx
                            })
            else:
                # Batch cancellation failed on exchange
                error_msg = exchange_result.get('error', 'Batch cancellation failed')
                
                for conviction, idx in valid_convictions:
                    results.append({
                        "convictionId": conviction.conviction_id,
                        "success": False,
                        "error": error_msg,
                        "index": idx
                    })
        elif valid_convictions:
            # No simulator - just mark convictions as canceled in database
            for conviction, idx in valid_convictions:
                # Create new row with CANCELED status
                success = await self.record_manager.save_conviction_status(
                    conviction.conviction_id, user_id
                )
                
                results.append({
                    "convictionId": conviction.conviction_id,
                    "success": success,
                    "index": idx
                })
        
        # 5. Record metrics
        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.get('success', False))
        track_conviction_submission_latency("batch_cancel", success_count > 0, duration)
        
        # 6. Return final results sorted by original index
        sorted_results = sorted(results, key=lambda x: x.get('index', 0))
        return {
            "success": True,  # Overall request processed
            "results": [
                {
                    "success": r.get('success', False),
                    "convictionId": r.get('convictionId'),
                    "error": r.get('error')
                }
                for r in sorted_results
            ]
        }
