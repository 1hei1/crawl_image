"""
高可用数据库API服务器

用于节点间通信的API服务器，处理：
- 角色变更通知
- 数据同步请求
- 健康检查
- 集群状态查询
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from database.distributed_ha_manager import DistributedHAManager, DatabaseRole, SyncOperation

logger = logging.getLogger(__name__)


class RoleChangeRequest(BaseModel):
    """角色变更请求"""
    node_name: str
    new_role: str
    timestamp: str


class SyncRequest(BaseModel):
    """数据同步请求"""
    operation_id: str
    timestamp: str
    operation_type: str
    table_name: str
    data: Dict[str, Any]
    source_node: str


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str
    node_name: str
    role: str


class HAAPIServer:
    """高可用数据库API服务器"""
    
    def __init__(self, ha_manager: DistributedHAManager, port: int = 8001):
        """
        初始化API服务器
        
        Args:
            ha_manager: 分布式HA管理器
            port: 服务端口
        """
        self.ha_manager = ha_manager
        self.port = port
        self.app = FastAPI(
            title="数据库高可用API",
            description="用于数据库节点间通信的API服务",
            version="1.0.0"
        )
        
        self._setup_routes()
    
    def _setup_routes(self):
        """设置API路由"""
        
        @self.app.post("/api/role-change")
        async def handle_role_change(request: RoleChangeRequest):
            """处理角色变更通知"""
            try:
                node_name = request.node_name
                new_role = DatabaseRole(request.new_role)
                
                if node_name in self.ha_manager.nodes:
                    self.ha_manager.nodes[node_name].role = new_role
                    
                    # 如果变更的是主节点，更新当前主节点
                    if new_role == DatabaseRole.PRIMARY:
                        self.ha_manager.current_primary = node_name
                    
                    logger.info(f"节点 {node_name} 角色已变更为 {new_role.value}")
                    
                    return {"status": "success", "message": "角色变更成功"}
                else:
                    raise HTTPException(status_code=404, detail="节点不存在")
                    
            except Exception as e:
                logger.error(f"处理角色变更失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/sync")
        async def handle_sync_request(request: SyncRequest, background_tasks: BackgroundTasks):
            """处理数据同步请求"""
            try:
                # 创建同步操作对象
                operation = SyncOperation(
                    operation_id=request.operation_id,
                    timestamp=datetime.fromisoformat(request.timestamp),
                    operation_type=request.operation_type,
                    table_name=request.table_name,
                    data=request.data,
                    source_node=request.source_node,
                    target_nodes=[self.ha_manager.local_node_name]
                )
                
                # 在后台处理同步操作
                background_tasks.add_task(self._process_sync_operation, operation)
                
                return {"status": "success", "message": "同步请求已接收"}
                
            except Exception as e:
                logger.error(f"处理同步请求失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/health")
        async def health_check():
            """健康检查"""
            try:
                local_node = self.ha_manager.local_node
                
                # 测试数据库连接
                is_healthy = self.ha_manager._test_node_connection(
                    self.ha_manager.local_node_name
                )
                
                status = "healthy" if is_healthy else "unhealthy"
                
                return HealthCheckResponse(
                    status=status,
                    timestamp=datetime.now().isoformat(),
                    node_name=self.ha_manager.local_node_name,
                    role=local_node.role.value
                )
                
            except Exception as e:
                logger.error(f"健康检查失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/status")
        async def get_cluster_status():
            """获取集群状态"""
            try:
                return self.ha_manager.get_cluster_status()
            except Exception as e:
                logger.error(f"获取集群状态失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/sync-status")
        async def get_sync_status():
            """获取数据同步状态"""
            try:
                return self.ha_manager.get_sync_status()
            except Exception as e:
                logger.error(f"获取同步状态失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/sync/enable")
        async def enable_auto_sync():
            """启用自动同步"""
            try:
                self.ha_manager.enable_auto_sync()
                return {"message": "自动同步已启用", "status": "success"}
            except Exception as e:
                logger.error(f"启用自动同步失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/sync/disable")
        async def disable_auto_sync():
            """禁用自动同步"""
            try:
                self.ha_manager.disable_auto_sync()
                return {"message": "自动同步已禁用", "status": "success"}
            except Exception as e:
                logger.error(f"禁用自动同步失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/failover/{target_node}")
        async def manual_failover(target_node: str):
            """手动故障转移"""
            try:
                success = self.ha_manager.manual_failover(target_node)
                
                if success:
                    return {"status": "success", "message": f"故障转移到 {target_node} 成功"}
                else:
                    raise HTTPException(status_code=400, detail="故障转移失败")
                    
            except Exception as e:
                logger.error(f"手动故障转移失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/force-sync")
        async def force_sync():
            """强制全量同步"""
            try:
                success = self.ha_manager.force_sync_all()
                
                if success:
                    return {"status": "success", "message": "全量同步已启动"}
                else:
                    raise HTTPException(status_code=400, detail="全量同步启动失败")
                    
            except Exception as e:
                logger.error(f"强制全量同步失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/replication-lag")
        async def get_replication_lag():
            """获取复制延迟信息"""
            try:
                lag_info = {}
                for node_name, node in self.ha_manager.nodes.items():
                    if node.role == DatabaseRole.SECONDARY:
                        lag_info[node_name] = {
                            "replication_lag": node.replication_lag,
                            "health_status": node.health_status.value,
                            "last_check": node.last_check.isoformat() if node.last_check else None
                        }
                
                return lag_info
                
            except Exception as e:
                logger.error(f"获取复制延迟信息失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_sync_operation(self, operation: SyncOperation):
        """处理同步操作"""
        try:
            self.ha_manager._apply_local_operation(operation)
            logger.info(f"同步操作处理成功: {operation.operation_id}")
        except Exception as e:
            logger.error(f"同步操作处理失败: {e}")
    
    def start(self, host: str = "0.0.0.0"):
        """启动API服务器"""
        logger.info(f"启动HA API服务器: {host}:{self.port}")
        
        uvicorn.run(
            self.app,
            host=host,
            port=self.port,
            log_level="info"
        )
    
    async def start_async(self, host: str = "0.0.0.0"):
        """异步启动API服务器"""
        config = uvicorn.Config(
            self.app,
            host=host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


def create_ha_api_server(ha_manager: DistributedHAManager, port: int = 8001) -> HAAPIServer:
    """创建HA API服务器实例"""
    return HAAPIServer(ha_manager, port)


if __name__ == "__main__":
    # 示例用法
    from database.distributed_ha_manager import DatabaseNode, ServerInfo
    
    # 创建示例节点配置
    nodes = [
        DatabaseNode(
            name="primary",
            role=DatabaseRole.PRIMARY,
            priority=1,
            server=ServerInfo(host="localhost", port=5432, api_port=8001),
            database_url="sqlite:///data/images.db"
        ),
        DatabaseNode(
            name="secondary1",
            role=DatabaseRole.SECONDARY,
            priority=2,
            server=ServerInfo(host="192.168.1.100", port=5432, api_port=8001),
            database_url="postgresql://user:pass@192.168.1.100:5432/images"
        )
    ]
    
    # 创建HA管理器
    ha_manager = DistributedHAManager(nodes, "primary")
    ha_manager.start_monitoring()
    
    # 创建并启动API服务器
    api_server = create_ha_api_server(ha_manager, 8001)
    api_server.start()
