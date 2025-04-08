Based on the refactored code snippets you provided (`manager.py`, `dispatcher.py`, `heartbeat_handler.py`, `reconnect_handler.py`), here are the WebSocket message types implemented in your backend service:

**1. Messages Sent FROM Backend TO Client:**

* **`connected`**: Sent once when a client successfully authenticates and registers its WebSocket connection.
    * *Sent from:* `WebSocketManager.handle_connection`
* **`heartbeat_ack`**: Sent in response to a client's `heartbeat` message, acknowledging receipt and providing status.
    * *Sent from:* `handle_heartbeat` (in `heartbeat_handler.py`)
* **`reconnect_result`**: Sent in response to a client's `reconnect` message, indicating success or failure.
    * *Sent from:* `handle_reconnect` (in `reconnect_handler.py`)
* **`exchange_data_status`**: Sent to broadcast exchange data updates (symbols, orders, positions) to relevant clients in a session.
    * *Sent from:* `WebSocketManager.send_exchange_data_update` (via `broadcast_to_session`)
* **`error`**: Sent when an error occurs during connection setup, message processing, or due to internal issues. Contains an `errorCode` and `message`.
    * *Sent from:* `WebSocketManager._close_with_error`, `WebSocketDispatcher._send_error`
* **`timeout`**: Sent shortly before the server closes a connection due to inactivity (based on the cleanup task).
    * *Sent from:* `WebSocketManager._cleanup_stale_connections`
* **`shutdown`**: Sent to all connected clients when the server is shutting down gracefully.
    * *Sent from:* `WebSocketManager.close_all_connections`

**2. Messages Expected FROM Client TO Backend:**

* **`heartbeat`**: Expected periodically from the client to keep the connection alive and potentially update status (like connection quality). Handled by the dispatcher routing to `handle_heartbeat`.
    * *Handled by:* `handle_heartbeat` (in `heartbeat_handler.py`) via `WebSocketDispatcher`
* **`reconnect`**: Sent by a client attempting to re-establish or re-validate its state within an existing session, usually including a session token. Handled by the dispatcher routing to `handle_reconnect`.
    * *Handled by:* `handle_reconnect` (in `reconnect_handler.py`) via `WebSocketDispatcher`

Therefore, your backend explicitly handles incoming `heartbeat` and `reconnect` types and sends out `connected`, `heartbeat_ack`, `reconnect_result`, `exchange_data_status`, `error`, `timeout`, and `shutdown` types.