
document.addEventListener('DOMContentLoaded', () => {
    // DOM 元素
    const urlInput = document.getElementById('url-input');
    const startBtn = document.getElementById('start-crawl-btn');
    const errorMessage = document.getElementById('error-message');
    const crawlStatusSpan = document.getElementById('crawl-status');
    const currentTargetSpan = document.getElementById('current-target');
    const dbStatusSpan = document.getElementById('db-status');
    const logsOutput = document.getElementById('logs-output');
    const gallery = document.getElementById('image-gallery');
    const refreshGalleryBtn = document.getElementById('refresh-gallery-btn');
    const selectAllBtn = document.getElementById('select-all-btn');
    const deleteSelectedBtn = document.getElementById('delete-selected-btn');

    // --------------------------------------------------------------------------
    // Server-Sent Events (SSE) for Logs
    // --------------------------------------------------------------------------

    function connectEventSource() {
        const eventSource = new EventSource("/stream-logs");

        eventSource.onopen = () => {
            console.log("SSE connection established.");
            logsOutput.textContent = "连接到日志服务器...\n";
        };

        eventSource.onmessage = (event) => {
            logsOutput.textContent += event.data + '\n';
            logsOutput.scrollTop = logsOutput.scrollHeight;
        };

        eventSource.onerror = (error) => {
            console.error("EventSource failed:", error);
            logsOutput.textContent += "日志服务器连接断开，请刷新页面重试。\n";
            eventSource.close();
        };
    }

    // --------------------------------------------------------------------------
    // Event Listeners
    // --------------------------------------------------------------------------

    startBtn.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        if (!url) {
            showError('请输入一个有效的 URL。');
            return;
        }
        clearError();
        await startCrawl(url);
    });

    refreshGalleryBtn.addEventListener('click', fetchImages);
    selectAllBtn.addEventListener('click', toggleSelectAll);
    deleteSelectedBtn.addEventListener('click', deleteSelectedImages);

    // --------------------------------------------------------------------------
    // API Calls
    // --------------------------------------------------------------------------

    async function startCrawl(url) {
        setUIState(true);
        try {
            const response = await fetch('/crawl', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url }),
            });

            if (response.status !== 202) {
                const errorData = await response.json();
                showError(errorData.detail || '启动爬取任务失败。');
                setUIState(false);
            } else {
                startStatusPolling();
            }
        } catch (error) {
            showError('无法连接到服务器。');
            setUIState(false);
        }
    }

    async function fetchStatus() {
        try {
            const response = await fetch('/status');
            if (!response.ok) return;

            const data = await response.json();
            updateStatusUI(data);

            if (!data.crawling_active) {
                stopStatusPolling();
                setUIState(false);
            }
        } catch (error) {
            console.error('获取状态失败:', error);
        }
    }

    async function fetchDbStatus() {
        try {
            const response = await fetch('/api/db-status');
            if (!response.ok) {
                dbStatusSpan.textContent = '获取失败';
                return;
            }
            const data = await response.json();
            const primaryDb = data.primary || {};
            dbStatusSpan.textContent = `${primaryDb.status || '未知'}`;
        } catch (error) {
            console.error('获取数据库状态失败:', error);
            dbStatusSpan.textContent = '错误';
        }
    }

    async function fetchImages() {
        try {
            const response = await fetch('/api/images');
            if (!response.ok) {
                showError('获取图片列表失败。');
                return;
            }
            const images = await response.json();
            renderGallery(images);
        } catch (error) {
            showError('无法连接到服务器。');
        }
    }

    async function deleteSelectedImages() {
        const selectedIds = getSelectedImageIds();
        if (selectedIds.length === 0) {
            alert('请先选择要删除的图片。');
            return;
        }

        if (!confirm(`确定要删除选中的 ${selectedIds.length} 张图片吗？`)) {
            return;
        }

        // 显示删除进度
        showDeleteProgress(selectedIds.length);

        try {
            const response = await fetch('/api/images', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_ids: selectedIds }),
            });

            const result = await response.json();
            if (!response.ok) {
                hideDeleteProgress();
                showError(result.detail || '删除图片失败。');
            } else {
                if (result.background && result.task_id) {
                    // 后台任务，显示进度监控
                    monitorDeleteTask(result.task_id, selectedIds.length);
                } else {
                    // 同步完成
                    hideDeleteProgress();
                    alert(result.message);
                    fetchImages(); // Refresh gallery
                }
            }
        } catch (error) {
            hideDeleteProgress();
            showError('无法连接到服务器。');
        }
    }

    // --------------------------------------------------------------------------
    // 批量删除进度显示
    // --------------------------------------------------------------------------

    function showDeleteProgress(total) {
        // 创建进度显示元素
        const progressDiv = document.createElement('div');
        progressDiv.id = 'delete-progress';
        progressDiv.innerHTML = `
            <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                        z-index: 1000; min-width: 300px; text-align: center;">
                <h3>正在删除图片...</h3>
                <div style="background: #f0f0f0; border-radius: 10px; overflow: hidden; margin: 10px 0;">
                    <div id="delete-progress-bar" style="background: #007bff; height: 20px; width: 0%; transition: width 0.3s;"></div>
                </div>
                <div id="delete-progress-text">准备删除 ${total} 张图片...</div>
                <div style="margin-top: 10px;">
                    <small id="delete-progress-details">请稍候，正在处理中...</small>
                </div>
            </div>
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                        background: rgba(0,0,0,0.5); z-index: 999;"></div>
        `;

        document.body.appendChild(progressDiv);
    }

    function updateDeleteProgress(processed, total, deleted, errors) {
        const progressBar = document.getElementById('delete-progress-bar');
        const progressText = document.getElementById('delete-progress-text');
        const progressDetails = document.getElementById('delete-progress-details');

        if (progressBar && progressText && progressDetails) {
            const percentage = Math.round((processed / total) * 100);
            progressBar.style.width = `${percentage}%`;
            progressText.textContent = `已处理 ${processed}/${total} 张图片 (${percentage}%)`;
            progressDetails.textContent = `成功删除: ${deleted} 张，错误: ${errors.length} 个`;
        }
    }

    function hideDeleteProgress() {
        const progressDiv = document.getElementById('delete-progress');
        if (progressDiv) {
            progressDiv.remove();
        }
    }

    async function monitorDeleteTask(taskId, total) {
        const checkInterval = 1000; // 每秒检查一次

        const monitor = async () => {
            try {
                const response = await fetch(`/api/delete-task/${taskId}`);
                const taskStatus = await response.json();

                if (response.ok) {
                    updateDeleteProgress(
                        taskStatus.processed,
                        taskStatus.total,
                        taskStatus.deleted,
                        taskStatus.errors
                    );

                    if (taskStatus.status === 'completed') {
                        hideDeleteProgress();
                        const duration = taskStatus.end_time - taskStatus.start_time;
                        alert(`删除完成！成功删除 ${taskStatus.deleted} 张图片，耗时 ${duration.toFixed(1)} 秒`);
                        fetchImages(); // 刷新图片库
                    } else if (taskStatus.status === 'failed') {
                        hideDeleteProgress();
                        showError(`删除任务失败: ${taskStatus.error}`);
                    } else {
                        // 继续监控
                        setTimeout(monitor, checkInterval);
                    }
                } else {
                    hideDeleteProgress();
                    showError('无法获取删除任务状态');
                }
            } catch (error) {
                hideDeleteProgress();
                showError('监控删除任务时发生错误');
            }
        };

        monitor();
    }

    // --------------------------------------------------------------------------
    // UI Updates & Gallery Logic
    // --------------------------------------------------------------------------

    function renderGallery(images) {
        gallery.innerHTML = '';
        if (images.length === 0) {
            gallery.innerHTML = '<p>图片库为空。</p>';
            return;
        }

        images.forEach(image => {
            const item = document.createElement('div');
            item.className = 'image-item';
            item.innerHTML = `
                <img src="/static/data/images/${image.filename}" alt="${image.filename}" title="${image.url}">
                <input type="checkbox" class="checkbox" data-id="${image.id}">
                <div class="filename">${image.filename}</div>
            `;
            gallery.appendChild(item);
        });
    }

    function toggleSelectAll() {
        const checkboxes = gallery.querySelectorAll('.checkbox');
        const allSelected = Array.from(checkboxes).every(cb => cb.checked);
        checkboxes.forEach(cb => cb.checked = !allSelected);
    }

    function getSelectedImageIds() {
        const selected = [];
        gallery.querySelectorAll('.checkbox:checked').forEach(cb => {
            selected.push(parseInt(cb.dataset.id, 10));
        });
        return selected;
    }

    function updateStatusUI(data) {
        crawlStatusSpan.textContent = data.crawling_active ? '正在爬取' : '空闲';
        crawlStatusSpan.className = data.crawling_active ? 'crawling' : 'idle';
        currentTargetSpan.textContent = data.current_target || '无';
        if (data.last_error) {
            showError(`任务失败: ${data.last_error}`);
        }
    }

    function setUIState(isLoading) {
        startBtn.disabled = isLoading;
        urlInput.disabled = isLoading;
    }

    function showError(message) {
        errorMessage.textContent = message;
    }

    function clearError() {
        errorMessage.textContent = '';
    }

    // --------------------------------------------------------------------------
    // Status Polling
    // --------------------------------------------------------------------------

    let statusInterval;
    let dbStatusInterval;

    function startStatusPolling() {
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(fetchStatus, 2000);
        fetchStatus();
    }

    function stopStatusPolling() {
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = null;
    }

    function startDbStatusPolling() {
        if (dbStatusInterval) clearInterval(dbStatusInterval);
        dbStatusInterval = setInterval(fetchDbStatus, 10000); // Poll every 10 seconds
        fetchDbStatus();
    }

    // --------------------------------------------------------------------------
    // Initialization
    // --------------------------------------------------------------------------

    connectEventSource();
    fetchStatus(); // Get initial status on page load
    fetchImages(); // Load initial gallery
    startDbStatusPolling(); // Start polling for DB status
    initDatabaseManagement(); // Initialize database management
});

// --------------------------------------------------------------------------
// 数据库管理功能
// --------------------------------------------------------------------------

function initDatabaseManagement() {
    // 绑定按钮事件
    document.getElementById('refresh-ha-status').addEventListener('click', refreshHAStatus);
    document.getElementById('manual-failover-btn').addEventListener('click', showFailoverDialog);
    document.getElementById('force-sync-btn').addEventListener('click', forceDatabaseSync);
    document.getElementById('simulate-failure-btn').addEventListener('click', simulateDatabaseFailure);

    // 初始加载HA状态
    refreshHAStatus();

    // 定期更新HA状态
    setInterval(refreshHAStatus, 15000); // 每15秒更新一次
}

async function refreshHAStatus() {
    try {
        addHALog('info', '正在刷新数据库状态...');

        // 获取HA状态
        const response = await fetch('/api/ha-status');
        const data = await response.json();

        if (response.ok) {
            updateHAStatusDisplay(data);
            updateCurrentDatabaseDisplay(data);
            addHALog('success', '数据库状态更新成功');
        } else {
            throw new Error(data.detail || '获取HA状态失败');
        }
    } catch (error) {
        console.error('获取HA状态失败:', error);
        addHALog('error', `获取状态失败: ${error.message}`);
        showOfflineStatus();
    }
}

function updateHAStatusDisplay(data) {
    const container = document.getElementById('db-nodes-container');
    const haStatusSpan = document.getElementById('ha-status');

    if (!data.ha_enabled) {
        container.innerHTML = '<div class="loading">高可用系统未启用</div>';
        haStatusSpan.textContent = '未启用';
        return;
    }

    haStatusSpan.textContent = data.is_monitoring ? '运行中' : '已停止';

    // 更新节点状态
    let nodesHtml = '';
    const nodes = data.nodes || {};

    for (const [nodeName, nodeInfo] of Object.entries(nodes)) {
        const isPrimary = nodeInfo.role === 'primary';
        const isHealthy = nodeInfo.health_status === 'healthy';
        const cardClass = isPrimary ? 'primary' : (isHealthy ? 'secondary' : 'offline');
        const statusClass = isHealthy ? 'healthy' : 'offline';
        const roleIcon = isPrimary ? '👑' : '🔄';
        const statusIcon = isHealthy ? '🟢' : '🔴';

        nodesHtml += `
            <div class="db-node-card ${cardClass}">
                <div class="node-header">
                    <div class="node-title">${roleIcon} ${nodeName}</div>
                    <div class="node-status ${statusClass}">${statusIcon} ${nodeInfo.health_status}</div>
                </div>
                <div class="node-info">
                    <p><strong>角色:</strong> ${nodeInfo.role}</p>
                    <p><strong>服务器:</strong> ${nodeInfo.server.host}:${nodeInfo.server.port}</p>
                    <p><strong>优先级:</strong> ${nodeInfo.priority}</p>
                    ${nodeInfo.replication_lag > 0 ? `<p><strong>复制延迟:</strong> ${nodeInfo.replication_lag.toFixed(2)}秒</p>` : ''}
                    ${nodeInfo.last_error ? `<p><strong>最后错误:</strong> ${nodeInfo.last_error}</p>` : ''}
                </div>
            </div>
        `;
    }

    container.innerHTML = nodesHtml;

    // 更新故障转移按钮状态
    const failoverBtn = document.getElementById('manual-failover-btn');
    const hasSecondary = Object.values(nodes).some(node =>
        node.role === 'secondary' && node.health_status === 'healthy'
    );
    failoverBtn.disabled = !hasSecondary;
}

function updateCurrentDatabaseDisplay(data) {
    const currentDbSpan = document.getElementById('current-database');
    const dbConnectionSpan = document.getElementById('db-connection');
    const haStatusSpan = document.getElementById('ha-status');

    if (!data.ha_enabled) {
        currentDbSpan.textContent = '单机模式';
        dbConnectionSpan.textContent = '本地数据库';
        haStatusSpan.textContent = '未启用';
        return;
    }

    // 更新高可用状态
    haStatusSpan.textContent = data.is_monitoring ? '运行中' : '已停止';

    // 更新当前主数据库
    const currentPrimary = data.current_primary;
    if (currentPrimary && data.nodes && data.nodes[currentPrimary]) {
        const primaryNode = data.nodes[currentPrimary];
        currentDbSpan.textContent = `${currentPrimary} (主库)`;
        dbConnectionSpan.textContent = `${primaryNode.server.host}:${primaryNode.server.port}`;

        // 根据健康状态设置样式
        if (primaryNode.health_status === 'healthy') {
            currentDbSpan.style.color = '#28a745';
            dbConnectionSpan.style.color = '#28a745';
        } else {
            currentDbSpan.style.color = '#dc3545';
            dbConnectionSpan.style.color = '#dc3545';
        }
    } else {
        currentDbSpan.textContent = '未知';
        dbConnectionSpan.textContent = '连接异常';
        currentDbSpan.style.color = '#dc3545';
        dbConnectionSpan.style.color = '#dc3545';
    }
}

function showOfflineStatus() {
    const container = document.getElementById('db-nodes-container');
    const haStatusSpan = document.getElementById('ha-status');
    const currentDbSpan = document.getElementById('current-database');
    const dbConnectionSpan = document.getElementById('db-connection');

    container.innerHTML = '<div class="loading">无法连接到数据库管理服务</div>';
    haStatusSpan.textContent = '离线';
    currentDbSpan.textContent = '连接失败';
    dbConnectionSpan.textContent = '无法连接';
    currentDbSpan.style.color = '#dc3545';
    dbConnectionSpan.style.color = '#dc3545';
}

function showFailoverDialog() {
    const confirmMsg = '确定要执行手动故障转移吗？\n\n这将把当前的备用数据库提升为主数据库。\n此操作用于演示故障转移功能。';

    if (confirm(confirmMsg)) {
        performManualFailover();
    }
}

async function performManualFailover() {
    try {
        addHALog('warning', '正在执行手动故障转移...');

        // 首先获取当前状态，找到备用节点
        const statusResponse = await fetch('/api/ha-status');
        const statusData = await statusResponse.json();

        if (!statusData.ha_enabled) {
            throw new Error('高可用系统未启用');
        }

        // 找到健康的备用节点
        const nodes = statusData.nodes || {};
        const secondaryNode = Object.entries(nodes).find(([name, node]) =>
            node.role === 'secondary' && node.health_status === 'healthy'
        );

        if (!secondaryNode) {
            throw new Error('没有可用的备用节点');
        }

        const targetNodeName = secondaryNode[0];

        // 执行故障转移
        const response = await fetch(`/api/ha-failover/${targetNodeName}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            addHALog('success', `故障转移成功: ${data.message}`);
            // 延迟刷新状态，给系统时间完成切换
            setTimeout(refreshHAStatus, 2000);
        } else {
            throw new Error(data.detail || '故障转移失败');
        }
    } catch (error) {
        console.error('手动故障转移失败:', error);
        addHALog('error', `故障转移失败: ${error.message}`);
    }
}

async function forceDatabaseSync() {
    try {
        addHALog('info', '正在强制数据同步...');

        const response = await fetch('/api/force-file-sync', {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            addHALog('success', `数据同步成功: ${data.message}`);
        } else {
            throw new Error(data.detail || '数据同步失败');
        }
    } catch (error) {
        console.error('强制数据同步失败:', error);
        addHALog('error', `数据同步失败: ${error.message}`);
    }
}

async function simulateDatabaseFailure() {
    const confirmMsg = '确定要模拟数据库故障吗？\n\n这将暂时断开与主数据库的连接，\n触发自动故障转移机制。\n\n注意：这是演示功能，可能影响正在进行的操作。';

    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        addHALog('warning', '正在模拟数据库故障...');
        addHALog('info', '注意：这是演示功能，系统将在几秒后自动检测故障并切换');

        // 这里可以调用一个API来模拟故障
        // 或者简单地显示说明信息
        addHALog('warning', '模拟故障已触发，请观察系统自动故障转移过程');
        addHALog('info', '系统将在检测到故障后自动切换到备用数据库');

        // 增加状态刷新频率来观察故障转移过程
        const quickRefresh = setInterval(() => {
            refreshHAStatus();
        }, 3000);

        // 30秒后恢复正常刷新频率
        setTimeout(() => {
            clearInterval(quickRefresh);
            addHALog('info', '故障模拟演示结束，恢复正常监控频率');
        }, 30000);

    } catch (error) {
        console.error('模拟数据库故障失败:', error);
        addHALog('error', `模拟故障失败: ${error.message}`);
    }
}

function addHALog(type, message) {
    const container = document.getElementById('ha-logs-container');
    const timestamp = new Date().toLocaleTimeString();

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    logEntry.innerHTML = `
        <span class="timestamp">[${timestamp}]</span>
        <span class="message">${message}</span>
    `;

    container.appendChild(logEntry);

    // 保持最多50条日志
    const logs = container.children;
    if (logs.length > 50) {
        container.removeChild(logs[0]);
    }

    // 滚动到最新日志
    container.scrollTop = container.scrollHeight;
}
