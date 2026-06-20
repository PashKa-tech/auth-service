import json
import uuid
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.action import Action
from src.core.logging import logger

try:
    from py_mini_racer import MiniRacer
    HAS_MINI_RACER = True
except ImportError:
    HAS_MINI_RACER = False
    logger.warning("mini-racer is not installed. JS actions will not be executed.")

class ActionsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_actions(self, tenant_id: uuid.UUID, trigger: str) -> List[Action]:
        res = await self.db.execute(
            select(Action)
            .where(Action.tenant_id == tenant_id, Action.trigger == trigger, Action.is_active == True)
            .order_by(Action.created_at)
        )
        return list(res.scalars().all())

    def _execute_action_sync(self, code: str, event_data: Dict[str, Any], api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a JS script using mini-racer synchronously.
        """
        if not HAS_MINI_RACER:
            logger.warning("Skipping JS execution because mini-racer is not installed.")
            return api_data
            
        ctx = MiniRacer()
        
        # Load the user's code
        try:
            ctx.eval(code)
        except Exception as e:
            logger.error(f"Error compiling JS action: {str(e)}")
            return api_data

        # We construct a wrapper that calls their function and returns the modified API object.
        wrapper = f"""
        function _runWrapper(eventJson, apiJson) {{
            let event = JSON.parse(eventJson);
            let api = JSON.parse(apiJson);
            
            // Provide simple helper functions on the api object
            api.user = api.user || {{}};
            api.user.app_metadata = api.user.app_metadata || {{}};
            api.user.user_metadata = api.user.user_metadata || {{}};
            
            api.idToken = api.idToken || {{}};
            api.idToken.customClaims = api.idToken.customClaims || {{}};
            api.idToken.setCustomClaim = function(name, value) {{
                api.idToken.customClaims[name] = value;
            }};
            
            api.accessToken = api.accessToken || {{}};
            api.accessToken.customClaims = api.accessToken.customClaims || {{}};
            api.accessToken.setCustomClaim = function(name, value) {{
                api.accessToken.customClaims[name] = value;
            }};
            
            api.access = api.access || {{}};
            api.access.deny = function(reason) {{
                api.access.denied = true;
                api.access.denyReason = reason;
            }};

            try {{
                if (typeof onExecutePostLogin === 'function') {{
                    onExecutePostLogin(event, api);
                }} else if (typeof onExecute === 'function') {{
                    onExecute(event, api);
                }}
            }} catch (err) {{
                api.error = err.toString();
            }}
            
            return JSON.stringify(api);
        }}
        """
        ctx.eval(wrapper)
        
        try:
            result_json = ctx.call("_runWrapper", json.dumps(event_data), json.dumps(api_data), timeout=1000)
            return json.loads(result_json)
        except Exception as e:
            logger.error(f"Error executing JS action: {str(e)}")
            return api_data

    async def execute_action(self, code: str, event_data: Dict[str, Any], api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a JS script using mini-racer asynchronously without blocking the event loop.
        """
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_action_sync, code, event_data, api_data)

    async def execute_post_login_actions(self, tenant_id: uuid.UUID, user: Any, request_info: dict) -> Dict[str, Any]:
        """Runs all post-login actions for a tenant and returns the mutated api object."""
        actions = await self.get_active_actions(tenant_id, "post-login")
        if not actions:
            return {}
            
        event_data = {
            "tenant": {"id": str(tenant_id)},
            "user": {
                "id": str(user.id),
                "email": user.email,
                "role": user.role
            },
            "request": request_info
        }
        
        api_data = {}
        
        for action in actions:
            api_data = await self.execute_action(action.code, event_data, api_data)
            
            if api_data.get("access", {}).get("denied"):
                raise ValueError(api_data["access"].get("denyReason", "Access denied by custom action"))
                
        return api_data
